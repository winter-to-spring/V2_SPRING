from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.artifact import ArtifactStorageKind, ArtifactType
from v2_spring.domain.decision import DecisionKind
from v2_spring.domain.execution_claim import ExecutionClaimStatus
from v2_spring.domain.founder_intervention import FounderReplyKind
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.patch_intake import PatchIntakeStatus, PatchResolutionCode, PatchRiskClass
from v2_spring.domain.planner_attempt import PlannerAttemptOutcome
from v2_spring.domain.routing import ExecutionRuntime
from v2_spring.domain.run import RiskLevel, RunStatus, UrgencyLevel
from v2_spring.domain.runtime_trust import RuntimeTrustMode
from v2_spring.domain.task import TaskKind, TaskStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class LedgerEventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    OBSERVATION_RECORDED = "OBSERVATION_RECORDED"
    DECISION_RECORDED = "DECISION_RECORDED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_RESOLVED = "APPROVAL_RESOLVED"
    TASK_CREATED = "TASK_CREATED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    ARTIFACT_RECORDED = "ARTIFACT_RECORDED"
    PATCH_INTAKE_RECORDED = "PATCH_INTAKE_RECORDED"
    PATCH_INTAKE_APPLIED = "PATCH_INTAKE_APPLIED"
    PATCH_INTAKE_REJECTED = "PATCH_INTAKE_REJECTED"
    PLANNER_ATTEMPT_RECORDED = "PLANNER_ATTEMPT_RECORDED"
    FOUNDER_INTERVENTION_RECORDED = "FOUNDER_INTERVENTION_RECORDED"
    EXECUTION_CLAIM_ACQUIRED = "EXECUTION_CLAIM_ACQUIRED"
    EXECUTION_CLAIM_RENEWED = "EXECUTION_CLAIM_RENEWED"
    EXECUTION_CLAIM_RELEASED = "EXECUTION_CLAIM_RELEASED"
    EXECUTION_CLAIM_RECLAIMED = "EXECUTION_CLAIM_RECLAIMED"
    EXECUTION_RESULT_REJECTED = "EXECUTION_RESULT_REJECTED"


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project: Mapped[str] = mapped_column(String(120), nullable=False)
    goal: Mapped[str] = mapped_column(String(4000), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False),
        nullable=False,
        default=RunStatus.CREATED,
    )
    urgency: Mapped[UrgencyLevel] = mapped_column(
        Enum(UrgencyLevel, native_enum=False),
        nullable=False,
    )
    risk: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    ledger_events: Mapped[list["EventLedgerRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    decisions: Mapped[list["DecisionRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    observations: Mapped[list["ObservationRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[list["ApprovalRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[list["TaskRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[list["ArtifactRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    patch_intakes: Mapped[list["PatchIntakeRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    planner_attempts: Mapped[list["PlannerAttemptRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    founder_interventions: Mapped[list["FounderInterventionRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    execution_claims: Mapped[list["ExecutionClaimRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class DecisionRecord(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[DecisionKind] = mapped_column(
        Enum(DecisionKind, native_enum=False),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    rationale: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="decisions")


class ObservationRecord(Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[ObservationKind] = mapped_column(
        Enum(ObservationKind, native_enum=False),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    details: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="observations")


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, native_enum=False),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    requested_action: Mapped[str] = mapped_column(String(400), nullable=False)
    reason: Mapped[str] = mapped_column(String(4000), nullable=False)
    approve_effect: Mapped[str] = mapped_column(String(4000), nullable=False)
    reject_effect: Mapped[str] = mapped_column(String(4000), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    run: Mapped[RunRecord] = relationship(back_populates="approvals")


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[TaskKind] = mapped_column(
        Enum(TaskKind, native_enum=False),
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False),
        nullable=False,
        default=TaskStatus.CREATED,
    )
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    execution_context_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    execution_claim_token: Mapped[str | None] = mapped_column(String(120), nullable=True)
    execution_claim_fencing_token: Mapped[int | None] = mapped_column(nullable=True)
    command: Mapped[str] = mapped_column(String(400), nullable=False)
    cwd: Mapped[str] = mapped_column(String(4000), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(nullable=False)
    stdout: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    stderr: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[RunRecord] = relationship(back_populates="tasks")
    decision: Mapped["DecisionRecord | None"] = relationship()
    artifacts: Mapped[list["ArtifactRecord"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    patch_intakes: Mapped[list["PatchIntakeRecord"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    execution_claims: Mapped[list["ExecutionClaimRecord"]] = relationship(back_populates="task")


class ExecutionClaimRecord(Base):
    __tablename__ = "execution_claims"
    __table_args__ = (
        Index("ix_execution_claims_status_expires_at", "status", "expires_at"),
        Index("ix_execution_claims_runtime_status", "runtime", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    runtime: Mapped[str] = mapped_column(String(120), nullable=False)
    owner: Mapped[str] = mapped_column(String(120), nullable=False)
    lease_token: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[ExecutionClaimStatus] = mapped_column(
        Enum(ExecutionClaimStatus, native_enum=False),
        nullable=False,
        default=ExecutionClaimStatus.ACTIVE,
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reclaim_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    run: Mapped[RunRecord] = relationship(back_populates="execution_claims")
    task: Mapped["TaskRecord | None"] = relationship(back_populates="execution_claims")


class RuntimeTrustRecord(Base):
    __tablename__ = "runtime_trust"

    runtime: Mapped[ExecutionRuntime] = mapped_column(
        Enum(ExecutionRuntime, native_enum=False),
        primary_key=True,
    )
    mode: Mapped[RuntimeTrustMode] = mapped_column(
        Enum(RuntimeTrustMode, native_enum=False),
        nullable=False,
        default=RuntimeTrustMode.STATIC_MANIFEST,
    )
    dynamic_preflight_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    mismatch_strike_threshold: Mapped[int] = mapped_column(nullable=False, default=3)
    recovery_success_threshold: Mapped[int] = mapped_column(nullable=False, default=2)
    consecutive_mismatch_failures: Mapped[int] = mapped_column(nullable=False, default=0)
    total_mismatch_failures: Mapped[int] = mapped_column(nullable=False, default=0)
    recovery_success_streak: Mapped[int] = mapped_column(nullable=False, default=0)
    last_failure_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class ArtifactRecord(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(ArtifactType, native_enum=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_kind: Mapped[ArtifactStorageKind] = mapped_column(
        Enum(ArtifactStorageKind, native_enum=False),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(4000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_context_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    command: Mapped[str] = mapped_column(String(400), nullable=False)
    cwd: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="artifacts")
    task: Mapped[TaskRecord] = relationship(back_populates="artifacts")
    decision: Mapped["DecisionRecord | None"] = relationship()


class PatchIntakeRecord(Base):
    __tablename__ = "patch_intakes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patch_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receipt_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validation_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[PatchIntakeStatus] = mapped_column(
        Enum(PatchIntakeStatus, native_enum=False),
        nullable=False,
        default=PatchIntakeStatus.PENDING,
    )
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    source_workspace: Mapped[str] = mapped_column(String(4000), nullable=False)
    changed_files: Mapped[list[Any]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    touched_file_count: Mapped[int] = mapped_column(nullable=False)
    patch_size_bytes: Mapped[int] = mapped_column(nullable=False)
    patch_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_class: Mapped[PatchRiskClass] = mapped_column(
        Enum(PatchRiskClass, native_enum=False),
        nullable=False,
    )
    auto_apply_eligible: Mapped[bool] = mapped_column(nullable=False, default=False)
    warnings: Mapped[list[Any]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_code: Mapped[PatchResolutionCode | None] = mapped_column(
        Enum(PatchResolutionCode, native_enum=False),
        nullable=True,
    )
    resolution_reason: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    validation_command: Mapped[str | None] = mapped_column(String(400), nullable=True)

    run: Mapped[RunRecord] = relationship(back_populates="patch_intakes")
    task: Mapped[TaskRecord] = relationship(back_populates="patch_intakes")
    patch_artifact: Mapped[ArtifactRecord] = relationship(
        foreign_keys=[patch_artifact_id],
    )
    receipt_artifact: Mapped[ArtifactRecord] = relationship(
        foreign_keys=[receipt_artifact_id],
    )
    validation_artifact: Mapped[ArtifactRecord | None] = relationship(
        foreign_keys=[validation_artifact_id],
    )


class EventLedgerRecord(Base):
    __tablename__ = "event_ledger"
    __table_args__ = (
        Index("ix_event_ledger_run_recorded_at", "run_id", "recorded_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[LedgerEventType] = mapped_column(
        Enum(LedgerEventType, native_enum=False),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="ledger_events")


class PlannerAttemptRecord(Base):
    __tablename__ = "planner_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_action: Mapped[str | None] = mapped_column(String(120), nullable=True)
    submission_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    proposal_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    outcome: Mapped[PlannerAttemptOutcome] = mapped_column(
        Enum(PlannerAttemptOutcome, native_enum=False),
        nullable=False,
    )
    outcome_reason: Mapped[str] = mapped_column(String(4000), nullable=False)
    attempt_index: Mapped[int] = mapped_column(nullable=False)
    budget_limit: Mapped[int] = mapped_column(nullable=False)
    budget_used: Mapped[int] = mapped_column(nullable=False)
    budget_remaining: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="planner_attempts")


class FounderInterventionRecord(Base):
    __tablename__ = "founder_interventions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_observation_id: Mapped[str] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    phase_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    reply_kind: Mapped[FounderReplyKind] = mapped_column(
        Enum(FounderReplyKind, native_enum=False),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    detail: Mapped[str] = mapped_column(String(4000), nullable=False)
    override_action: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="founder_interventions")
    target_observation: Mapped["ObservationRecord"] = relationship()


def _prevent_mutation(_: Any, __: Any, target: EventLedgerRecord) -> None:
    raise ValueError(
        f"EventLedgerRecord {target.id} is append-only and cannot be mutated or deleted.",
    )


event.listen(EventLedgerRecord, "before_update", _prevent_mutation)
event.listen(EventLedgerRecord, "before_delete", _prevent_mutation)
event.listen(DecisionRecord, "before_update", _prevent_mutation)
event.listen(DecisionRecord, "before_delete", _prevent_mutation)
event.listen(ObservationRecord, "before_update", _prevent_mutation)
event.listen(ObservationRecord, "before_delete", _prevent_mutation)
event.listen(ArtifactRecord, "before_update", _prevent_mutation)
event.listen(ArtifactRecord, "before_delete", _prevent_mutation)
event.listen(PlannerAttemptRecord, "before_update", _prevent_mutation)
event.listen(PlannerAttemptRecord, "before_delete", _prevent_mutation)
event.listen(FounderInterventionRecord, "before_update", _prevent_mutation)
event.listen(FounderInterventionRecord, "before_delete", _prevent_mutation)
