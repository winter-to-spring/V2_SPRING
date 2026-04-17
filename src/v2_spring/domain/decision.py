from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DecisionKind(StrEnum):
    INTAKE_ACCEPTED = "intake_accepted"
    FOLLOW_UP = "follow_up"
    BOUNDED_TASK_SELECTED = "bounded_task_selected"
    ISOLATED_WORKER_SELECTED = "isolated_worker_selected"
    CONTAINERIZED_WORKER_SELECTED = "containerized_worker_selected"
    PLANNER_PROPOSAL_ACCEPTED = "planner_proposal_accepted"
    FOUNDER_OVERRIDE_ACCEPTED = "founder_override_accepted"


class DecisionView(BaseModel):
    """Stable CLI-facing projection of a recorded decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    kind: DecisionKind
    summary: str
    rationale: str
    created_at: datetime

    @field_validator("summary", "rationale")
    @classmethod
    def ensure_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned
