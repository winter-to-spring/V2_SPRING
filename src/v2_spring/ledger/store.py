from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from v2_spring.domain.approval import ApprovalStatus, ApprovalView
from v2_spring.domain.artifact import ArtifactStorageKind, ArtifactType, ArtifactView
from v2_spring.domain.decision import DecisionKind, DecisionView
from v2_spring.domain.observation import ObservationKind, ObservationView
from v2_spring.domain.replay import ArtifactInspectionView, RunReplayView, TaskReplayView
from v2_spring.domain.run import RunCreateInput, RunStatus, RunView
from v2_spring.domain.snapshot import (
    ArtifactHeadlineView,
    RunSnapshotView,
    SnapshotActionState,
    TaskHeadlineView,
    TaskStatusSummary,
)
from v2_spring.domain.task import TaskKind, TaskStatus, TaskView
from v2_spring.executor.bounded import (
    BoundedExecutorError,
    BoundedExecutorTimeout,
    TaskExecutionReceipt,
    execute_repository_scan,
)
from v2_spring.ledger.models import (
    ApprovalRecord,
    ArtifactRecord,
    Base,
    DecisionRecord,
    EventLedgerRecord,
    LedgerEventType,
    ObservationRecord,
    RunRecord,
    TaskRecord,
    utc_now,
)


@dataclass(frozen=True)
class BoundedExecutionResult:
    """Return the first execution proof in a single typed bundle."""

    task: TaskView
    artifact: ArtifactView | None
    observation: ObservationView


