from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from v2_spring.domain.routing import ExecutionRuntime


class RuntimeTrustMode(StrEnum):
    STATIC_MANIFEST = "static_manifest"
    DYNAMIC_PROMOTED = "dynamic_promoted"


class RuntimeTrustView(BaseModel):
    """Founder/operator-facing trust state for one execution runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime: ExecutionRuntime
    mode: RuntimeTrustMode
    dynamic_preflight_required: bool = False
    mismatch_strike_threshold: int = Field(ge=1, le=20)
    recovery_success_threshold: int = Field(ge=1, le=20)
    consecutive_mismatch_failures: int = Field(ge=0)
    total_mismatch_failures: int = Field(ge=0)
    recovery_success_streak: int = Field(ge=0)
    last_failure_reason: str | None = Field(default=None, max_length=240)
    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None

    @field_validator("last_failure_reason")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("last_failure_reason must not be blank when provided")
        return cleaned
