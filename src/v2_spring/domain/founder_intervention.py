from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from v2_spring.domain.actions import PossibleActionName


class FounderReplyKind(StrEnum):
    """Typed founder response lanes after planner escalation."""

    HINT = "hint"
    OVERRIDE = "override"
    REJECT = "reject"


class FounderHintInput(BaseModel):
    """Founder guidance that asks the planner to try again with extra context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["hint"]
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def ensure_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned


class FounderOverrideInput(BaseModel):
    """Founder-enforced bounded action that stays inside the legal move set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["override"]
    selected_action: PossibleActionName
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def ensure_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason must not be blank")
        return cleaned


class FounderRejectInput(BaseModel):
    """Founder refusal to provide further help for the current escalation lane."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["reject"]
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def ensure_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason must not be blank")
        return cleaned


FounderReplyInput = Annotated[FounderHintInput | FounderOverrideInput | FounderRejectInput, Field(discriminator="kind")]
FOUNDER_REPLY_INPUT_ADAPTER = TypeAdapter(FounderReplyInput)


class FounderInterventionView(BaseModel):
    """Replayable founder intervention recorded against one planner escalation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    run_id: UUID
    target_escalation_id: UUID
    phase_key: str = Field(min_length=64, max_length=64)
    policy_version: str = Field(min_length=1, max_length=100)
    reply_kind: FounderReplyKind
    summary: str = Field(min_length=1, max_length=400)
    detail: str = Field(min_length=1, max_length=4000)
    override_action: PossibleActionName | None = None
    created_at: datetime

    @field_validator("phase_key")
    @classmethod
    def ensure_phase_key(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("phase_key must be a 64-character hexadecimal string")
        return cleaned

    @field_validator("policy_version", "summary", "detail")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class FounderInterventionDigest(BaseModel):
    """Small founder-intervention projection safe to feed back into the planner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reply_kind: FounderReplyKind
    summary: str = Field(min_length=1, max_length=400)
    detail: str = Field(min_length=1, max_length=1000)
    override_action: PossibleActionName | None = None
    created_at: datetime

    @field_validator("summary", "detail")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned
