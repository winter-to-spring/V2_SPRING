from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

from pydantic import ValidationError

from v2_spring.config import load_config
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.planner_attempt import PlannerAttemptView
from v2_spring.domain.proposal import PlannerProposalInput, PlannerProposalView
from v2_spring.domain.replay import ArtifactInspectionView, RunReplayView, TaskReplayView
from v2_spring.domain.snapshot import PossibleActionEvaluationView, PossibleActionName, RunSnapshotView
from v2_spring.ledger.store import BoundedExecutionResult, LedgerStore
from v2_spring.planner.actions import evaluate_possible_actions
from v2_spring.planner.proposals import (
    CognitiveDuplicatePlannerProposalError,
    IllegalPlannerProposalError,
    PlannerPhaseExhaustedError,
    StalePlannerProposalError,
    TransportDuplicatePlannerProposalError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v2-spring",
        description="V2_SPRING CLI bootstrap.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("doctor", help="Show bootstrap status.")
    subparsers.add_parser("tracer-bullet", help="Print tracer bullet entrypoint guidance.")

    run_parser = subparsers.add_parser("run", help="Manage tracer bullet runs.")
    run_subparsers = run_parser.add_subparsers(dest="run_command")

    create_parser = run_subparsers.add_parser("create", help="Create a new run.")
    create_parser.add_argument("--project", required=True, help="Project slug or label.")
    create_parser.add_argument("--goal", required=True, help="Human goal for this run.")
    create_parser.add_argument(
        "--urgency",
        required=True,
        choices=["low", "normal", "high", "critical"],
        help="Urgency level.",
    )
    create_parser.add_argument(
        "--risk",
        required=True,
        choices=["low", "medium", "high", "critical"],
        help="Risk level.",
    )
    create_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    show_parser = run_subparsers.add_parser("show", help="Show a run by id.")
    show_parser.add_argument("run_id", help="Run id to show.")
    show_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    events_parser = run_subparsers.add_parser("events", help="Show ledger events for a run.")
    events_parser.add_argument("run_id", help="Run id to inspect.")
    events_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    snapshot_parser = run_subparsers.add_parser(
        "snapshot",
        help="Show the current planner-ready run snapshot.",
    )
    snapshot_parser.add_argument("run_id", help="Run id to inspect.")
    snapshot_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    snapshot_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    actions_parser = run_subparsers.add_parser(
        "actions",
        help="Show deterministic legal next actions for a run.",
    )
    actions_parser.add_argument("run_id", help="Run id to inspect.")
    actions_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    actions_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    replay_parser = run_subparsers.add_parser(
        "replay",
        help="Show a compact replay summary for a run.",
    )
    replay_parser.add_argument("run_id", help="Run id to replay.")
    replay_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    replay_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include deeper details such as full observations and approval history.",
    )
    replay_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    execute_parser = run_subparsers.add_parser(
        "execute",
        help="Execute the first bounded task for an approved run.",
    )
    execute_parser.add_argument("run_id", help="Run id to execute.")
    execute_parser.add_argument(
        "--workspace",
        default=".",
        help="Read-only workspace path to scan. Defaults to the current directory.",
    )
    execute_parser.add_argument(
        "--artifact-root",
        default=".local/artifacts",
        help="Root directory where bounded execution artifacts should be written.",
    )
    execute_parser.add_argument(
        "--timeout-seconds",
        default=5,
        type=int,
        help="Execution timeout in seconds. Defaults to 5.",
    )
    execute_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    task_parser = subparsers.add_parser("task", help="Inspect bounded execution tasks.")
    task_subparsers = task_parser.add_subparsers(dest="task_command")

    task_list_parser = task_subparsers.add_parser("list", help="List tasks for a run.")
    task_list_parser.add_argument("--run", required=True, help="Run id to inspect.")
    task_list_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    task_show_parser = task_subparsers.add_parser("show", help="Show one task with linkage details.")
    task_show_parser.add_argument("task_id", help="Task id to inspect.")
    task_show_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    task_show_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    artifact_parser = subparsers.add_parser("artifact", help="Inspect produced artifacts.")
    artifact_subparsers = artifact_parser.add_subparsers(dest="artifact_command")

    artifact_list_parser = artifact_subparsers.add_parser("list", help="List artifacts for a run.")
    artifact_list_parser.add_argument("--run", required=True, help="Run id to inspect.")
    artifact_list_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    artifact_show_parser = artifact_subparsers.add_parser(
        "show",
        help="Show one artifact with provenance and integrity details.",
    )
    artifact_show_parser.add_argument("artifact_id", help="Artifact id to inspect.")
    artifact_show_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    artifact_show_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    approval_parser = subparsers.add_parser("approval", help="Inspect and resolve approvals.")
    approval_subparsers = approval_parser.add_subparsers(dest="approval_command")

    approval_list_parser = approval_subparsers.add_parser("list", help="List approvals.")
    approval_list_parser.add_argument(
        "--status",
        default="pending",
        choices=["pending", "approved", "rejected", "all"],
        help="Filter approvals by status.",
    )
    approval_list_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    approval_resolve_parser = approval_subparsers.add_parser(
        "resolve",
        help="Resolve a pending approval.",
    )
    approval_resolve_parser.add_argument("approval_id", help="Approval id to resolve.")
    resolve_group = approval_resolve_parser.add_mutually_exclusive_group(required=True)
    resolve_group.add_argument("--approve", action="store_true", help="Approve the request.")
    resolve_group.add_argument("--reject", action="store_true", help="Reject the request.")
    approval_resolve_parser.add_argument(
        "--reason",
        default=None,
        help="Optional structured feedback. Required for --reject.",
    )
    approval_resolve_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    planner_parser = subparsers.add_parser("planner", help="Validate and inspect planner proposals.")
    planner_subparsers = planner_parser.add_subparsers(dest="planner_command")

    planner_propose_parser = planner_subparsers.add_parser(
        "propose",
        help="Submit one planner proposal against the current legal move set.",
    )
    planner_propose_parser.add_argument("run_id", help="Run id to target.")
    planner_propose_parser.add_argument(
        "--snapshot-hash",
        required=True,
        help="Snapshot hash returned by `v2-spring run snapshot` or `run actions`.",
    )
    planner_propose_parser.add_argument(
        "--action",
        required=True,
        choices=[action.value for action in PossibleActionName],
        help="Selected legal move.",
    )
    planner_propose_parser.add_argument(
        "--rationale",
        required=True,
        help="Why this action should be selected now.",
    )
    planner_propose_parser.add_argument(
        "--expected-outcome",
        required=True,
        help="What the planner expects to happen if this action is executed.",
    )
    planner_propose_parser.add_argument(
        "--submission-key",
        default=None,
        help="Optional caller-supplied idempotency key for transport-level deduplication.",
    )
    planner_propose_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    planner_propose_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    planner_show_parser = planner_subparsers.add_parser(
        "show",
        help="Show accepted planner proposals for one run.",
    )
    planner_show_parser.add_argument("run_id", help="Run id to inspect.")
    planner_show_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    planner_show_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    planner_attempts_parser = planner_subparsers.add_parser(
        "attempts",
        help="Show planner governance attempts for one run.",
    )
    planner_attempts_parser.add_argument("run_id", help="Run id to inspect.")
    planner_attempts_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    planner_attempts_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )

    planner_recharge_parser = planner_subparsers.add_parser(
        "recharge",
        help="Reopen an exhausted planner phase with an explicit founder reason.",
    )
    planner_recharge_parser.add_argument("run_id", help="Run id to recharge.")
    planner_recharge_parser.add_argument(
        "--reason",
        required=True,
        help="Why the founder believes another planner attempt should be allowed.",
    )
    planner_recharge_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json"],
        help="Output format. Defaults to pretty.",
    )
    planner_recharge_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this invocation.",
    )
    return parser


