from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from v2_spring.domain.approval import ApprovalView
from v2_spring.domain.execution_claim import ExecutionClaimView
from v2_spring.domain.founder_intervention import FounderInterventionDigest
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.run import RunView
from v2_spring.domain.snapshot import (
    ArtifactHeadlineView,
    PendingFounderEscalationView,
    PendingPatchIntakeView,
    SnapshotActionState,
)


class ProgressSurfaceStatus(StrEnum):
    """Founder/operator-facing top-level status with blocker ownership baked in."""

    WAITING_ON_FOUNDER = "waiting_on_founder"
    WAITING_ON_APPROVAL = "waiting_on_approval"
    SUSPENDED_ON_TIMEOUT = "suspended_on_timeout"
    READY_FOR_NEXT_ACTION = "ready_for_next_action"
    RUNNING_EXECUTION = "running_execution"
    COMPLETED = "completed"
    FAILED = "failed"
    IDLE = "idle"


class ProgressActionOwner(StrEnum):
    """Who should act next to move the run forward."""

    FOUNDER = "founder"
    SYSTEM = "system"
    EXECUTOR = "executor"
    NONE = "none"


class ProgressTraceMode(StrEnum):
    """How much diagnostic detail was included in the projection."""

    SUMMARY = "summary"
    TRACE = "trace"
    RAW = "raw"


class ProgressAuditItemView(BaseModel):
    """Compact audit/event digest safe for the founder-facing progress surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: UUID
    kind: ObservationKind
    created_at: datetime
    error_code: str | None = Field(default=None, max_length=120)
    summary: str = Field(min_length=1, max_length=400)
    detail_preview: str | None = Field(default=None, max_length=500)
    raw_detail: str | None = Field(default=None, max_length=4000)

    @field_validator("error_code", "summary", "detail_preview", "raw_detail")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class ProgressCommandHintView(BaseModel):
    """One founder/operator command suggestion emitted by the progress surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    command: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=400)

    @field_validator("label", "command", "purpose")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class ProgressSummaryView(BaseModel):
    """On-the-fly founder/operator cockpit view derived from current ledger-backed state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    trace_mode: ProgressTraceMode
    run: RunView
    snapshot_hash: str = Field(min_length=64, max_length=64)
    snapshot_generation: int = Field(ge=0)
    action_state: SnapshotActionState
    surface_status: ProgressSurfaceStatus
    action_required_by: ProgressActionOwner
    headline: str = Field(min_length=1, max_length=400)
    blocker_reason: str | None = Field(default=None, max_length=500)
    next_step_hint: str | None = Field(default=None, max_length=500)
    pending_approval: ApprovalView | None = None
    pending_founder_escalation: PendingFounderEscalationView | None = None
    pending_patch_intake: PendingPatchIntakeView | None = None
    active_execution_claim: ExecutionClaimView | None = None
    planner_budget_remaining: int = Field(ge=0)
    planner_phase_exhausted: bool = False
    planner_stale_quota_remaining: int = Field(ge=0)
    latest_planner_summary: str | None = Field(default=None, max_length=400)
    latest_execution_summary: str | None = Field(default=None, max_length=500)
    latest_artifact: ArtifactHeadlineView | None = None
    recent_artifacts: list[ArtifactHeadlineView]
    recent_founder_interventions: list[FounderInterventionDigest]
    recent_audits: list[ProgressAuditItemView]
    suggested_commands: list[ProgressCommandHintView]
    consistency_warnings: list[str]
    trace_entries: list[ProgressAuditItemView]

    @field_validator(
        "snapshot_hash",
    )
    @classmethod
    def ensure_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("value must be a 64-character hexadecimal string")
        return cleaned

    @field_validator(
        "headline",
        "blocker_reason",
        "next_step_hint",
        "latest_planner_summary",
        "latest_execution_summary",
    )
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned

    @field_validator("consistency_warnings")
    @classmethod
    def ensure_warning_text(cls, values: list[str]) -> list[str]:
        cleaned_values: list[str] = []
        for value in values:
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("consistency warnings must not be blank")
            cleaned_values.append(cleaned)
        return cleaned_values
