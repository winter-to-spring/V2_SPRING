from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from v2_spring.domain.snapshot import PossibleActionName
from v2_spring.domain.routing import ExecutionRequirements, default_requirements_for_bounded_execution


class PlannerProposalInput(BaseModel):
    """Typed planner proposal contract before any real LLM adapter is attached."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_hash: str = Field(min_length=64, max_length=64)
    selected_action: PossibleActionName
    submission_key: str | None = Field(default=None, max_length=120)
    rationale: str = Field(min_length=1, max_length=4000)
    expected_outcome: str = Field(min_length=1, max_length=4000)
    execution_requirements: ExecutionRequirements | None = None

    @model_validator(mode="before")
    @classmethod
    def inject_default_execution_requirements(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        selected_action = value.get("selected_action")
        if isinstance(selected_action, PossibleActionName):
            selected_action = selected_action.value
        if selected_action == PossibleActionName.EXECUTE_BOUNDED_TASK.value and value.get("execution_requirements") is None:
            payload = dict(value)
            payload["execution_requirements"] = default_requirements_for_bounded_execution().model_dump(mode="python")
            return payload
        return value

    @field_validator("snapshot_hash")
    @classmethod
    def ensure_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("snapshot_hash must be a 64-character hexadecimal string")
        return cleaned

    @field_validator("rationale", "expected_outcome")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("submission_key")
    @classmethod
    def ensure_optional_submission_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class PlannerProposalView(BaseModel):
    """Recorded planner proposal after legality and freshness checks pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID
    run_id: UUID
    policy_version: str = Field(min_length=1, max_length=100)
    snapshot_hash: str = Field(min_length=64, max_length=64)
    selected_action: PossibleActionName
    submission_key: str | None = Field(default=None, max_length=120)
    rationale: str = Field(min_length=1, max_length=4000)
    expected_outcome: str = Field(min_length=1, max_length=4000)
    execution_requirements: ExecutionRequirements | None = None
    created_at: datetime

    @field_validator("policy_version")
    @classmethod
    def ensure_policy_version(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("snapshot_hash")
    @classmethod
    def ensure_hash(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("snapshot_hash must be a 64-character hexadecimal string")
        return cleaned

    @field_validator("rationale", "expected_outcome")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("submission_key")
    @classmethod
    def ensure_optional_submission_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned
