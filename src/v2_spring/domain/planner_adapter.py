from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from v2_spring.domain.planner_attempt import PlannerAttemptOutcome
from v2_spring.domain.snapshot import PossibleActionName, PossibleActionView, RunSnapshotView


class PlannerConfidence(StrEnum):
    """Bounded confidence levels for founder-readable planner output."""

    LOW_NEEDS_REVIEW = "low_needs_review"
    MEDIUM = "medium"
    HIGH = "high"


class FailureClass(StrEnum):
    """Normalized failure buckets fed back into the planner."""

    DETERMINISTIC_RUNTIME = "deterministic_runtime"
    TRANSIENT_INFRASTRUCTURE = "transient_infrastructure"
    UNKNOWN_RUNTIME = "unknown_runtime"


class EscalationHelpKind(StrEnum):
    """Structured founder-help taxonomy for bounded escalations."""

    CLARIFICATION = "clarification"
    POLICY_DECISION = "policy_decision"
    EXTERNAL_DEPENDENCY = "external_dependency"
    MISSING_CREDENTIAL = "missing_credential"
    MANUAL_OVERRIDE_REQUEST = "manual_override_request"


class FailureReportView(BaseModel):
    """Small, sanitized failure report suitable for planner self-correction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    failure_class: FailureClass
    error_code: str = Field(min_length=1, max_length=120)
    short_traceback: str | None = Field(default=None, max_length=500)
    normalized_failure_signature: str = Field(min_length=64, max_length=64)
    previous_rationale: str | None = Field(default=None, max_length=4000)
    observed_outcome: str = Field(min_length=1, max_length=500)
    repeated_failure_streak: int = Field(ge=1)
    deterministic: bool

    @field_validator(
        "error_code",
        "short_traceback",
        "previous_rationale",
        "observed_outcome",
    )
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned

    @field_validator("normalized_failure_signature")
    @classmethod
    def ensure_signature(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("value must be a 64-character hexadecimal string")
        return cleaned


class PlannerAttemptDigest(BaseModel):
    """Recent planner attempts distilled for bounded planner context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: PlannerAttemptOutcome
    selected_action: PossibleActionName | None
    outcome_reason: str = Field(min_length=1, max_length=600)
    created_at: datetime

    @field_validator("outcome_reason")
    @classmethod
    def ensure_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class MaskedActionView(BaseModel):
    """One legal action that is temporarily hidden from the planner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: PossibleActionName
    reason: str = Field(min_length=1, max_length=400)

    @field_validator("reason")
    @classmethod
    def ensure_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class PlannerContextWindow(BaseModel):
    """Bounded planner-ready context assembled from deterministic state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot: RunSnapshotView
    legal_actions: list[PossibleActionView]
    masked_actions: list[MaskedActionView]
    recent_attempts: list[PlannerAttemptDigest]
    latest_rejection_reason: str | None = Field(default=None, max_length=4000)
    failure_report: FailureReportView | None = None
    stale_quota_limit: int = Field(ge=1)
    stale_quota_used: int = Field(ge=0)
    stale_quota_remaining: int = Field(ge=0)

    @field_validator("latest_rejection_reason")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class ActionProposal(BaseModel):
    """Planner-selected legal action with bounded reasoning metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["action"]
    analysis_summary: str = Field(min_length=1, max_length=4000)
    confidence: PlannerConfidence
    selected_action: PossibleActionName
    expected_outcome: str = Field(min_length=1, max_length=4000)

    @field_validator("analysis_summary", "expected_outcome")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class EscalationProposal(BaseModel):
    """Planner request for founder help when no safe next action is clear."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["escalation"]
    analysis_summary: str = Field(min_length=1, max_length=4000)
    confidence: PlannerConfidence
    escalation_target: Literal["founder"] = "founder"
    help_kind: EscalationHelpKind
    blocking_reason: str = Field(min_length=1, max_length=4000)
    requested_help: str = Field(min_length=1, max_length=4000)

    @field_validator("analysis_summary", "blocking_reason", "requested_help")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


PlannerAdapterOutput = Annotated[ActionProposal | EscalationProposal, Field(discriminator="kind")]
PLANNER_ADAPTER_OUTPUT_ADAPTER = TypeAdapter(PlannerAdapterOutput)


class PlannerInvocationProofView(BaseModel):
    """CLI-facing proof bundle for one adapter invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID
    policy_version: str = Field(min_length=1, max_length=100)
    snapshot_hash: str = Field(min_length=64, max_length=64)
    context_window: PlannerContextWindow
    parsed_output: PlannerAdapterOutput
    format_failures: int = Field(ge=0)
    accepted_decision_id: UUID | None = None
    escalation_observation_id: UUID | None = None
    stale_quota_exhausted: bool = False

    @field_validator("policy_version")
    @classmethod
    def ensure_policy_version(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("snapshot_hash")
    @classmethod
    def ensure_hash(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("snapshot_hash must be a 64-character hexadecimal string")
        return cleaned