def _build_store(database_url_override: str | None) -> LedgerStore:
    return LedgerStore(load_config(database_url_override).database_url)


def _render_run(run_id: str, store: LedgerStore) -> str:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"Run {run_id} was not found.")

    return dedent(
        f"""\
        Run
        ---
        id:         {run.id}
        project:    {run.project}
        status:     {run.status.value}
        urgency:    {run.urgency.value}
        risk:       {run.risk.value}
        created_at: {run.created_at.isoformat()}
        updated_at: {run.updated_at.isoformat()}

        goal:
        {run.goal}
        """,
    ).strip()


def _render_events(run_id: str, store: LedgerStore) -> str:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"Run {run_id} was not found.")

    ledger_events = store.list_events_for_run(run_id)
    decisions = {str(item.id): item for item in store.list_decisions_for_run(run_id)}
    observations = {str(item.id): item for item in store.list_observations_for_run(run_id)}
    tasks = {str(item.id): item for item in store.list_tasks_for_run(run_id)}
    artifacts = {str(item.id): item for item in store.list_artifacts_for_run(run_id)}

    lines = [
        "Run events",
        "----------",
        f"run_id: {run.id}",
    ]

    for index, event in enumerate(ledger_events, start=1):
        lines.extend(
            [
                "",
                f"{index}. {event.event_type.value}",
                f"   recorded_at: {event.recorded_at.isoformat()}",
            ],
        )

        if event.event_type.value == "DECISION_RECORDED":
            decision = decisions.get(event.payload.get("decision_id", ""))
            if decision is not None:
                lines.append(f"   summary:     {decision.summary}")
                lines.append(f"   rationale:   {decision.rationale}")
                continue

        if event.event_type.value == "OBSERVATION_RECORDED":
            observation = observations.get(event.payload.get("observation_id", ""))
            if observation is not None:
                lines.append(f"   summary:     {observation.summary}")
                lines.append(f"   details:     {observation.details}")
                continue

        if event.event_type.value in {"TASK_CREATED", "TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED"}:
            task = tasks.get(event.payload.get("task_id", ""))
            if task is not None:
                lines.append(f"   task:        {task.summary}")
                lines.append(
                    f"   status:      {event.payload.get('status', task.status.value)}",
                )
            lines.append(f"   payload:     {event.payload}")
            continue

        if event.event_type.value == "ARTIFACT_RECORDED":
            artifact = artifacts.get(event.payload.get("artifact_id", ""))
            if artifact is not None:
                lines.append(f"   artifact:    {artifact.title}")
                lines.append(f"   path:        {artifact.path}")
                lines.append(f"   sha256:      {artifact.sha256}")
                continue

        if event.event_type.value in {"APPROVAL_REQUESTED", "APPROVAL_RESOLVED"}:
            lines.append(f"   payload:     {event.payload}")
            continue

        lines.append(f"   payload:     {event.payload}")

    return "\n".join(lines)


