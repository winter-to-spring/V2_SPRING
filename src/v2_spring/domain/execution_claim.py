from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExecutionClaimStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    RECLAIMED = "reclaimed"
    EXPIRED = "expired"


class ExecutionClaimRenewalPressure(StrEnum):
    HEALTHY = "healthy"
    RENEW_WINDOW = "renew_window"
    COALESCED = "coalesced"


class ExecutionClaimView(BaseModel):
    """Compact, typed execution lease visible to founder/operator surfaces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    task_id: UUID | None
    runtime: str = Field(min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=120)
    lease_token: str = Field(min_length=1, max_length=120)
    fencing_token: int = Field(ge=1)
    status: ExecutionClaimStatus
    acquired_at: datetime
    heartbeat_at: datetime
    expires_at: datetime
    released_at: datetime | None
    reclaim_reason: str | None = Field(default=None, max_length=1000)
    renew_threshold_seconds: int | None = Field(default=None, ge=1, le=600)
    min_renew_cadence_seconds: int | None = Field(default=None, ge=1, le=600)
    renewal_pressure: ExecutionClaimRenewalPressure | None = None

    @field_validator("runtime", "owner", "lease_token", "reclaim_reason")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class ExecutionClaimRefusalCode(StrEnum):
    ACTIVE_CLAIM_HELD = "active_claim_held"


class ExecutionClaimRefusalView(BaseModel):
    """Typed refusal returned when a competing execution claim blocks dispatch or mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ExecutionClaimRefusalCode
    message: str = Field(min_length=1, max_length=400)
    existing_claim: ExecutionClaimView

    @field_validator("message")
    @classmethod
    def ensure_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned
