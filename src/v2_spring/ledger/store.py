from __future__ import annotations

import ast
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import textwrap
from typing import Iterator
from uuid import uuid4

from sqlalchemy import create_engine, func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from v2_spring.domain.approval import ApprovalStatus, ApprovalView
from v2_spring.domain.artifact import ArtifactStorageKind, ArtifactType, ArtifactView
from v2_spring.domain.decision import DecisionKind, DecisionView
from v2_spring.domain.execution_claim import (
    ExecutionClaimRefusalCode,
    ExecutionClaimRefusalView,
    ExecutionClaimRenewalPressure,
    ExecutionClaimStatus,
    ExecutionClaimView,
)
from v2_spring.domain.founder_intervention import (
    FounderInterventionDigest,
    FounderInterventionView,
    FounderOverrideInput,
    FounderReplyInput,
    FounderReplyKind,
)
from v2_spring.domain.observation import ObservationKind, ObservationView
from v2_spring.domain.patch_intake import (
    PatchIntakeStatus,
    PatchIntakeView,
    PatchResolutionCode,
    PatchResolutionView,
    PatchReviewView,
    PatchReviewWarningView,
    PatchRiskClass,
    PatchWarningCode,
)
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
from v2_spring.domain.progress import (
    ProgressActionOwner,
    ProgressAuditItemView,
    ProgressCommandHintView,
    ProgressSummaryView,
    ProgressSurfaceStatus,
    ProgressTraceMode,
)
from v2_spring.domain.proposal import PlannerProposalInput, PlannerProposalView
from v2_spring.domain.replay import ArtifactInspectionView, RunReplayView, TaskReplayView
from v2_spring.domain.routing import (
    ExecutionRequirements,
    ExecutionRuntime,
    RoutingDecision,
    RoutingInspectionView,
    RoutingOutcome,
    RoutingRefusalCode,
    RoutingRefusalReceipt,
    SystemLimits,
    default_requirements_for_bounded_execution,
    default_system_limits,
    derive_requirements_for_snapshot,
    route_task,
)
from v2_spring.domain.run import RunCreateInput, RunStatus, RunView
from v2_spring.domain.runtime_trust import RuntimeTrustMode, RuntimeTrustView
from v2_spring.domain.snapshot import (
    ArtifactHeadlineView,
    PendingPatchIntakeView,
    PendingFounderEscalationView,
    PossibleActionEvaluationView,
    PossibleActionView,
    PossibleActionName,
    RunSnapshotView,
    SnapshotActionState,
    SnapshotFreshnessConflictError,
    SnapshotFreshnessRefusalCode,
    SnapshotFreshnessRefusalView,
    SnapshotFreshnessView,
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
    ExecutionClaimRecord,
    FounderInterventionRecord,
    LedgerEventType,
    ObservationRecord,
    PatchIntakeRecord,
    PlannerAttemptRecord,
    RunRecord,
    RuntimeTrustRecord,
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
from v2_spring.runtime import (
    ContainerizedWorkerPreflightRefusal,
    ContainerizedWorkerReceipt,
    ContainerizedWorkerTimeout,
    IsolatedWorkerReceipt,
    IsolatedWorkerTimeout,
    PatchApplyOutcome,
    PatchApplyReceipt,
    apply_patch_strict,
    execute_containerized_worker_proof,
    execute_isolated_worker_proof,
    reclaim_containerized_worker_execution,
)


@dataclass(frozen=True)
class BoundedExecutionResult:
    """Return the first execution proof in a single typed bundle."""

    task: TaskView
    artifact: ArtifactView | None
    observation: ObservationView


@dataclass(frozen=True)
class IsolatedWorkerDispatchResult:
    """Return the isolated worker proof in a typed bundle."""

    task: TaskView
    artifacts: list[ArtifactView]
    observation: ObservationView
    receipt: IsolatedWorkerReceipt | ContainerizedWorkerReceipt


class ExecutionClaimConflictError(PermissionError):
    """Raised when a live execution claim blocks a new dispatch or mutation."""

    def __init__(self, refusal: ExecutionClaimRefusalView) -> None:
        super().__init__(refusal.message)
        self.refusal = refusal


class SchemaBootstrapRequiredError(RuntimeError):
    """Raised when a migration-controlled database has not been bootstrapped yet."""


@dataclass(frozen=True)
class SchemaStatus:
    """Compact schema-management status for doctor/bootstrap surfaces."""

    dialect_name: str
    management_mode: str
    ready: bool
    bootstrap_required: bool
    migration_controlled: bool
    current_revision: str | None
    missing_tables: tuple[str, ...]


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
    _PATCH_AUTO_APPLY_BURST_LIMIT = 2
    _PATCH_REPAIR_QUOTA_LIMIT = 3
    _PATCH_POLICY_WINDOW = timedelta(hours=1)
    _PATCH_AUTO_APPLY_MAX_CHANGED_LINES = 10
    _EXECUTION_LEASE_SLACK = timedelta(seconds=15)
    _EXECUTION_LEASE_RENEW_THRESHOLD = timedelta(seconds=10)
    _EXECUTION_LEASE_MIN_RENEW_CADENCE = timedelta(seconds=5)
    _RUNTIME_TRUST_MISMATCH_STRIKE_THRESHOLD = 3
    _RUNTIME_TRUST_RECOVERY_SUCCESS_THRESHOLD = 2

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._dialect_name = make_url(database_url).get_backend_name()
        self._schema_ready = False
        engine_kwargs: dict[str, object] = {"future": True}
        if self._dialect_name == "postgresql":
            engine_kwargs.update(
                {
                    "pool_pre_ping": True,
                    "pool_size": 5,
                    "max_overflow": 10,
                    "pool_recycle": 1800,
                },
            )
        self._engine = create_engine(database_url, **engine_kwargs)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

    @property
    def dialect_name(self) -> str:
        return self._dialect_name

    @property
    def supports_row_level_locking(self) -> bool:
        return self._dialect_name == "postgresql"

    @property
    def supports_jsonb(self) -> bool:
        return self._dialect_name == "postgresql"

    def inspect_schema_status(self) -> SchemaStatus:
        expected_tables = tuple(sorted(Base.metadata.tables.keys()))
        with self._engine.begin() as connection:
            inspector = inspect(connection)
            table_names = set(inspector.get_table_names())
            migration_controlled = "alembic_version" in table_names
            current_revision = None
            if migration_controlled:
                current_revision = connection.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1"),
                ).scalar_one_or_none()
            missing_tables = tuple(
                table_name for table_name in expected_tables if table_name not in table_names
            )

        if self._dialect_name == "postgresql":
            bootstrap_required = (not migration_controlled) or bool(missing_tables)
            management_mode = "alembic_migration"
            ready = not bootstrap_required
        else:
            bootstrap_required = False
            management_mode = "sqlite_self_bootstrap"
            ready = True

        return SchemaStatus(
            dialect_name=self._dialect_name,
            management_mode=management_mode,
            ready=ready,
            bootstrap_required=bootstrap_required,
            migration_controlled=migration_controlled,
            current_revision=current_revision,
            missing_tables=missing_tables,
        )

    def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        if self._dialect_name == "postgresql":
            status = self.inspect_schema_status()
            if status.bootstrap_required:
                missing_tables = ", ".join(status.missing_tables) if status.missing_tables else "-"
                raise SchemaBootstrapRequiredError(
                    "PostgreSQL schema is not bootstrapped yet. "
                    "Run Alembic migrations before using the control plane. "
                    f"current_revision={status.current_revision or '-'}; missing_tables={missing_tables}. "
                    "Suggested command: `. .venv/bin/activate && DATABASE_URL=... alembic upgrade head`.",
                )
            self._backfill_approval_expirations()
            self._schema_ready = True
            return

        Base.metadata.create_all(self._engine)
        self._ensure_schema_columns()
        self._backfill_approval_expirations()
        self._schema_ready = True

    def _ensure_schema_columns(self) -> None:
        with self._engine.begin() as connection:
            inspector = inspect(connection)
            if "approvals" not in inspector.get_table_names():
                return
            approval_columns = {column["name"] for column in inspector.get_columns("approvals")}
            if "expires_at" not in approval_columns:
                connection.execute(text("ALTER TABLE approvals ADD COLUMN expires_at DATETIME"))
            if "tasks" in inspector.get_table_names():
                task_columns = {column["name"] for column in inspector.get_columns("tasks")}
                if "execution_claim_token" not in task_columns:
                    connection.execute(text("ALTER TABLE tasks ADD COLUMN execution_claim_token VARCHAR(120)"))
                if "execution_claim_fencing_token" not in task_columns:
                    connection.execute(text("ALTER TABLE tasks ADD COLUMN execution_claim_fencing_token INTEGER"))

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

    @classmethod
    def _build_execution_claim_ttl(cls, timeout_seconds: int) -> timedelta:
        return timedelta(seconds=timeout_seconds) + cls._EXECUTION_LEASE_SLACK

    @staticmethod
    def _build_execution_claim_renew_threshold(timeout_seconds: int) -> timedelta:
        return min(
            timedelta(seconds=max(5, timeout_seconds // 3)),
            LedgerStore._EXECUTION_LEASE_RENEW_THRESHOLD,
        )

    @staticmethod
    def _build_execution_claim_renew_cadence(timeout_seconds: int) -> timedelta:
        return min(
            timedelta(seconds=max(2, timeout_seconds // 6)),
            LedgerStore._EXECUTION_LEASE_MIN_RENEW_CADENCE,
        )

    @staticmethod
    def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _to_execution_claim_view(
        cls,
        record: ExecutionClaimRecord,
        *,
        task_timeout_seconds: int | None = None,
    ) -> ExecutionClaimView:
        renew_threshold_seconds: int | None = None
        min_renew_cadence_seconds: int | None = None
        renewal_pressure: ExecutionClaimRenewalPressure | None = None
        if task_timeout_seconds is not None and task_timeout_seconds > 0:
            renew_threshold = cls._build_execution_claim_renew_threshold(task_timeout_seconds)
            renew_cadence = cls._build_execution_claim_renew_cadence(task_timeout_seconds)
            renew_threshold_seconds = int(renew_threshold.total_seconds())
            min_renew_cadence_seconds = int(renew_cadence.total_seconds())
            expires_at = cls._coerce_utc_datetime(record.expires_at)
            heartbeat_at = cls._coerce_utc_datetime(record.heartbeat_at)
            if expires_at is not None and heartbeat_at is not None:
                now = utc_now()
                remaining = expires_at - now
                if remaining > renew_threshold:
                    renewal_pressure = ExecutionClaimRenewalPressure.HEALTHY
                elif now - heartbeat_at < renew_cadence:
                    renewal_pressure = ExecutionClaimRenewalPressure.COALESCED
                else:
                    renewal_pressure = ExecutionClaimRenewalPressure.RENEW_WINDOW
        return ExecutionClaimView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "task_id": record.task_id,
                "runtime": record.runtime,
                "owner": record.owner,
                "lease_token": record.lease_token,
                "fencing_token": record.version,
                "status": record.status.value,
                "acquired_at": cls._coerce_utc_datetime(record.acquired_at),
                "heartbeat_at": cls._coerce_utc_datetime(record.heartbeat_at),
                "expires_at": cls._coerce_utc_datetime(record.expires_at),
                "released_at": cls._coerce_utc_datetime(record.released_at),
                "reclaim_reason": record.reclaim_reason,
                "renew_threshold_seconds": renew_threshold_seconds,
                "min_renew_cadence_seconds": min_renew_cadence_seconds,
                "renewal_pressure": renewal_pressure,
            },
        )

    @staticmethod
    def _build_execution_claim_select(
        run_id: str,
        *,
        for_update: bool = False,
        skip_locked: bool = False,
        dialect_name: str | None = None,
    ):
        statement = select(ExecutionClaimRecord).where(ExecutionClaimRecord.run_id == run_id).limit(1)
        if for_update and dialect_name == "postgresql":
            statement = statement.with_for_update(skip_locked=skip_locked)
        return statement

    @classmethod
    def _load_execution_claim(
        cls,
        session: Session,
        run_id: str,
        *,
        for_update: bool = False,
        skip_locked: bool = False,
        dialect_name: str | None = None,
    ) -> ExecutionClaimRecord | None:
        return session.scalar(
            cls._build_execution_claim_select(
                run_id,
                for_update=for_update,
                skip_locked=skip_locked,
                dialect_name=dialect_name,
            ),
        )

    def _load_run_for_claim_mutation(self, session: Session, run_id: str) -> RunRecord | None:
        if self.supports_row_level_locking:
            return session.scalar(
                select(RunRecord).where(RunRecord.id == run_id).with_for_update().limit(1),
            )
        return session.get(RunRecord, run_id)

    @classmethod
    def _to_runtime_trust_view(cls, record: RuntimeTrustRecord) -> RuntimeTrustView:
        return RuntimeTrustView.model_validate(
            {
                "runtime": record.runtime,
                "mode": record.mode,
                "dynamic_preflight_required": record.dynamic_preflight_required,
                "mismatch_strike_threshold": record.mismatch_strike_threshold,
                "recovery_success_threshold": record.recovery_success_threshold,
                "consecutive_mismatch_failures": record.consecutive_mismatch_failures,
                "total_mismatch_failures": record.total_mismatch_failures,
                "recovery_success_streak": record.recovery_success_streak,
                "last_failure_reason": record.last_failure_reason,
                "last_failure_at": cls._coerce_utc_datetime(record.last_failure_at),
                "last_success_at": cls._coerce_utc_datetime(record.last_success_at),
            },
        )

    @staticmethod
    def _load_runtime_trust(session: Session, runtime: ExecutionRuntime) -> RuntimeTrustRecord | None:
        return session.get(RuntimeTrustRecord, runtime)

    def _ensure_runtime_trust_record(self, session: Session, runtime: ExecutionRuntime) -> RuntimeTrustRecord:
        record = self._load_runtime_trust(session, runtime)
        if record is not None:
            return record
        record = RuntimeTrustRecord(
            runtime=runtime,
            mode=RuntimeTrustMode.STATIC_MANIFEST,
            dynamic_preflight_required=False,
            mismatch_strike_threshold=self._RUNTIME_TRUST_MISMATCH_STRIKE_THRESHOLD,
            recovery_success_threshold=self._RUNTIME_TRUST_RECOVERY_SUCCESS_THRESHOLD,
            consecutive_mismatch_failures=0,
            total_mismatch_failures=0,
            recovery_success_streak=0,
            last_failure_reason=None,
            last_failure_at=None,
            last_success_at=None,
        )
        session.add(record)
        session.flush()
        return record

    def _raise_execution_claim_conflict(self, record: ExecutionClaimRecord, *, mutation_name: str) -> None:
        claim = self._to_execution_claim_view(record)
        raise ExecutionClaimConflictError(
            ExecutionClaimRefusalView(
                code=ExecutionClaimRefusalCode.ACTIVE_CLAIM_HELD,
                message=(
                    f"Run {record.run_id} already has a live execution claim; {mutation_name} is blocked "
                    f"until the current owner releases or is reclaimed."
                ),
                existing_claim=claim,
            ),
        )

    @staticmethod
    def _task_claim_matches_record(task: TaskRecord, claim: ExecutionClaimRecord) -> bool:
        if task.execution_claim_token is None or task.execution_claim_fencing_token is None:
            return False
        return (
            claim.task_id == task.id
            and claim.lease_token == task.execution_claim_token
            and claim.version == task.execution_claim_fencing_token
        )

    def _build_execution_claim_view(
        self,
        session: Session,
        claim: ExecutionClaimRecord,
    ) -> ExecutionClaimView:
        task_timeout_seconds: int | None = None
        if claim.task_id is not None:
            task = session.get(TaskRecord, claim.task_id)
            if task is not None:
                task_timeout_seconds = task.timeout_seconds
        return self._to_execution_claim_view(claim, task_timeout_seconds=task_timeout_seconds)

    def _reclaim_execution_claim_locked(
        self,
        *,
        session: Session,
        run: RunRecord,
        claim: ExecutionClaimRecord,
        reason: str,
    ) -> ExecutionClaimRecord:
        now = utc_now()
        task = session.get(TaskRecord, claim.task_id) if claim.task_id is not None else None
        hard_reclaim_attempted = False
        hard_reclaim_succeeded = False
        if claim.runtime == ExecutionRuntime.CONTAINERIZED_WORKER.value and task is not None:
            hard_reclaim_attempted = True
            hard_reclaim_succeeded = reclaim_containerized_worker_execution(
                execution_context_id=task.execution_context_id,
            )

        claim.status = ExecutionClaimStatus.RECLAIMED
        claim.released_at = now
        claim.reclaim_reason = reason
        claim.version += 1
        claim.heartbeat_at = now

        if task is not None and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.FAILED
            task.completed_at = now
            task.stderr = reason
            if run.status == RunStatus.RUNNING:
                run.status = RunStatus.READY
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.TASK_FAILED,
                    payload={
                        "task_id": task.id,
                        "decision_id": task.decision_id,
                        "execution_context_id": task.execution_context_id,
                        "status": task.status.value,
                        "error": reason,
                        "timed_out": False,
                        "reclaimed": True,
                    },
                ),
            )

        session.add(
            EventLedgerRecord(
                run_id=run.id,
                event_type=LedgerEventType.EXECUTION_CLAIM_RECLAIMED,
                payload={
                    "claim_id": claim.id,
                    "task_id": claim.task_id,
                    "runtime": claim.runtime,
                    "owner": claim.owner,
                    "fencing_token": claim.version,
                    "reason": reason,
                    "hard_reclaim_attempted": hard_reclaim_attempted,
                    "hard_reclaim_succeeded": hard_reclaim_succeeded,
                },
            ),
        )
        observation = ObservationRecord(
            run_id=run.id,
            kind=ObservationKind.SYSTEM_AUDIT,
            summary="Execution claim was reclaimed after expiry or orphan detection.",
            details=(
                f"error_code=execution_claim_reclaimed; claim_id={claim.id}; task_id={claim.task_id}; "
                f"runtime={claim.runtime}; fencing_token={claim.version}; reason={reason}; "
                f"hard_reclaim_attempted={hard_reclaim_attempted}; "
                f"hard_reclaim_succeeded={hard_reclaim_succeeded}."
            ),
        )
        session.add(observation)
        session.flush()
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
        return claim

    def _ensure_no_live_execution_claim(
        self,
        *,
        session: Session,
        run: RunRecord,
        mutation_name: str,
    ) -> None:
        claim = self._load_execution_claim(
            session,
            run.id,
            for_update=True,
            dialect_name=self._dialect_name,
        )
        if claim is None or claim.status != ExecutionClaimStatus.ACTIVE:
            return
        now = utc_now()
        claim_expires_at = self._coerce_utc_datetime(claim.expires_at)
        if claim_expires_at is not None and claim_expires_at <= now:
            self._reclaim_execution_claim_locked(
                session=session,
                run=run,
                claim=claim,
                reason=(
                    f"Execution lease expired before {mutation_name}; the claim was reclaimed pessimistically."
                ),
            )
            return
        self._raise_execution_claim_conflict(claim, mutation_name=mutation_name)

    def _acquire_execution_claim(
        self,
        *,
        session: Session,
        run: RunRecord,
        task: TaskRecord,
        runtime: ExecutionRuntime,
        timeout_seconds: int,
        owner: str,
    ) -> ExecutionClaimRecord:
        locked_run = self._load_run_for_claim_mutation(session, run.id)
        if locked_run is None:  # pragma: no cover - defensive impossible edge
            raise LookupError(f"Run {run.id} was not found while acquiring an execution claim.")
        run = locked_run
        self._ensure_no_live_execution_claim(
            session=session,
            run=run,
            mutation_name="bounded execution dispatch",
        )
        now = utc_now()
        lease_token = str(uuid4())
        claim = self._load_execution_claim(
            session,
            run.id,
            for_update=True,
            dialect_name=self._dialect_name,
        )
        if claim is None:
            claim = ExecutionClaimRecord(
                run_id=run.id,
                task_id=task.id,
                runtime=runtime.value,
                owner=owner,
                lease_token=lease_token,
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=now,
                heartbeat_at=now,
                expires_at=now + self._build_execution_claim_ttl(timeout_seconds),
                released_at=None,
                reclaim_reason=None,
                version=1,
            )
            session.add(claim)
            try:
                session.flush()
            except IntegrityError as exc:  # pragma: no cover - defensive concurrent guard
                raise ExecutionClaimConflictError(
                    ExecutionClaimRefusalView(
                        code=ExecutionClaimRefusalCode.ACTIVE_CLAIM_HELD,
                        message=(
                            f"Run {run.id} hit a concurrent execution-claim insert and dispatch was refused "
                            "to preserve single-owner semantics."
                        ),
                        existing_claim=self._to_execution_claim_view(
                            self._load_execution_claim(
                                session,
                                run.id,
                                for_update=True,
                                dialect_name=self._dialect_name,
                            )
                            or claim,
                        ),
                    ),
                ) from exc
        else:
            prior_version = claim.version
            expires_at = now + self._build_execution_claim_ttl(timeout_seconds)
            update_result = session.execute(
                update(ExecutionClaimRecord)
                .where(
                    ExecutionClaimRecord.id == claim.id,
                    ExecutionClaimRecord.version == prior_version,
                )
                .values(
                    task_id=task.id,
                    runtime=runtime.value,
                    owner=owner,
                    lease_token=lease_token,
                    status=ExecutionClaimStatus.ACTIVE,
                    acquired_at=now,
                    heartbeat_at=now,
                    expires_at=expires_at,
                    released_at=None,
                    reclaim_reason=None,
                    version=prior_version + 1,
                ),
            )
            if update_result.rowcount != 1:
                session.expire_all()
                current_claim = self._load_execution_claim(session, run.id)
                if current_claim is None:  # pragma: no cover - defensive impossible edge
                    raise RuntimeError("Execution claim disappeared during atomic acquisition.")
                self._raise_execution_claim_conflict(
                    current_claim,
                    mutation_name="bounded execution dispatch",
                )
            session.expire(claim)
            session.flush()
            claim = session.get(ExecutionClaimRecord, claim.id)
            if claim is None:  # pragma: no cover - defensive impossible edge
                raise RuntimeError("Execution claim disappeared after atomic acquisition.")

        task.execution_claim_token = claim.lease_token
        task.execution_claim_fencing_token = claim.version

        session.add(
            EventLedgerRecord(
                run_id=run.id,
                event_type=LedgerEventType.EXECUTION_CLAIM_ACQUIRED,
                payload={
                    "claim_id": claim.id,
                    "task_id": task.id,
                    "runtime": runtime.value,
                    "owner": owner,
                    "lease_token": lease_token,
                    "fencing_token": claim.version,
                    "expires_at": claim.expires_at.isoformat(),
                },
            ),
        )
        observation = ObservationRecord(
            run_id=run.id,
            kind=ObservationKind.SYSTEM_AUDIT,
            summary="Execution claim was acquired for a bounded worker dispatch.",
            details=(
                f"error_code=execution_claim_acquired; claim_id={claim.id}; task_id={task.id}; "
                f"runtime={runtime.value}; owner={owner}; fencing_token={claim.version}; "
                f"expires_at={claim.expires_at.isoformat()}."
            ),
        )
        session.add(observation)
        session.flush()
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
        return claim

    def _release_execution_claim(
        self,
        *,
        session: Session,
        run_id: str,
        execution_context_id: str,
        reason: str,
    ) -> None:
        claim = self._load_execution_claim(
            session,
            run_id,
            for_update=True,
            dialect_name=self._dialect_name,
        )
        if claim is None:
            return
        if claim.status != ExecutionClaimStatus.ACTIVE:
            return
        task = session.get(TaskRecord, claim.task_id) if claim.task_id is not None else None
        if task is None or task.execution_context_id != execution_context_id:
            return
        now = utc_now()
        claim.status = ExecutionClaimStatus.RELEASED
        claim.released_at = now
        claim.heartbeat_at = now
        claim.reclaim_reason = reason
        claim.version += 1
        task.execution_claim_token = claim.lease_token
        task.execution_claim_fencing_token = claim.version
        session.add(
            EventLedgerRecord(
                run_id=run_id,
                event_type=LedgerEventType.EXECUTION_CLAIM_RELEASED,
                payload={
                    "claim_id": claim.id,
                    "task_id": claim.task_id,
                    "runtime": claim.runtime,
                    "owner": claim.owner,
                    "fencing_token": claim.version,
                    "reason": reason,
                },
            ),
        )
        observation = ObservationRecord(
            run_id=run_id,
            kind=ObservationKind.SYSTEM_AUDIT,
            summary="Execution claim was released after bounded execution finished.",
            details=(
                f"error_code=execution_claim_released; claim_id={claim.id}; task_id={claim.task_id}; "
                f"runtime={claim.runtime}; owner={claim.owner}; fencing_token={claim.version}; "
                f"reason={reason}."
            ),
        )
        session.add(observation)
        session.flush()
        session.add(
            EventLedgerRecord(
                run_id=run_id,
                event_type=LedgerEventType.OBSERVATION_RECORDED,
                payload={
                    "observation_id": observation.id,
                    "kind": observation.kind.value,
                    "summary": observation.summary,
                },
            ),
        )

    def get_execution_claim(self, run_id: str) -> ExecutionClaimView | None:
        self.ensure_schema()
        with self.session() as session:
            claim = self._load_execution_claim(session, run_id)
            if claim is None:
                return None
            return self._build_execution_claim_view(session, claim)

    def renew_execution_claim(
        self,
        *,
        run_id: str,
        execution_context_id: str,
        lease_token: str,
        fencing_token: int,
        timeout_seconds: int,
        owner: str,
    ) -> ExecutionClaimView | None:
        self.ensure_schema()
        with self.session() as session:
            locked_run = self._load_run_for_claim_mutation(session, run_id)
            if locked_run is None:
                return None
            claim = self._load_execution_claim(
                session,
                run_id,
                for_update=True,
                dialect_name=self._dialect_name,
            )
            if claim is None or claim.status != ExecutionClaimStatus.ACTIVE:
                return None
            task = session.get(TaskRecord, claim.task_id) if claim.task_id is not None else None
            if task is None or task.execution_context_id != execution_context_id:
                return None
            if task.execution_claim_token != lease_token or task.execution_claim_fencing_token != fencing_token:
                return None
            if claim.lease_token != lease_token or claim.version != fencing_token:
                return None

            now = utc_now()
            claim_expires_at = self._coerce_utc_datetime(claim.expires_at)
            if claim_expires_at is not None:
                remaining = claim_expires_at - now
                if remaining > self._build_execution_claim_renew_threshold(timeout_seconds):
                    cadence = self._build_execution_claim_renew_cadence(timeout_seconds)
                    last_heartbeat = self._coerce_utc_datetime(claim.heartbeat_at)
                    if last_heartbeat is not None and now - last_heartbeat < cadence:
                        return self._to_execution_claim_view(
                            claim,
                            task_timeout_seconds=timeout_seconds,
                        )
                    return self._to_execution_claim_view(claim, task_timeout_seconds=timeout_seconds)

            last_heartbeat = self._coerce_utc_datetime(claim.heartbeat_at)
            cadence = self._build_execution_claim_renew_cadence(timeout_seconds)
            if last_heartbeat is not None and now - last_heartbeat < cadence:
                return self._to_execution_claim_view(claim, task_timeout_seconds=timeout_seconds)

            expires_at = now + self._build_execution_claim_ttl(timeout_seconds)
            update_result = session.execute(
                update(ExecutionClaimRecord)
                .where(
                    ExecutionClaimRecord.id == claim.id,
                    ExecutionClaimRecord.status == ExecutionClaimStatus.ACTIVE,
                    ExecutionClaimRecord.version == fencing_token,
                    ExecutionClaimRecord.lease_token == lease_token,
                )
                .values(
                    heartbeat_at=now,
                    expires_at=expires_at,
                ),
            )
            if update_result.rowcount != 1:
                return None
            session.expire(claim)
            session.flush()
            claim = session.get(ExecutionClaimRecord, claim.id)
            if claim is None:  # pragma: no cover - defensive impossible edge
                return None
            session.add(
                EventLedgerRecord(
                    run_id=run_id,
                    event_type=LedgerEventType.EXECUTION_CLAIM_RENEWED,
                    payload={
                        "claim_id": claim.id,
                        "task_id": claim.task_id,
                        "runtime": claim.runtime,
                        "owner": owner,
                        "lease_token": lease_token,
                        "fencing_token": claim.version,
                        "expires_at": claim.expires_at.isoformat(),
                    },
                ),
            )
            observation = ObservationRecord(
                run_id=run_id,
                kind=ObservationKind.SYSTEM_AUDIT,
                summary="Execution claim lease was renewed by an active worker heartbeat.",
                details=(
                    f"error_code=execution_claim_renewed; claim_id={claim.id}; task_id={claim.task_id}; "
                    f"runtime={claim.runtime}; owner={owner}; fencing_token={claim.version}; "
                    f"expires_at={claim.expires_at.isoformat()}."
                ),
            )
            session.add(observation)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run_id,
                    event_type=LedgerEventType.OBSERVATION_RECORDED,
                    payload={
                        "observation_id": observation.id,
                        "kind": observation.kind.value,
                        "summary": observation.summary,
                    },
                ),
            )
            return self._to_execution_claim_view(claim, task_timeout_seconds=timeout_seconds)

    def reclaim_execution_claims(self, run_id: str | None = None) -> list[ExecutionClaimView]:
        self.ensure_schema()
        with self.session() as session:
            statement = select(ExecutionClaimRecord).where(ExecutionClaimRecord.status == ExecutionClaimStatus.ACTIVE)
            if run_id is not None:
                statement = statement.where(ExecutionClaimRecord.run_id == run_id)
            if self.supports_row_level_locking:
                statement = statement.with_for_update(skip_locked=True)
            claims = list(session.scalars(statement.order_by(ExecutionClaimRecord.acquired_at.asc())).all())
            reclaimed: list[ExecutionClaimView] = []
            for claim in claims:
                run = session.get(RunRecord, claim.run_id)
                if run is None:
                    continue
                claim_expires_at = self._coerce_utc_datetime(claim.expires_at)
                if claim_expires_at is not None and claim_expires_at > utc_now():
                    continue
                reclaimed_record = self._reclaim_execution_claim_locked(
                    session=session,
                    run=run,
                    claim=claim,
                    reason="Execution lease expired and was reclaimed by the Step 17 reconciliation path.",
                )
                reclaimed.append(self._build_execution_claim_view(session, reclaimed_record))
            session.flush()
            return reclaimed

    def get_runtime_trust(self, runtime: ExecutionRuntime) -> RuntimeTrustView:
        self.ensure_schema()
        with self.session() as session:
            record = self._ensure_runtime_trust_record(session, runtime)
            return self._to_runtime_trust_view(record)

    def list_runtime_trust(self) -> list[RuntimeTrustView]:
        self.ensure_schema()
        with self.session() as session:
            records = list(session.scalars(select(RuntimeTrustRecord).order_by(RuntimeTrustRecord.runtime)).all())
            if not records:
                self._ensure_runtime_trust_record(session, ExecutionRuntime.CONTAINERIZED_WORKER)
                records = list(session.scalars(select(RuntimeTrustRecord).order_by(RuntimeTrustRecord.runtime)).all())
            return [self._to_runtime_trust_view(record) for record in records]

    @staticmethod
    def _classify_container_runtime_mismatch(
        *,
        receipt: ContainerizedWorkerReceipt | None = None,
        preflight_refusal_code: str | None = None,
        failure_summary: str | None = None,
    ) -> str | None:
        if preflight_refusal_code == "dynamic_tool_check_failed":
            return "dynamic_tool_check_failed"
        text = "\n".join(
            part
            for part in (
                failure_summary,
                receipt.summary if receipt is not None else None,
                receipt.stderr_preview if receipt is not None else None,
            )
            if part
        ).lower()
        if any(
            token in text
            for token in (
                "command not found",
                "not found",
                "no such file or directory",
                "exec format error",
            )
        ):
            return "runtime_tool_missing_or_broken"
        return None

    def _record_runtime_trust_failure(
        self,
        *,
        run_id: str,
        runtime: ExecutionRuntime,
        reason_code: str,
        details: str,
    ) -> RuntimeTrustView:
        self.ensure_schema()
        with self.session() as session:
            record = self._ensure_runtime_trust_record(session, runtime)
            now = utc_now()
            record.consecutive_mismatch_failures += 1
            record.total_mismatch_failures += 1
            record.recovery_success_streak = 0
            record.last_failure_reason = reason_code
            record.last_failure_at = now
            if record.consecutive_mismatch_failures >= record.mismatch_strike_threshold:
                record.dynamic_preflight_required = True
                record.mode = RuntimeTrustMode.DYNAMIC_PROMOTED

            observation = ObservationRecord(
                run_id=run_id,
                kind=ObservationKind.SYSTEM_AUDIT,
                summary="Runtime trust strike recorded after a capability mismatch.",
                details=(
                    f"error_code=runtime_trust_strike_recorded; runtime={runtime.value}; reason_code={reason_code}; "
                    f"consecutive_failures={record.consecutive_mismatch_failures}; total_failures={record.total_mismatch_failures}; "
                    f"dynamic_preflight_required={record.dynamic_preflight_required}; "
                    f"details={self._sanitize_planner_text(details, limit=1800) or '-'}."
                ),
            )
            session.add(observation)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=run_id,
                    event_type=LedgerEventType.OBSERVATION_RECORDED,
                    payload={
                        "observation_id": observation.id,
                        "kind": observation.kind.value,
                        "summary": observation.summary,
                    },
                ),
            )
            return self._to_runtime_trust_view(record)

    def _record_runtime_trust_success(
        self,
        *,
        run_id: str,
        runtime: ExecutionRuntime,
        dynamic_preflight_performed: bool,
    ) -> RuntimeTrustView:
        self.ensure_schema()
        with self.session() as session:
            record = self._ensure_runtime_trust_record(session, runtime)
            now = utc_now()
            record.last_success_at = now
            record.consecutive_mismatch_failures = 0

            should_emit_recovery_observation = False
            if record.dynamic_preflight_required and dynamic_preflight_performed:
                record.recovery_success_streak += 1
                if record.recovery_success_streak >= record.recovery_success_threshold:
                    record.dynamic_preflight_required = False
                    record.mode = RuntimeTrustMode.STATIC_MANIFEST
                    record.recovery_success_streak = 0
                    should_emit_recovery_observation = True
            else:
                record.recovery_success_streak = 0

            if should_emit_recovery_observation:
                observation = ObservationRecord(
                    run_id=run_id,
                    kind=ObservationKind.SYSTEM_AUDIT,
                    summary="Runtime trust recovered back to static-first preflight.",
                    details=(
                        f"error_code=runtime_trust_recovered; runtime={runtime.value}; "
                        f"recovery_success_threshold={record.recovery_success_threshold}; "
                        "dynamic_preflight_required=false."
                    ),
                )
                session.add(observation)
                session.flush()
                session.add(
                    EventLedgerRecord(
                        run_id=run_id,
                        event_type=LedgerEventType.OBSERVATION_RECORDED,
                        payload={
                            "observation_id": observation.id,
                            "kind": observation.kind.value,
                            "summary": observation.summary,
                        },
                    ),
                )
            return self._to_runtime_trust_view(record)

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
            self._ensure_no_live_execution_claim(
                session=session,
                run=run,
                mutation_name="approval resolution",
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

    def list_patch_intakes_for_run(self, run_id: str) -> list[PatchIntakeView]:
        self.ensure_schema()
        with self.session() as session:
            records = list(
                session.scalars(
                    select(PatchIntakeRecord)
                    .where(PatchIntakeRecord.run_id == run_id)
                    .order_by(PatchIntakeRecord.created_at.asc(), PatchIntakeRecord.id.asc()),
                ).all(),
            )
            return [self._to_patch_intake_view(record) for record in records]

    def build_patch_review(self, run_id: str, *, include_raw: bool = False) -> PatchReviewView:
        self.ensure_schema()
        snapshot = self.build_run_snapshot(run_id)
        with self.session() as session:
            record = next(
                (
                    item
                    for item in reversed(
                        list(
                            session.scalars(
                                select(PatchIntakeRecord)
                                .where(PatchIntakeRecord.run_id == run_id)
                                .order_by(PatchIntakeRecord.created_at.asc(), PatchIntakeRecord.id.asc()),
                            ).all(),
                        )
                    )
                    if item.status == PatchIntakeStatus.PENDING
                ),
                None,
            )
            if record is None:
                raise LookupError(f"Run {run_id} has no pending patch intake to review.")

            patch_artifact = session.get(ArtifactRecord, record.patch_artifact_id)
            receipt_artifact = session.get(ArtifactRecord, record.receipt_artifact_id)
            if patch_artifact is None or receipt_artifact is None:
                raise LookupError(
                    f"Patch intake {record.id} is missing its patch or execution receipt artifact.",
                )

            patch_body = Path(patch_artifact.path).read_text(encoding="utf-8")
            raw_receipt = Path(receipt_artifact.path).read_text(encoding="utf-8")
            receipt_payload = json.loads(raw_receipt)
            added, removed = self._count_patch_lines(patch_body)

            return PatchReviewView(
                intake=self._to_patch_intake_view(record),
                snapshot_hash=snapshot.state_hash,
                freshness_generation=snapshot.freshness_generation,
                patch_body=patch_body,
                receipt_preview=(
                    f"runtime={receipt_payload.get('runtime', '-')}; "
                    f"changed_files={len(receipt_payload.get('changed_files', []))}; "
                    f"summary={receipt_payload.get('summary', '-')}"
                ),
                changed_lines_added=added,
                changed_lines_removed=removed,
                raw_receipt=raw_receipt if include_raw else None,
            )

    def approve_patch_intake(
        self,
        patch_intake_id: str,
        *,
        snapshot_hash: str | None = None,
        freshness_generation: int | None = None,
    ) -> PatchResolutionView:
        self.ensure_schema()
        with self.session() as session:
            patch_intake = session.get(PatchIntakeRecord, patch_intake_id)
            if patch_intake is None:
                raise LookupError(f"Patch intake {patch_intake_id} was not found.")
            run_id = patch_intake.run_id
        self._assert_snapshot_freshness(
            run_id=run_id,
            mutation_name="patch approval",
            snapshot_hash=snapshot_hash,
            freshness_generation=freshness_generation,
        )
        with self.session() as session:
            patch_intake = session.get(PatchIntakeRecord, patch_intake_id)
            if patch_intake is None:
                raise LookupError(f"Patch intake {patch_intake_id} was not found.")
            if patch_intake.status != PatchIntakeStatus.PENDING:
                raise ValueError(
                    f"Patch intake {patch_intake_id} is already {patch_intake.status.value} and cannot be approved again.",
                )

            run = session.get(RunRecord, patch_intake.run_id)
            task = session.get(TaskRecord, patch_intake.task_id)
            patch_artifact = session.get(ArtifactRecord, patch_intake.patch_artifact_id)
            receipt_artifact = session.get(ArtifactRecord, patch_intake.receipt_artifact_id)
            if run is None or task is None or patch_artifact is None or receipt_artifact is None:
                raise LookupError(
                    f"Patch intake {patch_intake_id} is missing one of its required run/task/artifact links.",
                )
            self._ensure_no_live_execution_claim(
                session=session,
                run=run,
                mutation_name="patch approval",
            )
            message, _, _ = self._apply_patch_intake_resolution(
                session=session,
                run=run,
                task=task,
                patch_intake=patch_intake,
                patch_artifact=patch_artifact,
                receipt_artifact=receipt_artifact,
                approval_mode="founder",
            )
            return PatchResolutionView(
                intake=self._to_patch_intake_view(patch_intake),
                message=message,
            )

    def reject_patch_intake(
        self,
        patch_intake_id: str,
        *,
        reason: str,
        snapshot_hash: str | None = None,
        freshness_generation: int | None = None,
    ) -> PatchResolutionView:
        self.ensure_schema()
        normalized_reason = self._normalize_optional_text(reason)
        if normalized_reason is None:
            raise ValueError("Patch rejection requires a non-blank founder reason.")
        with self.session() as session:
            patch_intake = session.get(PatchIntakeRecord, patch_intake_id)
            if patch_intake is None:
                raise LookupError(f"Patch intake {patch_intake_id} was not found.")
            run_id = patch_intake.run_id
        self._assert_snapshot_freshness(
            run_id=run_id,
            mutation_name="patch rejection",
            snapshot_hash=snapshot_hash,
            freshness_generation=freshness_generation,
        )
        with self.session() as session:
            patch_intake = session.get(PatchIntakeRecord, patch_intake_id)
            if patch_intake is None:
                raise LookupError(f"Patch intake {patch_intake_id} was not found.")
            if patch_intake.status != PatchIntakeStatus.PENDING:
                raise ValueError(
                    f"Patch intake {patch_intake_id} is already {patch_intake.status.value} and cannot be rejected again.",
                )
            run = session.get(RunRecord, patch_intake.run_id)
            if run is None:
                raise LookupError(f"Run {patch_intake.run_id} was not found.")
            self._ensure_no_live_execution_claim(
                session=session,
                run=run,
                mutation_name="patch rejection",
            )

            patch_intake.status = PatchIntakeStatus.REJECTED
            patch_intake.resolved_at = utc_now()
            patch_intake.resolution_code = PatchResolutionCode.FOUNDER_REJECTED
            patch_intake.resolution_reason = normalized_reason
            run.status = RunStatus.READY

            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.PATCH_INTAKE_REJECTED,
                    payload={
                        "patch_intake_id": patch_intake.id,
                        "task_id": patch_intake.task_id,
                        "patch_artifact_id": patch_intake.patch_artifact_id,
                        "resolution_code": patch_intake.resolution_code.value,
                    },
                ),
            )
            observation = ObservationRecord(
                run_id=run.id,
                kind=ObservationKind.SYSTEM_AUDIT,
                summary="Founder rejected the worker patch intake.",
                details=(
                    f"error_code={patch_intake.resolution_code.value}; "
                    f"patch_intake_id={patch_intake.id}; "
                    f"reason={patch_intake.resolution_reason}."
                ),
            )
            session.add(observation)
            session.flush()
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
            return PatchResolutionView(
                intake=self._to_patch_intake_view(patch_intake),
                message="Founder rejected the patch intake. The run is ready for a new planning cycle.",
            )

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
            patch_intake_records = list(
                session.scalars(
                    select(PatchIntakeRecord)
                    .where(PatchIntakeRecord.run_id == run_id)
                    .order_by(PatchIntakeRecord.created_at.asc(), PatchIntakeRecord.id.asc()),
                ).all(),
            )
            execution_claim = self._load_execution_claim(session, run_id)
            active_execution_claim = (
                self._build_execution_claim_view(session, execution_claim)
                if execution_claim is not None and execution_claim.status == ExecutionClaimStatus.ACTIVE
                else None
            )
            founder_intervention_records = list(
                session.scalars(
                    select(FounderInterventionRecord)
                    .where(FounderInterventionRecord.run_id == run_id)
                    .order_by(FounderInterventionRecord.created_at.asc(), FounderInterventionRecord.id.asc()),
                ).all(),
            )
            freshness_generation = int(
                session.scalar(
                    select(func.count())
                    .select_from(EventLedgerRecord)
                    .where(EventLedgerRecord.run_id == run_id),
                )
                or 0,
            )
            patch_intake_records = list(
                session.scalars(
                    select(PatchIntakeRecord)
                    .where(PatchIntakeRecord.run_id == run_id)
                    .order_by(PatchIntakeRecord.created_at.asc(), PatchIntakeRecord.id.asc()),
                ).all(),
            )
            patch_intake_records = list(
                session.scalars(
                    select(PatchIntakeRecord)
                    .where(PatchIntakeRecord.run_id == run_id)
                    .order_by(PatchIntakeRecord.created_at.asc(), PatchIntakeRecord.id.asc()),
                ).all(),
            )
            patch_intake_records = list(
                session.scalars(
                    select(PatchIntakeRecord)
                    .where(PatchIntakeRecord.run_id == run_id)
                    .order_by(PatchIntakeRecord.created_at.asc(), PatchIntakeRecord.id.asc()),
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
            patch_intakes = [self._to_patch_intake_view(record) for record in patch_intake_records]

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
                patch_intakes=patch_intakes,
                observations=observations,
                orphan_artifacts=orphan_artifacts,
                consistency_warnings=self._build_consistency_warnings(
                    run=self._to_run_view(run_record),
                    approvals=approvals,
                    tasks=task_replays,
                    patch_intakes=patch_intakes,
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
            patch_intake_records = list(
                session.scalars(
                    select(PatchIntakeRecord)
                    .where(PatchIntakeRecord.run_id == run_id)
                    .order_by(PatchIntakeRecord.created_at.asc(), PatchIntakeRecord.id.asc()),
                ).all(),
            )
            freshness_generation = int(
                session.scalar(
                    select(func.count())
                    .select_from(EventLedgerRecord)
                    .where(EventLedgerRecord.run_id == run_id),
                )
                or 0,
            )
            execution_claim = self._load_execution_claim(session, run_id)
            active_execution_claim = (
                self._build_execution_claim_view(session, execution_claim)
                if execution_claim is not None and execution_claim.status == ExecutionClaimStatus.ACTIVE
                else None
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
            patch_intakes = [self._to_patch_intake_view(record) for record in patch_intake_records]
            pending_patch_intake = next(
                (item for item in reversed(patch_intakes) if item.status == PatchIntakeStatus.PENDING),
                None,
            )
            latest_patch_intake = patch_intakes[-1] if patch_intakes else None
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
                latest_patch_intake=latest_patch_intake,
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
                "freshness_generation": freshness_generation,
                "run": self._to_run_view(run_record).model_dump(mode="json"),
                "pending_approval": pending_approval.model_dump(mode="json") if pending_approval else None,
                "pending_founder_escalation": (
                    pending_founder_escalation.model_dump(mode="json") if pending_founder_escalation else None
                ),
                "pending_patch_intake": (
                    pending_patch_intake.model_dump(mode="json") if pending_patch_intake else None
                ),
                "active_execution_claim": (
                    active_execution_claim.model_dump(mode="json") if active_execution_claim else None
                ),
                "latest_founder_intervention_summary": latest_founder_intervention_summary,
                "latest_rejection_reason": latest_rejection_reason,
                "latest_decision_summary": latest_decision_summary,
                "latest_patch_intake_status": latest_patch_intake.status.value if latest_patch_intake else None,
                "latest_patch_intake_summary": latest_patch_intake.summary if latest_patch_intake else None,
                "latest_patch_rejection_reason": (
                    latest_patch_intake.resolution_reason
                    if latest_patch_intake is not None and latest_patch_intake.status == PatchIntakeStatus.REJECTED
                    else None
                ),
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
                freshness_generation=freshness_generation,
                run=self._to_run_view(run_record),
                action_state=SnapshotActionState.STUCK,
                action_state_reason="Possible actions have not been evaluated yet.",
                pending_approval=pending_approval,
                pending_founder_escalation=pending_founder_escalation,
                pending_patch_intake=self._build_pending_patch_intake(pending_patch_intake),
                active_execution_claim=active_execution_claim,
                latest_founder_intervention_summary=latest_founder_intervention_summary,
                latest_rejection_reason=latest_rejection_reason,
                latest_decision_summary=latest_decision_summary,
                latest_patch_intake_status=latest_patch_intake.status if latest_patch_intake else None,
                latest_patch_intake_summary=latest_patch_intake.summary if latest_patch_intake else None,
                latest_patch_rejection_reason=(
                    latest_patch_intake.resolution_reason
                    if latest_patch_intake is not None and latest_patch_intake.status == PatchIntakeStatus.REJECTED
                    else None
                ),
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

    @staticmethod
    def _build_snapshot_freshness_view(snapshot: RunSnapshotView) -> SnapshotFreshnessView:
        return SnapshotFreshnessView(
            snapshot_hash=snapshot.state_hash,
            freshness_generation=snapshot.freshness_generation,
        )

    def _assert_snapshot_freshness(
        self,
        *,
        run_id: str,
        mutation_name: str,
        snapshot_hash: str | None = None,
        freshness_generation: int | None = None,
    ) -> None:
        if snapshot_hash is None and freshness_generation is None:
            return

        current_snapshot = self.build_run_snapshot(run_id)
        current = self._build_snapshot_freshness_view(current_snapshot)
        hash_mismatch = snapshot_hash is not None and snapshot_hash != current.snapshot_hash
        generation_mismatch = (
            freshness_generation is not None and freshness_generation != current.freshness_generation
        )
        if not hash_mismatch and not generation_mismatch:
            return

        expected = SnapshotFreshnessView(
            snapshot_hash=snapshot_hash or current.snapshot_hash,
            freshness_generation=(
                current.freshness_generation if freshness_generation is None else freshness_generation
            ),
        )
        raise SnapshotFreshnessConflictError(
            SnapshotFreshnessRefusalView(
                code=SnapshotFreshnessRefusalCode.STALE_SNAPSHOT,
                mutation_name=mutation_name,
                message=(
                    f"Run {run_id} changed since the snapshot you inspected; {mutation_name} is blocked until "
                    "you refresh the current founder/operator surface."
                ),
                expected=expected,
                current=current,
            ),
        )

    def build_run_progress(
        self,
        run_id: str,
        *,
        trace_mode: ProgressTraceMode = ProgressTraceMode.SUMMARY,
    ) -> ProgressSummaryView:
        """Build the founder/operator cockpit view directly from current read models."""

        evaluation = evaluate_possible_actions(self.build_run_snapshot(run_id))
        snapshot = evaluation.snapshot
        replay = self.build_run_replay(run_id)

        recent_artifacts = self._build_recent_artifact_headlines(replay)
        recent_audits = self._build_progress_audit_items(
            replay.observations,
            include_raw=False,
            limit=3,
        )
        trace_entries: list[ProgressAuditItemView] = []
        if trace_mode != ProgressTraceMode.SUMMARY:
            trace_entries = self._build_progress_audit_items(
                replay.observations,
                include_raw=trace_mode == ProgressTraceMode.RAW,
                limit=8,
            )

        surface_status, action_required_by, headline, blocker_reason, next_step_hint = self._build_progress_surface(
            snapshot=snapshot,
            evaluation=evaluation,
            replay=replay,
        )

        return ProgressSummaryView(
            generated_at=utc_now(),
            trace_mode=trace_mode,
            run=snapshot.run,
            snapshot_hash=snapshot.state_hash,
            snapshot_generation=snapshot.freshness_generation,
            action_state=snapshot.action_state,
            surface_status=surface_status,
            action_required_by=action_required_by,
            headline=self._sanitize_planner_text(headline, limit=400) or "Progress summary unavailable.",
            blocker_reason=self._sanitize_planner_text(blocker_reason, limit=500),
            next_step_hint=self._sanitize_planner_text(next_step_hint, limit=500),
            pending_approval=snapshot.pending_approval,
            pending_founder_escalation=snapshot.pending_founder_escalation,
            pending_patch_intake=snapshot.pending_patch_intake,
            active_execution_claim=snapshot.active_execution_claim,
            planner_budget_remaining=snapshot.planner_budget_remaining,
            planner_phase_exhausted=snapshot.planner_phase_exhausted,
            planner_stale_quota_remaining=snapshot.planner_stale_quota_remaining,
            latest_planner_summary=self._sanitize_planner_text(
                snapshot.latest_planner_attempt_summary,
                limit=400,
            ),
            latest_execution_summary=self._build_progress_execution_summary(snapshot),
            latest_artifact=snapshot.latest_artifact,
            recent_artifacts=recent_artifacts,
            recent_founder_interventions=snapshot.recent_founder_interventions,
            recent_audits=recent_audits,
            suggested_commands=self._build_progress_command_hints(
                run_id=run_id,
                snapshot=snapshot,
                evaluation=evaluation,
                surface_status=surface_status,
            ),
            consistency_warnings=replay.consistency_warnings,
            trace_entries=trace_entries,
        )

    def inspect_task_route(
        self,
        run_id: str,
        *,
        requirements: ExecutionRequirements | None = None,
        system_limits: SystemLimits | None = None,
        record: bool = False,
    ) -> RoutingInspectionView:
        """Project one deterministic execution routing decision for founder/operator inspection."""

        evaluation = evaluate_possible_actions(self.build_run_snapshot(run_id))
        snapshot = evaluation.snapshot
        source_action = next(
            (action for action in evaluation.actions if action.name == PossibleActionName.EXECUTE_BOUNDED_TASK),
            None,
        )
        effective_requirements = requirements or derive_requirements_for_snapshot(snapshot)
        effective_limits = system_limits or default_system_limits()

        if source_action is None:
            outcome: RoutingOutcome = RoutingRefusalReceipt(
                refusal_code=RoutingRefusalCode.NO_ROUTABLE_WORK,
                message="No execution-plane task is currently legal for this run.",
                next_step_hint=(
                    "Resolve the current approval/founder blocker or advance the planner state before routing execution."
                ),
                guard_notes=[
                    f"action_state={snapshot.action_state.value}",
                    f"action_state_reason={snapshot.action_state_reason}",
                ],
            )
            effective_requirements = None
        elif effective_requirements is None:
            outcome = RoutingRefusalReceipt(
                refusal_code=RoutingRefusalCode.NO_ROUTABLE_WORK,
                message="The run has an execution lane open, but no deterministic execution requirements could be derived.",
                next_step_hint=(
                    "Inspect the current legal action set and provide explicit execution requirements before dispatch."
                ),
                guard_notes=[
                    f"action_state={snapshot.action_state.value}",
                    f"action_state_reason={snapshot.action_state_reason}",
                ],
            )
        else:
            outcome = route_task(
                requirements=effective_requirements,
                system_limits=effective_limits,
            )

        recorded_observation_id = None
        if record:
            observation = self.record_observation(
                run_id=run_id,
                kind=ObservationKind.SYSTEM_AUDIT,
                summary=self._build_route_summary(source_action, outcome),
                details=self._build_route_audit_details(
                    snapshot=snapshot,
                    source_action=source_action,
                    requirements=effective_requirements,
                    system_limits=effective_limits,
                    outcome=outcome,
                ),
            )
            recorded_observation_id = observation.id

        return RoutingInspectionView(
            run_id=snapshot.run.id,
            snapshot_hash=snapshot.state_hash,
            source_action=source_action.name if source_action is not None else None,
            source_action_reason=source_action.reason if source_action is not None else None,
            requirements=effective_requirements,
            system_limits=effective_limits,
            outcome=outcome,
            recorded_observation_id=recorded_observation_id,
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
            execution_requirements=proposal.execution_requirements,
        )
        proposal_intent_signature = self._build_planner_proposal_intent_signature(
            selected_action=proposal.selected_action,
            rationale=proposal.rationale,
            expected_outcome=proposal.expected_outcome,
            execution_requirements=proposal.execution_requirements,
        )

        if governance.exhausted:
            raise PlannerPhaseExhaustedError(
                "Planner phase budget is exhausted for the current state segment. "
                "Use `v2-spring planner recharge <run-id> --reason ...` before proposing again.",
            )
        if snapshot.pending_patch_intake is not None:
            raise PermissionError(
                "Founder patch review is still required before new planner proposals are allowed. "
                f"Pending patch intake={snapshot.pending_patch_intake.intake_id}.",
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
                "execution_requirements": (
                    proposal.execution_requirements.model_dump(mode="json")
                    if proposal.execution_requirements is not None
                    else None
                ),
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
            execution_requirements=proposal.execution_requirements,
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
            patch_intake_records = list(
                session.scalars(
                    select(PatchIntakeRecord)
                    .where(PatchIntakeRecord.run_id == run_id)
                    .order_by(PatchIntakeRecord.created_at.asc(), PatchIntakeRecord.id.asc()),
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
            latest_patch_intake = (
                self._to_patch_intake_view(patch_intake_records[-1])
                if patch_intake_records
                else None
            )
            task_summary = self._build_task_status_summary(task_records)
            phase_key = self._build_planner_phase_key(
                run=self._to_run_view(run_record),
                pending_approval=pending_approval,
                latest_rejection_reason=latest_rejection_reason,
                latest_patch_intake=latest_patch_intake,
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
                        "execution_requirements": event.payload.get("execution_requirements"),
                        "created_at": event.recorded_at,
                    },
                ),
            )
        return proposals

    def build_failure_report(self, run_id: str) -> FailureReportView | None:
        """Return the latest sanitized execution failure summary for planner context."""
        self.ensure_schema()
        with self.session() as session:
            failed_task_records = list(
                session.scalars(
                    select(TaskRecord)
                    .where(TaskRecord.run_id == run_id)
                    .where(TaskRecord.status == TaskStatus.FAILED)
                    .order_by(TaskRecord.completed_at.asc(), TaskRecord.id.asc()),
                ).all(),
            )
            rejected_patch_records = list(
                session.scalars(
                    select(PatchIntakeRecord)
                    .where(PatchIntakeRecord.run_id == run_id)
                    .where(PatchIntakeRecord.status == PatchIntakeStatus.REJECTED)
                    .order_by(PatchIntakeRecord.resolved_at.asc(), PatchIntakeRecord.id.asc()),
                ).all(),
            )

            latest_failed_task = failed_task_records[-1] if failed_task_records else None
            latest_rejected_patch = rejected_patch_records[-1] if rejected_patch_records else None

            if latest_failed_task is None and latest_rejected_patch is None:
                return None

            if latest_rejected_patch is not None and (
                latest_failed_task is None
                or (latest_rejected_patch.resolved_at or latest_rejected_patch.created_at)
                >= (latest_failed_task.completed_at or latest_failed_task.created_at)
            ):
                return self._build_patch_failure_report(
                    session=session,
                    run_id=run_id,
                    rejected_patch=latest_rejected_patch,
                    rejected_patch_records=rejected_patch_records,
                )

            assert latest_failed_task is not None
            return self._build_task_failure_report(
                run_id=run_id,
                latest_failed_task=latest_failed_task,
                failed_task_records=failed_task_records,
            )

    def _build_task_failure_report(
        self,
        *,
        run_id: str,
        latest_failed_task: TaskRecord,
        failed_task_records: list[TaskRecord],
    ) -> FailureReportView:
        failure_text = latest_failed_task.stderr or latest_failed_task.failure_hint or latest_failed_task.summary
        failure_class, error_code = self._classify_failure(failure_text)
        deterministic = failure_class == FailureClass.DETERMINISTIC_RUNTIME
        normalized_signature = self._build_failure_signature(
            error_code=error_code,
            task_kind=latest_failed_task.kind.value,
            failure_text=failure_text,
        )
        streak = 0
        for task_record in reversed(failed_task_records):
            comparison_text = task_record.stderr or task_record.failure_hint or task_record.summary
            _, comparison_error_code = self._classify_failure(comparison_text)
            comparison_signature = self._build_failure_signature(
                error_code=comparison_error_code,
                task_kind=task_record.kind.value,
                failure_text=comparison_text,
            )
            if comparison_signature != normalized_signature:
                break
            streak += 1

        proposals = self.list_planner_proposals_for_run(run_id)
        failure_anchor = latest_failed_task.started_at or latest_failed_task.created_at
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
                latest_failed_task.stderr or latest_failed_task.summary,
                limit=500,
            )
            or "Task failed without a normalized failure hint.",
            repeated_failure_streak=max(streak, 1),
            deterministic=deterministic,
        )

    def _build_patch_failure_report(
        self,
        *,
        session: Session,
        run_id: str,
        rejected_patch: PatchIntakeRecord,
        rejected_patch_records: list[PatchIntakeRecord],
    ) -> FailureReportView:
        failure_text = rejected_patch.resolution_reason or rejected_patch.summary
        error_code = (
            rejected_patch.resolution_code.value
            if rejected_patch.resolution_code is not None
            else "patch_rejected"
        )
        normalized_signature = self._build_failure_signature(
            error_code=error_code,
            task_kind="patch_intake",
            failure_text=failure_text,
        )
        streak = 0
        for record in reversed(rejected_patch_records):
            comparison_signature = self._build_failure_signature(
                error_code=record.resolution_code.value if record.resolution_code is not None else "patch_rejected",
                task_kind="patch_intake",
                failure_text=record.resolution_reason or record.summary,
            )
            if comparison_signature != normalized_signature:
                break
            streak += 1

        proposals = self.list_planner_proposals_for_run(run_id)
        failure_anchor = rejected_patch.resolved_at or rejected_patch.created_at
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

        short_traceback = None
        observed_outcome = self._sanitize_planner_text(rejected_patch.resolution_reason or rejected_patch.summary, limit=500)
        if rejected_patch.validation_artifact_id is not None:
            validation_artifact = session.get(ArtifactRecord, rejected_patch.validation_artifact_id)
            if validation_artifact is not None and Path(validation_artifact.path).exists():
                payload = json.loads(Path(validation_artifact.path).read_text(encoding="utf-8"))
                short_traceback = self._sanitize_planner_text(
                    payload.get("validation_stderr_preview")
                    or payload.get("apply_check_stderr")
                    or payload.get("validation_stdout_preview")
                    or rejected_patch.resolution_reason
                    or rejected_patch.summary,
                    limit=500,
                )
                observed_outcome = self._sanitize_planner_text(
                    payload.get("summary") or rejected_patch.resolution_reason or rejected_patch.summary,
                    limit=500,
                )

        return FailureReportView(
            failure_class=FailureClass.DETERMINISTIC_RUNTIME,
            error_code=error_code,
            short_traceback=short_traceback,
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
            observed_outcome=observed_outcome or "Patch intake was rejected without a detailed validation receipt.",
            repeated_failure_streak=max(streak, 1),
            deterministic=True,
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
            run = session.get(RunRecord, run_id)
            if run is None:
                raise LookupError(f"Run {run_id} was not found.")
            self._ensure_no_live_execution_claim(
                session=session,
                run=run,
                mutation_name="founder reply",
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
            self._acquire_execution_claim(
                session=session,
                run=run,
                task=task,
                runtime=ExecutionRuntime.ISOLATED_WORKER,
                timeout_seconds=timeout_seconds,
                owner="isolated_worker_dispatch",
            )
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

    def dispatch_isolated_worker_task(
        self,
        *,
        run_id: str,
        workspace: Path,
        artifact_root: Path,
        timeout_seconds: int = 30,
        snapshot_hash: str | None = None,
        freshness_generation: int | None = None,
    ) -> IsolatedWorkerDispatchResult:
        """Dispatch one bounded isolated-worker proof and persist its trail."""

        self.ensure_schema()
        self._assert_snapshot_freshness(
            run_id=run_id,
            mutation_name="task dispatch",
            snapshot_hash=snapshot_hash,
            freshness_generation=freshness_generation,
        )
        workspace = workspace.expanduser().resolve()
        artifact_root = artifact_root.expanduser().resolve()
        requirements = ExecutionRequirements(
            task_complexity="low",
            needs_isolation=True,
            requires_network=False,
            needs_multi_file_context=False,
            write_scope="single_file",
            expected_output_kind="unified_patch",
        )

        inspection = self.inspect_task_route(run_id, requirements=requirements, record=True)
        if not isinstance(inspection.outcome, RoutingDecision):
            raise PermissionError(
                f"Run {run_id} cannot be dispatched to the isolated worker: {inspection.outcome.message}",
            )
        if inspection.outcome.runtime != ExecutionRuntime.ISOLATED_WORKER:
            raise PermissionError(
                f"Run {run_id} currently routes to {inspection.outcome.runtime.value}, not isolated_worker.",
            )

        with self.session() as session:
            run = self._get_run_for_execution(session, run_id)

            decision = DecisionRecord(
                run_id=run.id,
                kind=DecisionKind.ISOLATED_WORKER_SELECTED,
                summary="An isolated worker proof was selected for dispatch.",
                rationale=(
                    "Step 12-b intentionally proves one soft-isolated worker lane before broader execution-plane "
                    "fan-out is introduced."
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
                        "runtime": inspection.outcome.runtime.value,
                        "routing_policy": inspection.outcome.matched_policy,
                    },
                ),
            )

            execution_context_id = str(uuid4())
            sandbox_cwd = str(artifact_root / run_id / execution_context_id / "sandbox")
            task = TaskRecord(
                run_id=run.id,
                decision_id=decision.id,
                kind=TaskKind.ISOLATED_WORKER_PROOF,
                status=TaskStatus.READY,
                summary="Run one bounded patch-producing proof inside an isolated worker sandbox.",
                execution_context_id=execution_context_id,
                command=f"isolated_worker_proof --workspace {workspace}",
                cwd=sandbox_cwd,
                timeout_seconds=timeout_seconds,
            )
            session.add(task)
            session.flush()
            self._acquire_execution_claim(
                session=session,
                run=run,
                task=task,
                runtime=ExecutionRuntime.ISOLATED_WORKER,
                timeout_seconds=timeout_seconds,
                owner="isolated_worker_dispatch",
            )
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
                        "runtime": inspection.outcome.runtime.value,
                        "requirements": requirements.model_dump(mode="json"),
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
                        "runtime": inspection.outcome.runtime.value,
                        "snapshot_hash": inspection.snapshot_hash,
                        "base_context": {
                            "source_action": inspection.source_action.value if inspection.source_action else None,
                            "requirements": requirements.model_dump(mode="json"),
                        },
                    },
                ),
            )
            session.flush()
            task_id = task.id

        try:
            receipt = execute_isolated_worker_proof(
                workspace=workspace,
                timeout_seconds=timeout_seconds,
                execution_context_id=execution_context_id,
            )
        except (IsolatedWorkerTimeout, FileNotFoundError, NotADirectoryError) as exc:
            synthetic_receipt = self._build_failed_isolated_receipt(
                workspace=workspace,
                execution_context_id=execution_context_id,
                timeout_seconds=timeout_seconds,
                summary=str(exc),
            )
            return self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=synthetic_receipt,
                failure_summary=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            synthetic_receipt = self._build_failed_isolated_receipt(
                workspace=workspace,
                execution_context_id=execution_context_id,
                timeout_seconds=timeout_seconds,
                summary=f"Unexpected isolated worker failure: {exc}",
            )
            return self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=synthetic_receipt,
                failure_summary=f"Unexpected isolated worker failure: {exc}",
            )

        if receipt.timed_out or receipt.returncode not in (0, None):
            failure_summary = receipt.summary
            return self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
                failure_summary=failure_summary,
            )
        if not receipt.patch_body:
            return self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
                failure_summary="Isolated worker proof completed without producing a bounded patch.",
            )
        try:
            return self._finalize_completed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
            )
        except Exception as exc:
            return self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
                failure_summary=f"Patch/receipt persistence failed after isolated execution: {exc}",
            )

    def dispatch_containerized_worker_task(
        self,
        *,
        run_id: str,
        workspace: Path,
        artifact_root: Path,
        timeout_seconds: int = 30,
        snapshot_hash: str | None = None,
        freshness_generation: int | None = None,
    ) -> IsolatedWorkerDispatchResult:
        """Dispatch one bounded containerized-worker proof and persist its trail."""

        self.ensure_schema()
        self._assert_snapshot_freshness(
            run_id=run_id,
            mutation_name="task dispatch",
            snapshot_hash=snapshot_hash,
            freshness_generation=freshness_generation,
        )
        workspace = workspace.expanduser().resolve()
        artifact_root = artifact_root.expanduser().resolve()
        requirements = ExecutionRequirements(
            task_complexity="low",
            needs_isolation=True,
            requires_network=False,
            needs_multi_file_context=False,
            write_scope="single_file",
            expected_output_kind="unified_patch",
        )
        system_limits = SystemLimits(available_runtimes=(ExecutionRuntime.CONTAINERIZED_WORKER,))

        inspection = self.inspect_task_route(
            run_id,
            requirements=requirements,
            system_limits=system_limits,
            record=True,
        )
        if not isinstance(inspection.outcome, RoutingDecision):
            raise PermissionError(
                f"Run {run_id} cannot be dispatched to the containerized worker: {inspection.outcome.message}",
            )
        if inspection.outcome.runtime != ExecutionRuntime.CONTAINERIZED_WORKER:
            raise PermissionError(
                f"Run {run_id} currently routes to {inspection.outcome.runtime.value}, not containerized_worker.",
            )
        runtime_trust = self.get_runtime_trust(ExecutionRuntime.CONTAINERIZED_WORKER)

        with self.session() as session:
            run = self._get_run_for_execution(session, run_id)

            decision = DecisionRecord(
                run_id=run.id,
                kind=DecisionKind.CONTAINERIZED_WORKER_SELECTED,
                summary="A containerized worker proof was selected for dispatch.",
                rationale=(
                    "Step 13 intentionally proves the patch/receipt contract behind a containerized runtime boundary."
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
                        "runtime": inspection.outcome.runtime.value,
                        "routing_policy": inspection.outcome.matched_policy,
                    },
                ),
            )

            execution_context_id = str(uuid4())
            task = TaskRecord(
                run_id=run.id,
                decision_id=decision.id,
                kind=TaskKind.CONTAINERIZED_WORKER_PROOF,
                status=TaskStatus.READY,
                summary="Run one bounded patch-producing proof inside a containerized worker runtime.",
                execution_context_id=execution_context_id,
                command=f"containerized_worker_proof --workspace {workspace}",
                cwd="/workspace",
                timeout_seconds=timeout_seconds,
            )
            session.add(task)
            session.flush()
            self._acquire_execution_claim(
                session=session,
                run=run,
                task=task,
                runtime=ExecutionRuntime.CONTAINERIZED_WORKER,
                timeout_seconds=timeout_seconds,
                owner="containerized_worker_dispatch",
            )
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
                        "runtime": inspection.outcome.runtime.value,
                        "requirements": requirements.model_dump(mode="json"),
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
                        "runtime": inspection.outcome.runtime.value,
                        "snapshot_hash": inspection.snapshot_hash,
                        "base_context": {
                            "source_action": inspection.source_action.value if inspection.source_action else None,
                            "requirements": requirements.model_dump(mode="json"),
                        },
                    },
                ),
            )
            session.flush()
            task_id = task.id

        try:
            receipt = execute_containerized_worker_proof(
                workspace=workspace,
                timeout_seconds=timeout_seconds,
                execution_context_id=execution_context_id,
                run_id=run_id,
                requirements=requirements,
                force_dynamic_preflight=runtime_trust.dynamic_preflight_required,
            )
        except ContainerizedWorkerPreflightRefusal as exc:
            summary = f"Containerized worker preflight refusal: {exc}"
            synthetic_receipt = self._build_failed_containerized_receipt(
                workspace=workspace,
                execution_context_id=execution_context_id,
                timeout_seconds=timeout_seconds,
                summary=summary,
                preflight_refusal_code=exc.refusal_code,
            )
            result = self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=synthetic_receipt,
                failure_summary=summary,
            )
            reason_code = self._classify_container_runtime_mismatch(
                preflight_refusal_code=exc.refusal_code,
                failure_summary=summary,
            )
            if reason_code is not None:
                self._record_runtime_trust_failure(
                    run_id=run_id,
                    runtime=ExecutionRuntime.CONTAINERIZED_WORKER,
                    reason_code=reason_code,
                    details=summary,
                )
            return result
        except (ContainerizedWorkerTimeout, FileNotFoundError, NotADirectoryError) as exc:
            synthetic_receipt = self._build_failed_containerized_receipt(
                workspace=workspace,
                execution_context_id=execution_context_id,
                timeout_seconds=timeout_seconds,
                summary=str(exc),
            )
            result = self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=synthetic_receipt,
                failure_summary=str(exc),
            )
            reason_code = self._classify_container_runtime_mismatch(
                receipt=synthetic_receipt,
                failure_summary=str(exc),
            )
            if reason_code is not None:
                self._record_runtime_trust_failure(
                    run_id=run_id,
                    runtime=ExecutionRuntime.CONTAINERIZED_WORKER,
                    reason_code=reason_code,
                    details=str(exc),
                )
            return result
        except Exception as exc:  # pragma: no cover - defensive guard
            failure_summary = f"Unexpected containerized worker failure: {exc}"
            synthetic_receipt = self._build_failed_containerized_receipt(
                workspace=workspace,
                execution_context_id=execution_context_id,
                timeout_seconds=timeout_seconds,
                summary=failure_summary,
            )
            result = self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=synthetic_receipt,
                failure_summary=failure_summary,
            )
            reason_code = self._classify_container_runtime_mismatch(
                receipt=synthetic_receipt,
                failure_summary=failure_summary,
            )
            if reason_code is not None:
                self._record_runtime_trust_failure(
                    run_id=run_id,
                    runtime=ExecutionRuntime.CONTAINERIZED_WORKER,
                    reason_code=reason_code,
                    details=failure_summary,
                )
            return result

        if receipt.timed_out or receipt.returncode not in (0, None):
            result = self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
                failure_summary=receipt.summary,
            )
            reason_code = self._classify_container_runtime_mismatch(
                receipt=receipt,
                failure_summary=receipt.summary,
            )
            if reason_code is not None:
                self._record_runtime_trust_failure(
                    run_id=run_id,
                    runtime=ExecutionRuntime.CONTAINERIZED_WORKER,
                    reason_code=reason_code,
                    details=receipt.summary,
                )
            return result
        if not receipt.patch_body:
            result = self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
                failure_summary="Containerized worker proof completed without producing a bounded patch.",
            )
            reason_code = self._classify_container_runtime_mismatch(
                receipt=receipt,
                failure_summary=receipt.summary,
            )
            if reason_code is not None:
                self._record_runtime_trust_failure(
                    run_id=run_id,
                    runtime=ExecutionRuntime.CONTAINERIZED_WORKER,
                    reason_code=reason_code,
                    details=receipt.summary,
                )
            return result
        try:
            result = self._finalize_completed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
            )
            self._record_runtime_trust_success(
                run_id=run_id,
                runtime=ExecutionRuntime.CONTAINERIZED_WORKER,
                dynamic_preflight_performed=receipt.dynamic_check_performed,
            )
            return result
        except Exception as exc:
            failure_summary = f"Patch/receipt persistence failed after containerized execution: {exc}"
            result = self._finalize_failed_isolated_task(
                run_id=run_id,
                task_id=task_id,
                artifact_root=artifact_root,
                receipt=receipt,
                failure_summary=failure_summary,
            )
            reason_code = self._classify_container_runtime_mismatch(
                receipt=receipt,
                failure_summary=failure_summary,
            )
            if reason_code is not None:
                self._record_runtime_trust_failure(
                    run_id=run_id,
                    runtime=ExecutionRuntime.CONTAINERIZED_WORKER,
                    reason_code=reason_code,
                    details=failure_summary,
                )
            return result

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

    @staticmethod
    def _extract_error_code(details: str) -> str | None:
        for segment in details.split(";"):
            cleaned = segment.strip()
            if cleaned.startswith("error_code="):
                value = cleaned.split("=", 1)[1].strip()
                return value or None
        return None

    @classmethod
    def _build_progress_audit_items(
        cls,
        observations: list[ObservationView],
        *,
        include_raw: bool,
        limit: int,
    ) -> list[ProgressAuditItemView]:
        audit_observations = [
            observation
            for observation in observations
            if observation.kind == ObservationKind.SYSTEM_AUDIT
        ]
        items: list[ProgressAuditItemView] = []
        for observation in audit_observations[-limit:]:
            items.append(
                ProgressAuditItemView(
                    observation_id=observation.id,
                    kind=observation.kind,
                    created_at=observation.created_at,
                    error_code=cls._extract_error_code(observation.details),
                    summary=cls._sanitize_planner_text(observation.summary, limit=400)
                    or "System audit event recorded.",
                    detail_preview=cls._sanitize_planner_text(observation.details, limit=500),
                    raw_detail=observation.details[:4000] if include_raw else None,
                ),
            )
        return items

    @classmethod
    def _build_recent_artifact_headlines(
        cls,
        replay: RunReplayView,
    ) -> list[ArtifactHeadlineView]:
        inspections: list[ArtifactInspectionView] = []
        for task_replay in replay.tasks:
            inspections.extend(task_replay.artifacts)
        inspections.extend(replay.orphan_artifacts)
        return [cls._build_artifact_headline(item) for item in inspections[-3:]]

    @staticmethod
    def _build_progress_execution_summary(snapshot: RunSnapshotView) -> str | None:
        if snapshot.active_execution_claim is not None and snapshot.latest_task is None:
            return (
                f"Execution lease is held by {snapshot.active_execution_claim.owner} "
                f"until {snapshot.active_execution_claim.expires_at.isoformat()}."
            )
        latest_task = snapshot.latest_task
        if latest_task is None:
            return None
        if snapshot.pending_patch_intake is not None:
            return (
                f"{latest_task.summary} produced a patch and is waiting for founder review "
                f"({snapshot.pending_patch_intake.touched_file_count} touched file(s))."
            )
        if latest_task.status == TaskStatus.FAILED:
            return (
                f"{latest_task.summary} failed"
                + (
                    f": {latest_task.failure_hint}"
                    if latest_task.failure_hint
                    else "."
                )
            )
        if latest_task.status == TaskStatus.RUNNING:
            return f"{latest_task.summary} is currently running."
        if latest_task.status == TaskStatus.COMPLETED:
            return f"{latest_task.summary} completed successfully."
        return f"{latest_task.summary} is {latest_task.status.value}."

    @classmethod
    def _build_progress_surface(
        cls,
        *,
        snapshot: RunSnapshotView,
        evaluation: PossibleActionEvaluationView,
        replay: RunReplayView,
    ) -> tuple[ProgressSurfaceStatus, ProgressActionOwner, str, str | None, str | None]:
        if snapshot.pending_founder_escalation is not None:
            return (
                ProgressSurfaceStatus.WAITING_ON_FOUNDER,
                ProgressActionOwner.FOUNDER,
                "Founder reply is blocking the next planner step.",
                snapshot.pending_founder_escalation.summary,
                "Respond with a hint, bounded override, or reject to close the founder-help lane.",
            )
        if snapshot.pending_patch_intake is not None:
            return (
                ProgressSurfaceStatus.WAITING_ON_FOUNDER,
                ProgressActionOwner.FOUNDER,
                "Founder patch review is blocking the next execution-plane step.",
                snapshot.pending_patch_intake.summary,
                "Review the compact patch summary and choose approve or reject.",
            )
        if snapshot.pending_approval is not None:
            return (
                ProgressSurfaceStatus.WAITING_ON_APPROVAL,
                ProgressActionOwner.FOUNDER,
                "Run is waiting on approval before it can advance.",
                snapshot.pending_approval.reason,
                "Approve or reject the pending approval gate.",
            )
        if snapshot.active_execution_claim is not None:
            return (
                ProgressSurfaceStatus.RUNNING_EXECUTION,
                ProgressActionOwner.EXECUTOR,
                "A bounded execution lease is currently active.",
                (
                    f"{snapshot.active_execution_claim.runtime} owned by {snapshot.active_execution_claim.owner} "
                    f"until {snapshot.active_execution_claim.expires_at.isoformat()}."
                ),
                "Wait for execution to finish or reconcile the claim if the lease has expired.",
            )
        if snapshot.run.status == RunStatus.SUSPENDED:
            return (
                ProgressSurfaceStatus.SUSPENDED_ON_TIMEOUT,
                ProgressActionOwner.FOUNDER,
                "Run is suspended after an approval timeout.",
                snapshot.action_state_reason,
                "Inspect the replay and choose whether to reopen a safe next step.",
            )
        if snapshot.planner_phase_exhausted:
            return (
                ProgressSurfaceStatus.WAITING_ON_FOUNDER,
                ProgressActionOwner.FOUNDER,
                "Planner phase is exhausted and needs founder review.",
                snapshot.latest_planner_attempt_summary,
                "Run `planner recharge-check` before reopening the exhausted phase.",
            )
        if snapshot.task_summary.running > 0 or snapshot.run.status == RunStatus.RUNNING:
            return (
                ProgressSurfaceStatus.RUNNING_EXECUTION,
                ProgressActionOwner.EXECUTOR,
                "Bounded execution is currently running.",
                (
                    snapshot.latest_task.summary
                    if snapshot.latest_task is not None
                    else (
                        f"Execution lease is held by {snapshot.active_execution_claim.owner}."
                        if snapshot.active_execution_claim is not None
                        else None
                    )
                ),
                "Wait for execution to finish or inspect the current task output or lease state.",
            )
        if snapshot.run.status == RunStatus.COMPLETED:
            return (
                ProgressSurfaceStatus.COMPLETED,
                ProgressActionOwner.NONE,
                "Run completed and produced a bounded result.",
                snapshot.latest_artifact.title if snapshot.latest_artifact is not None else None,
                "Inspect artifacts or replay for the final result package.",
            )
        if snapshot.run.status == RunStatus.FAILED:
            latest_failed_task = next(
                (task for task in reversed(replay.tasks) if task.task.status == TaskStatus.FAILED),
                None,
            )
            failure_hint = None
            if latest_failed_task is not None:
                failure_hint = latest_failed_task.task.failure_hint or latest_failed_task.task.stderr
            return (
                ProgressSurfaceStatus.FAILED,
                ProgressActionOwner.FOUNDER,
                "Run failed and needs review before more work continues.",
                cls._sanitize_planner_text(failure_hint, limit=500) if failure_hint else snapshot.action_state_reason,
                "Inspect replay or raw trace before reopening another lane.",
            )
        if evaluation.actions:
            return (
                ProgressSurfaceStatus.READY_FOR_NEXT_ACTION,
                ProgressActionOwner.SYSTEM,
                "Run is ready for the next bounded action.",
                evaluation.actions[0].reason,
                "Inspect legal moves or invoke the planner for the next bounded step.",
            )
        return (
            ProgressSurfaceStatus.IDLE,
            ProgressActionOwner.NONE,
            "Run is idle and has no immediate next move.",
            snapshot.action_state_reason,
            "Inspect replay and recent audits before deciding how to proceed.",
        )

    @staticmethod
    def _build_progress_command_hints(
        *,
        run_id: str,
        snapshot: RunSnapshotView,
        evaluation: PossibleActionEvaluationView,
        surface_status: ProgressSurfaceStatus,
    ) -> list[ProgressCommandHintView]:
        commands = [
            ProgressCommandHintView(
                label="Replay",
                command=f"v2-spring run replay {run_id}",
                purpose="Review the full bounded execution and governance narrative.",
            ),
        ]
        if snapshot.active_execution_claim is not None:
            commands.extend(
                [
                    ProgressCommandHintView(
                        label="Claim inspect",
                        command=f"v2-spring task claim {run_id}",
                        purpose="Inspect the current execution lease owner and expiry window.",
                    ),
                    ProgressCommandHintView(
                        label="Claim reconcile",
                        command=f"v2-spring task reconcile-claims {run_id}",
                        purpose="Reclaim an expired execution lease and record the result as typed audit evidence.",
                    ),
                ],
            )
        if surface_status == ProgressSurfaceStatus.WAITING_ON_APPROVAL and snapshot.pending_approval is not None:
            commands.extend(
                [
                    ProgressCommandHintView(
                        label="List approvals",
                        command="v2-spring approval list",
                        purpose="See the current approval gate and any other pending approvals.",
                    ),
                    ProgressCommandHintView(
                        label="Resolve approval",
                        command=(
                            f"v2-spring approval resolve {snapshot.pending_approval.id} --approve"
                        ),
                        purpose="Approve the current gate or swap --approve for --reject --reason-file ./approval_reason.txt.",
                    ),
                ],
            )
        elif surface_status == ProgressSurfaceStatus.WAITING_ON_FOUNDER and snapshot.pending_patch_intake is not None:
            commands.extend(
                [
                    ProgressCommandHintView(
                        label="Patch review",
                        command=f"v2-spring patch review {run_id}",
                        purpose="Open the compact patch review surface with warnings and inline diff.",
                    ),
                    ProgressCommandHintView(
                        label="Patch approve",
                        command=f"v2-spring patch approve {snapshot.pending_patch_intake.intake_id}",
                        purpose="Apply the current patch through the strict all-or-nothing intake gate.",
                    ),
                    ProgressCommandHintView(
                        label="Patch reject",
                        command=(
                            f"v2-spring patch reject {snapshot.pending_patch_intake.intake_id} "
                            "--reason-file ./patch_reject_reason.txt"
                        ),
                        purpose="Reject the current patch and reopen planning with the founder rejection recorded.",
                    ),
                ],
            )
        elif surface_status == ProgressSurfaceStatus.WAITING_ON_FOUNDER and snapshot.pending_founder_escalation is not None:
            commands.extend(
                [
                    ProgressCommandHintView(
                        label="Founder hint",
                        command=(
                            "v2-spring planner reply hint "
                            f"{run_id} --escalation-id {snapshot.pending_founder_escalation.observation_id} "
                            "--message-file ./founder_hint.txt"
                        ),
                        purpose="Route one bounded founder hint back into the planner lane.",
                    ),
                    ProgressCommandHintView(
                        label="Founder override",
                        command=(
                            "v2-spring planner reply override "
                            f"{run_id} --escalation-id {snapshot.pending_founder_escalation.observation_id} "
                            "--action <legal-action> --reason-file ./override_reason.txt"
                        ),
                        purpose="Force one currently legal move without opening god mode.",
                    ),
                    ProgressCommandHintView(
                        label="Founder reject",
                        command=(
                            "v2-spring planner reply reject "
                            f"{run_id} --escalation-id {snapshot.pending_founder_escalation.observation_id} "
                            "--reason-file ./reject_reason.txt"
                        ),
                        purpose="Close the founder-help lane when no more help should be given in this phase.",
                    ),
                ],
            )
        elif surface_status == ProgressSurfaceStatus.WAITING_ON_FOUNDER and snapshot.planner_phase_exhausted:
            commands.extend(
                [
                    ProgressCommandHintView(
                        label="Recharge preflight",
                        command=f"v2-spring planner recharge-check {run_id}",
                        purpose="Review caution codes before reopening an exhausted planner phase.",
                    ),
                    ProgressCommandHintView(
                        label="Manual recharge",
                        command=(
                            f"v2-spring planner recharge {run_id} --reason "
                            "\"Founder explicitly wants one more bounded planner pass.\""
                        ),
                        purpose="Reopen the exhausted phase after reviewing the blocker context.",
                    ),
                ],
            )
        elif surface_status == ProgressSurfaceStatus.READY_FOR_NEXT_ACTION:
            commands.extend(
                [
                    ProgressCommandHintView(
                        label="Legal moves",
                        command=f"v2-spring run actions {run_id}",
                        purpose="Inspect the current deterministic legal move set.",
                    ),
                    ProgressCommandHintView(
                        label="Planner invoke",
                        command=f"v2-spring planner invoke {run_id}",
                        purpose="Ask the bounded planner adapter to pick the next legal move.",
                    ),
                ],
            )
        elif surface_status == ProgressSurfaceStatus.RUNNING_EXECUTION:
            commands.append(
                ProgressCommandHintView(
                    label="Task list",
                    command=f"v2-spring task list --run {run_id}",
                    purpose="Inspect the current bounded execution lane while it is running.",
                ),
            )
        elif surface_status == ProgressSurfaceStatus.COMPLETED:
            commands.append(
                ProgressCommandHintView(
                    label="Artifact list",
                    command=f"v2-spring artifact list --run {run_id}",
                    purpose="Inspect the latest bounded output package.",
                ),
            )
        elif surface_status in {ProgressSurfaceStatus.FAILED, ProgressSurfaceStatus.SUSPENDED_ON_TIMEOUT}:
            commands.append(
                ProgressCommandHintView(
                    label="Detailed replay",
                    command=f"v2-spring run replay {run_id} --verbose",
                    purpose="Open the full trace before choosing another intervention.",
                ),
            )
        if evaluation.actions and all(
            command.command != f"v2-spring run actions {run_id}" for command in commands
        ):
            commands.append(
                ProgressCommandHintView(
                    label="Legal moves",
                    command=f"v2-spring run actions {run_id}",
                    purpose="Inspect the current deterministic legal move set.",
                ),
            )
        return commands

    @staticmethod
    def _build_route_summary(
        source_action: PossibleActionView | None,
        outcome: RoutingOutcome,
    ) -> str:
        action_label = source_action.name.value if source_action is not None else "no_routable_work"
        if isinstance(outcome, RoutingDecision):
            return f"Execution routing selected {outcome.runtime.value} for {action_label}."
        return f"Execution routing refused {action_label} with {outcome.refusal_code.value}."

    def _build_route_audit_details(
        self,
        *,
        snapshot: RunSnapshotView,
        source_action: PossibleActionView | None,
        requirements: ExecutionRequirements | None,
        system_limits: SystemLimits,
        outcome: RoutingOutcome,
    ) -> str:
        payload = {
            "snapshot_hash": snapshot.state_hash,
            "planner_phase_key": snapshot.planner_phase_key,
            "source_action": source_action.name.value if source_action is not None else None,
            "source_action_reason": source_action.reason if source_action is not None else None,
            "requirements": requirements.model_dump(mode="json") if requirements is not None else None,
            "system_limits": system_limits.model_dump(mode="json"),
            "outcome": outcome.model_dump(mode="json"),
        }
        return self._sanitize_planner_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            limit=4000,
        ) or "Execution routing audit payload unavailable."

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
    def _acquire_run_status_guard(
        session: Session,
        run_id: str,
        *,
        mutation_name: str,
        allow_during_waiting_approval: bool = False,
        allow_during_suspended: bool = False,
        required_status: RunStatus | None = None,
    ) -> RunRecord:
        statement = update(RunRecord).where(RunRecord.id == run_id).values(updated_at=RunRecord.updated_at)
        if required_status is not None:
            statement = statement.where(RunRecord.status == required_status)
        else:
            if not allow_during_waiting_approval:
                statement = statement.where(RunRecord.status != RunStatus.WAITING_APPROVAL)
            if not allow_during_suspended:
                statement = statement.where(RunRecord.status != RunStatus.SUSPENDED)

        rowcount = session.execute(statement).rowcount
        run = session.get(RunRecord, run_id)
        if run is None:
            raise LookupError(f"Run {run_id} was not found.")
        if rowcount:
            return run
        if required_status is not None:
            raise PermissionError(
                f"Run {run_id} is {run.status.value}; {mutation_name} requires the run to be {required_status.value}.",
            )
        if run.status == RunStatus.WAITING_APPROVAL and not allow_during_waiting_approval:
            raise PermissionError(
                f"Run {run_id} is waiting for approval; {mutation_name} is blocked until approval is resolved.",
            )
        if run.status == RunStatus.SUSPENDED and not allow_during_suspended:
            raise PermissionError(
                f"Run {run_id} is suspended; {mutation_name} is blocked until the timed-out approval is explicitly recovered.",
            )
        raise PermissionError(
            f"Run {run_id} changed while attempting {mutation_name}; refresh the current state and retry deterministically.",
        )

    @classmethod
    def _get_run_for_execution(cls, session: Session, run_id: str) -> RunRecord:
        return cls._acquire_run_status_guard(
            session,
            run_id,
            mutation_name="bounded execution",
            required_status=RunStatus.READY,
        )

    @classmethod
    def _get_run_for_mutation(
        cls,
        session: Session,
        run_id: str,
        *,
        mutation_name: str,
        allow_during_waiting_approval: bool = False,
        allow_during_suspended: bool = False,
    ) -> RunRecord:
        return cls._acquire_run_status_guard(
            session,
            run_id,
            mutation_name=mutation_name,
            allow_during_waiting_approval=allow_during_waiting_approval,
            allow_during_suspended=allow_during_suspended,
        )

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

    def _build_failed_isolated_receipt(
        self,
        *,
        workspace: Path,
        execution_context_id: str,
        timeout_seconds: int,
        summary: str,
    ) -> IsolatedWorkerReceipt:
        now = utc_now()
        return IsolatedWorkerReceipt(
            execution_context_id=execution_context_id,
            command=f"isolated_worker_proof --workspace {workspace}",
            source_workspace=str(workspace),
            sandbox_cwd=str(workspace),
            started_at=now,
            finished_at=now,
            timeout_seconds=timeout_seconds,
            returncode=None,
            timed_out=False,
            stdout_preview="",
            stderr_preview=summary,
            stdout_bytes=0,
            stderr_bytes=len(summary.encode("utf-8")),
            stderr_truncated=False,
            changed_files=[],
            patch_body=None,
            summary=summary,
            base_file_hashes={},
            excluded_names=[],
            env_allowlist=[],
            secret_surface_present=False,
        )

    def _build_failed_containerized_receipt(
        self,
        *,
        workspace: Path,
        execution_context_id: str,
        timeout_seconds: int,
        summary: str,
        preflight_refusal_code: str | None = None,
    ) -> ContainerizedWorkerReceipt:
        now = utc_now()
        image = "unavailable"
        base_image_reference: str | None = None
        metadata_registry_path: str | None = None
        metadata_registry_schema_version: int | None = None
        metadata_registry_checksum: str | None = None
        capability_manifest_tools: list[str] = []
        try:
            from v2_spring.runtime.worker_metadata import load_worker_metadata_registry

            metadata_registry = load_worker_metadata_registry()
            metadata_registry_path = metadata_registry.path
            metadata_registry_schema_version = metadata_registry.registry.schema_version
            metadata_registry_checksum = metadata_registry.checksum
            manifest = metadata_registry.registry.runtimes.get("containerized_worker")
            if manifest is not None:
                image = manifest.worker_image_tag
                base_image_reference = manifest.base_image_reference
                capability_manifest_tools = list(manifest.required_tools)
        except Exception:
            pass
        return ContainerizedWorkerReceipt(
            execution_context_id=execution_context_id,
            image=image,
            image_digest=None,
            base_image_reference=base_image_reference,
            container_name=f"v2-spring-worker-{execution_context_id[:12]}",
            command=f"containerized_worker_proof --workspace {workspace}",
            source_workspace=str(workspace),
            sandbox_cwd="/workspace",
            started_at=now,
            finished_at=now,
            timeout_seconds=timeout_seconds,
            returncode=None,
            timed_out=False,
            metadata_registry_path=metadata_registry_path,
            metadata_registry_schema_version=metadata_registry_schema_version,
            metadata_registry_checksum=metadata_registry_checksum,
            preflight_strategy="static_manifest",
            preflight_refusal_code=preflight_refusal_code,
            dynamic_check_performed=False,
            dynamic_check_tools=[],
            capability_manifest_tools=capability_manifest_tools,
            stdout_preview="",
            stderr_preview=summary,
            stdout_bytes=0,
            stderr_bytes=len(summary.encode("utf-8")),
            stderr_truncated=False,
            changed_files=[],
            patch_body=None,
            summary=summary,
            base_file_hashes={},
            excluded_names=[],
            env_allowlist=[],
            secret_surface_present=False,
            ownership_normalized=False,
            orphan_gc_removed=0,
            resource_limits={},
        )

    @staticmethod
    def _worker_runtime_phrase(runtime: str) -> str:
        if runtime == "containerized_worker":
            return "Containerized worker proof"
        return "Isolated worker proof"

    def _build_stale_execution_result_rejection(
        self,
        *,
        session: Session,
        run: RunRecord,
        task: TaskRecord,
        receipt: IsolatedWorkerReceipt | ContainerizedWorkerReceipt,
        receipt_path: Path,
        receipt_hash: str,
        receipt_bytes: bytes,
        runtime_phrase: str,
        reason: str,
    ) -> IsolatedWorkerDispatchResult:
        receipt_artifact = ArtifactRecord(
            run_id=run.id,
            task_id=task.id,
            decision_id=task.decision_id,
            artifact_type=ArtifactType.EXECUTION_RECEIPT,
            title=f"{runtime_phrase} execution receipt (rejected stale result)",
            storage_kind=ArtifactStorageKind.FILESYSTEM_PATH,
            path=str(receipt_path),
            size_bytes=len(receipt_bytes),
            sha256=receipt_hash,
            execution_context_id=receipt.execution_context_id,
            command=receipt.command,
            cwd=receipt.sandbox_cwd,
        )
        session.add(receipt_artifact)
        session.flush()

        observation = ObservationRecord(
            run_id=run.id,
            kind=ObservationKind.SYSTEM_AUDIT,
            summary="Late worker result was rejected because its execution claim was no longer current.",
            details=(
                f"error_code=stale_execution_result_rejected; task_id={task.id}; "
                f"execution_context_id={receipt.execution_context_id}; "
                f"task_claim_token={task.execution_claim_token}; "
                f"task_fencing_token={task.execution_claim_fencing_token}; "
                f"reason={reason}."
            ),
        )
        session.add(observation)
        session.flush()

        session.add(
            EventLedgerRecord(
                run_id=run.id,
                event_type=LedgerEventType.ARTIFACT_RECORDED,
                payload={
                    "artifact_id": receipt_artifact.id,
                    "task_id": task.id,
                    "decision_id": task.decision_id,
                    "execution_context_id": receipt_artifact.execution_context_id,
                    "path": receipt_artifact.path,
                    "sha256": receipt_artifact.sha256,
                },
            ),
        )
        session.add(
            EventLedgerRecord(
                run_id=run.id,
                event_type=LedgerEventType.EXECUTION_RESULT_REJECTED,
                payload={
                    "task_id": task.id,
                    "decision_id": task.decision_id,
                    "execution_context_id": receipt.execution_context_id,
                    "runtime": receipt.runtime,
                    "reason": reason,
                    "task_claim_token": task.execution_claim_token,
                    "task_fencing_token": task.execution_claim_fencing_token,
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
        return IsolatedWorkerDispatchResult(
            task=self._to_task_view(task),
            artifacts=[self._to_artifact_view(receipt_artifact)],
            observation=self._to_observation_view(observation),
            receipt=receipt,
        )

    def _validate_current_execution_claim_for_task(
        self,
        *,
        session: Session,
        run_id: str,
        task: TaskRecord,
    ) -> str | None:
        claim = self._load_execution_claim(session, run_id)
        if claim is None:
            return "no execution claim is present for the run"
        if claim.status != ExecutionClaimStatus.ACTIVE:
            return f"claim status is {claim.status.value}"
        if not self._task_claim_matches_record(task, claim):
            return (
                f"active claim mismatch: claim_task_id={claim.task_id}; "
                f"claim_token={claim.lease_token}; claim_fencing_token={claim.version}"
            )
        return None

    def _finalize_failed_isolated_task(
        self,
        *,
        run_id: str,
        task_id: str,
        artifact_root: Path,
        receipt: IsolatedWorkerReceipt | ContainerizedWorkerReceipt,
        failure_summary: str,
    ) -> IsolatedWorkerDispatchResult:
        runtime_phrase = self._worker_runtime_phrase(receipt.runtime)
        artifact_directory = artifact_root / run_id / task_id
        artifact_directory.mkdir(parents=True, exist_ok=True)
        receipt_path = artifact_directory / f"{receipt.runtime.replace('_', '-')}-receipt.json"
        receipt_path.write_text(
            json.dumps(receipt.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        receipt_bytes = receipt_path.read_bytes()
        receipt_hash = sha256(receipt_bytes).hexdigest()

        with self.session() as session:
            run = session.get(RunRecord, run_id)
            task = session.get(TaskRecord, task_id)
            if run is None or task is None:
                raise LookupError("Isolated task finalization failed because the run or task no longer exists.")
            stale_reason = self._validate_current_execution_claim_for_task(
                session=session,
                run_id=run.id,
                task=task,
            )
            if stale_reason is not None:
                return self._build_stale_execution_result_rejection(
                    session=session,
                    run=run,
                    task=task,
                    receipt=receipt,
                    receipt_path=receipt_path,
                    receipt_hash=receipt_hash,
                    receipt_bytes=receipt_bytes,
                    runtime_phrase=runtime_phrase,
                    reason=stale_reason,
                )

            task.execution_context_id = receipt.execution_context_id
            task.command = receipt.command
            task.cwd = receipt.sandbox_cwd
            task.timeout_seconds = receipt.timeout_seconds
            task.stdout = receipt.stdout_preview
            task.stderr = receipt.stderr_preview or failure_summary
            task.completed_at = receipt.finished_at
            task.status = TaskStatus.FAILED
            run.status = RunStatus.FAILED
            self._release_execution_claim(
                session=session,
                run_id=run.id,
                execution_context_id=receipt.execution_context_id,
                reason="execution_failed",
            )

            receipt_artifact = ArtifactRecord(
                run_id=run.id,
                task_id=task.id,
                decision_id=task.decision_id,
                artifact_type=ArtifactType.EXECUTION_RECEIPT,
                title=f"{runtime_phrase} execution receipt",
                storage_kind=ArtifactStorageKind.FILESYSTEM_PATH,
                path=str(receipt_path),
                size_bytes=len(receipt_bytes),
                sha256=receipt_hash,
                execution_context_id=receipt.execution_context_id,
                command=receipt.command,
                cwd=receipt.sandbox_cwd,
            )
            session.add(receipt_artifact)
            session.flush()

            observation = ObservationRecord(
                run_id=run.id,
                kind=ObservationKind.TASK_EXECUTION,
                summary=f"{runtime_phrase} failed before a patch could be accepted.",
                details=failure_summary,
            )
            session.add(observation)
            session.flush()

            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.ARTIFACT_RECORDED,
                    payload={
                        "artifact_id": receipt_artifact.id,
                        "task_id": task.id,
                        "decision_id": task.decision_id,
                        "execution_context_id": receipt_artifact.execution_context_id,
                        "path": receipt_artifact.path,
                        "sha256": receipt_artifact.sha256,
                    },
                ),
            )
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.TASK_FAILED,
                    payload={
                        "task_id": task.id,
                        "decision_id": task.decision_id,
                        "execution_context_id": task.execution_context_id,
                        "status": task.status.value,
                        "error": failure_summary,
                        "timed_out": receipt.timed_out,
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
            return IsolatedWorkerDispatchResult(
                task=self._to_task_view(task),
                artifacts=[self._to_artifact_view(receipt_artifact)],
                observation=self._to_observation_view(observation),
                receipt=receipt,
            )

    def _finalize_completed_isolated_task(
        self,
        *,
        run_id: str,
        task_id: str,
        artifact_root: Path,
        receipt: IsolatedWorkerReceipt | ContainerizedWorkerReceipt,
    ) -> IsolatedWorkerDispatchResult:
        runtime_phrase = self._worker_runtime_phrase(receipt.runtime)
        artifact_directory = artifact_root / run_id / task_id
        artifact_directory.mkdir(parents=True, exist_ok=True)
        patch_path = artifact_directory / f"{receipt.runtime.replace('_', '-')}-proof.patch"
        receipt_path = artifact_directory / f"{receipt.runtime.replace('_', '-')}-receipt.json"
        patch_path.write_text(receipt.patch_body or "", encoding="utf-8")
        receipt_path.write_text(
            json.dumps(receipt.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        patch_bytes = patch_path.read_bytes()
        receipt_bytes = receipt_path.read_bytes()
        patch_hash = sha256(patch_bytes).hexdigest()
        receipt_hash = sha256(receipt_bytes).hexdigest()

        try:
            with self.session() as session:
                run = session.get(RunRecord, run_id)
                task = session.get(TaskRecord, task_id)
                if run is None or task is None:
                    raise LookupError("Isolated task finalization failed because the run or task no longer exists.")
                stale_reason = self._validate_current_execution_claim_for_task(
                    session=session,
                    run_id=run.id,
                    task=task,
                )
                if stale_reason is not None:
                    return self._build_stale_execution_result_rejection(
                        session=session,
                        run=run,
                        task=task,
                        receipt=receipt,
                        receipt_path=receipt_path,
                        receipt_hash=receipt_hash,
                        receipt_bytes=receipt_bytes,
                        runtime_phrase=runtime_phrase,
                        reason=stale_reason,
                    )

                task.execution_context_id = receipt.execution_context_id
                task.command = receipt.command
                task.cwd = receipt.sandbox_cwd
                task.timeout_seconds = receipt.timeout_seconds
                task.stdout = receipt.stdout_preview
                task.stderr = receipt.stderr_preview
                task.completed_at = receipt.finished_at
                task.status = TaskStatus.COMPLETED
                run.status = RunStatus.READY
                self._release_execution_claim(
                    session=session,
                    run_id=run.id,
                    execution_context_id=receipt.execution_context_id,
                    reason="execution_completed",
                )

                patch_warnings, risk_class, auto_apply_eligible, patch_summary = self._build_patch_review_policy(
                    session=session,
                    run_id=run.id,
                    patch_body=receipt.patch_body or "",
                    changed_files=receipt.changed_files,
                )

                patch_artifact = ArtifactRecord(
                    run_id=run.id,
                    task_id=task.id,
                    decision_id=task.decision_id,
                    artifact_type=ArtifactType.UNIFIED_PATCH,
                    title=f"{runtime_phrase} patch",
                    storage_kind=ArtifactStorageKind.FILESYSTEM_PATH,
                    path=str(patch_path),
                    size_bytes=len(patch_bytes),
                    sha256=patch_hash,
                    execution_context_id=receipt.execution_context_id,
                    command=receipt.command,
                    cwd=receipt.sandbox_cwd,
                )
                receipt_artifact = ArtifactRecord(
                    run_id=run.id,
                    task_id=task.id,
                    decision_id=task.decision_id,
                    artifact_type=ArtifactType.EXECUTION_RECEIPT,
                    title=f"{runtime_phrase} execution receipt",
                    storage_kind=ArtifactStorageKind.FILESYSTEM_PATH,
                    path=str(receipt_path),
                    size_bytes=len(receipt_bytes),
                    sha256=receipt_hash,
                    execution_context_id=receipt.execution_context_id,
                    command=receipt.command,
                    cwd=receipt.sandbox_cwd,
                )
                session.add(patch_artifact)
                session.add(receipt_artifact)
                session.flush()

                patch_intake = PatchIntakeRecord(
                    run_id=run.id,
                    task_id=task.id,
                    patch_artifact_id=patch_artifact.id,
                    receipt_artifact_id=receipt_artifact.id,
                    status=PatchIntakeStatus.PENDING,
                    summary=patch_summary,
                    source_workspace=receipt.source_workspace,
                    changed_files=receipt.changed_files,
                    touched_file_count=len(receipt.changed_files),
                    patch_size_bytes=len(patch_bytes),
                    patch_sha256=patch_hash,
                    risk_class=risk_class,
                    auto_apply_eligible=auto_apply_eligible,
                    warnings=[warning.model_dump(mode="json") for warning in patch_warnings],
                )
                session.add(patch_intake)
                session.flush()

                observation: ObservationRecord | None = None

                for artifact in (patch_artifact, receipt_artifact):
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
                        event_type=LedgerEventType.PATCH_INTAKE_RECORDED,
                        payload={
                            "patch_intake_id": patch_intake.id,
                            "task_id": task.id,
                            "patch_artifact_id": patch_artifact.id,
                            "receipt_artifact_id": receipt_artifact.id,
                            "risk_class": patch_intake.risk_class.value,
                            "auto_apply_eligible": patch_intake.auto_apply_eligible,
                            "warning_count": len(patch_warnings),
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
                            "status": task.status.value,
                            "runtime": receipt.runtime,
                            "changed_files": receipt.changed_files,
                            "base_file_hashes": receipt.base_file_hashes,
                            "patch_intake_id": patch_intake.id,
                        },
                    ),
                )
                extra_artifacts: list[ArtifactView] = []
                if patch_intake.auto_apply_eligible:
                    try:
                        _, observation, validation_artifact = self._apply_patch_intake_resolution(
                            session=session,
                            run=run,
                            task=task,
                            patch_intake=patch_intake,
                            patch_artifact=patch_artifact,
                            receipt_artifact=receipt_artifact,
                            approval_mode="auto",
                        )
                        extra_artifacts.append(self._to_artifact_view(validation_artifact))
                    except Exception as exc:
                        observation = ObservationRecord(
                            run_id=run.id,
                            kind=ObservationKind.SYSTEM_AUDIT,
                            summary="Auto-apply candidate fell back to founder review after an internal gate error.",
                            details=(
                                f"error_code=auto_apply_internal_fallback; "
                                f"patch_intake_id={patch_intake.id}; "
                                f"reason={exc}."
                            ),
                        )
                        session.add(observation)
                        session.flush()
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
                        observation = ObservationRecord(
                            run_id=run.id,
                            kind=ObservationKind.TASK_EXECUTION,
                            summary=f"{runtime_phrase} completed and is waiting on founder patch review.",
                            details=(
                                f"Task {task.id} produced patch artifact {patch_artifact.id}, receipt artifact {receipt_artifact.id}, "
                                f"and patch intake {patch_intake.id}. Changed files: {', '.join(receipt.changed_files) if receipt.changed_files else '-'}."
                            ),
                        )
                        session.add(observation)
                        session.flush()
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
                else:
                    observation = ObservationRecord(
                        run_id=run.id,
                        kind=ObservationKind.TASK_EXECUTION,
                        summary=f"{runtime_phrase} completed and is waiting on founder patch review.",
                        details=(
                            f"Task {task.id} produced patch artifact {patch_artifact.id}, receipt artifact {receipt_artifact.id}, "
                            f"and patch intake {patch_intake.id}. Changed files: {', '.join(receipt.changed_files) if receipt.changed_files else '-'}."
                        ),
                    )
                    session.add(observation)
                    session.flush()
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
                return IsolatedWorkerDispatchResult(
                    task=self._to_task_view(task),
                    artifacts=[
                        self._to_artifact_view(patch_artifact),
                        self._to_artifact_view(receipt_artifact),
                        *extra_artifacts,
                    ],
                    observation=self._to_observation_view(observation),
                    receipt=receipt,
                )
        except Exception:
            if patch_path.exists():
                patch_path.unlink()
            if receipt_path.exists():
                receipt_path.unlink()
            raise

    def _build_patch_review_policy(
        self,
        *,
        session: Session,
        run_id: str,
        patch_body: str,
        changed_files: list[str],
    ) -> tuple[list[PatchReviewWarningView], PatchRiskClass, bool, str]:
        warnings: list[PatchReviewWarningView] = []
        lowered_patch = patch_body.lower()
        danger_terms = (
            "os.system(",
            "subprocess.run(",
            "subprocess.popen(",
            "rm -rf",
            "shutil.rmtree(",
            "eval(",
            "exec(",
        )
        if any(term in lowered_patch for term in danger_terms):
            warnings.append(
                PatchReviewWarningView(
                    code=PatchWarningCode.DANGEROUS_KEYWORD,
                    message="Dangerous execution keywords were detected in the patch body.",
                ),
            )
        if self._touches_sensitive_path(changed_files):
            warnings.append(
                PatchReviewWarningView(
                    code=PatchWarningCode.SENSITIVE_PATH,
                    message="The patch touches a sensitive path and should be reviewed carefully.",
                ),
            )
        if self._touches_central_file(changed_files):
            warnings.append(
                PatchReviewWarningView(
                    code=PatchWarningCode.CENTRAL_FILE,
                    message="The patch touches a protected central file and must stay founder-reviewed.",
                ),
            )
        warnings.extend(self._scan_patch_structural_risks(patch_body))
        if len(changed_files) >= 4:
            warnings.append(
                PatchReviewWarningView(
                    code=PatchWarningCode.MANY_FILES,
                    message="The patch touches several files and may be too broad for a trivial founder review.",
                ),
            )
        lines_added, lines_removed = self._count_patch_lines(patch_body)
        changed_line_total = lines_added + lines_removed
        if len(patch_body.encode("utf-8")) >= 12000 or changed_line_total > self._PATCH_AUTO_APPLY_MAX_CHANGED_LINES:
            warnings.append(
                PatchReviewWarningView(
                    code=PatchWarningCode.LARGE_PATCH,
                    message=(
                        "The patch is large for bounded auto-apply and should be reviewed through the inline diff."
                    ),
                ),
            )
        if self._recent_auto_apply_burst_detected(session=session, run_id=run_id, changed_files=changed_files):
            warnings.append(
                PatchReviewWarningView(
                    code=PatchWarningCode.AUTO_APPLY_BURST,
                    message=(
                        "Recent auto-apply activity already touched this file or module repeatedly, "
                        "so founder review is required."
                    ),
                ),
            )

        blocking_codes = {
            PatchWarningCode.DANGEROUS_KEYWORD,
            PatchWarningCode.SENSITIVE_PATH,
            PatchWarningCode.CENTRAL_FILE,
            PatchWarningCode.AUTO_APPLY_BURST,
            PatchWarningCode.STRUCTURAL_DANGER,
        }
        if any(warning.code in blocking_codes for warning in warnings):
            risk_class = PatchRiskClass.HIGH
        elif warnings:
            risk_class = PatchRiskClass.MEDIUM
        else:
            risk_class = PatchRiskClass.LOW

        auto_apply_eligible = (
            risk_class == PatchRiskClass.LOW
            and len(changed_files) == 1
            and changed_line_total <= self._PATCH_AUTO_APPLY_MAX_CHANGED_LINES
        )
        summary = self._build_patch_intake_summary(
            warnings=warnings,
            changed_files=changed_files,
            auto_apply_eligible=auto_apply_eligible,
        )
        return warnings, risk_class, auto_apply_eligible, summary

    @classmethod
    def _touches_sensitive_path(cls, changed_files: list[str]) -> bool:
        sensitive_prefixes = (
            ".github/workflows/",
            ".env",
            "pyproject.toml",
            "src/v2_spring/ledger/",
        )
        return any(
            changed_file == prefix or changed_file.startswith(prefix)
            for changed_file in changed_files
            for prefix in sensitive_prefixes
        )

    @classmethod
    def _touches_central_file(cls, changed_files: list[str]) -> bool:
        protected_prefixes = (
            "src/v2_spring/domain/",
            "src/v2_spring/planner/",
            "src/v2_spring/runtime/",
        )
        protected_names = {"base.py", "constants.py", "config.py", "settings.py"}
        for changed_file in changed_files:
            normalized = changed_file.strip()
            if any(normalized.startswith(prefix) for prefix in protected_prefixes):
                return True
            if Path(normalized).name in protected_names:
                return True
        return False

    @classmethod
    def _scan_patch_structural_risks(cls, patch_body: str) -> list[PatchReviewWarningView]:
        added_source = cls._extract_added_python_source(patch_body)
        if not added_source:
            return []
        warnings: list[PatchReviewWarningView] = []
        try:
            tree = ast.parse(added_source)
        except SyntaxError:
            if re.search(r"getattr\(\s*(os|subprocess|shutil|builtins)\s*,", added_source):
                warnings.append(
                    PatchReviewWarningView(
                        code=PatchWarningCode.STRUCTURAL_WARNING,
                        message="Dynamic attribute access against a sensitive module was detected in added code.",
                    ),
                )
            return warnings

        blocked_hits: set[str] = set()
        warning_hits: set[str] = set()

        class StructuralVisitor(ast.NodeVisitor):
            def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
                qualified_name = cls._resolve_ast_call_name(node.func)
                if qualified_name in {
                    "eval",
                    "exec",
                    "__import__",
                    "os.system",
                    "os.popen",
                    "shutil.rmtree",
                    "subprocess.run",
                    "subprocess.Popen",
                    "subprocess.call",
                    "subprocess.check_output",
                }:
                    blocked_hits.add(qualified_name)
                elif qualified_name == "importlib.import_module":
                    warning_hits.add(qualified_name)
                elif qualified_name == "getattr":
                    base_name = cls._resolve_ast_call_name(node.args[0]) if node.args else None
                    attribute_name = cls._extract_constant_string(node.args[1]) if len(node.args) > 1 else None
                    if base_name in {"os", "subprocess", "shutil", "builtins"}:
                        if attribute_name in {"system", "popen", "run", "Popen", "call", "check_output", "rmtree"}:
                            blocked_hits.add(f"getattr({base_name}, {attribute_name})")
                        else:
                            warning_hits.add(f"getattr({base_name}, dynamic)")
                self.generic_visit(node)

        StructuralVisitor().visit(tree)
        if blocked_hits:
            warnings.append(
                PatchReviewWarningView(
                    code=PatchWarningCode.STRUCTURAL_DANGER,
                    message=(
                        "Structural scan detected dangerous execution patterns: "
                        + ", ".join(sorted(blocked_hits))
                        + "."
                    ),
                ),
            )
        if warning_hits:
            warnings.append(
                PatchReviewWarningView(
                    code=PatchWarningCode.STRUCTURAL_WARNING,
                    message=(
                        "Structural scan detected suspicious dynamic patterns that should be founder-reviewed: "
                        + ", ".join(sorted(warning_hits))
                        + "."
                    ),
                ),
            )
        return warnings

    @staticmethod
    def _extract_added_python_source(patch_body: str) -> str:
        added_lines: list[str] = []
        for line in patch_body.splitlines():
            if line.startswith("+++") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                added_lines.append(line[1:])
        added_source = "\n".join(added_lines).strip()
        if not added_source:
            return ""
        return textwrap.dedent(added_source)

    @staticmethod
    def _resolve_ast_call_name(node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = LedgerStore._resolve_ast_call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return None

    @staticmethod
    def _extract_constant_string(node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = LedgerStore._extract_constant_string(node.left)
            right = LedgerStore._extract_constant_string(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    def _recent_auto_apply_burst_detected(
        self,
        *,
        session: Session,
        run_id: str,
        changed_files: list[str],
    ) -> bool:
        if not changed_files:
            return False
        cutoff = utc_now() - self._PATCH_POLICY_WINDOW
        records = list(
            session.scalars(
                select(PatchIntakeRecord)
                .where(PatchIntakeRecord.run_id == run_id)
                .where(PatchIntakeRecord.resolution_code == PatchResolutionCode.AUTO_APPLIED)
                .where(PatchIntakeRecord.resolved_at.is_not(None))
                .where(PatchIntakeRecord.resolved_at >= cutoff)
                .order_by(PatchIntakeRecord.resolved_at.asc(), PatchIntakeRecord.id.asc()),
            ).all(),
        )
        overlap_count = 0
        for record in records:
            if self._patch_scope_overlaps(changed_files, list(record.changed_files or [])):
                overlap_count += 1
        return overlap_count >= self._PATCH_AUTO_APPLY_BURST_LIMIT

    @classmethod
    def _patch_scope_overlaps(cls, changed_files: list[str], other_files: list[str]) -> bool:
        if not changed_files or not other_files:
            return False
        if set(changed_files).intersection(other_files):
            return True
        current_modules = {cls._module_scope_for_path(path) for path in changed_files}
        other_modules = {cls._module_scope_for_path(path) for path in other_files}
        return bool(current_modules.intersection(other_modules))

    @staticmethod
    def _module_scope_for_path(path: str) -> str:
        parts = Path(path).parts
        if len(parts) >= 3:
            return "/".join(parts[:3])
        if len(parts) >= 2:
            return "/".join(parts[:2])
        return parts[0] if parts else path

    @classmethod
    def _build_patch_intake_summary(
        cls,
        *,
        warnings: list[PatchReviewWarningView],
        changed_files: list[str],
        auto_apply_eligible: bool,
    ) -> str:
        touched = len(changed_files)
        if auto_apply_eligible:
            return f"Low-risk patch qualified for strict auto-apply after touching {touched} file(s)."
        if warnings:
            lead = warnings[0]
            return (
                f"Founder review is required before applying a patch touching {touched} file(s): "
                f"{lead.message}"
            )
        return f"Founder review is required before applying a patch touching {touched} file(s)."

    @staticmethod
    def _count_patch_lines(patch_body: str) -> tuple[int, int]:
        added = 0
        removed = 0
        for line in patch_body.splitlines():
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
        return added, removed

    @staticmethod
    def _build_pending_patch_intake(view: PatchIntakeView | None) -> PendingPatchIntakeView | None:
        if view is None:
            return None
        return PendingPatchIntakeView(
            intake_id=view.id,
            task_id=view.task_id,
            patch_artifact_id=view.patch_artifact_id,
            summary=view.summary,
            risk_class=view.risk_class,
            warning_count=len(view.warnings),
            touched_file_count=view.touched_file_count,
            created_at=view.created_at,
        )

    def _persist_validation_receipt_artifact(
        self,
        *,
        session: Session,
        run: RunRecord,
        task: TaskRecord,
        patch_intake: PatchIntakeRecord,
        patch_artifact: ArtifactRecord,
        receipt: PatchApplyReceipt,
    ) -> ArtifactRecord:
        artifact_directory = Path(patch_artifact.path).resolve().parent
        artifact_directory.mkdir(parents=True, exist_ok=True)
        validation_path = artifact_directory / "patch-validation-receipt.json"
        validation_path.write_text(
            json.dumps(receipt.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        validation_bytes = validation_path.read_bytes()
        validation_hash = sha256(validation_bytes).hexdigest()
        artifact = ArtifactRecord(
            run_id=run.id,
            task_id=task.id,
            decision_id=task.decision_id,
            artifact_type=ArtifactType.VALIDATION_RECEIPT,
            title="Patch intake validation receipt",
            storage_kind=ArtifactStorageKind.FILESYSTEM_PATH,
            path=str(validation_path),
            size_bytes=len(validation_bytes),
            sha256=validation_hash,
            execution_context_id=task.execution_context_id,
            command=receipt.validation_command,
            cwd=str(Path(patch_intake.source_workspace).resolve()),
        )
        session.add(artifact)
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
        return artifact

    def _build_patch_repair_feedback(
        self,
        *,
        patch_intake: PatchIntakeRecord,
        apply_receipt: PatchApplyReceipt,
    ) -> str:
        changed_files = ", ".join(list(patch_intake.changed_files or [])) or "-"
        details: list[str] = [
            f"Patch repair failed with {apply_receipt.outcome.value}.",
            f"changed_files={changed_files}",
            f"validation_command={apply_receipt.validation_command}",
        ]
        if apply_receipt.base_hash_conflicts:
            details.append(
                "base_hash_conflicts=" + ", ".join(apply_receipt.base_hash_conflicts),
            )
        if apply_receipt.apply_check_stderr:
            details.append(
                "apply_check=" + (self._sanitize_planner_text(apply_receipt.apply_check_stderr, limit=800) or "-"),
            )
        if apply_receipt.validation_returncode is not None:
            details.append(f"validation_returncode={apply_receipt.validation_returncode}")
        if apply_receipt.validation_stdout_preview:
            details.append(
                "validation_stdout="
                + (self._sanitize_planner_text(apply_receipt.validation_stdout_preview, limit=800) or "-"),
            )
        if apply_receipt.validation_stderr_preview:
            details.append(
                "validation_stderr="
                + (self._sanitize_planner_text(apply_receipt.validation_stderr_preview, limit=1200) or "-"),
            )
        return self._sanitize_planner_text(" ; ".join(details), limit=4000) or apply_receipt.summary

    def _count_patch_repair_failures(
        self,
        *,
        session: Session,
        run_id: str,
        changed_files: list[str],
    ) -> int:
        cutoff = utc_now() - self._PATCH_POLICY_WINDOW
        records = list(
            session.scalars(
                select(PatchIntakeRecord)
                .where(PatchIntakeRecord.run_id == run_id)
                .where(PatchIntakeRecord.status == PatchIntakeStatus.REJECTED)
                .where(PatchIntakeRecord.resolved_at.is_not(None))
                .where(PatchIntakeRecord.resolved_at >= cutoff)
                .where(
                    PatchIntakeRecord.resolution_code.in_(
                        (
                            PatchResolutionCode.BASE_HASH_CONFLICT,
                            PatchResolutionCode.APPLY_CHECK_FAILED,
                            PatchResolutionCode.VALIDATION_FAILED,
                        ),
                    ),
                )
                .order_by(PatchIntakeRecord.resolved_at.asc(), PatchIntakeRecord.id.asc()),
            ).all(),
        )
        failures = 0
        for record in records:
            if self._patch_scope_overlaps(changed_files, list(record.changed_files or [])):
                failures += 1
        return failures

    def _has_pending_founder_escalation(self, *, session: Session, run_id: str) -> bool:
        observation_records = list(
            session.scalars(
                select(ObservationRecord)
                .where(ObservationRecord.run_id == run_id)
                .where(ObservationRecord.kind == ObservationKind.PLANNER_ESCALATION)
                .order_by(ObservationRecord.created_at.asc(), ObservationRecord.id.asc()),
            ).all(),
        )
        founder_intervention_records = list(
            session.scalars(
                select(FounderInterventionRecord)
                .where(FounderInterventionRecord.run_id == run_id)
                .order_by(FounderInterventionRecord.created_at.asc(), FounderInterventionRecord.id.asc()),
            ).all(),
        )
        return self._build_pending_founder_escalation(
            observation_records=observation_records,
            founder_intervention_records=founder_intervention_records,
        ) is not None

    def _maybe_record_patch_repair_escalation(
        self,
        *,
        session: Session,
        run: RunRecord,
        patch_intake: PatchIntakeRecord,
        repair_failure_count: int,
    ) -> None:
        if repair_failure_count < self._PATCH_REPAIR_QUOTA_LIMIT:
            return
        if self._has_pending_founder_escalation(session=session, run_id=run.id):
            return
        details = (
            f"repair_failure_count={repair_failure_count}; "
            f"patch_intake_id={patch_intake.id}; "
            f"changed_files={', '.join(list(patch_intake.changed_files or [])) or '-'}; "
            f"latest_reason={patch_intake.resolution_reason or patch_intake.summary}."
        )
        observation = ObservationRecord(
            run_id=run.id,
            kind=ObservationKind.PLANNER_ESCALATION,
            summary="Repeated patch repair failures now require founder guidance.",
            details=self._sanitize_planner_text(details, limit=4000)
            or "Repeated patch repair failures now require founder guidance.",
        )
        session.add(observation)
        session.flush()
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

    def _apply_patch_intake_resolution(
        self,
        *,
        session: Session,
        run: RunRecord,
        task: TaskRecord,
        patch_intake: PatchIntakeRecord,
        patch_artifact: ArtifactRecord,
        receipt_artifact: ArtifactRecord,
        approval_mode: str,
    ) -> tuple[str, ObservationRecord, ArtifactRecord]:
        patch_body = Path(patch_artifact.path).read_text(encoding="utf-8")
        receipt_payload = json.loads(Path(receipt_artifact.path).read_text(encoding="utf-8"))
        apply_receipt = apply_patch_strict(
            workspace=Path(patch_intake.source_workspace),
            patch_body=patch_body,
            patch_sha256=patch_intake.patch_sha256,
            changed_files=list(patch_intake.changed_files),
            base_file_hashes=dict(receipt_payload.get("base_file_hashes", {})),
        )

        validation_artifact = self._persist_validation_receipt_artifact(
            session=session,
            run=run,
            task=task,
            patch_intake=patch_intake,
            patch_artifact=patch_artifact,
            receipt=apply_receipt,
        )
        patch_intake.validation_artifact_id = validation_artifact.id
        patch_intake.validation_command = apply_receipt.validation_command

        if apply_receipt.outcome == PatchApplyOutcome.APPLIED:
            patch_intake.status = PatchIntakeStatus.APPLIED
            patch_intake.resolved_at = apply_receipt.finished_at
            patch_intake.resolution_code = (
                PatchResolutionCode.AUTO_APPLIED
                if approval_mode == "auto"
                else PatchResolutionCode.FOUNDER_APPROVED
            )
            patch_intake.resolution_reason = apply_receipt.summary
            run.status = RunStatus.COMPLETED
            session.add(
                EventLedgerRecord(
                    run_id=run.id,
                    event_type=LedgerEventType.PATCH_INTAKE_APPLIED,
                    payload={
                        "patch_intake_id": patch_intake.id,
                        "task_id": task.id,
                        "patch_artifact_id": patch_artifact.id,
                        "validation_artifact_id": validation_artifact.id,
                        "resolution_code": patch_intake.resolution_code.value,
                    },
                ),
            )
            if approval_mode == "auto":
                summary = "Low-risk patch was auto-applied after strict validation."
                message = "Low-risk patch was auto-applied strictly and the run is now completed."
            else:
                summary = "Founder approved the patch intake and strict apply succeeded."
                message = "Patch was applied strictly and the run is now completed."
            observation = ObservationRecord(
                run_id=run.id,
                kind=ObservationKind.SYSTEM_AUDIT,
                summary=summary,
                details=(
                    f"error_code={patch_intake.resolution_code.value}; "
                    f"patch_intake_id={patch_intake.id}; "
                    f"validation_artifact_id={validation_artifact.id}; "
                    f"validation_command={apply_receipt.validation_command}."
                ),
            )
            session.add(observation)
            session.flush()
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
            return message, observation, validation_artifact

        resolution_map = {
            PatchApplyOutcome.BASE_HASH_CONFLICT: PatchResolutionCode.BASE_HASH_CONFLICT,
            PatchApplyOutcome.APPLY_CHECK_FAILED: PatchResolutionCode.APPLY_CHECK_FAILED,
            PatchApplyOutcome.VALIDATION_FAILED: PatchResolutionCode.VALIDATION_FAILED,
        }
        patch_intake.status = PatchIntakeStatus.REJECTED
        patch_intake.resolved_at = apply_receipt.finished_at
        patch_intake.resolution_code = resolution_map[apply_receipt.outcome]
        patch_intake.resolution_reason = self._build_patch_repair_feedback(
            patch_intake=patch_intake,
            apply_receipt=apply_receipt,
        )
        patch_intake.validation_command = apply_receipt.validation_command
        run.status = RunStatus.READY
        session.add(
            EventLedgerRecord(
                run_id=run.id,
                event_type=LedgerEventType.PATCH_INTAKE_REJECTED,
                payload={
                    "patch_intake_id": patch_intake.id,
                    "task_id": task.id,
                    "patch_artifact_id": patch_artifact.id,
                    "validation_artifact_id": validation_artifact.id,
                    "resolution_code": patch_intake.resolution_code.value,
                },
            ),
        )
        if approval_mode == "auto":
            summary = "Auto-apply candidate was rejected by strict apply or validation."
            message = patch_intake.resolution_reason or "Auto-apply candidate was rejected."
        else:
            summary = "Founder approved the patch review, but intake was rejected by strict apply or validation."
            message = patch_intake.resolution_reason or "Patch intake was rejected."
        observation = ObservationRecord(
            run_id=run.id,
            kind=ObservationKind.SYSTEM_AUDIT,
            summary=summary,
            details=(
                f"error_code={patch_intake.resolution_code.value}; "
                f"patch_intake_id={patch_intake.id}; "
                f"validation_artifact_id={validation_artifact.id}; "
                f"reason={patch_intake.resolution_reason}."
            ),
        )
        session.add(observation)
        session.flush()
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
        repair_failure_count = self._count_patch_repair_failures(
            session=session,
            run_id=run.id,
            changed_files=list(patch_intake.changed_files or []),
        )
        self._maybe_record_patch_repair_escalation(
            session=session,
            run=run,
            patch_intake=patch_intake,
            repair_failure_count=repair_failure_count,
        )
        session.flush()
        return message, observation, validation_artifact

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
    def _to_patch_intake_view(record: PatchIntakeRecord) -> PatchIntakeView:
        return PatchIntakeView.model_validate(
            {
                "id": record.id,
                "run_id": record.run_id,
                "task_id": record.task_id,
                "patch_artifact_id": record.patch_artifact_id,
                "receipt_artifact_id": record.receipt_artifact_id,
                "validation_artifact_id": record.validation_artifact_id,
                "status": record.status,
                "summary": record.summary,
                "source_workspace": record.source_workspace,
                "changed_files": list(record.changed_files or []),
                "touched_file_count": record.touched_file_count,
                "patch_size_bytes": record.patch_size_bytes,
                "patch_sha256": record.patch_sha256,
                "risk_class": record.risk_class,
                "auto_apply_eligible": record.auto_apply_eligible,
                "warnings": list(record.warnings or []),
                "created_at": record.created_at,
                "resolved_at": record.resolved_at,
                "resolution_code": record.resolution_code,
                "resolution_reason": record.resolution_reason,
                "validation_command": record.validation_command,
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
        patch_intakes: list[PatchIntakeView],
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
        patch_intake_recorded_ids = {
            str(event.payload.get("patch_intake_id"))
            for event in ledger_events
            if event.event_type == LedgerEventType.PATCH_INTAKE_RECORDED
        }

        if orphan_artifacts:
            warnings.append("At least one artifact is not linked to a known task.")

        if run.status == RunStatus.COMPLETED and not any(
            task.task.status == TaskStatus.COMPLETED for task in tasks
        ):
            warnings.append("Run is marked completed but no completed task is present.")
        if run.status == RunStatus.COMPLETED and any(
            intake.status == PatchIntakeStatus.PENDING for intake in patch_intakes
        ):
            warnings.append("Run is marked completed while a patch intake is still pending founder review.")

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
        for intake in patch_intakes:
            if str(intake.id) not in patch_intake_recorded_ids:
                warnings.append(
                    f"Patch intake {intake.id} exists in state but is missing PATCH_INTAKE_RECORDED in the ledger.",
                )
        return warnings

    @staticmethod
    def _build_planner_phase_key(
        *,
        run: RunView,
        pending_approval: ApprovalView | None,
        latest_rejection_reason: str | None,
        latest_patch_intake: PatchIntakeView | None,
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
            "latest_patch_intake": latest_patch_intake.model_dump(mode="json") if latest_patch_intake else None,
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
        execution_requirements: ExecutionRequirements | None,
    ) -> str:
        payload = {
            "snapshot_hash": snapshot_hash,
            "selected_action": selected_action.value,
            "rationale": rationale.strip(),
            "expected_outcome": expected_outcome.strip(),
            "execution_requirements": (
                execution_requirements.model_dump(mode="json") if execution_requirements is not None else None
            ),
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
        execution_requirements: ExecutionRequirements | None,
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
            "execution_requirements": (
                execution_requirements.model_dump(mode="json") if execution_requirements is not None else None
            ),
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