def _render_approvals(store: LedgerStore, status_filter: str) -> str:
    status = None if status_filter == "all" else ApprovalStatus(status_filter)
    approvals = store.list_approvals(status=status)
    lines = ["Approvals", "---------"]
    if not approvals:
        lines.append("No approvals matched the current filter.")
        if status_filter != "all":
            lines.append("Tip: use --status all to include already resolved approvals.")
        return "\n".join(lines)

    for index, approval in enumerate(approvals, start=1):
        lines.extend(
            [
                "",
                f"{index}. {approval.id}",
                f"   run_id:           {approval.run_id}",
                f"   status:           {approval.status.value}",
                f"   requested_action: {approval.requested_action}",
                f"   reason:           {approval.reason}",
                f"   approve_effect:   {approval.approve_effect}",
                f"   reject_effect:    {approval.reject_effect}",
                f"   requested_at:     {approval.requested_at.isoformat()}",
                f"   resolved_at:      {approval.resolved_at.isoformat() if approval.resolved_at else '-'}",
                f"   resolution_reason:{approval.resolution_reason if approval.resolution_reason else '-'}",
            ],
        )
    return "\n".join(lines)


def _render_resolved_approval(
    approval_id: str,
    store: LedgerStore,
    *,
    approved: bool,
    reason: str | None,
) -> str:
    approval = store.resolve_approval(approval_id, approved=approved, reason=reason)
    outcome = "approved" if approved else "rejected"
    return dedent(
        f"""\
        Approval resolved
        -----------------
        id:               {approval.id}
        run_id:           {approval.run_id}
        new_status:       {approval.status.value}
        requested_action: {approval.requested_action}
        outcome:          {outcome}
        resolution_reason:{approval.resolution_reason if approval.resolution_reason else "-"}
        resolved_at:      {approval.resolved_at.isoformat() if approval.resolved_at else "-"}
        """,
    ).strip()


def _render_tasks(run_id: str, store: LedgerStore) -> str:
    tasks = store.list_tasks_for_run(run_id)
    lines = ["Tasks", "-----", f"run_id: {run_id}"]
    if not tasks:
        lines.append("No tasks have been recorded for this run yet.")
        return "\n".join(lines)

    for index, task in enumerate(tasks, start=1):
        lines.extend(
            [
                "",
                f"{index}. {task.id}",
                f"   status:              {task.status.value}",
                f"   kind:                {task.kind.value}",
                f"   summary:             {task.summary}",
                f"   decision_id:         {task.decision_id if task.decision_id else '-'}",
                f"   execution_context:   {task.execution_context_id}",
                f"   command:             {task.command}",
                f"   cwd:                 {task.cwd}",
                f"   timeout_seconds:     {task.timeout_seconds}",
                f"   started_at:          {task.started_at.isoformat() if task.started_at else '-'}",
                f"   completed_at:        {task.completed_at.isoformat() if task.completed_at else '-'}",
                f"   stdout:              {task.stdout if task.stdout else '-'}",
                f"   stderr:              {task.stderr if task.stderr else '-'}",
            ],
        )
    return "\n".join(lines)


