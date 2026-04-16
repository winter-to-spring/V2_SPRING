from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from v2_spring.domain.approval import ApprovalView
from v2_spring.domain.artifact import ArtifactType
from v2_spring.domain.run import RunView
from v2_spring.domain.task import TaskKind, TaskStatus


class SnapshotActionState(StrEnum):
    AVAILABLE = "available"
    BLOCKED = "blocked"
    TERMINAL = "terminal"
    STUCK = "stuck"


class PossibleActionName(StrEnum):
    RESOLVE_PENDING_APPROVAL = "resolve_pending_approval"
    EXECUTE_BOUNDED_TASK = "execute_bounded_task"
    REPLAN_WITH_REJECTION_FEEDBACK = "replan_with_rejection_feedback"
    REPLAN_FROM_FAILED_EXECUTION = "replan_from_failed_execution"


class TaskStatusSummary(BaseModel):
    """Compact task counts so snapshots stay planner-friendly and bounded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    created: int = Field(ge=0, default=0)
    ready: int = Field(ge=0, default=0)
    running: int = Field(ge=0, default=0)
    completed: int = Field(ge=0, default=0)
    failed: int = Field(ge=0, default=0)


class TaskHeadlineView(BaseModel):
    """Small task projection safe to surface to planners and founders."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    kind: TaskKind
    status: TaskStatus
    summary: str = Field(min_length=1, max_length=400)
    started_at: datetime | None
    completed_at: datetime | None
    failure_hint: str | None

    @field_validator("summary")
    @classmethod
    def ensure_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class ArtifactHeadlineView(BaseModel):
    """Small artifact projection that avoids exposing internal paths."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    artifact_type: ArtifactType
    title: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0)
    file_exists: bool
    hash_matches: bool | None

    @field_validator("title")
    @classmethod
    def ensure_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class RunSnapshotView(BaseModel):
    """Planner-ready, founder-readable snapshot of current run state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_timestamp: datetime
    policy_version: str = Field(min_length=1, max_length=100)
    state_hash: str = Field(min_length=64, max_length=64)
    run: RunView
    action_state: SnapshotActionState
    action_state_reason: str = Field(min_length=1, max_length=400)
    pending_approval: ApprovalView | None
    latest_rejection_reason: str | None
    latest_decision_summary: str | None
    planner_phase_key: str = Field(min_length=64, max_length=64)
    planner_budget_limit: int = Field(ge=1)
    planner_budget_used: int = Field(ge=0)
    planner_budget_remaining: int = Field(ge=0)
    planner_phase_exhausted: bool = False
    latest_planner_attempt_summary: str | None
    task_summary: TaskStatusSummary
    latest_task: TaskHeadlineView | None
    latest_artifact: ArtifactHeadlineView | None

    @field_validator("state_hash", "planner_phase_key")
    @classmethod
    def ensure_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("value must be a 64-character hexadecimal string")
        return cleaned

    @field_validator(
        "policy_version",
        "action_state_reason",
        "latest_rejection_reason",
        "latest_decision_summary",
        "latest_planner_attempt_summary",
    )
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class PossibleActionView(BaseModel):
    """One legal next move derived from the deterministic substrate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: PossibleActionName
    reason: str = Field(min_length=1, max_length=400)
    context_hint: str | None = Field(default=None, max_length=4000)

    @field_validator("reason", "context_hint")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


class PossibleActionEvaluationView(BaseModel):
    """Deterministic legal moves for the current run snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot: RunSnapshotView
    actions: list[PossibleActionView]
