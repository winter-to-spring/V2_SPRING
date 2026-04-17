from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from v2_spring.domain.actions import PossibleActionName
from v2_spring.domain.approval import ApprovalView
from v2_spring.domain.founder_intervention import FounderInterventionDigest
from v2_spring.domain.artifact import ArtifactType
from v2_spring.domain.execution_claim import ExecutionClaimView
from v2_spring.domain.patch_intake import PatchIntakeStatus, PatchRiskClass
from v2_spring.domain.run import RunView
from v2_spring.domain.task import TaskKind, TaskStatus


class SnapshotActionState(StrEnum):
    AVAILABLE = "available"
    BLOCKED = "blocked"
    TERMINAL = "terminal"
    STUCK = "stuck"


class TaskStatusSummary(BaseModel):
    """Compact task counts so snapshots stay planner-friendly and bounded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    created: int = Field(ge=0, default=0)
    ready: int = Field(ge=0, default=0)
    running: int = Field(ge=0, default=0)
    completed: int = Field(ge=0, default=0)
    failed: int = Field(ge=0, default=0)


class TaskHeadlineView(BaseModel):
    """Small task projection safe to surface to planners and founders."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    kind: TaskKind
    status: TaskStatus
    summary: str = Field(min_length=1, max_length=400)
    started_at: datetime | None
    completed_at: datetime | None
    failure_hint: str | None

    @field_validator("summary")
    @classmethod
    def ensure_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class ArtifactHeadlineView(BaseModel):
    """Small artifact projection that avoids exposing internal paths."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    artifact_type: ArtifactType
    title: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0)
    file_exists: bool
    hash_matches: bool | None

    @field_validator("title")
    @classmethod
    def ensure_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class PendingFounderEscalationView(BaseModel):
    """Open planner escalation that still requires founder intervention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: UUID
    summary: str = Field(min_length=1, max_length=400)
    details: str = Field(min_length=1, max_length=1000)
    created_at: datetime

    @field_validator("summary", "details")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class PendingPatchIntakeView(BaseModel):
    """Open patch intake that still requires founder review before apply/reject."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intake_id: UUID
    task_id: UUID
    patch_artifact_id: UUID
    summary: str = Field(min_length=1, max_length=400)
    risk_class: PatchRiskClass
    warning_count: int = Field(ge=0)
    touched_file_count: int = Field(ge=0)
    created_at: datetime

    @field_validator("summary")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class SnapshotFreshnessView(BaseModel):
    """Bounded freshness token carried between founder surfaces and mutations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_hash: str = Field(min_length=64, max_length=64)
    freshness_generation: int = Field(ge=0)

    @field_validator("snapshot_hash")
    @classmethod
    def ensure_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("snapshot_hash must be a 64-character hexadecimal string")
        return cleaned


class SnapshotFreshnessRefusalCode(StrEnum):
    STALE_SNAPSHOT = "stale_snapshot"


class SnapshotFreshnessRefusalView(BaseModel):
    """Typed refusal emitted when a founder/action uses a stale snapshot anchor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: SnapshotFreshnessRefusalCode
    mutation_name: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=500)
    expected: SnapshotFreshnessView
    current: SnapshotFreshnessView

    @field_validator("mutation_name", "message")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class SnapshotFreshnessConflictError(PermissionError):
    """Raised when a founder/operator mutation is attempted from a stale snapshot."""

    def __init__(self, refusal: SnapshotFreshnessRefusalView) -> None:
        super().__init__(refusal.message)
        self.refusal = refusal


class RunSnapshotView(BaseModel):
    """Planner-ready, founder-readable snapshot of current run state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_timestamp: datetime
    policy_version: str = Field(min_length=1, max_length=100)
    state_hash: str = Field(min_length=64, max_length=64)
    freshness_generation: int = Field(ge=0)
    run: RunView
    action_state: SnapshotActionState
    action_state_reason: str = Field(min_length=1, max_length=400)
    pending_approval: ApprovalView | None
    pending_founder_escalation: PendingFounderEscalationView | None
    pending_patch_intake: PendingPatchIntakeView | None
    active_execution_claim: ExecutionClaimView | None = None
    latest_founder_intervention_summary: str | None
    latest_rejection_reason: str | None
    latest_decision_summary: str | None
    latest_patch_intake_status: PatchIntakeStatus | None = None
    latest_patch_intake_summary: str | None = None
    latest_patch_rejection_reason: str | None = None
    planner_phase_key: str = Field(min_length=64, max_length=64)
    planner_budget_limit: int = Field(ge=1)
    planner_budget_used: int = Field(ge=0)
    planner_budget_remaining: int = Field(ge=0)
    planner_phase_exhausted: bool = False
    planner_stale_quota_limit: int = Field(ge=1)
    planner_stale_quota_used: int = Field(ge=0)
    planner_stale_quota_remaining: int = Field(ge=0)
    planner_stale_quota_exhausted: bool = False
    latest_planner_attempt_summary: str | None
    task_summary: TaskStatusSummary
    latest_task: TaskHeadlineView | None
    latest_artifact: ArtifactHeadlineView | None
    recent_founder_interventions: list[FounderInterventionDigest]

    @field_validator("state_hash", "planner_phase_key")
    @classmethod
    def ensure_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("value must be a 64-character hexadecimal string")
        return cleaned

    @field_validator(
        "policy_version",
        "action_state_reason",
        "latest_founder_intervention_summary",
        "latest_rejection_reason",
        "latest_decision_summary",
        "latest_patch_intake_summary",
        "latest_patch_rejection_reason",
        "latest_planner_attempt_summary",
    )
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class PossibleActionView(BaseModel):
    """One legal next move derived from the deterministic substrate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: PossibleActionName
    reason: str = Field(min_length=1, max_length=400)
    context_hint: str | None = Field(default=None, max_length=4000)

    @field_validator("reason", "context_hint")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class PossibleActionEvaluationView(BaseModel):
    """Deterministic legal moves for the current run snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot: RunSnapshotView
    actions: list[PossibleActionView]