def _render_artifacts(run_id: str, store: LedgerStore) -> str:
    artifacts = store.list_artifacts_for_run(run_id)
    lines = ["Artifacts", "---------", f"run_id: {run_id}"]
    if not artifacts:
        lines.append("No artifacts have been recorded for this run yet.")
        return "\n".join(lines)

    for index, artifact in enumerate(artifacts, start=1):
        lines.extend(
            [
                "",
                f"{index}. {artifact.id}",
                f"   task_id:             {artifact.task_id}",
                f"   decision_id:         {artifact.decision_id if artifact.decision_id else '-'}",
                f"   type:                {artifact.artifact_type.value}",
                f"   title:               {artifact.title}",
                f"   storage_kind:        {artifact.storage_kind.value}",
                f"   path:                {artifact.path}",
                f"   size_bytes:          {artifact.size_bytes}",
                f"   sha256:              {artifact.sha256}",
                f"   execution_context:   {artifact.execution_context_id}",
                f"   command:             {artifact.command}",
                f"   cwd:                 {artifact.cwd}",
                f"   created_at:          {artifact.created_at.isoformat()}",
            ],
        )
    return "\n".join(lines)


def _render_execution_result(result: BoundedExecutionResult) -> str:
    artifact_line = result.artifact.path if result.artifact is not None else "-"
    hash_line = result.artifact.sha256 if result.artifact is not None else "-"
    return dedent(
        f"""\
        Bounded execution finished
        --------------------------
        task_id:             {result.task.id}
        task_status:         {result.task.status.value}
        execution_context:   {result.task.execution_context_id}
        observation:         {result.observation.summary}
        artifact_path:       {artifact_line}
        artifact_sha256:     {hash_line}
        """,
    ).strip()


def _render_snapshot(snapshot: RunSnapshotView) -> str:
    lines = [
        "Run snapshot",
        "------------",
        f"run_id:              {snapshot.run.id}",
        f"snapshot_timestamp:  {snapshot.snapshot_timestamp.isoformat()}",
        f"policy_version:      {snapshot.policy_version}",
        f"state_hash:          {snapshot.state_hash}",
        f"status:              {snapshot.run.status.value}",
        f"action_state:        {snapshot.action_state.value}",
        f"action_state_reason: {snapshot.action_state_reason}",
        f"latest_decision:     {snapshot.latest_decision_summary if snapshot.latest_decision_summary else '-'}",
        f"latest_rejection:    {snapshot.latest_rejection_reason if snapshot.latest_rejection_reason else '-'}",
        "",
        "Task summary",
        "------------",
        f"created:             {snapshot.task_summary.created}",
        f"ready:               {snapshot.task_summary.ready}",
        f"running:             {snapshot.task_summary.running}",
        f"completed:           {snapshot.task_summary.completed}",
        f"failed:              {snapshot.task_summary.failed}",
    ]
    if snapshot.pending_approval is not None:
        lines.extend(
            [
                "",
                "Pending approval",
                "----------------",
                f"id:                  {snapshot.pending_approval.id}",
                f"requested_action:    {snapshot.pending_approval.requested_action}",
                f"reason:              {snapshot.pending_approval.reason}",
            ],
        )
    if snapshot.latest_task is not None:
        lines.extend(
            [
                "",
                "Latest task",
                "-----------",
                f"id:                  {snapshot.latest_task.id}",
                f"status:              {snapshot.latest_task.status.value}",
                f"kind:                {snapshot.latest_task.kind.value}",
                f"summary:             {snapshot.latest_task.summary}",
                f"failure_hint:        {snapshot.latest_task.failure_hint if snapshot.latest_task.failure_hint else '-'}",
            ],
        )
    if snapshot.latest_artifact is not None:
        lines.extend(
            [
                "",
                "Latest artifact",
                "---------------",
                f"id:                  {snapshot.latest_artifact.id}",
                f"title:               {snapshot.latest_artifact.title}",
                f"type:                {snapshot.latest_artifact.artifact_type.value}",
                f"size_bytes:          {snapshot.latest_artifact.size_bytes}",
                f"file_exists:         {snapshot.latest_artifact.file_exists}",
                f"hash_matches:        {snapshot.latest_artifact.hash_matches}",
            ],
        )
    return "\n".join(lines)


