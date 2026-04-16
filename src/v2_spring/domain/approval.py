from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalView(BaseModel):
    """Stable CLI-facing projection of an approval gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    status: ApprovalStatus
    requested_action: str
    reason: str
    approve_effect: str
    reject_effect: str
    requested_at: datetime
    resolved_at: datetime | None

    @field_validator("requested_action", "reason", "approve_effect", "reject_effect")
    @classmethod
    def ensure_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned
