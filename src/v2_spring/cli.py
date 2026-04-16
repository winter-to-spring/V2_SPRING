from __future__ import annotations

import argparse
from textwrap import dedent

from pydantic import ValidationError

from v2_spring.config import load_config
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

    parser.print_help()