def _render_actions(evaluation: PossibleActionEvaluationView) -> str:
    lines = [
        "Run actions",
        "-----------",
        f"run_id:              {evaluation.snapshot.run.id}",
        f"snapshot_timestamp:  {evaluation.snapshot.snapshot_timestamp.isoformat()}",
        f"policy_version:      {evaluation.snapshot.policy_version}",
        f"state_hash:          {evaluation.snapshot.state_hash}",
        f"action_state:        {evaluation.snapshot.action_state.value}",
        f"action_state_reason: {evaluation.snapshot.action_state_reason}",
    ]
    if not evaluation.actions:
        lines.extend(["", "No legal next actions are available."])
        return "\n".join(lines)

    lines.extend(["", "Legal moves", "-----------"])
    for index, action in enumerate(evaluation.actions, start=1):
        lines.extend(
            [
                f"{index}. {action.name.value}",
                f"   reason:       {action.reason}",
                f"   context_hint: {action.context_hint if action.context_hint else '-'}",
            ],
        )
    return "\n".join(lines)


def _render_planner_proposal(proposal: PlannerProposalView) -> str:
    return dedent(
        f"""\
        Planner proposal accepted
        -------------------------
        decision_id:        {proposal.decision_id}
        run_id:             {proposal.run_id}
        policy_version:     {proposal.policy_version}
        snapshot_hash:      {proposal.snapshot_hash}
        selected_action:    {proposal.selected_action.value}
        submission_key:     {proposal.submission_key if proposal.submission_key else '-'}
        rationale:          {proposal.rationale}
        expected_outcome:   {proposal.expected_outcome}
        created_at:         {proposal.created_at.isoformat()}
        """,
    ).strip()


def _render_planner_proposals(proposals: list[PlannerProposalView], *, run_id: str) -> str:
    lines = ["Planner proposals", "-----------------", f"run_id: {run_id}"]
    if not proposals:
        lines.append("No accepted planner proposals are recorded for this run yet.")
        return "\n".join(lines)

    for index, proposal in enumerate(proposals, start=1):
        lines.extend(
            [
                "",
                f"{index}. {proposal.decision_id}",
                f"   action:            {proposal.selected_action.value}",
                f"   policy_version:    {proposal.policy_version}",
                f"   snapshot_hash:     {proposal.snapshot_hash}",
                f"   submission_key:    {proposal.submission_key if proposal.submission_key else '-'}",
                f"   rationale:         {proposal.rationale}",
                f"   expected_outcome:  {proposal.expected_outcome}",
                f"   created_at:        {proposal.created_at.isoformat()}",
            ],
        )
    return "\n".join(lines)


def _render_planner_attempt(attempt: PlannerAttemptView) -> str:
    return dedent(
        f"""\
        Planner governance event
        -----------------------
        attempt_id:         {attempt.id}
        run_id:             {attempt.run_id}
        phase_key:          {attempt.phase_key}
        policy_version:     {attempt.policy_version}
        outcome:            {attempt.outcome.value}
        selected_action:    {attempt.selected_action.value if attempt.selected_action is not None else '-'}
        submission_key:     {attempt.submission_key if attempt.submission_key else '-'}
        attempt_index:      {attempt.attempt_index}
        budget_limit:       {attempt.budget_limit}
        budget_used:        {attempt.budget_used}
        budget_remaining:   {attempt.budget_remaining}
        reason:             {attempt.outcome_reason}
        created_at:         {attempt.created_at.isoformat()}
        """,
    ).strip()


def _render_planner_attempts(attempts: list[PlannerAttemptView], *, run_id: str) -> str:
    lines = ["Planner attempts", "----------------", f"run_id: {run_id}"]
    if not attempts:
        lines.append("No planner attempts are recorded for this run yet.")
        return "\n".join(lines)

    for index, attempt in enumerate(attempts, start=1):
        lines.extend(
            [
                "",
                f"{index}. {attempt.outcome.value}",
                f"   attempt_id:       {attempt.id}",
                f"   phase_key:        {attempt.phase_key}",
                f"   action:           {attempt.selected_action.value if attempt.selected_action is not None else '-'}",
                f"   submission_key:   {attempt.submission_key if attempt.submission_key else '-'}",
                f"   budget:           {attempt.budget_used}/{attempt.budget_limit}",
                f"   remaining:        {attempt.budget_remaining}",
                f"   reason:           {attempt.outcome_reason}",
                f"   created_at:       {attempt.created_at.isoformat()}",
            ],
        )
    return "\n".join(lines)


