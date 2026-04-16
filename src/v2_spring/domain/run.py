from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UrgencyLevel(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RunStatus(StrEnum):
    CREATED = "created"
    WAITING_APPROVAL = "waiting_approval"
    READY = "ready"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunCreateInput(BaseModel):
    """Validated input for creating a new run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=4000)
    urgency: UrgencyLevel
    risk: RiskLevel

    @field_validator("project", "goal")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class RunView(BaseModel):
    """Stable CLI-facing projection of a stored run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project: str
    goal: str
    status: RunStatus
    urgency: UrgencyLevel
    risk: RiskLevel
    created_at: datetime
    updated_at: datetime
