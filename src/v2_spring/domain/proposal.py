from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from v2_spring.domain.snapshot import PossibleActionName


class PlannerProposalInput(BaseModel):
    """Typed planner proposal contract before any real LLM adapter is attached."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_hash: str = Field(min_length=64, max_length=64)
    selected_action: PossibleActionName
    rationale: str = Field(min_length=1, max_length=4000)
    expected_outcome: str = Field(min_length=1, max_length=4000)

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


class PlannerProposalView(BaseModel):
    """Recorded planner proposal after legality and freshness checks pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID
    run_id: UUID
    policy_version: str = Field(min_length=1, max_length=100)
    snapshot_hash: str = Field(min_length=64, max_length=64)
    selected_action: PossibleActionName
    rationale: str = Field(min_length=1, max_length=4000)
    expected_outcome: str = Field(min_length=1, max_length=4000)
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
