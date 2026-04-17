from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArtifactType(StrEnum):
    TEXT_REPORT = "text_report"
    UNIFIED_PATCH = "unified_patch"
    EXECUTION_RECEIPT = "execution_receipt"
    VALIDATION_RECEIPT = "validation_receipt"


class ArtifactStorageKind(StrEnum):
    FILESYSTEM_PATH = "filesystem_path"


class ArtifactView(BaseModel):
    """Stable CLI-facing projection of a produced artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    task_id: UUID
    decision_id: UUID | None
    artifact_type: ArtifactType
    title: str = Field(min_length=1, max_length=200)
    storage_kind: ArtifactStorageKind
    path: str = Field(min_length=1, max_length=4000)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    execution_context_id: str = Field(min_length=1, max_length=120)
    command: str = Field(min_length=1, max_length=400)
    cwd: str = Field(min_length=1, max_length=4000)
    created_at: datetime

    @field_validator("title", "path", "execution_context_id", "command", "cwd")
    @classmethod
    def ensure_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("sha256")
    @classmethod
    def ensure_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("sha256 must be a 64-character hexadecimal string")
        return cleaned
