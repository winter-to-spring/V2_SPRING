from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


_CONTROL_FILE_NAME = "worker-proof-control.json"
_PREFERRED_TARGETS = ("README.md", "README.txt", "README.rst")
_TEXT_SUFFIXES = {".md", ".txt", ".py"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="isolated-worker-entry",
        description="Deterministic Step 12-b worker proof entrypoint.",
    )
    parser.add_argument("--workspace", required=True, help="Sandbox workspace path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        raise SystemExit(f"Workspace {workspace} does not exist.")
    if not workspace.is_dir():
        raise SystemExit(f"Workspace {workspace} is not a directory.")

    control = _load_control_file(workspace)
    sleep_seconds = int(control.get("sleep_seconds", 0) or 0)
    stdout_lines = int(control.get("stdout_lines", 0) or 0)
    stderr_lines = int(control.get("stderr_lines", 0) or 0)
    exit_code = int(control.get("exit_code", 0) or 0)

    if sleep_seconds > 0:
        print(f"Sleeping for {sleep_seconds}s before writing the patch proof.")
        sys.stdout.flush()
        time.sleep(sleep_seconds)

    target_path = _choose_target_file(workspace)
    _apply_proof_edit(target_path)

    print(f"Applied isolated worker proof edit to {target_path.relative_to(workspace)}.")
    for index in range(stdout_lines):
        print(f"stdout proof line {index + 1}")
    for index in range(stderr_lines):
        print(f"stderr proof line {index + 1}", file=sys.stderr)

    if exit_code != 0:
        print(f"Worker proof exiting with code {exit_code} by control request.", file=sys.stderr)
        return exit_code
    return 0


def _load_control_file(workspace: Path) -> dict[str, object]:
    control_path = workspace / _CONTROL_FILE_NAME
    if not control_path.exists():
        return {}
    try:
        return json.loads(control_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _choose_target_file(workspace: Path) -> Path:
    for relative_name in _PREFERRED_TARGETS:
        candidate = workspace / relative_name
        if candidate.exists() and candidate.is_file():
            return candidate

    candidates: list[Path] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        if path.name == _CONTROL_FILE_NAME:
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() in _TEXT_SUFFIXES:
            candidates.append(path)
    if candidates:
        return candidates[0]

    return workspace / "worker-proof-note.txt"


def _apply_proof_edit(target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    existing = target_path.read_text(encoding="utf-8") if target_path.exists() else ""

    if target_path.suffix.lower() == ".py":
        marker = "# isolated worker proof"
    else:
        marker = "<!-- isolated worker proof -->"

    if marker in existing:
        return

    separator = "" if not existing or existing.endswith("\n") else "\n"
    updated = f"{existing}{separator}{marker}\n"
    target_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
