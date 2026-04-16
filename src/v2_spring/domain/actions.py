from __future__ import annotations

from enum import StrEnum


class PossibleActionName(StrEnum):
    """Deterministic legal moves that planner and founder lanes can reference."""

    RESOLVE_PENDING_APPROVAL = "resolve_pending_approval"
    EXECUTE_BOUNDED_TASK = "execute_bounded_task"
    REPLAN_WITH_REJECTION_FEEDBACK = "replan_with_rejection_feedback"
    REPLAN_FROM_FAILED_EXECUTION = "replan_from_failed_execution"
