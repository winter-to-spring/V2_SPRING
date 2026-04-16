from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Iterator
from uuid import uuid4

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from v2_spring.domain.approval import ApprovalStatus, ApprovalView
from v2_spring.domain.artifact import ArtifactStorageKind, ArtifactType, ArtifactView
from v2_spring.domain.decision import DecisionKind, DecisionView
from v2_spring.domain.founder_intervention import (
    FounderInterventionDigest,
    FounderInterventionView,
    FounderOverrideInput,
    FounderReplyInput,
    FounderReplyKind,
)
from v2_spring.domain.observation import ObservationKind, ObservationView
from v2_spring.domain.planner_adapter import (
    EscalationProposal,
    FailureClass,
    FailureReportView,
    MaskedActionView,
    PlannerAttemptDigest,
    PlannerContextWindow,
)
from v2_spring.domain.planner_attempt import (
    PlannerAttemptOutcome,
    PlannerAttemptView,
    PlannerGovernanceView,
    PlannerRechargeCautionCode,
    PlannerRechargePreflightView,
)
from v2_spring.domain.proposal import PlannerProposalInput, PlannerProposalView
from v2_spring.domain.replay import ArtifactInspectionView, RunReplayView, TaskReplayView
from v2_spring.domain.run import RunCreateInput, RunStatus, RunView
from v2_spring.domain.snapshot import (
    ArtifactHeadlineView,
    PendingFounderEscalationView,
    PossibleActionView,
    PossibleActionName,
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
    FounderInterventionRecord,
    LedgerEventType,
    ObservationRecord,
    PlannerAttemptRecord,
    RunRecord,
    TaskRecord,
    utc_now,
)
from v2_spring.planner.actions import POSSIBLE_ACTIONS_ENGINE_VERSION, evaluate_possible_actions
from v2_spring.planner.proposals import (
    PlannerAdapterFormatError,
    CognitiveDuplicatePlannerProposalError,
    IllegalPlannerProposalError,
    PlannerPhaseExhaustedError,
    PlannerStaleQuotaExhaustedError,
    StalePlannerProposalError,
    TransportDuplicatePlannerProposalError,
)


@dataclass(frozen=True)
class BoundedExecutionResult:
    """Return the first execution proof in a single typed bundle."""

    task: TaskView
    artifact: ArtifactView | None
    observation: ObservationView


