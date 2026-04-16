from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import dedent

from pydantic import ValidationError

from v2_spring.config import load_config
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.ledger.store import BoundedExecutionResult, LedgerStore


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

    artifact_parser = subparsers.add_parser("artifact", help="Inspect produced artifacts.")
    artifact_subparsers = artifact_parser.add_subparsers(dest="artifact_command")

    artifact_list_parser = artifact_subparsers.add_parser("list", help="List artifacts for a run.")
    artifact_list_parser.add_argument("--run", required=True, help="Run id to inspect.")
    artifact_list_parser.add_argument(
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

    if args.command == "artifact" and args.artifact_command == "list":
        store = _build_store(args.database_url)
        print(_render_artifacts(args.run, store))
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

    parser.print_help()