def _render_replay(replay: RunReplayView, *, verbose: bool) -> str:
    lines = [
        "Run replay",
        "----------",
        f"run_id:         {replay.run.id}",
        f"project:        {replay.run.project}",
        f"status:         {replay.run.status.value}",
        f"urgency:        {replay.run.urgency.value}",
        f"risk:           {replay.run.risk.value}",
        "",
        "goal:",
        replay.run.goal,
        "",
        "Approval summary",
        "----------------",
    ]

    if replay.approvals:
        latest_approval = replay.approvals[-1]
        lines.extend(
            [
                f"- current approval state: {latest_approval.status.value}",
                f"- requested action: {latest_approval.requested_action}",
                f"- resolution reason: {latest_approval.resolution_reason if latest_approval.resolution_reason else '-'}",
            ],
        )
    else:
        lines.append("- no approvals recorded")

    lines.extend(["", "Execution path", "--------------"])
    if not replay.tasks:
        lines.append("- no tasks recorded yet")
    else:
        for task_replay in replay.tasks:
            lines.append(
                f"- {task_replay.task.summary} [{task_replay.task.status.value}]",
            )
            if task_replay.decision is not None:
                lines.append(f"  decision: {task_replay.decision.summary}")
            if task_replay.artifacts:
                for artifact in task_replay.artifacts:
                    lines.append(
                        f"  artifact: {artifact.artifact.title} "
                        f"(exists={artifact.file_exists}, hash_matches={artifact.hash_matches})",
                    )
            elif task_replay.task.status == task_replay.task.status.COMPLETED:
                lines.append("  artifact: -")

    failed_attempts = [
        task_replay
        for task_replay in replay.tasks
        if task_replay.task.status.value == "failed"
    ]
    if failed_attempts:
        lines.extend(["", "Failed attempts", "---------------"])
        for task_replay in failed_attempts:
            lines.append(f"- {task_replay.task.summary}")
            lines.append(f"  stderr: {task_replay.task.stderr if task_replay.task.stderr else '-'}")

    if replay.planner_attempts:
        lines.extend(["", "Planner governance", "------------------"])
        grouped_failures = [
            attempt
            for attempt in replay.planner_attempts
            if attempt.outcome.value.startswith("rejected") or attempt.outcome.value == "phase_exhausted"
        ]
        latest_attempt = replay.planner_attempts[-1]
        lines.append(
            f"- total attempts: {len(replay.planner_attempts)} / latest outcome: {latest_attempt.outcome.value}",
        )
        if grouped_failures:
            lines.append(f"- first failure: {grouped_failures[0].outcome.value} / {grouped_failures[0].outcome_reason}")
            lines.append(f"- latest failure: {grouped_failures[-1].outcome.value} / {grouped_failures[-1].outcome_reason}")

    if replay.consistency_warnings:
        lines.extend(["", "Consistency warnings", "--------------------"])
        for warning in replay.consistency_warnings:
            lines.append(f"- {warning}")

    if verbose:
        lines.extend(["", "Detailed approvals", "-----------------"])
        for approval in replay.approvals:
            lines.append(
                f"- {approval.id}: {approval.status.value} / {approval.requested_action}",
            )

        lines.extend(["", "Detailed decisions", "------------------"])
        for decision in replay.decisions:
            lines.append(f"- {decision.id}: {decision.summary}")
            lines.append(f"  rationale: {decision.rationale}")

        lines.extend(["", "Detailed observations", "---------------------"])
        for observation in replay.observations:
            lines.append(f"- {observation.kind.value}: {observation.summary}")
            lines.append(f"  details: {observation.details}")

        if replay.planner_attempts:
            lines.extend(["", "Detailed planner attempts", "------------------------"])
            for attempt in replay.planner_attempts:
                lines.append(f"- {attempt.outcome.value} [{attempt.budget_used}/{attempt.budget_limit}]")
                lines.append(f"  action: {attempt.selected_action.value if attempt.selected_action is not None else '-'}")
                lines.append(f"  reason: {attempt.outcome_reason}")
                lines.append(f"  phase_key: {attempt.phase_key}")

    return "\n".join(lines)