class LedgerStore:
    """Typed persistence boundary for V2_SPRING tracer-bullet state and events."""

    _DEFAULT_APPROVAL_TIMEOUT = timedelta(hours=24)
    # Approval should pause stateful progression, not blind the system.
    _APPROVAL_SAFE_OBSERVATION_KINDS = frozenset(
        {
            ObservationKind.SYSTEM_AUDIT,
            ObservationKind.PLANNER_ESCALATION,
        },
    )
    _PLANNER_PHASE_BUDGET_LIMIT = 3
    _PLANNER_STALE_QUOTA_LIMIT = 3
    _FOUNDER_HINT_QUOTA_LIMIT = 2
    _PLANNER_BUDGET_CONSUMING_OUTCOMES = frozenset(
        {
            PlannerAttemptOutcome.REJECTED_ILLEGAL,
            PlannerAttemptOutcome.REJECTED_FORMAT,
            PlannerAttemptOutcome.REJECTED_DUPLICATE_COGNITIVE,
        },
    )

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
        self._ensure_schema_columns()
        self._backfill_approval_expirations()

    def _ensure_schema_columns(self) -> None:
        with self._engine.begin() as connection:
            inspector = inspect(connection)
            if "approvals" not in inspector.get_table_names():
                return
            approval_columns = {column["name"] for column in inspector.get_columns("approvals")}
            if "expires_at" not in approval_columns:
                connection.execute(text("ALTER TABLE approvals ADD COLUMN expires_at DATETIME"))

    def _backfill_approval_expirations(self) -> None:
        with self.session() as session:
            records = list(
                session.scalars(
                    select(ApprovalRecord).where(ApprovalRecord.expires_at.is_(None)),
                ).all(),
            )
            changed = False
            for record in records:
                record.expires_at = record.requested_at + self._DEFAULT_APPROVAL_TIMEOUT
                changed = True
            if changed:
                session.flush()

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
                expires_at=utc_now() + self._DEFAULT_APPROVAL_TIMEOUT,
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
                        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
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
                        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                    },
                ),
            )
            session.flush()
            return self._to_approval_view(approval)

    def expire_overdue_approvals(self, *, now=None) -> list[ApprovalView]:
        self.ensure_schema()
        effective_now = now or utc_now()
        with self.session() as session:
            records = list(
                session.scalars(
                    select(ApprovalRecord)
                    .where(ApprovalRecord.status == ApprovalStatus.PENDING)
                    .where(ApprovalRecord.expires_at.is_not(None))
                    .where(ApprovalRecord.expires_at <= effective_now)
                    .order_by(ApprovalRecord.expires_at.asc(), ApprovalRecord.id.asc()),
                ).all(),
            )
            expired_views: list[ApprovalView] = []
            for approval in records:
                approval.status = ApprovalStatus.EXPIRED
                approval.resolved_at = effective_now
                approval.resolution_reason = self._build_approval_timeout_reason(approval.expires_at)

                run = session.get(RunRecord, approval.run_id)
                run_status = None
                if run is not None and run.status == RunStatus.WAITING_APPROVAL:
                    run.status = RunStatus.SUSPENDED
                    run_status = run.status.value
                elif run is not None:
                    run_status = run.status.value

                session.add(
                    EventLedgerRecord(
                        run_id=approval.run_id,
                        event_type=LedgerEventType.APPROVAL_RESOLVED,
                        payload={
                            "approval_id": approval.id,
                            "status": approval.status.value,
                            "run_status": run_status,
                            "resolution_reason": approval.resolution_reason,
                            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                            "timeout_applied_at": effective_now.isoformat(),
                        },
                    ),
                )
                audit = ObservationRecord(
                    run_id=approval.run_id,
                    kind=ObservationKind.SYSTEM_AUDIT,
                    summary="Approval expired and suspended the run.",
                    details=(
                        f"Approval {approval.id} expired at {approval.expires_at.isoformat() if approval.expires_at else '-'} "
                        f"without a founder response. The run moved to {run_status if run_status else 'its current status'} "
                        "and now requires explicit recovery before work can continue."
                    ),
                )
                session.add(audit)
                session.flush()
                session.add(
                    EventLedgerRecord(
                        run_id=approval.run_id,
                        event_type=LedgerEventType.OBSERVATION_RECORDED,
                        payload={
                            "observation_id": audit.id,
                            "kind": audit.kind.value,
                            "summary": audit.summary,
                        },
                    ),
                )
                expired_views.append(self._to_approval_view(approval))

            session.flush()
            return expired_views

    def record_decision(
        self,
        *,
        run_id: str,
        kind: DecisionKind,
        summary: str,
        rationale: str,
        extra_payload: dict[str, object] | None = None,
        allow_during_waiting_approval: bool = False,
    ) -> DecisionView:
        self.ensure_schema()
        with self.session() as session:
            run = self._get_run_for_mutation(
                session,
                run_id,
                mutation_name="decision recording",
                allow_during_waiting_approval=allow_during_waiting_approval,
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
                        "rationale": record.rationale,
                        **(extra_payload or {}),
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
                allow_during_suspended=kind in self._APPROVAL_SAFE_OBSERVATION_KINDS,
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

    def list_planner_attempts_for_run(self, run_id: str) -> list[PlannerAttemptView]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(PlannerAttemptRecord)
                .where(PlannerAttemptRecord.run_id == run_id)
                .order_by(PlannerAttemptRecord.created_at.asc(), PlannerAttemptRecord.id.asc())
            )
            records = list(session.scalars(statement).all())
            return [self._to_planner_attempt_view(record) for record in records]

    def list_founder_interventions_for_run(self, run_id: str) -> list[FounderInterventionView]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(FounderInterventionRecord)
                .where(FounderInterventionRecord.run_id == run_id)
                .order_by(FounderInterventionRecord.created_at.asc(), FounderInterventionRecord.id.asc())
            )
            records = list(session.scalars(statement).all())
            return [self._to_founder_intervention_view(record) for record in records]

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
            planner_attempt_records = list(
                session.scalars(
                    select(PlannerAttemptRecord)
                    .where(PlannerAttemptRecord.run_id == run_id)
                    .order_by(PlannerAttemptRecord.created_at.asc(), PlannerAttemptRecord.id.asc()),
                ).all(),
            )
            founder_intervention_records = list(
                session.scalars(
                    select(FounderInterventionRecord)
                    .where(FounderInterventionRecord.run_id == run_id)
                    .order_by(FounderInterventionRecord.created_at.asc(), FounderInterventionRecord.id.asc()),
                ).all(),
            )
            ledger_events = list(
                session.scalars(
                    select(EventLedgerRecord)
                    .where(EventLedgerRecord.run_id == run_id)
                    .order_by(EventLedgerRecord.recorded_at.asc(), EventLedgerRecord.id.asc()),
                ).all(),
            )
            planner_attempts = [self._to_planner_attempt_view(record) for record in planner_attempt_records]
            founder_interventions = [
                self._to_founder_intervention_view(record) for record in founder_intervention_records
            ]

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
                planner_attempts=planner_attempts,
                founder_interventions=founder_interventions,
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
            observation_records = list(
                session.scalars(
                    select(ObservationRecord)
                    .where(ObservationRecord.run_id == run_id)
                    .order_by(ObservationRecord.created_at.asc(), ObservationRecord.id.asc()),
                ).all(),
            )
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
            planner_attempt_records = list(
                session.scalars(
                    select(PlannerAttemptRecord)
                    .where(PlannerAttemptRecord.run_id == run_id)
                    .order_by(PlannerAttemptRecord.created_at.asc(), PlannerAttemptRecord.id.asc()),
                ).all(),
            )
            founder_intervention_records = list(
                session.scalars(
                    select(FounderInterventionRecord)
                    .where(FounderInterventionRecord.run_id == run_id)
                    .order_by(FounderInterventionRecord.created_at.asc(), FounderInterventionRecord.id.asc()),
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
            pending_founder_escalation = self._build_pending_founder_escalation(
                observation_records=observation_records,
                founder_intervention_records=founder_intervention_records,
            )
            founder_interventions = [
                self._to_founder_intervention_view(record) for record in founder_intervention_records
            ]
            recent_founder_interventions = [
                FounderInterventionDigest(
                    reply_kind=item.reply_kind,
                    summary=self._sanitize_planner_text(item.summary, limit=400)
                    or "Founder intervention recorded.",
                    detail=self._sanitize_planner_text(item.detail, limit=1000)
                    or "Founder intervention detail is unavailable.",
                    override_action=item.override_action,
                    created_at=item.created_at,
                )
                for item in founder_interventions[-2:]
            ]
            latest_founder_intervention_summary = founder_interventions[-1].summary if founder_interventions else None
            task_summary = self._build_task_status_summary(task_records)
            planner_phase_key = self._build_planner_phase_key(
                run=self._to_run_view(run_record),
                pending_approval=pending_approval,
                latest_rejection_reason=latest_rejection_reason,
                task_summary=task_summary,
                latest_task=latest_task,
                latest_artifact=latest_artifact,
            )
            planner_governance = self._build_planner_governance_from_records(
                run_id=run_id,
                phase_key=planner_phase_key,
                records=planner_attempt_records,
            )

            snapshot_payload = {
                "policy_version": POSSIBLE_ACTIONS_ENGINE_VERSION,
                "run": self._to_run_view(run_record).model_dump(mode="json"),
                "pending_approval": pending_approval.model_dump(mode="json") if pending_approval else None,
                "pending_founder_escalation": (
                    pending_founder_escalation.model_dump(mode="json") if pending_founder_escalation else None
                ),
                "latest_founder_intervention_summary": latest_founder_intervention_summary,
                "latest_rejection_reason": latest_rejection_reason,
                "latest_decision_summary": latest_decision_summary,
                "planner_phase_key": planner_governance.phase_key,
                "planner_budget_limit": planner_governance.budget_limit,
                "planner_budget_used": planner_governance.budget_used,
                "planner_budget_remaining": planner_governance.budget_remaining,
                "planner_phase_exhausted": planner_governance.exhausted,
                "planner_stale_quota_limit": planner_governance.stale_quota_limit,
                "planner_stale_quota_used": planner_governance.stale_quota_used,
                "planner_stale_quota_remaining": planner_governance.stale_quota_remaining,
                "planner_stale_quota_exhausted": planner_governance.stale_quota_exhausted,
                "latest_planner_attempt_summary": planner_governance.latest_attempt_summary,
                "task_summary": task_summary.model_dump(mode="json"),
                "latest_task": latest_task.model_dump(mode="json") if latest_task else None,
                "latest_artifact": latest_artifact.model_dump(mode="json") if latest_artifact else None,
            }
            state_hash = sha256(
                json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            ).hexdigest()

            return RunSnapshotView(
                snapshot_timestamp=utc_now(),
                policy_version=POSSIBLE_ACTIONS_ENGINE_VERSION,
                state_hash=state_hash,
                run=self._to_run_view(run_record),
                action_state=SnapshotActionState.STUCK,
                action_state_reason="Possible actions have not been evaluated yet.",
                pending_approval=pending_approval,
                pending_founder_escalation=pending_founder_escalation,
                latest_founder_intervention_summary=latest_founder_intervention_summary,
                latest_rejection_reason=latest_rejection_reason,
                latest_decision_summary=latest_decision_summary,
                planner_phase_key=planner_governance.phase_key,
                planner_budget_limit=planner_governance.budget_limit,
                planner_budget_used=planner_governance.budget_used,
                planner_budget_remaining=planner_governance.budget_remaining,
                planner_phase_exhausted=planner_governance.exhausted,
                planner_stale_quota_limit=planner_governance.stale_quota_limit,
                planner_stale_quota_used=planner_governance.stale_quota_used,
                planner_stale_quota_remaining=planner_governance.stale_quota_remaining,
                planner_stale_quota_exhausted=planner_governance.stale_quota_exhausted,
                latest_planner_attempt_summary=planner_governance.latest_attempt_summary,
                task_summary=task_summary,
                latest_task=latest_task,
                latest_artifact=latest_artifact,
                recent_founder_interventions=recent_founder_interventions,
            )

    def record_planner_proposal(
        self,
        *,
        run_id: str,
        proposal: PlannerProposalInput,
    ) -> PlannerProposalView:
        """Validate and persist one planner proposal against the current legal move set."""

        snapshot = self.build_run_snapshot(run_id)
        evaluation = evaluate_possible_actions(snapshot)
        legal_actions = {action.name for action in evaluation.actions}
        legal_action_descriptions = [
            {
                "name": action.name.value,
                "reason": action.reason,
                "context_hint": action.context_hint,
            }
            for action in evaluation.actions
        ]
        governance = self.build_planner_governance(run_id)
        current_attempts = governance.attempts
        proposal_fingerprint = self._build_planner_proposal_fingerprint(
            snapshot_hash=proposal.snapshot_hash,
            selected_action=proposal.selected_action,
            rationale=proposal.rationale,
            expected_outcome=proposal.expected_outcome,
        )
        proposal_intent_signature = self._build_planner_proposal_intent_signature(
            selected_action=proposal.selected_action,
            rationale=proposal.rationale,
            expected_outcome=proposal.expected_outcome,
        )

        if governance.exhausted:
            raise PlannerPhaseExhaustedError(
                "Planner phase budget is exhausted for the current state segment. "
                "Use `v2-spring planner recharge <run-id> --reason ...` before proposing again.",
            )
        if snapshot.pending_founder_escalation is not None:
            raise PermissionError(
                "Founder reply is still required for the current planner escalation before new proposals are allowed. "
                f"Pending escalation={snapshot.pending_founder_escalation.observation_id}.",
            )
        repeated_failure_escalation = self.open_repeated_failure_founder_escalation_if_needed(run_id)
        if repeated_failure_escalation is not None:
            raise PermissionError(
                "Founder review is now required because deterministic execution failure repeated without state advancement. "
                f"Pending escalation={repeated_failure_escalation.observation_id}.",
            )

        if proposal.submission_key is not None:
            duplicate_transport = next(
                (
                    attempt
                    for attempt in current_attempts
                    if attempt.submission_key == proposal.submission_key
                ),
                None,
            )
            if duplicate_transport is not None:
                attempt = self._record_planner_attempt(
                    run_id=run_id,
                    phase_key=governance.phase_key,
                    policy_version=governance.policy_version,
                    snapshot_hash=evaluation.snapshot.state_hash,
                selected_action=proposal.selected_action,
                submission_key=proposal.submission_key,
                proposal_fingerprint=proposal_fingerprint,
                proposal_intent_signature=proposal_intent_signature,
                outcome=PlannerAttemptOutcome.REJECTED_DUPLICATE_TRANSPORT,
                outcome_reason=(
                    f"Submission key {proposal.submission_key} already exists for this phase; "
                    "transport-level duplicates are rejected explicitly."
                ),
                    budget_used=governance.budget_used,
                    budget_limit=governance.budget_limit,
                    consume_budget=False,
                )
                raise TransportDuplicatePlannerProposalError(
                    "Planner submission was rejected as a transport-level duplicate. "
                    f"Existing phase key={attempt.phase_key}, submission_key={proposal.submission_key}.",
                )

        if proposal.snapshot_hash != evaluation.snapshot.state_hash:
            stale_used = governance.stale_quota_used + 1
            self._record_planner_attempt(
                run_id=run_id,
                phase_key=governance.phase_key,
                policy_version=governance.policy_version,
                snapshot_hash=proposal.snapshot_hash,
                selected_action=proposal.selected_action,
                submission_key=proposal.submission_key,
                proposal_fingerprint=proposal_fingerprint,
                proposal_intent_signature=proposal_intent_signature,
                outcome=PlannerAttemptOutcome.REJECTED_STALE,
                outcome_reason=(
                    f"Provided snapshot hash {proposal.snapshot_hash} does not match current "
                    f"state hash {evaluation.snapshot.state_hash}."
                ),
                budget_used=governance.budget_used,
                budget_limit=governance.budget_limit,
                consume_budget=False,
            )
            self.record_observation(
                run_id=run_id,
                kind=ObservationKind.SYSTEM_AUDIT,
                summary="Planner proposal rejected because the snapshot hash was stale.",
                details=(
                    f"error_code={PlannerAttemptOutcome.REJECTED_STALE.value}; "
                    f"selected_action={proposal.selected_action.value}; "
                    f"policy_version={evaluation.snapshot.policy_version}; "
                    f"provided_hash={proposal.snapshot_hash}; "
                    f"current_hash={evaluation.snapshot.state_hash}."
                ),
            )
            if stale_used >= governance.stale_quota_limit:
                raise PlannerStaleQuotaExhaustedError(
                    "Planner proposal snapshot hash is stale and the separate stale quota is exhausted. "
                    "Wait for state to stabilize or ask the founder to inspect the run before proposing again.",
                )
            raise StalePlannerProposalError(
                "Planner proposal snapshot hash is stale; refresh the run snapshot before proposing again. "
                f"Provided={proposal.snapshot_hash}, current={evaluation.snapshot.state_hash}. "
                f"Stale quota {stale_used}/{governance.stale_quota_limit}.",
            )
        existing_accepted = next(
            (
                attempt
                for attempt in current_attempts
                if attempt.outcome == PlannerAttemptOutcome.ACCEPTED and attempt.selected_action is not None
            ),
            None,
        )
        duplicate_cognitive = next(
            (
                attempt
                for attempt in current_attempts
                if attempt.proposal_fingerprint == proposal_fingerprint
                and attempt.outcome
                in {
                    PlannerAttemptOutcome.ACCEPTED,
                    PlannerAttemptOutcome.REJECTED_DUPLICATE_COGNITIVE,
                }
            ),
            None,
        )
        semantic_duplicate = next(
            (
                event.payload
                for event in self.list_events_for_run(run_id)
                if event.event_type == LedgerEventType.PLANNER_ATTEMPT_RECORDED
                and event.payload.get("phase_key") == governance.phase_key
                and event.payload.get("selected_action") == proposal.selected_action.value
                and event.payload.get("proposal_intent_signature") == proposal_intent_signature
                and event.payload.get("outcome")
                in {
                    PlannerAttemptOutcome.ACCEPTED.value,
                    PlannerAttemptOutcome.REJECTED_ILLEGAL.value,
                    PlannerAttemptOutcome.REJECTED_DUPLICATE_COGNITIVE.value,
                }
            ),
            None,
        )
        if existing_accepted is not None or duplicate_cognitive is not None or semantic_duplicate is not None:
            duplicate_reason = (
                "The current phase already has an accepted planner proposal and state has not advanced yet."
                if existing_accepted is not None
                else (
                    "The planner repeated the same proposal fingerprint inside the current phase."
                    if duplicate_cognitive is not None
                    else "The planner repeated the same normalized proposal intent inside the current phase."
                )
            )
            budget_used = governance.budget_used + 1
            self._record_planner_attempt(
                run_id=run_id,
                phase_key=governance.phase_key,
                policy_version=governance.policy_version,
                snapshot_hash=evaluation.snapshot.state_hash,
                selected_action=proposal.selected_action,
                submission_key=proposal.submission_key,
                proposal_fingerprint=proposal_fingerprint,
                proposal_intent_signature=proposal_intent_signature,
                outcome=PlannerAttemptOutcome.REJECTED_DUPLICATE_COGNITIVE,
                outcome_reason=duplicate_reason,
                budget_used=governance.budget_used,
                budget_limit=governance.budget_limit,
                consume_budget=True,
            )
            self.record_observation(
                run_id=run_id,
                kind=ObservationKind.SYSTEM_AUDIT,
                summary="Planner proposal rejected as a cognitive duplicate.",
                details=(
                    f"error_code={PlannerAttemptOutcome.REJECTED_DUPLICATE_COGNITIVE.value}; "
                    f"selected_action={proposal.selected_action.value}; "
                    f"proposal_fingerprint={proposal_fingerprint}; "
                    f"proposal_intent_signature={proposal_intent_signature}; "
                    f"phase_key={governance.phase_key}."
                ),
            )
            if budget_used >= governance.budget_limit:
                self._record_phase_exhaustion(
                    run_id=run_id,
                    governance=governance,
                    snapshot_hash=evaluation.snapshot.state_hash,
                    reason="Planner phase budget was exhausted after repeated duplicate proposals.",
                )
            raise CognitiveDuplicatePlannerProposalError(
                f"Planner proposal was rejected as a cognitive duplicate for phase {governance.phase_key}.",
            )

        if proposal.selected_action not in legal_actions:
            budget_used = governance.budget_used + 1
            self._record_planner_attempt(
                run_id=run_id,
                phase_key=governance.phase_key,
                policy_version=governance.policy_version,
                snapshot_hash=evaluation.snapshot.state_hash,
                selected_action=proposal.selected_action,
                submission_key=proposal.submission_key,
                proposal_fingerprint=proposal_fingerprint,
                proposal_intent_signature=proposal_intent_signature,
                outcome=PlannerAttemptOutcome.REJECTED_ILLEGAL,
                outcome_reason=(
                    f"Selected action {proposal.selected_action.value} is not legal under "
                    f"{evaluation.snapshot.action_state.value} ({evaluation.snapshot.action_state_reason})."
                ),
                budget_used=governance.budget_used,
                budget_limit=governance.budget_limit,
                consume_budget=True,
            )
            self.record_observation(
                run_id=run_id,
                kind=ObservationKind.SYSTEM_AUDIT,
                summary="Planner proposal rejected because the selected action was not legal.",
                details=(
                    f"error_code={PlannerAttemptOutcome.REJECTED_ILLEGAL.value}; "
                    f"selected_action={proposal.selected_action.value}; "
                    f"action_state={evaluation.snapshot.action_state.value}; "
                    f"action_state_reason={evaluation.snapshot.action_state_reason}; "
                    f"legal_actions={legal_action_descriptions}."
                ),
            )
            legal_action_summary = ", ".join(
                f"{action['name']} ({action['reason']})" for action in legal_action_descriptions
            )
            if budget_used >= governance.budget_limit:
                self._record_phase_exhaustion(
                    run_id=run_id,
                    governance=governance,
                    snapshot_hash=evaluation.snapshot.state_hash,
                    reason="Planner phase budget was exhausted after an illegal proposal attempt.",
                )
            raise IllegalPlannerProposalError(
                f"Planner action {proposal.selected_action.value} is not legal for run {run_id} under the current snapshot. "
                f"Current action_state={evaluation.snapshot.action_state.value} "
                f"({evaluation.snapshot.action_state_reason}). "
                f"Legal actions: {legal_action_summary if legal_action_summary else 'none'}.",
            )

        self._record_planner_attempt(
            run_id=run_id,
            phase_key=governance.phase_key,
            policy_version=governance.policy_version,
            snapshot_hash=proposal.snapshot_hash,
            selected_action=proposal.selected_action,
            submission_key=proposal.submission_key,
            proposal_fingerprint=proposal_fingerprint,
            proposal_intent_signature=proposal_intent_signature,
            outcome=PlannerAttemptOutcome.ACCEPTED,
            outcome_reason="Planner proposal was accepted under the current legal-action guard.",
            budget_used=governance.budget_used,
            budget_limit=governance.budget_limit,
            consume_budget=False,
        )

        decision = self.record_decision(
            run_id=run_id,
            kind=DecisionKind.PLANNER_PROPOSAL_ACCEPTED,
            summary=f"Planner selected {proposal.selected_action.value}.",
            rationale=proposal.rationale,
            allow_during_waiting_approval=True,
            extra_payload={
                "policy_version": evaluation.snapshot.policy_version,
                "snapshot_hash": proposal.snapshot_hash,
                "selected_action": proposal.selected_action.value,
                "submission_key": proposal.submission_key,
                "proposal_fingerprint": proposal_fingerprint,
                "proposal_intent_signature": proposal_intent_signature,
                "expected_outcome": proposal.expected_outcome,
                "legal_actions": [action.name.value for action in evaluation.actions],
                "legal_action_details": legal_action_descriptions,
                "action_state": evaluation.snapshot.action_state.value,
                "action_state_reason": evaluation.snapshot.action_state_reason,
            },
        )

        return PlannerProposalView(
            decision_id=decision.id,
            run_id=decision.run_id,
            policy_version=evaluation.snapshot.policy_version,
            snapshot_hash=proposal.snapshot_hash,
            selected_action=proposal.selected_action,
            submission_key=proposal.submission_key,
            rationale=proposal.rationale,
            expected_outcome=proposal.expected_outcome,
            created_at=decision.created_at,
        )

    def build_planner_governance(self, run_id: str) -> PlannerGovernanceView:
        """Return the current phase-scoped planner budget state for one run."""

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
            planner_attempt_records = list(
                session.scalars(
                    select(PlannerAttemptRecord)
                    .where(PlannerAttemptRecord.run_id == run_id)
                    .order_by(PlannerAttemptRecord.created_at.asc(), PlannerAttemptRecord.id.asc()),
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
            latest_task = self._build_task_headline(task_records[-1]) if task_records else None
            latest_artifact = (
                self._build_artifact_headline(self._inspect_artifact(artifact_records[-1]))
                if artifact_records
                else None
            )
            task_summary = self._build_task_status_summary(task_records)
            phase_key = self._build_planner_phase_key(
                run=self._to_run_view(run_record),
                pending_approval=pending_approval,
                latest_rejection_reason=latest_rejection_reason,
                task_summary=task_summary,
                latest_task=latest_task,
                latest_artifact=latest_artifact,
            )
            return self._build_planner_governance_from_records(
                run_id=run_id,
                phase_key=phase_key,
                records=planner_attempt_records,
            )

    def build_planner_recharge_preflight(self, run_id: str) -> PlannerRechargePreflightView:
        """Explain whether a founder should reopen the exhausted planner phase yet."""

        snapshot = self.build_run_snapshot(run_id)
        governance = self.build_planner_governance(run_id)
        failure_report = self.build_failure_report(run_id)
        latest_founder_intervention = (
            snapshot.recent_founder_interventions[-1]
            if snapshot.recent_founder_interventions
            else None
        )

        caution_codes: list[PlannerRechargeCautionCode] = []
        guidance: list[str] = []

        if not governance.exhausted:
            guidance.append(
                "The current planner phase is not exhausted yet, so manual recharge is unavailable.",
            )
        else:
            guidance.append(
                "The current planner phase is exhausted, so one founder-controlled recharge is allowed if the blockage was reviewed.",
            )

        if governance.recharge_count > 0:
            caution_codes.append(PlannerRechargeCautionCode.REPEATED_RECHARGE)
            guidance.append(
                f"This phase has already been manually recharged {governance.recharge_count} time(s). "
                "Only reopen it again if the operating context changed or you intentionally want one more bounded pass.",
            )

        if failure_report is not None:
            guidance.append(
                f"Latest execution failure: {failure_report.error_code} - {failure_report.observed_outcome}",
            )
            if failure_report.deterministic:
                caution_codes.append(PlannerRechargeCautionCode.DETERMINISTIC_FAILURE)
                guidance.append(
                    "That failure looks deterministic, so recharge should usually wait until the underlying blocker is fixed.",
                )
            else:
                guidance.append(
                    "That failure looks transient or infrastructure-related, so recharge may be reasonable once the environment recovers.",
                )
        else:
            guidance.append(
                "No structured execution failure is attached to the current phase.",
            )

        if snapshot.latest_rejection_reason is not None:
            caution_codes.append(PlannerRechargeCautionCode.LATEST_REJECTION_PRESENT)
            guidance.append(
                f"Latest rejection reason is still active: {snapshot.latest_rejection_reason}",
            )

        if (
            latest_founder_intervention is not None
            and latest_founder_intervention.reply_kind == FounderReplyKind.REJECT
        ):
            caution_codes.append(PlannerRechargeCautionCode.PRIOR_FOUNDER_REJECT)
            guidance.append(
                "The most recent founder intervention rejected the previous escalation, so another recharge should only happen if genuinely new information exists.",
            )

        return PlannerRechargePreflightView(
            run_id=snapshot.run.id,
            phase_key=governance.phase_key,
            policy_version=governance.policy_version,
            exhausted=governance.exhausted,
            budget_limit=governance.budget_limit,
            budget_used=governance.budget_used,
            budget_remaining=governance.budget_remaining,
            recharge_count=governance.recharge_count,
            latest_attempt_summary=self._sanitize_planner_text(
                governance.latest_attempt_summary,
                limit=4000,
            ),
            latest_failure_error_code=failure_report.error_code if failure_report is not None else None,
            latest_failure_summary=(
                self._sanitize_planner_text(
                    failure_report.observed_outcome,
                    limit=500,
                )
                if failure_report is not None
                else None
            ),
            latest_failure_deterministic=(
                failure_report.deterministic if failure_report is not None else None
            ),
            latest_rejection_reason=self._sanitize_planner_text(
                snapshot.latest_rejection_reason,
                limit=4000,
            ),
            latest_founder_intervention_kind=(
                latest_founder_intervention.reply_kind
                if latest_founder_intervention is not None
                else None
            ),
            latest_founder_intervention_summary=(
                self._sanitize_planner_text(
                    latest_founder_intervention.summary,
                    limit=400,
                )
                if latest_founder_intervention is not None
                else None
            ),
            caution_codes=caution_codes,
            requires_acknowledgement=bool(caution_codes),
            guidance=guidance,
        )

    def record_planner_recharge(
        self,
        *,
        run_id: str,
        reason: str,
        acknowledge_unchanged_context: bool = False,
    ) -> PlannerAttemptView:
        """Manually reopen a planner phase after the current budget is exhausted."""

        normalized_reason = self._normalize_optional_text(reason)
        if normalized_reason is None:
            raise ValueError("Planner recharge requires a non-blank reason.")

        snapshot = self.build_run_snapshot(run_id)
        governance = self.build_planner_governance(run_id)
        preflight = self.build_planner_recharge_preflight(run_id)
        if not governance.exhausted:
            raise PermissionError(
                f"Run {run_id} is not exhausted in the current planner phase; recharge is not allowed yet.",
            )
        if preflight.requires_acknowledgement and not acknowledge_unchanged_context:
            caution_summary = ", ".join(code.value for code in preflight.caution_codes)
            raise PermissionError(
                "Planner recharge requires explicit acknowledgement because the current phase still carries caution signals "
                f"({caution_summary}). Review `v2-spring planner recharge-check {run_id}` and rerun with "
                "`--acknowledge-unchanged-context` if you still want to reopen this phase.",
            )

        attempt = self._record_planner_attempt(
            run_id=run_id,
            phase_key=governance.phase_key,
            policy_version=governance.policy_version,
            snapshot_hash=snapshot.state_hash,
            selected_action=None,
            submission_key=None,
            proposal_fingerprint=None,
            outcome=PlannerAttemptOutcome.MANUAL_RECHARGE,
            outcome_reason=(
                "Founder manually reopened the current planner phase after exhaustion. "
                f"Reason: {normalized_reason}. "
                f"Caution codes: {', '.join(code.value for code in preflight.caution_codes) if preflight.caution_codes else 'none'}."
            ),
            budget_used=governance.budget_used,
            budget_limit=governance.budget_limit,
            consume_budget=False,
        )
        self.record_observation(
            run_id=run_id,
            kind=ObservationKind.SYSTEM_AUDIT,
            summary="Planner phase was manually recharged after exhaustion.",
            details=(
                f"error_code={PlannerAttemptOutcome.MANUAL_RECHARGE.value}; "
                f"phase_key={governance.phase_key}; "
                f"budget_limit={governance.budget_limit}; "
                f"requires_ack={preflight.requires_acknowledgement}; "
                f"caution_codes={','.join(code.value for code in preflight.caution_codes) if preflight.caution_codes else '-'}; "
                f"latest_failure_error_code={preflight.latest_failure_error_code if preflight.latest_failure_error_code else '-'}; "
                f"latest_rejection_reason={preflight.latest_rejection_reason if preflight.latest_rejection_reason else '-'}; "
                f"reason={normalized_reason}."
            ),
        )
        return attempt

    def list_planner_proposals_for_run(self, run_id: str) -> list[PlannerProposalView]:
        """Return accepted planner proposals recorded for one run."""

        proposals: list[PlannerProposalView] = []
        for event in self.list_events_for_run(run_id):
            if event.event_type != LedgerEventType.DECISION_RECORDED:
                continue
            if event.payload.get("kind") != DecisionKind.PLANNER_PROPOSAL_ACCEPTED.value:
                continue
            proposals.append(
                PlannerProposalView.model_validate(
                    {
                        "decision_id": event.payload["decision_id"],
                        "run_id": run_id,
                        "policy_version": event.payload.get("policy_version", POSSIBLE_ACTIONS_ENGINE_VERSION),
                        "snapshot_hash": event.payload["snapshot_hash"],
                        "selected_action": event.payload["selected_action"],
                        "submission_key": event.payload.get("submission_key"),
                        "rationale": event.payload["rationale"],
                        "expected_outcome": event.payload["expected_outcome"],
                        "created_at": event.recorded_at,
                    },
                ),
            )
        return proposals

    def build_failure_report(self, run_id: str) -> FailureReportView | None:
        """Return the latest sanitized execution failure summary for planner context."""

        replay = self.build_run_replay(run_id)
        failed_tasks = [task for task in replay.tasks if task.task.status == TaskStatus.FAILED]
        if not failed_tasks:
            return None

        latest_failed = failed_tasks[-1]
        failure_text = latest_failed.task.stderr or latest_failed.task.failure_hint or latest_failed.task.summary
        failure_class, error_code = self._classify_failure(failure_text)
        deterministic = failure_class == FailureClass.DETERMINISTIC_RUNTIME
        normalized_signature = self._build_failure_signature(
            error_code=error_code,
            task_kind=latest_failed.task.kind.value,
            failure_text=failure_text,
        )
        streak = 0
        for task_replay in reversed(failed_tasks):
            comparison_text = task_replay.task.stderr or task_replay.task.failure_hint or task_replay.task.summary
            comparison_class, comparison_error_code = self._classify_failure(comparison_text)
            comparison_signature = self._build_failure_signature(
                error_code=comparison_error_code,
                task_kind=task_replay.task.kind.value,
                failure_text=comparison_text,
            )
            if comparison_signature != normalized_signature:
                break
            streak += 1

        proposals = self.list_planner_proposals_for_run(run_id)
        failure_anchor = latest_failed.task.started_at or latest_failed.task.created_at
        latest_proposal = next(
            (
                proposal
                for proposal in reversed(proposals)
                if proposal.created_at <= failure_anchor
            ),
            None,
        )
        if latest_proposal is None:
            latest_proposal = proposals[-1] if proposals else None
        return FailureReportView(
            failure_class=failure_class,
            error_code=error_code,
            short_traceback=self._sanitize_planner_text(failure_text, limit=500),
            normalized_failure_signature=normalized_signature,
            previous_rationale=(
                self._sanitize_planner_text(latest_proposal.rationale, limit=4000)
                if latest_proposal is not None
                else None
            ),
            previous_expected_outcome=(
                self._sanitize_planner_text(latest_proposal.expected_outcome, limit=4000)
                if latest_proposal is not None
                else None
            ),
            observed_outcome=self._sanitize_planner_text(
                latest_failed.task.stderr or latest_failed.task.summary,
                limit=500,
            )
            or "Task failed without a normalized failure hint.",
            repeated_failure_streak=max(streak, 1),
            deterministic=deterministic,
        )

    def build_planner_context(self, run_id: str) -> PlannerContextWindow:
        """Assemble the bounded, sanitized planner context window for one run."""

        snapshot = self.build_run_snapshot(run_id)
        evaluation = evaluate_possible_actions(snapshot)
        governance = self.build_planner_governance(run_id)
        recent_attempts = [
            PlannerAttemptDigest(
                outcome=attempt.outcome,
                selected_action=attempt.selected_action,
                outcome_reason=self._sanitize_planner_text(attempt.outcome_reason, limit=600)
                or "Planner attempt ended without a normalized reason.",
                created_at=attempt.created_at,
            )
            for attempt in governance.attempts[-3:]
        ]
        failure_report = self.build_failure_report(run_id)
        masked_actions = self._build_masked_actions(
            actions=evaluation.actions,
            failure_report=failure_report,
        )
        masked_action_names = {item.name for item in masked_actions}
        legal_actions = [action for action in evaluation.actions if action.name not in masked_action_names]
        return PlannerContextWindow(
            snapshot=evaluation.snapshot,
            legal_actions=legal_actions,
            masked_actions=masked_actions,
            recent_attempts=recent_attempts,
            founder_interventions=evaluation.snapshot.recent_founder_interventions,
            latest_rejection_reason=self._sanitize_planner_text(
                evaluation.snapshot.latest_rejection_reason,
                limit=4000,
            ),
            failure_report=failure_report,
            stale_quota_limit=governance.stale_quota_limit,
            stale_quota_used=governance.stale_quota_used,
            stale_quota_remaining=governance.stale_quota_remaining,
        )

    def open_repeated_failure_founder_escalation_if_needed(
        self,
        run_id: str,
    ) -> PendingFounderEscalationView | None:
        """Open a founder-help lane when deterministic execution failure repeats."""

        snapshot = self.build_run_snapshot(run_id)
        if snapshot.pending_founder_escalation is not None:
            return None

        failure_report = self.build_failure_report(run_id)
        if failure_report is None:
            return None
        if not failure_report.deterministic:
            return None
        if failure_report.repeated_failure_streak < 2:
            return None

        observation = self.record_observation(
            run_id=run_id,
            kind=ObservationKind.PLANNER_ESCALATION,
            summary="System requires founder review after repeated deterministic execution failure.",
            details=(
                "escalation_target=founder; "
                "help_kind=manual_override_request; "
                "error_code=execution_failure_loop_detected; "
                f"failure_error_code={failure_report.error_code}; "
                f"repeated_failure_streak={failure_report.repeated_failure_streak}; "
                f"normalized_failure_signature={failure_report.normalized_failure_signature}; "
                f"blocking_reason={self._sanitize_planner_text(failure_report.observed_outcome, limit=500)}; "
                f"analysis_summary={self._sanitize_planner_text(failure_report.previous_rationale, limit=500) or '-'}; "
                "requested_help=Review whether the same bounded execution path should be redirected, overridden, or stopped before another planner attempt."
            ),
        )
        refreshed_snapshot = self.build_run_snapshot(run_id)
        pending = refreshed_snapshot.pending_founder_escalation
        if pending is None or str(pending.observation_id) != str(observation.id):
            raise RuntimeError(
                "Repeated execution failure escalation was recorded, but the founder-help lane did not become visible in the refreshed snapshot.",
            )
        return pending

    def record_planner_escalation(
        self,
        *,
        run_id: str,
        snapshot_hash: str,
        analysis_summary: str,
        confidence: str,
        help_kind: str,
        blocking_reason: str,
        requested_help: str,
    ) -> ObservationView:
        """Persist one accepted planner escalation request as a governed observation."""

        snapshot = self.build_run_snapshot(run_id)
        governance = self.build_planner_governance(run_id)
        if governance.exhausted:
            raise PlannerPhaseExhaustedError(
                "Planner phase budget is exhausted for the current state segment. "
                "Use `v2-spring planner recharge <run-id> --reason ...` before escalating again.",
            )
        if snapshot.pending_founder_escalation is not None:
            raise PermissionError(
                "Founder reply is still required for the current planner escalation before another escalation can be recorded. "
                f"Pending escalation={snapshot.pending_founder_escalation.observation_id}.",
            )
        founder_interventions = self.list_founder_interventions_for_run(run_id)
        phase_hint_count = sum(
            1
            for intervention in founder_interventions
            if intervention.phase_key == governance.phase_key and intervention.reply_kind == FounderReplyKind.HINT
        )
        if phase_hint_count >= self._FOUNDER_HINT_QUOTA_LIMIT:
            refreshed_governance = self.build_planner_governance(run_id)
            self._record_phase_exhaustion(
                run_id=run_id,
                governance=refreshed_governance,
                snapshot_hash=snapshot.state_hash,
                reason=(
                    "Planner escalation quota was exhausted after repeated founder hints in the current phase."
                ),
            )
            raise PlannerPhaseExhaustedError(
                "Planner escalation quota is exhausted for the current phase after repeated founder hints. "
                "Recharge or advance state before escalating again.",
            )
        proposal_fingerprint = sha256(
            json.dumps(
                {
                    "snapshot_hash": snapshot_hash,
                    "analysis_summary": analysis_summary.strip(),
                    "help_kind": help_kind,
                    "blocking_reason": blocking_reason.strip(),
                    "requested_help": requested_help.strip(),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        ).hexdigest()

        existing_duplicate = next(
            (
                attempt
                for attempt in governance.attempts
                if attempt.proposal_fingerprint == proposal_fingerprint
                and attempt.outcome
                in {
                    PlannerAttemptOutcome.ACCEPTED,
                    PlannerAttemptOutcome.REJECTED_DUPLICATE_COGNITIVE,
                }
            ),
            None,
        )
        if existing_duplicate is not None:
            self._record_planner_attempt(
                run_id=run_id,
                phase_key=governance.phase_key,
                policy_version=governance.policy_version,
                snapshot_hash=snapshot.state_hash,
                selected_action=None,
                submission_key=None,
                proposal_fingerprint=proposal_fingerprint,
                outcome=PlannerAttemptOutcome.REJECTED_DUPLICATE_COGNITIVE,
                outcome_reason="The planner repeated the same escalation request inside the current phase.",
                budget_used=governance.budget_used,
                budget_limit=governance.budget_limit,
                consume_budget=True,
            )
            raise CognitiveDuplicatePlannerProposalError(
                f"Planner escalation was rejected as a cognitive duplicate for phase {governance.phase_key}.",
            )

        self._record_planner_attempt(
            run_id=run_id,
            phase_key=governance.phase_key,
            policy_version=governance.policy_version,
            snapshot_hash=snapshot_hash,
            selected_action=None,
            submission_key=None,
            proposal_fingerprint=proposal_fingerprint,
            outcome=PlannerAttemptOutcome.ACCEPTED,
            outcome_reason="Planner escalation request was accepted and routed to the founder.",
            budget_used=governance.budget_used,
            budget_limit=governance.budget_limit,
            consume_budget=False,
        )
        return self.record_observation(
            run_id=run_id,
            kind=ObservationKind.PLANNER_ESCALATION,
            summary="Planner requested founder help instead of selecting a legal action.",
            details=(
                f"escalation_target=founder; "
                f"confidence={confidence}; "
                f"help_kind={help_kind}; "
                f"analysis_summary={self._sanitize_planner_text(analysis_summary, limit=500)}; "
                f"blocking_reason={self._sanitize_planner_text(blocking_reason, limit=500)}; "
                f"requested_help={self._sanitize_planner_text(requested_help, limit=500)}."
            ),
        )

    def record_founder_reply(
        self,
        *,
        run_id: str,
        target_escalation_id: str,
        reply: FounderReplyInput,
    ) -> FounderInterventionView:
        """Record one typed founder intervention against the current open escalation."""

        snapshot = self.build_run_snapshot(run_id)
        governance = self.build_planner_governance(run_id)
        pending_escalation = snapshot.pending_founder_escalation
        if pending_escalation is None:
            raise LookupError("No pending planner escalation is waiting for a founder reply.")
        if str(pending_escalation.observation_id) != target_escalation_id:
            raise ValueError(
                "Founder reply must target the current open planner escalation. "
                f"Expected={pending_escalation.observation_id}, provided={target_escalation_id}.",
            )

        override_action: PossibleActionName | None = None
        summary: str
        detail: str
        if reply.kind == "hint":
            summary = "Founder provided a bounded hint for the planner."
            detail = reply.message
        elif reply.kind == "override":
            legal_actions = {
                action.name
                for action in evaluate_possible_actions(
                    snapshot.model_copy(
                        update={
                            "pending_founder_escalation": None,
                            "action_state": SnapshotActionState.STUCK,
                            "action_state_reason": "Possible actions have not been evaluated yet.",
                        },
                    ),
                ).actions
            }
            if reply.selected_action not in legal_actions:
                legal_action_summary = ", ".join(action.value for action in sorted(legal_actions, key=lambda item: item.value))
                raise ValueError(
                    f"Founder override action {reply.selected_action.value} is not currently legal. "
                    f"Legal actions: {legal_action_summary if legal_action_summary else 'none'}.",
                )
            override_action = reply.selected_action
            summary = f"Founder overrode the planner and selected {reply.selected_action.value}."
            detail = reply.reason
        else:
            summary = "Founder rejected the planner escalation and stopped the current help lane."
            detail = reply.reason

        self.ensure_schema()
        with self.session() as session:
            target_observation = session.get(ObservationRecord, target_escalation_id)
            if target_observation is None or target_observation.run_id != run_id:
                raise LookupError(
                    f"Planner escalation observation {target_escalation_id} was not found for run {run_id}.",
                )
            if target_observation.kind != ObservationKind.PLANNER_ESCALATION:
                raise ValueError(
                    f"Observation {target_escalation_id} is not a planner escalation and cannot receive a founder reply.",
                )
            existing = session.scalars(
                select(FounderInterventionRecord).where(
                    FounderInterventionRecord.target_observation_id == target_escalation_id,
                ),
            ).first()
            if existing is not None:
                raise ValueError(
                    f"Planner escalation {target_escalation_id} already has a founder reply recorded.",
                )

            record = FounderInterventionRecord(
                run_id=run_id,
                target_observation_id=target_escalation_id,
                phase_key=governance.phase_key,
                policy_version=governance.policy_version,
                reply_kind=FounderReplyKind(reply.kind),
                summary=summary,
                detail=detail,
                override_action=override_action.value if override_action is not None else None,
            )
            session.add(record)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run_id,
                    event_type=LedgerEventType.FOUNDER_INTERVENTION_RECORDED,
                    payload={
                        "founder_intervention_id": record.id,
                        "target_escalation_id": target_escalation_id,
                        "reply_kind": record.reply_kind.value,
                        "summary": record.summary,
                        "override_action": record.override_action,
                        "phase_key": record.phase_key,
                    },
                ),
            )
            if override_action is not None:
                decision = DecisionRecord(
                    run_id=run_id,
                    kind=DecisionKind.FOUNDER_OVERRIDE_ACCEPTED,
                    summary=f"Founder manually selected {override_action.value}.",
                    rationale=detail,
                )
                session.add(decision)
                session.flush()
                session.add(
                    EventLedgerRecord(
                        run_id=run_id,
                        event_type=LedgerEventType.DECISION_RECORDED,
                        payload={
                            "decision_id": decision.id,
                            "kind": decision.kind.value,
                            "summary": decision.summary,
                            "rationale": decision.rationale,
                            "policy_version": governance.policy_version,
                            "selected_action": override_action.value,
                            "source": "founder_override",
                        },
                    ),
                )
            session.flush()

        intervention = self.list_founder_interventions_for_run(run_id)[-1]
        if reply.kind == "override":
            refreshed_governance = self.build_planner_governance(run_id)
            self._record_phase_exhaustion(
                run_id=run_id,
                governance=refreshed_governance,
                snapshot_hash=self.build_run_snapshot(run_id).state_hash,
                reason=(
                    f"Founder override selected {override_action.value}; planner proposals stay closed until state advances."
                ),
            )
        elif reply.kind == "reject":
            refreshed_governance = self.build_planner_governance(run_id)
            self._record_phase_exhaustion(
                run_id=run_id,
                governance=refreshed_governance,
                snapshot_hash=self.build_run_snapshot(run_id).state_hash,
                reason="Founder rejected further help for the current planner escalation lane.",
            )
        return intervention

    def record_planner_format_failure(
        self,
        *,
        run_id: str,
        snapshot_hash: str,
        reason: str,
    ) -> PlannerAttemptView:
        """Persist one planner adapter format failure without mutating legal state."""

        governance = self.build_planner_governance(run_id)
        attempt = self._record_planner_attempt(
            run_id=run_id,
            phase_key=governance.phase_key,
            policy_version=governance.policy_version,
            snapshot_hash=snapshot_hash,
            selected_action=None,
            submission_key=None,
            proposal_fingerprint=None,
            outcome=PlannerAttemptOutcome.REJECTED_FORMAT,
            outcome_reason=reason,
            budget_used=governance.budget_used,
            budget_limit=governance.budget_limit,
            consume_budget=True,
        )
        self.record_observation(
            run_id=run_id,
            kind=ObservationKind.SYSTEM_AUDIT,
            summary="Planner adapter rejected a malformed structured response.",
            details=(
                f"error_code={PlannerAttemptOutcome.REJECTED_FORMAT.value}; "
                f"snapshot_hash={snapshot_hash}; "
                f"reason={self._sanitize_planner_text(reason, limit=500)}."
            ),
        )
        if attempt.budget_remaining == 0:
            snapshot = self.build_run_snapshot(run_id)
            refreshed_governance = self.build_planner_governance(run_id)
            self._record_phase_exhaustion(
                run_id=run_id,
                governance=refreshed_governance,
                snapshot_hash=snapshot.state_hash,
                reason="Planner phase budget was exhausted after repeated adapter format failures.",
            )
        return attempt

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
    def _build_approval_timeout_reason(expires_at) -> str:
        return (
            "Approval timed out without a founder response"
            + (f" by {expires_at.isoformat()}." if expires_at is not None else ".")
        )

    @staticmethod
    def _sanitize_planner_text(value: str | None, *, limit: int) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.replace("\r", "\n").split())
        if not cleaned:
            return None
        redacted = cleaned.replace("/Users/changhyeon/Desktop/AI AGENT", "[workspace]")
        return redacted[:limit]

    @classmethod
    def _classify_failure(cls, failure_text: str) -> tuple[FailureClass, str]:
        normalized = failure_text.lower()
        if any(token in normalized for token in ("permission denied", "forbidden", "403")):
            return FailureClass.DETERMINISTIC_RUNTIME, "permission_denied"
        if any(token in normalized for token in ("no such file", "not found", "enoent")):
            return FailureClass.DETERMINISTIC_RUNTIME, "path_not_found"
        if any(token in normalized for token in ("timed out", "timeout", "deadline exceeded")):
            return FailureClass.TRANSIENT_INFRASTRUCTURE, "timeout"
        if any(token in normalized for token in ("service unavailable", "502", "503", "504", "rate limit", "429")):
            return FailureClass.TRANSIENT_INFRASTRUCTURE, "service_unavailable"
        return FailureClass.UNKNOWN_RUNTIME, "unknown_runtime_failure"

    @classmethod
    def _build_failure_signature(
        cls,
        *,
        error_code: str,
        task_kind: str,
        failure_text: str,
    ) -> str:
        payload = {
            "error_code": error_code,
            "task_kind": task_kind,
            "failure_excerpt": cls._sanitize_planner_text(failure_text, limit=200),
        }
        return sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        ).hexdigest()

    @classmethod
    def _build_masked_actions(
        cls,
        *,
        actions: list[PossibleActionView],
        failure_report: FailureReportView | None,
    ) -> list[MaskedActionView]:
        if failure_report is None:
            return []
        if not failure_report.deterministic:
            return []
        if failure_report.repeated_failure_streak < 2:
            return []
        masked: list[MaskedActionView] = []
        for action in actions:
            if action.name == PossibleActionName.EXECUTE_BOUNDED_TASK:
                masked.append(
                    MaskedActionView(
                        name=action.name,
                        reason=(
                            "The latest deterministic execution failure repeated without state advancement. "
                            "Use replanning or founder escalation before trying the same execution again."
                        ),
                    ),
                )
        return masked

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
        allow_during_suspended: bool = False,
    ) -> RunRecord:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise LookupError(f"Run {run_id} was not found.")
        if run.status == RunStatus.WAITING_APPROVAL and not allow_during_waiting_approval:
            raise PermissionError(
                f"Run {run_id} is waiting for approval; {mutation_name} is blocked until approval is resolved.",
            )
        if run.status == RunStatus.SUSPENDED and not allow_during_suspended:
            raise PermissionError(
                f"Run {run_id} is suspended; {mutation_name} is blocked until the timed-out approval is explicitly recovered.",
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
    def _to_founder_intervention_view(record: FounderInterventionRecord) -> FounderInterventionView:
        return FounderInterventionView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "target_escalation_id": record.target_observation_id,
                "phase_key": record.phase_key,
                "policy_version": record.policy_version,
                "reply_kind": record.reply_kind,
                "summary": record.summary,
                "detail": record.detail,
                "override_action": record.override_action,
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
                "expires_at": record.expires_at,
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
    def _build_pending_founder_escalation(
        *,
        observation_records: list[ObservationRecord],
        founder_intervention_records: list[FounderInterventionRecord],
    ) -> PendingFounderEscalationView | None:
        resolved_targets = {record.target_observation_id for record in founder_intervention_records}
        open_escalation = next(
            (
                record
                for record in reversed(observation_records)
                if record.kind == ObservationKind.PLANNER_ESCALATION and record.id not in resolved_targets
            ),
            None,
        )
        if open_escalation is None:
            return None
        return PendingFounderEscalationView(
            observation_id=open_escalation.id,
            summary=open_escalation.summary,
            details=open_escalation.details[:1000],
            created_at=open_escalation.created_at,
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

        if run.status == RunStatus.SUSPENDED and not any(
            approval.status == ApprovalStatus.EXPIRED for approval in approvals
        ):
            warnings.append("Run is marked suspended but no expired approval is recorded.")

        if any(approval.status == ApprovalStatus.EXPIRED for approval in approvals) and run.status != RunStatus.SUSPENDED:
            warnings.append("An approval expired but the run is not marked suspended.")

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

    @staticmethod
    def _build_planner_phase_key(
        *,
        run: RunView,
        pending_approval: ApprovalView | None,
        latest_rejection_reason: str | None,
        task_summary: TaskStatusSummary,
        latest_task: TaskHeadlineView | None,
        latest_artifact: ArtifactHeadlineView | None,
    ) -> str:
        """Hash only meaningful advancement signals, not planner-only traces."""

        payload = {
            "policy_version": POSSIBLE_ACTIONS_ENGINE_VERSION,
            "run": {
                "id": str(run.id),
                "status": run.status.value,
                "urgency": run.urgency.value,
                "risk": run.risk.value,
            },
            "pending_approval": pending_approval.model_dump(mode="json") if pending_approval else None,
            "latest_rejection_reason": latest_rejection_reason,
            "task_summary": task_summary.model_dump(mode="json"),
            "latest_task": latest_task.model_dump(mode="json") if latest_task else None,
            "latest_artifact": latest_artifact.model_dump(mode="json") if latest_artifact else None,
        }
        return sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        ).hexdigest()

    def _build_planner_governance_from_records(
        self,
        *,
        run_id: str,
        phase_key: str,
        records: list[PlannerAttemptRecord],
    ) -> PlannerGovernanceView:
        phase_records = [record for record in records if record.phase_key == phase_key]
        recharge_indices = [
            index
            for index, record in enumerate(phase_records)
            if record.outcome == PlannerAttemptOutcome.MANUAL_RECHARGE
        ]
        active_start_index = recharge_indices[-1] + 1 if recharge_indices else 0
        active_records = phase_records[active_start_index:]
        budget_used = sum(
            1
            for record in active_records
            if record.outcome in self._PLANNER_BUDGET_CONSUMING_OUTCOMES
        )
        stale_quota_used = sum(
            1
            for record in active_records
            if record.outcome == PlannerAttemptOutcome.REJECTED_STALE
        )
        exhausted = any(
            record.outcome == PlannerAttemptOutcome.PHASE_EXHAUSTED
            for record in active_records
        )
        latest_attempt_summary = None
        if phase_records:
            latest_attempt = phase_records[-1]
            latest_attempt_summary = (
                f"{latest_attempt.outcome.value}: {latest_attempt.outcome_reason}"
            )

        return PlannerGovernanceView(
            run_id=run_id,
            phase_key=phase_key,
            policy_version=POSSIBLE_ACTIONS_ENGINE_VERSION,
            budget_limit=self._PLANNER_PHASE_BUDGET_LIMIT,
            budget_used=budget_used,
            budget_remaining=max(self._PLANNER_PHASE_BUDGET_LIMIT - budget_used, 0),
            exhausted=exhausted,
            stale_quota_limit=self._PLANNER_STALE_QUOTA_LIMIT,
            stale_quota_used=stale_quota_used,
            stale_quota_remaining=max(self._PLANNER_STALE_QUOTA_LIMIT - stale_quota_used, 0),
            stale_quota_exhausted=stale_quota_used >= self._PLANNER_STALE_QUOTA_LIMIT,
            recharge_count=len(recharge_indices),
            latest_attempt_summary=latest_attempt_summary,
            attempts=[self._to_planner_attempt_view(record) for record in active_records],
        )

    @staticmethod
    def _build_planner_proposal_fingerprint(
        *,
        snapshot_hash: str,
        selected_action: PossibleActionName,
        rationale: str,
        expected_outcome: str,
    ) -> str:
        payload = {
            "snapshot_hash": snapshot_hash,
            "selected_action": selected_action.value,
            "rationale": rationale.strip(),
            "expected_outcome": expected_outcome.strip(),
        }
        return sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        ).hexdigest()

    @classmethod
    def _build_planner_proposal_intent_signature(
        cls,
        *,
        selected_action: PossibleActionName,
        rationale: str,
        expected_outcome: str,
    ) -> str:
        alias_map = {
            "db": "database",
            "repo": "repository",
            "repos": "repository",
            "review": "inspect",
            "inspect": "inspect",
            "check": "inspect",
            "examine": "inspect",
            "scan": "inspect",
            "proceed": "continue",
            "proceeding": "continue",
            "continue": "continue",
            "continuing": "continue",
            "path": "path",
            "paths": "path",
            "directory": "path",
            "directories": "path",
            "file": "path",
            "files": "path",
        }
        stopwords = {
            "a",
            "an",
            "and",
            "before",
            "can",
            "first",
            "for",
            "into",
            "later",
            "next",
            "one",
            "or",
            "should",
            "step",
            "that",
            "the",
            "then",
            "this",
            "to",
            "while",
            "with",
        }

        normalized_source = f"{rationale} {expected_outcome}".lower()
        tokens = re.findall(r"[a-z0-9_]+", normalized_source)
        normalized_tokens: list[str] = []
        for token in tokens:
            canonical = alias_map.get(token, token)
            if canonical in stopwords:
                continue
            if len(canonical) <= 2:
                continue
            normalized_tokens.append(canonical)
        unique_tokens = sorted(set(normalized_tokens))
        payload = {
            "selected_action": selected_action.value,
            "normalized_tokens": unique_tokens,
        }
        return sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        ).hexdigest()

    def _record_planner_attempt(
        self,
        *,
        run_id: str,
        phase_key: str,
        policy_version: str,
        snapshot_hash: str,
        selected_action: PossibleActionName | None,
        submission_key: str | None,
        proposal_fingerprint: str | None,
        proposal_intent_signature: str | None = None,
        outcome: PlannerAttemptOutcome,
        outcome_reason: str,
        budget_used: int,
        budget_limit: int,
        consume_budget: bool,
    ) -> PlannerAttemptView:
        self.ensure_schema()
        effective_budget_used = budget_used + (1 if consume_budget else 0)
        with self.session() as session:
            existing_phase_records = list(
                session.scalars(
                    select(PlannerAttemptRecord)
                    .where(
                        PlannerAttemptRecord.run_id == run_id,
                        PlannerAttemptRecord.phase_key == phase_key,
                    )
                    .order_by(PlannerAttemptRecord.created_at.asc(), PlannerAttemptRecord.id.asc()),
                ).all(),
            )
            record = PlannerAttemptRecord(
                run_id=run_id,
                phase_key=phase_key,
                policy_version=policy_version,
                snapshot_hash=snapshot_hash,
                selected_action=selected_action.value if selected_action is not None else None,
                submission_key=submission_key,
                proposal_fingerprint=proposal_fingerprint,
                outcome=outcome,
                outcome_reason=outcome_reason,
                attempt_index=len(existing_phase_records) + 1,
                budget_limit=budget_limit,
                budget_used=effective_budget_used,
                budget_remaining=max(budget_limit - effective_budget_used, 0),
            )
            session.add(record)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run_id,
                    event_type=LedgerEventType.PLANNER_ATTEMPT_RECORDED,
                    payload={
                        "planner_attempt_id": record.id,
                        "phase_key": phase_key,
                        "policy_version": policy_version,
                        "snapshot_hash": snapshot_hash,
                        "selected_action": selected_action.value if selected_action is not None else None,
                        "submission_key": submission_key,
                        "proposal_fingerprint": proposal_fingerprint,
                        "proposal_intent_signature": proposal_intent_signature,
                        "outcome": outcome.value,
                        "outcome_reason": outcome_reason,
                        "attempt_index": record.attempt_index,
                        "budget_limit": budget_limit,
                        "budget_used": record.budget_used,
                        "budget_remaining": record.budget_remaining,
                    },
                ),
            )
            session.flush()
            return self._to_planner_attempt_view(record)

    def _record_phase_exhaustion(
        self,
        *,
        run_id: str,
        governance: PlannerGovernanceView,
        snapshot_hash: str,
        reason: str,
    ) -> PlannerAttemptView:
        if governance.exhausted:
            return governance.attempts[-1]
        attempt = self._record_planner_attempt(
            run_id=run_id,
            phase_key=governance.phase_key,
            policy_version=governance.policy_version,
            snapshot_hash=snapshot_hash,
            selected_action=None,
            submission_key=None,
            proposal_fingerprint=None,
            outcome=PlannerAttemptOutcome.PHASE_EXHAUSTED,
            outcome_reason=reason,
            budget_used=governance.budget_limit,
            budget_limit=governance.budget_limit,
            consume_budget=False,
        )
        self.record_observation(
            run_id=run_id,
            kind=ObservationKind.SYSTEM_AUDIT,
            summary="Planner phase budget was exhausted and further proposals are blocked.",
            details=(
                f"error_code={PlannerAttemptOutcome.PHASE_EXHAUSTED.value}; "
                f"phase_key={governance.phase_key}; "
                f"budget_limit={governance.budget_limit}; "
                f"reason={reason}."
            ),
        )
        return attempt

    @staticmethod
    def _to_planner_attempt_view(record: PlannerAttemptRecord) -> PlannerAttemptView:
        return PlannerAttemptView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "phase_key": record.phase_key,
                "policy_version": record.policy_version,
                "snapshot_hash": record.snapshot_hash,
                "selected_action": record.selected_action,
                "submission_key": record.submission_key,
                "proposal_fingerprint": record.proposal_fingerprint,
                "outcome": record.outcome,
                "outcome_reason": record.outcome_reason,
                "attempt_index": record.attempt_index,
                "budget_limit": record.budget_limit,
                "budget_used": record.budget_used,
                "budget_remaining": record.budget_remaining,
                "created_at": record.created_at,
            },
        )
