from __future__ import annotations

import argparse
from textwrap import dedent

from pydantic import ValidationError

from v2_spring.config import load_config
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.run import RunCreateInput
from v2_spring.ledger.store import LedgerStore


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
            ],
        )
    return "\n".join(lines)


def _render_resolved_approval(approval_id: str, store: LedgerStore, *, approved: bool) -> str:
    approval = store.resolve_approval(approval_id, approved=approved)
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
        resolved_at:      {approval.resolved_at.isoformat() if approval.resolved_at else "-"}
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

    if args.command == "approval" and args.approval_command == "list":
        store = _build_store(args.database_url)
        print(_render_approvals(store, args.status))
        return

    if args.command == "approval" and args.approval_command == "resolve":
        store = _build_store(args.database_url)
        try:
            print(
                _render_resolved_approval(
                    args.approval_id,
                    store,
                    approved=args.approve,
                ),
            )
        except (LookupError, ValueError) as exc:
            print(str(exc))
            raise SystemExit(1) from exc
        return

    parser.print_help()