def _render_task_detail(task_replay: TaskReplayView) -> str:
    lines = [
        "Task",
        "----",
        f"id:                 {task_replay.task.id}",
        f"run_id:             {task_replay.task.run_id}",
        f"status:             {task_replay.task.status.value}",
        f"kind:               {task_replay.task.kind.value}",
        f"summary:            {task_replay.task.summary}",
        f"decision_id:        {task_replay.task.decision_id if task_replay.task.decision_id else '-'}",
        f"execution_context:  {task_replay.task.execution_context_id}",
        f"command:            {task_replay.task.command}",
        f"cwd:                {task_replay.task.cwd}",
        f"timeout_seconds:    {task_replay.task.timeout_seconds}",
        f"stdout:             {task_replay.task.stdout if task_replay.task.stdout else '-'}",
        f"stderr:             {task_replay.task.stderr if task_replay.task.stderr else '-'}",
    ]
    if task_replay.decision is not None:
        lines.extend(
            [
                "",
                "Decision linkage",
                "----------------",
                f"id:                 {task_replay.decision.id}",
                f"summary:            {task_replay.decision.summary}",
                f"rationale:          {task_replay.decision.rationale}",
            ],
        )
    lines.extend(["", "Artifacts", "---------"])
    if not task_replay.artifacts:
        lines.append("No artifacts linked to this task.")
    else:
        for artifact in task_replay.artifacts:
            lines.append(
                f"- {artifact.artifact.id}: {artifact.artifact.title} "
                f"(exists={artifact.file_exists}, hash_matches={artifact.hash_matches})",
            )
    return "\n".join(lines)


