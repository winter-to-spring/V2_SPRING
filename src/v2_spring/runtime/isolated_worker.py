from __future__ import annotations

from datetime import datetime, timezone
from difflib import unified_diff
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
_CONTROL_FILE_NAME = "worker-proof-control.json"
_STDOUT_FILE_NAME = "__worker_stdout.log"
_STDERR_FILE_NAME = "__worker_stderr.log"
_MAX_LOG_PREVIEW_BYTES = 4000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IsolatedWorkerExecutionError(RuntimeError):
    """Base class for isolated worker proof failures."""


class IsolatedWorkerTimeout(IsolatedWorkerExecutionError):
    """Raised when the isolated worker exceeds its timeout."""


class IsolatedWorkerReceipt(BaseModel):
    """Serializable receipt for one isolated worker proof execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_context_id: str = Field(min_length=1, max_length=120)
    runtime: Literal["isolated_worker"] = "isolated_worker"
    command: str = Field(min_length=1, max_length=400)
    source_workspace: str = Field(min_length=1, max_length=4000)
    sandbox_cwd: str = Field(min_length=1, max_length=4000)
    started_at: datetime
    finished_at: datetime
    timeout_seconds: int = Field(ge=1, le=600)
    returncode: int | None
    timed_out: bool = False
    log_capture_strategy: Literal["temp_file_tail"] = "temp_file_tail"
    stdout_preview: str
    stderr_preview: str
    stdout_bytes: int = Field(ge=0)
    stderr_bytes: int = Field(ge=0)
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    changed_files: list[str] = Field(default_factory=list)
    patch_body: str | None = None
    summary: str = Field(min_length=1, max_length=2000)
    base_file_hashes: dict[str, str] = Field(default_factory=dict)
    excluded_names: list[str] = Field(default_factory=list)
    env_allowlist: list[str] = Field(default_factory=list)
    secret_surface_present: bool = False

    @field_validator(
        "execution_context_id",
        "command",
        "source_workspace",
        "sandbox_cwd",
        "summary",
        "stdout_preview",
        "stderr_preview",
    )
    @classmethod
    def ensure_text(cls, value: str) -> str:
        return value.rstrip()


def execute_isolated_worker_proof(
    *,
    workspace: Path,
    timeout_seconds: int,
    execution_context_id: str | None = None,
) -> IsolatedWorkerReceipt:
    """Run the Step 12-b isolated worker proof in a strengthened soft-isolation sandbox."""

    workspace = workspace.expanduser().resolve()
    if not workspace.exists():
        raise FileNotFoundError(f"Workspace {workspace} does not exist.")
    if not workspace.is_dir():
        raise NotADirectoryError(f"Workspace {workspace} is not a directory.")

    execution_context_id = execution_context_id or str(uuid4())
    command = f"{sys.executable} isolated_worker_entry.py --workspace <sandbox>"
    started_at = utc_now()
    env = _build_allowlisted_env()
    base_file_hashes = _build_base_file_hashes(workspace)

    with tempfile.TemporaryDirectory(prefix="v2-spring-worker-") as sandbox_root:
        sandbox_root_path = Path(sandbox_root).resolve()
        sandbox_workspace = sandbox_root_path / "workspace"
        excluded_names = _copy_workspace_into_sandbox(workspace, sandbox_workspace)
        secret_surface_present = any(path.name.startswith(".env") for path in sandbox_workspace.rglob(".env*"))

        stdout_path = sandbox_root_path / _STDOUT_FILE_NAME
        stderr_path = sandbox_root_path / _STDERR_FILE_NAME
        worker_script_path = Path(__file__).with_name("isolated_worker_entry.py").resolve()

        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w",
            encoding="utf-8",
        ) as stderr_handle:
            process = subprocess.Popen(
                [sys.executable, str(worker_script_path), "--workspace", str(sandbox_workspace)],
                cwd=str(sandbox_workspace),
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=env,
                start_new_session=True,
                text=True,
            )
            timed_out = False
            returncode: int | None = None
            try:
                returncode = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_process_group(process)
                returncode = None

        stdout_preview, stdout_bytes, stdout_truncated = _read_bounded_tail(stdout_path)
        stderr_preview, stderr_bytes, stderr_truncated = _read_bounded_tail(stderr_path)
        finished_at = utc_now()

        if timed_out:
            return IsolatedWorkerReceipt(
                execution_context_id=execution_context_id,
                command=command,
                source_workspace=str(workspace),
                sandbox_cwd=str(sandbox_workspace),
                started_at=started_at,
                finished_at=finished_at,
                timeout_seconds=timeout_seconds,
                returncode=None,
                timed_out=True,
                stdout_preview=stdout_preview,
                stderr_preview=stderr_preview,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                changed_files=[],
                patch_body=None,
                summary=(
                    f"Isolated worker proof timed out after {timeout_seconds}s and was reclaimed synchronously."
                ),
                base_file_hashes=base_file_hashes,
                excluded_names=excluded_names,
                env_allowlist=sorted(env.keys()),
                secret_surface_present=secret_surface_present,
            )

        patch_body, changed_files = _build_patch(workspace, sandbox_workspace)
        if returncode not in (0, None):
            summary = f"Isolated worker proof exited with non-zero code {returncode}."
        elif patch_body:
            summary = (
                f"Isolated worker proof produced a bounded patch touching {len(changed_files)} file(s)."
            )
        else:
            summary = "Isolated worker proof completed without producing a patch."

        return IsolatedWorkerReceipt(
            execution_context_id=execution_context_id,
            command=command,
            source_workspace=str(workspace),
            sandbox_cwd=str(sandbox_workspace),
            started_at=started_at,
            finished_at=finished_at,
            timeout_seconds=timeout_seconds,
            returncode=returncode,
            timed_out=False,
            stdout_preview=stdout_preview,
            stderr_preview=stderr_preview,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            changed_files=changed_files,
            patch_body=patch_body or None,
            summary=summary,
            base_file_hashes=base_file_hashes,
            excluded_names=excluded_names,
            env_allowlist=sorted(env.keys()),
            secret_surface_present=secret_surface_present,
        )


def _copy_workspace_into_sandbox(source: Path, destination: Path) -> list[str]:
    excluded_names: set[str] = set()
    for root, directories, files in os.walk(source):
        root_path = Path(root)
        relative_root = root_path.relative_to(source)
        destination_root = destination / relative_root
        destination_root.mkdir(parents=True, exist_ok=True)

        kept_directories: list[str] = []
        for directory in sorted(directories):
            if _should_exclude_name(directory):
                excluded_names.add(directory)
                continue
            kept_directories.append(directory)
        directories[:] = kept_directories

        for file_name in sorted(files):
            source_file = root_path / file_name
            if _should_exclude_file(source_file):
                excluded_names.add(file_name)
                continue
            target_file = destination_root / file_name
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
    return sorted(excluded_names)


def _should_exclude_name(name: str) -> bool:
    if name in _BLOCKED_NAMES:
        return True
    if name.startswith(".env"):
        return True
    return False


def _should_exclude_file(path: Path) -> bool:
    name = path.name
    if _should_exclude_name(name):
        return True
    if name in {_STDOUT_FILE_NAME, _STDERR_FILE_NAME}:
        return True
    return False


def _build_allowlisted_env() -> dict[str, str]:
    env = {"PYTHONIOENCODING": "utf-8"}
    for key in ("TMPDIR",):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def _build_base_file_hashes(workspace: Path) -> dict[str, str]:
    import hashlib

    hashes: dict[str, str] = {}
    for path in _iter_relevant_files(workspace):
        relative_path = path.relative_to(workspace).as_posix()
        hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _iter_relevant_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name == _CONTROL_FILE_NAME:
            continue
        if _should_exclude_file(path):
            continue
        yield path


def _build_patch(source: Path, sandbox: Path) -> tuple[str, list[str]]:
    relevant_paths = {
        path.relative_to(source).as_posix()
        for path in _iter_relevant_files(source)
    } | {
        path.relative_to(sandbox).as_posix()
        for path in _iter_relevant_files(sandbox)
    }
    patch_chunks: list[str] = []
    changed_files: list[str] = []
    for relative_path in sorted(relevant_paths):
        source_file = source / relative_path
        sandbox_file = sandbox / relative_path
        before = _read_text_lines(source_file) if source_file.exists() else []
        after = _read_text_lines(sandbox_file) if sandbox_file.exists() else []
        if before == after:
            continue
        changed_files.append(relative_path)
        patch_chunks.extend(
            unified_diff(
                before,
                after,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                lineterm="",
            ),
        )
    if not patch_chunks:
        return "", changed_files
    return "\n".join(patch_chunks).strip() + "\n", changed_files


def _read_text_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _read_bounded_tail(path: Path, *, max_bytes: int = _MAX_LOG_PREVIEW_BYTES) -> tuple[str, int, bool]:
    if not path.exists():
        return "", 0, False
    size = path.stat().st_size
    truncated = size > max_bytes
    with path.open("rb") as handle:
        if truncated:
            handle.seek(-max_bytes, os.SEEK_END)
        data = handle.read()
    preview = data.decode("utf-8", errors="replace").rstrip()
    return preview, size, truncated


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive fallback
            process.kill()
