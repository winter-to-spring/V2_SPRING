from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import contextlib
import os
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BoundedExecutorError(RuntimeError):
    """Base class for bounded executor failures."""


class BoundedExecutorTimeout(BoundedExecutorError):
    """Raised when the bounded executor exceeds its timeout."""


@dataclass(frozen=True)
class TaskExecutionReceipt:
    execution_context_id: str
    command: str
    cwd: str
    started_at: datetime
    finished_at: datetime
    timeout_seconds: int
    stdout: str
    stderr: str
    artifact_title: str
    artifact_body: str


_BLOCKED_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
    },
)


def execute_repository_scan(
    *,
    workspace: Path,
    timeout_seconds: int,
    execution_context_id: str | None = None,
) -> TaskExecutionReceipt:
    """Run a small, read-only repository scan and return a receipt."""

    workspace = workspace.expanduser().resolve()
    if not workspace.exists():
        raise FileNotFoundError(f"Workspace {workspace} does not exist.")
    if not workspace.is_dir():
        raise NotADirectoryError(f"Workspace {workspace} is not a directory.")

    execution_context_id = execution_context_id or str(uuid4())
    command = f"scan_repository_tree --workspace {workspace} --max-depth 3"
    started_at = utc_now()

    def _work() -> tuple[str, str]:
        stdout_buffer = StringIO()
        with contextlib.redirect_stdout(stdout_buffer):
            print(f"Scanning workspace: {workspace}")
            print("Collecting repository tree and lightweight summary.")
            artifact_body = _build_repository_report(workspace)
            print("Repository scan finished.")
        return stdout_buffer.getvalue().rstrip(), artifact_body

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="bounded-executor") as pool:
        future = pool.submit(_work)
        try:
            stdout, artifact_body = future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            raise BoundedExecutorTimeout(
                f"Bounded executor exceeded {timeout_seconds}s while scanning {workspace}.",
            ) from exc

    finished_at = utc_now()
    return TaskExecutionReceipt(
        execution_context_id=execution_context_id,
        command=command,
        cwd=str(workspace),
        started_at=started_at,
        finished_at=finished_at,
        timeout_seconds=timeout_seconds,
        stdout=stdout,
        stderr="",
        artifact_title="Repository scan report",
        artifact_body=artifact_body,
    )


def _build_repository_report(workspace: Path) -> str:
    tree_lines: list[str] = []
    directory_count = 0
    file_count = 0
    max_depth = 3

    root_name = workspace.name or str(workspace)
    tree_lines.append(f"{root_name}/")

    for current_root, directories, files in os.walk(workspace):
        current_path = Path(current_root)
        relative_path = current_path.relative_to(workspace)
        depth = len(relative_path.parts)
        if depth >= max_depth:
            directories[:] = []
        directories[:] = sorted(
            [directory for directory in directories if _is_visible_name(directory)],
        )
        visible_files = sorted([file_name for file_name in files if _is_visible_name(file_name)])
        if relative_path.parts:
            directory_count += 1
        file_count += len(visible_files)

        indent = "  " * depth
        for directory in directories:
            tree_lines.append(f"{indent}- {directory}/")
        for file_name in visible_files:
            tree_lines.append(f"{indent}- {file_name}")

    summary_lines = [
        "# Repository Scan Report",
        "",
        "## Summary",
        f"- workspace: `{workspace}`",
        f"- directories_seen: {directory_count}",
        f"- files_seen: {file_count}",
        "",
        "## Tree (max depth 3)",
        *tree_lines,
        "",
        "## Safety Notes",
        "- Hidden or sensitive paths such as `.git`, `.env*`, and common cache directories are excluded.",
        "- The bounded executor only performs read-only inspection in this phase.",
    ]
    return "\n".join(summary_lines).strip() + "\n"


def _is_visible_name(name: str) -> bool:
    if name in _BLOCKED_NAMES:
        return False
    if name.startswith(".env"):
        return False
    return True