def _render_artifact_detail(artifact: ArtifactInspectionView) -> str:
    item = artifact.artifact
    return dedent(
        f"""\
        Artifact
        --------
        id:                 {item.id}
        run_id:             {item.run_id}
        task_id:            {item.task_id}
        decision_id:        {item.decision_id if item.decision_id else '-'}
        type:               {item.artifact_type.value}
        title:              {item.title}
        storage_kind:       {item.storage_kind.value}
        path:               {item.path}
        size_bytes:         {item.size_bytes}
        sha256:             {item.sha256}
        file_exists:        {artifact.file_exists}
        hash_matches:       {artifact.hash_matches}
        execution_context:  {item.execution_context_id}
        command:            {item.command}
        cwd:                {item.cwd}
        created_at:         {item.created_at.isoformat()}
        """,
    ).strip()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "doctor":
        print("V2_SPRING bootstrap is present.")
        print("Next milestone: deterministic substrate + CLI tracer bullet.")
        return

    if args.command == "tracer-bullet":
        print("See docs/specs/TRACER_BULLET.md for the first CLI-verifiable loop.")
        return

    if args.command == "run" and args.run_command == "create":
        from v2_spring.domain.run import RunCreateInput

        try:
            run_input = RunCreateInput(
                project=args.project,
                goal=args.goal,
                urgency=args.urgency,
                risk=args.risk,
            )
        except ValidationError as exc:
            print("Run creation failed validation.")
            print(exc)
            raise SystemExit(2) from exc

        store = _build_store(args.database_url)
        run = store.create_run(run_input)
        print(f"Created run {run.id}")
        print(_render_run(str(run.id), store))
        return

    if args.command == "run" and args.run_command == "show":
        store = _build_store(args.database_url)
        try:
            print(_render_run(args.run_id, store))
        except LookupError as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    if args.command == "run" and args.run_command == "events":
        store = _build_store(args.database_url)
        try:
            print(_render_events(args.run_id, store))
        except LookupError as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    if args.command == "run" and args.run_command == "snapshot":
        store = _build_store(args.database_url)
        try:
            snapshot = evaluate_possible_actions(store.build_run_snapshot(args.run_id)).snapshot
            if args.format == "json":
                print(json.dumps(snapshot.model_dump(mode="json"), indent=2, ensure_ascii=False))
            else:
                print(_render_snapshot(snapshot))
        except LookupError as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    if args.command == "run" and args.run_command == "actions":
        store = _build_store(args.database_url)
        try:
            snapshot = store.build_run_snapshot(args.run_id)
            evaluation = evaluate_possible_actions(snapshot)
            if args.format == "json":
                print(json.dumps(evaluation.model_dump(mode="json"), indent=2, ensure_ascii=False))
            else:
                print(_render_actions(evaluation))
        except LookupError as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    if args.command == "run" and args.run_command == "replay":
        store = _build_store(args.database_url)
        try:
            replay = store.build_run_replay(args.run_id)
            if args.format == "json":
                print(json.dumps(replay.model_dump(mode="json"), indent=2, ensure_ascii=False))
            else:
                print(_render_replay(replay, verbose=args.verbose))
        except LookupError as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    if args.command == "run" and args.run_command == "execute":
        store = _build_store(args.database_url)
        try:
            result = store.execute_bounded_task(
                run_id=args.run_id,
                workspace=Path(args.workspace),
                artifact_root=Path(args.artifact_root),
                timeout_seconds=args.timeout_seconds,
            )
            print(_render_execution_result(result))
        except (LookupError, PermissionError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    if args.command == "task" and args.task_command == "list":
        store = _build_store(args.database_url)
        print(_render_tasks(args.run, store))
        return

    if args.command == "task" and args.task_command == "show":
        store = _build_store(args.database_url)
        task = store.get_task(args.task_id)
        if task is None:
            print(f"Task {args.task_id} was not found.")
            raise SystemExit(1)
        replay = store.build_run_replay(str(task.run_id))
        task_replay = next((item for item in replay.tasks if str(item.task.id) == args.task_id), None)
        if task_replay is None:
            print(f"Task {args.task_id} is not linked inside run {task.run_id}.")
            raise SystemExit(1)
        if args.format == "json":
            print(json.dumps(task_replay.model_dump(mode="json"), indent=2, ensure_ascii=False))
        else:
            print(_render_task_detail(task_replay))
        return

    if args.command == "artifact" and args.artifact_command == "list":
        store = _build_store(args.database_url)
        print(_render_artifacts(args.run, store))
        return

    if args.command == "artifact" and args.artifact_command == "show":
        store = _build_store(args.database_url)
        artifact = store.get_artifact(args.artifact_id)
        if artifact is None:
            print(f"Artifact {args.artifact_id} was not found.")
            raise SystemExit(1)
        if args.format == "json":
            print(json.dumps(artifact.model_dump(mode="json"), indent=2, ensure_ascii=False))
        else:
            print(_render_artifact_detail(artifact))
        return

    if args.command == "approval" and args.approval_command == "list":
        store = _build_store(args.database_url)
        print(_render_approvals(store, args.status))
        return

    if args.command == "approval" and args.approval_command == "resolve":
        if args.reject and args.reason is None:
            print("Rejecting an approval requires --reason so the next planner loop can learn from it.")
            raise SystemExit(2)
        store = _build_store(args.database_url)
        try:
            print(
                _render_resolved_approval(
                    args.approval_id,
                    store,
                    approved=args.approve,
                    reason=args.reason,
                ),
            )
        except (LookupError, PermissionError, ValueError) as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    if args.command == "planner" and args.planner_command == "propose":
        store = _build_store(args.database_url)
        try:
            proposal = PlannerProposalInput(
                snapshot_hash=args.snapshot_hash,
                selected_action=args.action,
                submission_key=args.submission_key,
                rationale=args.rationale,
                expected_outcome=args.expected_outcome,
            )
        except ValidationError as exc:
            print("Planner proposal failed validation.")
            print(exc)
            raise SystemExit(2) from exc

        try:
            recorded = store.record_planner_proposal(run_id=args.run_id, proposal=proposal)
            if args.format == "json":
                print(json.dumps(recorded.model_dump(mode="json"), indent=2, ensure_ascii=False))
            else:
                print(_render_planner_proposal(recorded))
        except (
            LookupError,
            IllegalPlannerProposalError,
            StalePlannerProposalError,
            TransportDuplicatePlannerProposalError,
            CognitiveDuplicatePlannerProposalError,
            PlannerPhaseExhaustedError,
            PermissionError,
            ValueError,
        ) as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    if args.command == "planner" and args.planner_command == "show":
        store = _build_store(args.database_url)
        if store.get_run(args.run_id) is None:
            print(f"Run {args.run_id} was not found.")
            raise SystemExit(1)
        proposals = store.list_planner_proposals_for_run(args.run_id)
        if args.format == "json":
            print(json.dumps([proposal.model_dump(mode="json") for proposal in proposals], indent=2, ensure_ascii=False))
        else:
            print(_render_planner_proposals(proposals, run_id=args.run_id))
        return

    if args.command == "planner" and args.planner_command == "attempts":
        store = _build_store(args.database_url)
        if store.get_run(args.run_id) is None:
            print(f"Run {args.run_id} was not found.")
            raise SystemExit(1)
        attempts = store.list_planner_attempts_for_run(args.run_id)
        if args.format == "json":
            print(json.dumps([attempt.model_dump(mode="json") for attempt in attempts], indent=2, ensure_ascii=False))
        else:
            print(_render_planner_attempts(attempts, run_id=args.run_id))
        return

    if args.command == "planner" and args.planner_command == "recharge":
        store = _build_store(args.database_url)
        try:
            attempt = store.record_planner_recharge(run_id=args.run_id, reason=args.reason)
            if args.format == "json":
                print(json.dumps(attempt.model_dump(mode="json"), indent=2, ensure_ascii=False))
            else:
                print(_render_planner_attempt(attempt))
        except (LookupError, PermissionError, ValueError) as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    parser.print_help()
