from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatchIntakeStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"


class PatchRiskClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PatchWarningCode(StrEnum):
    DANGEROUS_KEYWORD = "dangerous_keyword"
    SENSITIVE_PATH = "sensitive_path"
    CENTRAL_FILE = "central_file"
    LARGE_PATCH = "large_patch"
    MANY_FILES = "many_files"
    AUTO_APPLY_BURST = "auto_apply_burst"
    STRUCTURAL_DANGER = "structural_danger"
    STRUCTURAL_WARNING = "structural_warning"


class PatchResolutionCode(StrEnum):
    AUTO_APPLIED = "auto_applied"
    FOUNDER_APPROVED = "founder_approved"
    FOUNDER_REJECTED = "founder_rejected"
    BASE_HASH_CONFLICT = "base_hash_conflict"
    APPLY_CHECK_FAILED = "apply_check_failed"
    VALIDATION_FAILED = "validation_failed"


class PatchReviewWarningView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: PatchWarningCode
    message: str = Field(min_length=1, max_length=400)

    @field_validator("message")
    @classmethod
    def ensure_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned


class PatchIntakeView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    task_id: UUID
    patch_artifact_id: UUID
    receipt_artifact_id: UUID
    validation_artifact_id: UUID | None
    status: PatchIntakeStatus
    summary: str = Field(min_length=1, max_length=400)
    source_workspace: str = Field(min_length=1, max_length=4000)
    changed_files: list[str]
    touched_file_count: int = Field(ge=0)
    patch_size_bytes: int = Field(ge=0)
    patch_sha256: str = Field(min_length=64, max_length=64)
    risk_class: PatchRiskClass
    auto_apply_eligible: bool = False
    warnings: list[PatchReviewWarningView]
    created_at: datetime
    resolved_at: datetime | None
    resolution_code: PatchResolutionCode | None = None
    resolution_reason: str | None = Field(default=None, max_length=4000)
    validation_command: str | None = Field(default=None, max_length=400)

    @field_validator("summary", "source_workspace", "resolution_reason", "validation_command")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned

    @field_validator("changed_files")
    @classmethod
    def ensure_changed_files(cls, value: list[str]) -> list[str]:
        cleaned_values: list[str] = []
        for item in value:
            cleaned = item.strip()
            if not cleaned:
                raise ValueError("changed_files entries must not be blank")
            cleaned_values.append(cleaned)
        return cleaned_values

    @field_validator("patch_sha256")
    @classmethod
    def ensure_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("patch_sha256 must be a 64-character hexadecimal string")
        return cleaned


class PendingPatchIntakeView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intake_id: UUID
    task_id: UUID
    patch_artifact_id: UUID
    summary: str = Field(min_length=1, max_length=400)
    risk_class: PatchRiskClass
    warning_count: int = Field(ge=0)
    touched_file_count: int = Field(ge=0)
    created_at: datetime

    @field_validator("summary")
    @classmethod
    def ensure_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("summary must not be blank")
        return cleaned


class PatchReviewView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intake: PatchIntakeView
    snapshot_hash: str = Field(min_length=64, max_length=64)
    freshness_generation: int = Field(ge=0)
    patch_body: str = Field(min_length=1, max_length=200000)
    receipt_preview: str = Field(min_length=1, max_length=2000)
    changed_lines_added: int = Field(ge=0)
    changed_lines_removed: int = Field(ge=0)
    raw_receipt: str | None = Field(default=None, max_length=40000)

    @field_validator("snapshot_hash")
    @classmethod
    def ensure_snapshot_hash(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("snapshot_hash must be a 64-character hexadecimal string")
        return cleaned

    @field_validator("patch_body", "receipt_preview", "raw_receipt")
    @classmethod
    def ensure_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.rstrip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class PatchResolutionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intake: PatchIntakeView
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def ensure_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned
