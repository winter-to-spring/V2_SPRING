from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from v2_spring.domain.founder_intervention import FounderReplyKind
from v2_spring.domain.snapshot import PossibleActionName


class PlannerAttemptOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED_STALE = "rejected_stale"
    REJECTED_ILLEGAL = "rejected_illegal"
    REJECTED_FORMAT = "rejected_format"
    REJECTED_DUPLICATE_TRANSPORT = "rejected_duplicate_transport"
    REJECTED_DUPLICATE_COGNITIVE = "rejected_duplicate_cognitive"
    PHASE_EXHAUSTED = "phase_exhausted"
    MANUAL_RECHARGE = "manual_recharge"


class PlannerAttemptView(BaseModel):
    """Immutable planner-governance trace for one attempt within a phase."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    phase_key: str = Field(min_length=64, max_length=64)
    policy_version: str = Field(min_length=1, max_length=100)
    snapshot_hash: str = Field(min_length=64, max_length=64)
    selected_action: PossibleActionName | None
    submission_key: str | None = Field(default=None, max_length=120)
    proposal_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    outcome: PlannerAttemptOutcome
    outcome_reason: str = Field(min_length=1, max_length=4000)
    attempt_index: int = Field(ge=1)
    budget_limit: int = Field(ge=1)
    budget_used: int = Field(ge=0)
    budget_remaining: int = Field(ge=0)
    created_at: datetime

    @field_validator("phase_key", "snapshot_hash", "proposal_fingerprint")
    @classmethod
    def ensure_optional_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("value must be a 64-character hexadecimal string")
        return cleaned

    @field_validator("policy_version", "outcome_reason", "submission_key")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class PlannerGovernanceView(BaseModel):
    """Current phase-scoped planner governance summary for one run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID
    phase_key: str = Field(min_length=64, max_length=64)
    policy_version: str = Field(min_length=1, max_length=100)
    budget_limit: int = Field(ge=1)
    budget_used: int = Field(ge=0)
    budget_remaining: int = Field(ge=0)
    exhausted: bool
    stale_quota_limit: int = Field(ge=1)
    stale_quota_used: int = Field(ge=0)
    stale_quota_remaining: int = Field(ge=0)
    stale_quota_exhausted: bool
    recharge_count: int = Field(ge=0)
    latest_attempt_summary: str | None = Field(default=None, max_length=4000)
    attempts: list[PlannerAttemptView]

    @field_validator("phase_key")
    @classmethod
    def ensure_phase_key(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("phase_key must be a 64-character hexadecimal string")
        return cleaned

    @field_validator("policy_version", "latest_attempt_summary")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class PlannerRechargeCautionCode(StrEnum):
    """Structured caution codes that explain why recharge needs extra care."""

    REPEATED_RECHARGE = "repeated_recharge"
    DETERMINISTIC_FAILURE = "deterministic_failure"
    LATEST_REJECTION_PRESENT = "latest_rejection_present"
    PRIOR_FOUNDER_REJECT = "prior_founder_reject"


class PlannerRechargePreflightView(BaseModel):
    """Founder-readable recharge guidance before reopening an exhausted phase."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID
    phase_key: str = Field(min_length=64, max_length=64)
    policy_version: str = Field(min_length=1, max_length=100)
    exhausted: bool
    budget_limit: int = Field(ge=1)
    budget_used: int = Field(ge=0)
    budget_remaining: int = Field(ge=0)
    recharge_count: int = Field(ge=0)
    latest_attempt_summary: str | None = Field(default=None, max_length=4000)
    latest_failure_error_code: str | None = Field(default=None, max_length=120)
    latest_failure_summary: str | None = Field(default=None, max_length=500)
    latest_failure_deterministic: bool | None = None
    latest_rejection_reason: str | None = Field(default=None, max_length=4000)
    latest_founder_intervention_kind: FounderReplyKind | None = None
    latest_founder_intervention_summary: str | None = Field(default=None, max_length=400)
    caution_codes: list[PlannerRechargeCautionCode]
    requires_acknowledgement: bool
    guidance: list[str]

    @field_validator("phase_key")
    @classmethod
    def ensure_phase_key(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("phase_key must be a 64-character hexadecimal string")
        return cleaned

    @field_validator(
        "policy_version",
        "latest_attempt_summary",
        "latest_failure_error_code",
        "latest_failure_summary",
        "latest_rejection_reason",
        "latest_founder_intervention_summary",
    )
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned

    @field_validator("guidance")
    @classmethod
    def ensure_guidance(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("guidance must contain at least one item")
        cleaned_items: list[str] = []
        for item in value:
            cleaned = item.strip()
            if not cleaned:
                raise ValueError("guidance items must not be blank")
            cleaned_items.append(cleaned)
        return cleaned_items
