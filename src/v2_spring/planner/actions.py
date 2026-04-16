from __future__ import annotations

from v2_spring.domain.run import RunStatus
from v2_spring.domain.snapshot import (
    PossibleActionEvaluationView,
    PossibleActionName,
    PossibleActionView,
    RunSnapshotView,
    SnapshotActionState,
)


def evaluate_possible_actions(snapshot: RunSnapshotView) -> PossibleActionEvaluationView:
    """Return legal moves only; do not smuggle planner judgment into this layer."""

    actions: list[PossibleActionView] = []

    if snapshot.pending_approval is not None:
        actions.append(
            PossibleActionView(
                name=PossibleActionName.RESOLVE_PENDING_APPROVAL,
                reason="The run is blocked on a human approval gate.",
                context_hint=snapshot.pending_approval.reason,
            ),
        )
    elif snapshot.run.status == RunStatus.READY and snapshot.task_summary.created == 0 and snapshot.task_summary.running == 0:
        actions.append(
            PossibleActionView(
                name=PossibleActionName.EXECUTE_BOUNDED_TASK,
                reason="The run is approved and has no bounded execution evidence yet.",
                context_hint="Execute one safe, read-only bounded task.",
            ),
        )
    elif snapshot.run.status == RunStatus.REJECTED:
        actions.append(
            PossibleActionView(
                name=PossibleActionName.REPLAN_WITH_REJECTION_FEEDBACK,
                reason="The run was rejected and should re-enter planning with human feedback.",
                context_hint=snapshot.latest_rejection_reason,
            ),
        )
    elif snapshot.run.status == RunStatus.FAILED:
        actions.append(
            PossibleActionView(
                name=PossibleActionName.REPLAN_FROM_FAILED_EXECUTION,
                reason="The run failed during bounded execution and should re-enter planning with failure context.",
                context_hint=snapshot.latest_task.failure_hint if snapshot.latest_task is not None else None,
            ),
        )

    if actions:
        action_state = SnapshotActionState.AVAILABLE
        action_state_reason = "One or more legal next actions are available."
    elif snapshot.run.status == RunStatus.RUNNING:
        action_state = SnapshotActionState.BLOCKED
        action_state_reason = "A bounded task is currently running."
    elif snapshot.run.status == RunStatus.COMPLETED:
        action_state = SnapshotActionState.TERMINAL
        action_state_reason = "The run is already completed; no further mutating action is legal."
    else:
        action_state = SnapshotActionState.STUCK
        action_state_reason = "The run has no legal next action under the current deterministic rules."

    return PossibleActionEvaluationView(
        snapshot=snapshot.model_copy(
            update={
                "action_state": action_state,
                "action_state_reason": action_state_reason,
            },
        ),
        actions=actions,
    )