class LedgerStore:
    """Typed persistence boundary for V2_SPRING tracer-bullet state and events."""

    # Approval should pause stateful progression, not blind the system.
    _APPROVAL_SAFE_OBSERVATION_KINDS = frozenset({ObservationKind.SYSTEM_AUDIT})

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

    def ensure_schema(self) -> None:
        Base.metadata.create_all(self._engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_run(self, run_input: RunCreateInput) -> RunView:
        self.ensure_schema()
        with self.session() as session:
            record = RunRecord(
                project=run_input.project,
                goal=run_input.goal,
                urgency=run_input.urgency,
                risk=run_input.risk,
                status=RunStatus.WAITING_APPROVAL,
            )
            session.add(record)
            session.flush()

            session.add(self._build_run_created_event(record))

            observation = ObservationRecord(
                run_id=record.id,
                kind=ObservationKind.RUN_INTAKE,
                summary="Run was submitted from the CLI.",
                details=(
                    f"Project '{run_input.project}' submitted a new run with "
                    f"urgency '{run_input.urgency.value}' and risk '{run_input.risk.value}'."
                ),
            )
            session.add(observation)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=record.id,
                    event_type=LedgerEventType.OBSERVATION_RECORDED,
                    payload={
                        "observation_id": observation.id,
                        "kind": observation.kind.value,
                        "summary": observation.summary,
                    },
                ),
            )

            decision = DecisionRecord(
                run_id=record.id,
                kind=DecisionKind.INTAKE_ACCEPTED,
                summary="Run intake accepted.",
                rationale=(
                    "The CLI input passed typed validation, so the run was persisted "
                    "and the system recorded bootstrap evidence for the next planner step."
                ),
            )
            session.add(decision)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=record.id,
                    event_type=LedgerEventType.DECISION_RECORDED,
                    payload={
                        "decision_id": decision.id,
                        "kind": decision.kind.value,
                        "summary": decision.summary,
                    },
                ),
            )

            approval = ApprovalRecord(
                run_id=record.id,
                status=ApprovalStatus.PENDING,
                requested_action="Approve the tracer bullet to continue beyond intake.",
                reason=(
                    "The first bounded loop is intentionally semi-automatic. "
                    "A human must explicitly allow the run to continue after intake evidence is recorded."
                ),
                approve_effect="The run moves from waiting approval to ready for the next bounded step.",
                reject_effect="The run is marked rejected and remains stopped until a new decision is made.",
            )
            session.add(approval)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=record.id,
                    event_type=LedgerEventType.APPROVAL_REQUESTED,
                    payload={
                        "approval_id": approval.id,
                        "status": approval.status.value,
                        "requested_action": approval.requested_action,
                    },
                ),
            )
            session.flush()
            return self._to_run_view(record)

    def get_run(self, run_id: str) -> RunView | None:
        self.ensure_schema()
        with self.session() as session:
            record = session.get(RunRecord, run_id)
            if record is None:
                return None
            return self._to_run_view(record)

    def list_events_for_run(self, run_id: str) -> list[EventLedgerRecord]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(EventLedgerRecord)
                .where(EventLedgerRecord.run_id == run_id)
                .order_by(EventLedgerRecord.recorded_at.asc(), EventLedgerRecord.id.asc())
            )
            return list(session.scalars(statement).all())

    def list_approvals(self, status: ApprovalStatus | None = None) -> list[ApprovalView]:
        self.ensure_schema()
        with self.session() as session:
            statement = select(ApprovalRecord).order_by(ApprovalRecord.requested_at.asc(), ApprovalRecord.id.asc())
            if status is not None:
                statement = statement.where(ApprovalRecord.status == status)
            records = list(session.scalars(statement).all())
            return [self._to_approval_view(record) for record in records]

    def resolve_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        reason: str | None = None,
    ) -> ApprovalView:
        self.ensure_schema()
        with self.session() as session:
            approval = session.get(ApprovalRecord, approval_id)
            if approval is None:
                raise LookupError(f"Approval {approval_id} was not found.")
            if approval.status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Approval {approval_id} is already {approval.status.value} and cannot be resolved again.",
                )

            resolution_reason = self._normalize_optional_text(reason)
            if not approved and resolution_reason is None:
                raise ValueError(
                    f"Approval {approval_id} requires --reason when rejecting a request.",
                )

            approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            approval.resolved_at = utc_now()
            approval.resolution_reason = resolution_reason

            run = self._get_run_for_mutation(
                session,
                approval.run_id,
                mutation_name="approval resolution",
                allow_during_waiting_approval=True,
            )
            run.status = RunStatus.READY if approved else RunStatus.REJECTED

            session.add(
                EventLedgerRecord(
                    run_id=approval.run_id,
                    event_type=LedgerEventType.APPROVAL_RESOLVED,
                    payload={
                        "approval_id": approval.id,
                        "status": approval.status.value,
                        "run_status": run.status.value,
                        "resolution_reason": approval.resolution_reason,
                    },
                ),
            )
            session.flush()
            return self._to_approval_view(approval)

    def record_decision(
        self,
        *,
        run_id: str,
        kind: DecisionKind,
        summary: str,
        rationale: str,
    ) -> DecisionView:
        self.ensure_schema()
        with self.session() as session:
            run = self._get_run_for_mutation(
                session,
                run_id,
                mutation_name="decision recording",
            )
            record = DecisionRecord(
                run_id=run.id,
                kind=kind,
                summary=summary,
                rationale=rationale,
            )
            session.add(record)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.DECISION_RECORDED,
                    payload={
                        "decision_id": record.id,
                        "kind": record.kind.value,
                        "summary": record.summary,
                    },
                ),
            )
            session.flush()
            return self._to_decision_view(record)

    def record_observation(
        self,
        *,
        run_id: str,
        kind: ObservationKind,
        summary: str,
        details: str,
    ) -> ObservationView:
        self.ensure_schema()
        with self.session() as session:
            run = self._get_run_for_mutation(
                session,
                run_id,
                mutation_name="observation recording",
                allow_during_waiting_approval=kind in self._APPROVAL_SAFE_OBSERVATION_KINDS,
            )
            record = ObservationRecord(
                run_id=run.id,
                kind=kind,
                summary=summary,
                details=details,
            )
            session.add(record)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.OBSERVATION_RECORDED,
                    payload={
                        "observation_id": record.id,
                        "kind": record.kind.value,
                        "summary": record.summary,
                    },
                ),
            )
            session.flush()
            return self._to_observation_view(record)

    def list_decisions_for_run(self, run_id: str) -> list[DecisionView]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(DecisionRecord)
                .where(DecisionRecord.run_id == run_id)
                .order_by(DecisionRecord.created_at.asc(), DecisionRecord.id.asc())
            )
            records = list(session.scalars(statement).all())
            return [self._to_decision_view(record) for record in records]

    def list_observations_for_run(self, run_id: str) -> list[ObservationView]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(ObservationRecord)
                .where(ObservationRecord.run_id == run_id)
                .order_by(ObservationRecord.created_at.asc(), ObservationRecord.id.asc())
            )
            records = list(session.scalars(statement).all())
            return [self._to_observation_view(record) for record in records]

    def list_tasks_for_run(self, run_id: str) -> list[TaskView]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(TaskRecord)
                .where(TaskRecord.run_id == run_id)
                .order_by(TaskRecord.created_at.asc(), TaskRecord.id.asc())
            )
            records = list(session.scalars(statement).all())
            return [self._to_task_view(record) for record in records]

    def list_artifacts_for_run(self, run_id: str) -> list[ArtifactView]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(ArtifactRecord)
                .where(ArtifactRecord.run_id == run_id)
                .order_by(ArtifactRecord.created_at.asc(), ArtifactRecord.id.asc())
            )
            records = list(session.scalars(statement).all())
            return [self._to_artifact_view(record) for record in records]

    def get_task(self, task_id: str) -> TaskView | None:
        self.ensure_schema()
        with self.session() as session:
            record = session.get(TaskRecord, task_id)
            if record is None:
                return None
            return self._to_task_view(record)

    def get_artifact(self, artifact_id: str) -> ArtifactInspectionView | None:
        self.ensure_schema()
        with self.session() as session:
            record = session.get(ArtifactRecord, artifact_id)
            if record is None:
                return None
            return self._inspect_artifact(record)

    def build_run_replay(self, run_id: str) -> RunReplayView:
        """Build a fixed-query replay projection for one run."""

        self.ensure_schema()
        with self.session() as session:
            run_record = session.get(RunRecord, run_id)
            if run_record is None:
                raise LookupError(f"Run {run_id} was not found.")

            approvals = [
                self._to_approval_view(record)
                for record in session.scalars(
                    select(ApprovalRecord)
                    .where(ApprovalRecord.run_id == run_id)
                    .order_by(ApprovalRecord.requested_at.asc(), ApprovalRecord.id.asc()),
                ).all()
            ]
            decisions = [
                self._to_decision_view(record)
                for record in session.scalars(
                    select(DecisionRecord)
                    .where(DecisionRecord.run_id == run_id)
                    .order_by(DecisionRecord.created_at.asc(), DecisionRecord.id.asc()),
                ).all()
            ]
            observations = [
                self._to_observation_view(record)
                for record in session.scalars(
                    select(ObservationRecord)
                    .where(ObservationRecord.run_id == run_id)
                    .order_by(ObservationRecord.created_at.asc(), ObservationRecord.id.asc()),
                ).all()
            ]
            task_records = list(
                session.scalars(
                    select(TaskRecord)
                    .where(TaskRecord.run_id == run_id)
                    .order_by(TaskRecord.created_at.asc(), TaskRecord.id.asc()),
                ).all(),
            )
            artifact_records = list(
                session.scalars(
                    select(ArtifactRecord)
                    .where(ArtifactRecord.run_id == run_id)
                    .order_by(ArtifactRecord.created_at.asc(), ArtifactRecord.id.asc()),
                ).all(),
            )
            ledger_events = list(
                session.scalars(
                    select(EventLedgerRecord)
                    .where(EventLedgerRecord.run_id == run_id)
                    .order_by(EventLedgerRecord.recorded_at.asc(), EventLedgerRecord.id.asc()),
                ).all(),
            )

            decision_map = {str(decision.id): decision for decision in decisions}
            task_map = {record.id: self._to_task_view(record) for record in task_records}
            observation_by_task: dict[str, list[ObservationView]] = {}
            for observation in observations:
                if observation.kind != ObservationKind.TASK_EXECUTION:
                    continue
                for task_id in task_map:
                    if task_id in observation.details:
                        observation_by_task.setdefault(task_id, []).append(observation)

            artifact_by_task: dict[str, list[ArtifactInspectionView]] = {}
            for record in artifact_records:
                artifact_by_task.setdefault(record.task_id, []).append(self._inspect_artifact(record))

            task_replays: list[TaskReplayView] = []
            for task_record in task_records:
                task_view = task_map[task_record.id]
                task_replays.append(
                    TaskReplayView(
                        task=task_view,
                        decision=decision_map.get(task_record.decision_id) if task_record.decision_id else None,
                        artifacts=artifact_by_task.get(task_record.id, []),
                        observations=observation_by_task.get(task_record.id, []),
                    ),
                )

            orphan_artifacts = [
                inspection
                for task_id, inspections in artifact_by_task.items()
                if task_id not in task_map
                for inspection in inspections
            ]

            return RunReplayView(
                run=self._to_run_view(run_record),
                approvals=approvals,
                decisions=decisions,
                tasks=task_replays,
                observations=observations,
                orphan_artifacts=orphan_artifacts,
                consistency_warnings=self._build_consistency_warnings(
                    run=self._to_run_view(run_record),
                    approvals=approvals,
                    tasks=task_replays,
                    orphan_artifacts=orphan_artifacts,
                    ledger_events=ledger_events,
                ),
            )

    def build_run_snapshot(self, run_id: str) -> RunSnapshotView:
        """Build a planner-ready, bounded snapshot for one run."""

        self.ensure_schema()
        with self.session() as session:
            run_record = session.get(RunRecord, run_id)
            if run_record is None:
                raise LookupError(f"Run {run_id} was not found.")

            approvals = [
                self._to_approval_view(record)
                for record in session.scalars(
                    select(ApprovalRecord)
                    .where(ApprovalRecord.run_id == run_id)
                    .order_by(ApprovalRecord.requested_at.asc(), ApprovalRecord.id.asc()),
                ).all()
            ]
            decisions = [
                self._to_decision_view(record)
                for record in session.scalars(
                    select(DecisionRecord)
                    .where(DecisionRecord.run_id == run_id)
                    .order_by(DecisionRecord.created_at.asc(), DecisionRecord.id.asc()),
                ).all()
            ]
            task_records = list(
                session.scalars(
                    select(TaskRecord)
                    .where(TaskRecord.run_id == run_id)
                    .order_by(TaskRecord.created_at.asc(), TaskRecord.id.asc()),
                ).all(),
            )
            artifact_records = list(
                session.scalars(
                    select(ArtifactRecord)
                    .where(ArtifactRecord.run_id == run_id)
                    .order_by(ArtifactRecord.created_at.asc(), ArtifactRecord.id.asc()),
                ).all(),
            )

            pending_approval = next(
                (approval for approval in reversed(approvals) if approval.status == ApprovalStatus.PENDING),
                None,
            )
            latest_rejection_reason = next(
                (
                    approval.resolution_reason
                    for approval in reversed(approvals)
                    if approval.status == ApprovalStatus.REJECTED and approval.resolution_reason
                ),
                None,
            )
            latest_decision_summary = decisions[-1].summary if decisions else None
            latest_task = self._build_task_headline(task_records[-1]) if task_records else None
            latest_artifact = (
                self._build_artifact_headline(self._inspect_artifact(artifact_records[-1]))
                if artifact_records
                else None
            )
            task_summary = self._build_task_status_summary(task_records)

            snapshot_payload = {
                "run": self._to_run_view(run_record).model_dump(mode="json"),
                "pending_approval": pending_approval.model_dump(mode="json") if pending_approval else None,
                "latest_rejection_reason": latest_rejection_reason,
                "latest_decision_summary": latest_decision_summary,
                "task_summary": task_summary.model_dump(mode="json"),
                "latest_task": latest_task.model_dump(mode="json") if latest_task else None,
                "latest_artifact": latest_artifact.model_dump(mode="json") if latest_artifact else None,
            }
            state_hash = sha256(
                json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            ).hexdigest()

            return RunSnapshotView(
                snapshot_timestamp=utc_now(),
                state_hash=state_hash,
                run=self._to_run_view(run_record),
                action_state=SnapshotActionState.STUCK,
                action_state_reason="Possible actions have not been evaluated yet.",
                pending_approval=pending_approval,
                latest_rejection_reason=latest_rejection_reason,
                latest_decision_summary=latest_decision_summary,
                task_summary=task_summary,
                latest_task=latest_task,
                latest_artifact=latest_artifact,
            )

    def execute_bounded_task(
        self,
        *,
        run_id: str,
        workspace: Path,
        artifact_root: Path,
        timeout_seconds: int = 5,
    ) -> BoundedExecutionResult:
        """Execute the first bounded task and persist its task/artifact trail."""

        self.ensure_schema()
        workspace = workspace.expanduser().resolve()
        artifact_root = artifact_root.expanduser().resolve()

        with self.session() as session:
            run = self._get_run_for_execution(session, run_id)
            existing_task_count = session.scalar(
                select(TaskRecord).where(TaskRecord.run_id == run.id).limit(1),
            )
            if existing_task_count is not None:
                raise PermissionError(
                    f"Run {run_id} already has bounded execution evidence and cannot execute again in Step 5.",
                )

            decision = DecisionRecord(
                run_id=run.id,
                kind=DecisionKind.BOUNDED_TASK_SELECTED,
                summary="A bounded repository scan was selected for execution.",
                rationale=(
                    "Step 5 intentionally executes one safe, read-only task so the tracer bullet can "
                    "prove task, artifact, and ledger linkage before broader orchestration is introduced."
                ),
            )
            session.add(decision)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.DECISION_RECORDED,
                    payload={
                        "decision_id": decision.id,
                        "kind": decision.kind.value,
                        "summary": decision.summary,
                    },
                ),
            )

            execution_context_id = str(uuid4())
            task = TaskRecord(
                run_id=run.id,
                decision_id=decision.id,
                kind=TaskKind.REPOSITORY_SCAN,
                status=TaskStatus.READY,
                summary="Scan the repository tree and produce a short structural report.",
                execution_context_id=execution_context_id,
                command=f"scan_repository_tree --workspace {workspace} --max-depth 3",
                cwd=str(workspace),
                timeout_seconds=timeout_seconds,
            )
            session.add(task)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.TASK_CREATED,
                    payload={
                        "task_id": task.id,
                        "decision_id": decision.id,
                        "kind": task.kind.value,
                        "summary": task.summary,
                        "status": task.status.value,
                    },
                ),
            )

            task.status = TaskStatus.RUNNING
            task.started_at = utc_now()
            run.status = RunStatus.RUNNING
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.TASK_STARTED,
                    payload={
                        "task_id": task.id,
                        "decision_id": decision.id,
                        "kind": task.kind.value,
                        "status": task.status.value,
                        "workspace": str(workspace),
                    },
                ),
            )
            session.flush()
            task_id = task.id

        try:
            receipt = execute_repository_scan(
                workspace=workspace,
                timeout_seconds=timeout_seconds,
                execution_context_id=execution_context_id,
            )
        except (BoundedExecutorTimeout, BoundedExecutorError, FileNotFoundError, NotADirectoryError) as exc:
            return self._finalize_failed_task(
                run_id=run_id,
                task_id=task_id,
                stderr=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive final guard
            return self._finalize_failed_task(
                run_id=run_id,
                task_id=task_id,
                stderr=f"Unexpected bounded executor failure: {exc}",
            )

        try:
            return self._finalize_completed_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
            )
        except Exception as exc:
            return self._finalize_failed_task(
                run_id=run_id,
                task_id=task_id,
                stderr=f"Artifact persistence failed after execution: {exc}",
            )

    @staticmethod
    def _build_run_created_event(record: RunRecord) -> EventLedgerRecord:
        return EventLedgerRecord(
            run_id=record.id,
            event_type=LedgerEventType.RUN_CREATED,
            payload={
                "project": record.project,
                "goal": record.goal,
                "urgency": record.urgency.value,
                "risk": record.risk.value,
                "status": record.status.value,
            },
        )

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text fields must not be blank when provided.")
        return cleaned

    @staticmethod
    def _get_run_for_execution(session: Session, run_id: str) -> RunRecord:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise LookupError(f"Run {run_id} was not found.")
        if run.status != RunStatus.READY:
            raise PermissionError(
                f"Run {run_id} is {run.status.value}; bounded execution requires the run to be ready.",
            )
        return run

    @staticmethod
    def _get_run_for_mutation(
        session: Session,
        run_id: str,
        *,
        mutation_name: str,
        allow_during_waiting_approval: bool = False,
    ) -> RunRecord:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise LookupError(f"Run {run_id} was not found.")
        if run.status == RunStatus.WAITING_APPROVAL and not allow_during_waiting_approval:
            raise PermissionError(
                f"Run {run_id} is waiting for approval; {mutation_name} is blocked until approval is resolved.",
            )
        return run

    def _finalize_failed_task(
        self,
        *,
        run_id: str,
        task_id: str,
        stderr: str,
    ) -> BoundedExecutionResult:
        with self.session() as session:
            run = session.get(RunRecord, run_id)
            task = session.get(TaskRecord, task_id)
            if run is None or task is None:
                raise LookupError("Task finalization failed because the run or task no longer exists.")

            task.status = TaskStatus.FAILED
            task.completed_at = utc_now()
            task.stdout = task.stdout or ""
            task.stderr = stderr
            run.status = RunStatus.FAILED

            observation = ObservationRecord(
                run_id=run.id,
                kind=ObservationKind.TASK_EXECUTION,
                summary="Bounded task failed before producing an artifact.",
                details=stderr,
            )
            session.add(observation)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.TASK_FAILED,
                    payload={
                        "task_id": task.id,
                        "decision_id": task.decision_id,
                        "execution_context_id": task.execution_context_id,
                        "status": task.status.value,
                        "error": stderr,
                    },
                ),
            )
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.OBSERVATION_RECORDED,
                    payload={
                        "observation_id": observation.id,
                        "kind": observation.kind.value,
                        "summary": observation.summary,
                    },
                ),
            )
            session.flush()
            return BoundedExecutionResult(
                task=self._to_task_view(task),
                artifact=None,
                observation=self._to_observation_view(observation),
            )

    def _finalize_completed_task(
        self,
        *,
        run_id: str,
        task_id: str,
        artifact_root: Path,
        receipt: TaskExecutionReceipt,
    ) -> BoundedExecutionResult:
        artifact_directory = artifact_root / run_id / task_id
        artifact_directory.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_directory / "repository-scan-report.md"
        artifact_path.write_text(receipt.artifact_body, encoding="utf-8")
        artifact_bytes = artifact_path.read_bytes()
        artifact_hash = sha256(artifact_bytes).hexdigest()

        try:
            # Keep filesystem output and ledger state as close as possible: if the DB write
            # fails after the artifact file is written, we delete the file rather than leave
            # behind an untracked "successful" result.
            with self.session() as session:
                run = session.get(RunRecord, run_id)
                task = session.get(TaskRecord, task_id)
                if run is None or task is None:
                    raise LookupError("Task finalization failed because the run or task no longer exists.")

                task.execution_context_id = receipt.execution_context_id
                task.command = receipt.command
                task.cwd = receipt.cwd
                task.timeout_seconds = receipt.timeout_seconds
                task.stdout = receipt.stdout
                task.stderr = receipt.stderr
                task.completed_at = receipt.finished_at
                task.status = TaskStatus.COMPLETED
                run.status = RunStatus.COMPLETED

                artifact = ArtifactRecord(
                    run_id=run.id,
                    task_id=task.id,
                    decision_id=task.decision_id,
                    artifact_type=ArtifactType.TEXT_REPORT,
                    title=receipt.artifact_title,
                    storage_kind=ArtifactStorageKind.FILESYSTEM_PATH,
                    path=str(artifact_path),
                    size_bytes=len(artifact_bytes),
                    sha256=artifact_hash,
                    execution_context_id=receipt.execution_context_id,
                    command=receipt.command,
                    cwd=receipt.cwd,
                )
                session.add(artifact)
                session.flush()

                observation = ObservationRecord(
                    run_id=run.id,
                    kind=ObservationKind.TASK_EXECUTION,
                    summary="Bounded task completed and recorded an artifact.",
                    details=(
                        f"Task {task.id} finished with artifact {artifact.id} at {artifact.path} "
                        f"and sha256 {artifact.sha256}."
                    ),
                )
                session.add(observation)
                session.flush()

                session.add(
                    EventLedgerRecord(
                        run_id=run.id,
                        event_type=LedgerEventType.ARTIFACT_RECORDED,
                        payload={
                            "artifact_id": artifact.id,
                            "task_id": task.id,
                            "decision_id": task.decision_id,
                            "execution_context_id": artifact.execution_context_id,
                            "path": artifact.path,
                            "sha256": artifact.sha256,
                        },
                    ),
                )
                session.add(
                    EventLedgerRecord(
                        run_id=run.id,
                        event_type=LedgerEventType.TASK_COMPLETED,
                        payload={
                            "task_id": task.id,
                            "decision_id": task.decision_id,
                            "execution_context_id": task.execution_context_id,
                            "artifact_id": artifact.id,
                            "status": task.status.value,
                        },
                    ),
                )
                session.add(
                    EventLedgerRecord(
                        run_id=run.id,
                        event_type=LedgerEventType.OBSERVATION_RECORDED,
                        payload={
                            "observation_id": observation.id,
                            "kind": observation.kind.value,
                            "summary": observation.summary,
                        },
                    ),
                )
                session.flush()
                return BoundedExecutionResult(
                    task=self._to_task_view(task),
                    artifact=self._to_artifact_view(artifact),
                    observation=self._to_observation_view(observation),
                )
        except Exception:
            if artifact_path.exists():
                artifact_path.unlink()
            raise

    @staticmethod
    def _to_run_view(record: RunRecord) -> RunView:
        return RunView.model_validate(
            {
                "id": record.id,
                "project": record.project,
                "goal": record.goal,
                "status": record.status,
                "urgency": record.urgency,
                "risk": record.risk,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            },
        )

    @staticmethod
    def _to_decision_view(record: DecisionRecord) -> DecisionView:
        return DecisionView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "kind": record.kind,
                "summary": record.summary,
                "rationale": record.rationale,
                "created_at": record.created_at,
            },
        )

    @staticmethod
    def _to_observation_view(record: ObservationRecord) -> ObservationView:
        return ObservationView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "kind": record.kind,
                "summary": record.summary,
                "details": record.details,
                "created_at": record.created_at,
            },
        )

    @staticmethod
    def _to_approval_view(record: ApprovalRecord) -> ApprovalView:
        return ApprovalView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "status": record.status,
                "requested_action": record.requested_action,
                "reason": record.reason,
                "approve_effect": record.approve_effect,
                "reject_effect": record.reject_effect,
                "requested_at": record.requested_at,
                "resolved_at": record.resolved_at,
                "resolution_reason": record.resolution_reason,
            },
        )

    @staticmethod
    def _build_task_status_summary(records: list[TaskRecord]) -> TaskStatusSummary:
        counts = {
            TaskStatus.CREATED: 0,
            TaskStatus.READY: 0,
            TaskStatus.RUNNING: 0,
            TaskStatus.COMPLETED: 0,
            TaskStatus.FAILED: 0,
        }
        for record in records:
            counts[record.status] += 1
        return TaskStatusSummary(
            created=counts[TaskStatus.CREATED],
            ready=counts[TaskStatus.READY],
            running=counts[TaskStatus.RUNNING],
            completed=counts[TaskStatus.COMPLETED],
            failed=counts[TaskStatus.FAILED],
        )

    @staticmethod
    def _build_task_headline(record: TaskRecord) -> TaskHeadlineView:
        failure_hint = None
        if record.stderr:
            failure_hint = record.stderr.strip().splitlines()[0][:400]
        return TaskHeadlineView(
            id=record.id,
            kind=record.kind,
            status=record.status,
            summary=record.summary,
            started_at=record.started_at,
            completed_at=record.completed_at,
            failure_hint=failure_hint,
        )

    @staticmethod
    def _build_artifact_headline(artifact: ArtifactInspectionView) -> ArtifactHeadlineView:
        return ArtifactHeadlineView(
            id=artifact.artifact.id,
            artifact_type=artifact.artifact.artifact_type,
            title=artifact.artifact.title,
            size_bytes=artifact.artifact.size_bytes,
            file_exists=artifact.file_exists,
            hash_matches=artifact.hash_matches,
        )

    @staticmethod
    def _to_task_view(record: TaskRecord) -> TaskView:
        return TaskView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "decision_id": record.decision_id,
                "kind": record.kind,
                "status": record.status,
                "summary": record.summary,
                "execution_context_id": record.execution_context_id,
                "command": record.command,
                "cwd": record.cwd,
                "timeout_seconds": record.timeout_seconds,
                "stdout": record.stdout,
                "stderr": record.stderr,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
            },
        )

    @staticmethod
    def _to_artifact_view(record: ArtifactRecord) -> ArtifactView:
        return ArtifactView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "task_id": record.task_id,
                "decision_id": record.decision_id,
                "artifact_type": record.artifact_type,
                "title": record.title,
                "storage_kind": record.storage_kind,
                "path": record.path,
                "size_bytes": record.size_bytes,
                "sha256": record.sha256,
                "execution_context_id": record.execution_context_id,
                "command": record.command,
                "cwd": record.cwd,
                "created_at": record.created_at,
            },
        )

    @staticmethod
    def _inspect_artifact(record: ArtifactRecord) -> ArtifactInspectionView:
        artifact = LedgerStore._to_artifact_view(record)
        artifact_path = Path(artifact.path)
        if not artifact_path.exists():
            return ArtifactInspectionView(
                artifact=artifact,
                file_exists=False,
                hash_matches=None,
            )
        current_hash = sha256(artifact_path.read_bytes()).hexdigest()
        return ArtifactInspectionView(
            artifact=artifact,
            file_exists=True,
            hash_matches=current_hash == artifact.sha256,
        )

    @staticmethod
    def _build_consistency_warnings(
        *,
        run: RunView,
        approvals: list[ApprovalView],
        tasks: list[TaskReplayView],
        orphan_artifacts: list[ArtifactInspectionView],
        ledger_events: list[EventLedgerRecord],
    ) -> list[str]:
        warnings: list[str] = []
        task_completed_ids = {
            str(event.payload.get("task_id"))
            for event in ledger_events
            if event.event_type == LedgerEventType.TASK_COMPLETED
        }
        task_failed_ids = {
            str(event.payload.get("task_id"))
            for event in ledger_events
            if event.event_type == LedgerEventType.TASK_FAILED
        }
        artifact_recorded_ids = {
            str(event.payload.get("artifact_id"))
            for event in ledger_events
            if event.event_type == LedgerEventType.ARTIFACT_RECORDED
        }

        if orphan_artifacts:
            warnings.append("At least one artifact is not linked to a known task.")

        if run.status == RunStatus.COMPLETED and not any(
            task.task.status == TaskStatus.COMPLETED for task in tasks
        ):
            warnings.append("Run is marked completed but no completed task is present.")

        if run.status == RunStatus.FAILED and not any(
            task.task.status == TaskStatus.FAILED for task in tasks
        ):
            warnings.append("Run is marked failed but no failed task is present.")

        if run.status == RunStatus.REJECTED and not any(
            approval.status == ApprovalStatus.REJECTED for approval in approvals
        ):
            warnings.append("Run is marked rejected but no rejected approval is recorded.")

        for task in tasks:
            if task.task.status == TaskStatus.COMPLETED and str(task.task.id) not in task_completed_ids:
                warnings.append(
                    f"Task {task.task.id} is completed in state but missing TASK_COMPLETED in the ledger.",
                )
            if task.task.status == TaskStatus.FAILED and str(task.task.id) not in task_failed_ids:
                warnings.append(
                    f"Task {task.task.id} is failed in state but missing TASK_FAILED in the ledger.",
                )
            if task.task.status == TaskStatus.COMPLETED and not task.artifacts:
                warnings.append(
                    f"Task {task.task.id} completed without a linked artifact.",
                )
            for artifact in task.artifacts:
                if not artifact.file_exists:
                    warnings.append(
                        f"Artifact {artifact.artifact.id} is missing from the filesystem path recorded in the ledger.",
                    )
                if artifact.hash_matches is False:
                    warnings.append(
                        f"Artifact {artifact.artifact.id} exists but its contents no longer match the stored sha256.",
                    )
                if str(artifact.artifact.id) not in artifact_recorded_ids:
                    warnings.append(
                        f"Artifact {artifact.artifact.id} exists in state but is missing ARTIFACT_RECORDED in the ledger.",
                    )
        return warnings
