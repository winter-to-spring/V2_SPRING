from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskKind(StrEnum):
    REPOSITORY_SCAN = "repository_scan"
    ISOLATED_WORKER_PROOF = "isolated_worker_proof"
    CONTAINERIZED_WORKER_PROOF = "containerized_worker_proof"


class TaskStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskView(BaseModel):
    """Stable CLI-facing projection of a bounded execution task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    decision_id: UUID | None
    kind: TaskKind
    status: TaskStatus
    summary: str = Field(min_length=1, max_length=400)
    execution_context_id: str = Field(min_length=1, max_length=120)
    command: str = Field(min_length=1, max_length=400)
    cwd: str = Field(min_length=1, max_length=4000)
    timeout_seconds: int = Field(ge=1, le=300)
    stdout: str | None
    stderr: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @field_validator("summary", "execution_context_id", "command", "cwd")
    @classmethod
    def ensure_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("stdout", "stderr")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.rstrip()
