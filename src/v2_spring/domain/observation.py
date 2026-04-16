from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ObservationKind(StrEnum):
    RUN_INTAKE = "run_intake"
    FOLLOW_UP = "follow_up"
    SYSTEM_AUDIT = "system_audit"


class ObservationView(BaseModel):
    """Stable CLI-facing projection of a recorded observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    kind: ObservationKind
    summary: str
    details: str
    created_at: datetime

    @field_validator("summary", "details")
    @classmethod
    def ensure_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned
