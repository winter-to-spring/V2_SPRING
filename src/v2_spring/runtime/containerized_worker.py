from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from v2_spring.domain.routing import ExecutionRequirements
from v2_spring.runtime.isolated_worker import (
    _build_base_file_hashes,
    _build_patch,
    _copy_workspace_into_sandbox,
)
from v2_spring.runtime.worker_metadata import (
    ContainerRuntimeManifest,
    LoadedWorkerMetadataRegistry,
    load_worker_metadata_registry,
)


_WORKER_LABEL_KEY = "v2_spring.worker_kind"
_WORKER_LABEL_VALUE = "containerized_worker_proof"
_EXECUTION_CONTEXT_LABEL = "v2_spring.execution_context_id"
_RUN_ID_LABEL = "v2_spring.run_id"
_RAW_OUTPUT_DIR_NAME = "raw-output"
_RAW_WORKSPACE_DIR_NAME = "raw-workspace"
_NORMALIZED_OUTPUT_DIR_NAME = "output"
_NORMALIZED_WORKSPACE_DIR_NAME = "workspace-after"
_DOCKER_NETWORK_MODE = "none"
_CONTAINER_INPUT_WORKSPACE = "/input-workspace"
_CONTAINER_EXEC_WORKSPACE = "/workspace"
_CONTAINER_OUTPUT_DIR = "/output"
_RESOURCE_MEMORY_LIMIT = "256m"
_RESOURCE_CPU_LIMIT = "1.0"
_RESOURCE_PIDS_LIMIT = 128


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContainerizedWorkerExecutionError(RuntimeError):
    """Raised when the containerized worker proof cannot complete safely."""


class ContainerizedWorkerTimeout(ContainerizedWorkerExecutionError):
    """Raised when the containerized worker exceeds its timeout."""


class ContainerizedWorkerPreflightRefusal(ContainerizedWorkerExecutionError):
    """Raised when the local metadata registry refuses a containerized dispatch."""

    def __init__(self, *, refusal_code: str, message: str) -> None:
        super().__init__(message)
        self.refusal_code = refusal_code


class ContainerizedWorkerReceipt(BaseModel):
    """Serializable receipt for one Step 13 containerized worker proof."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_context_id: str = Field(min_length=1, max_length=120)
    runtime: Literal["containerized_worker"] = "containerized_worker"
    image: str = Field(min_length=1, max_length=200)
    image_digest: str | None = Field(default=None, max_length=200)
    base_image_reference: str | None = Field(default=None, max_length=400)
    container_name: str = Field(min_length=1, max_length=200)
    command: str = Field(min_length=1, max_length=800)
    source_workspace: str = Field(min_length=1, max_length=4000)
    sandbox_cwd: str = Field(min_length=1, max_length=4000)
    started_at: datetime
    finished_at: datetime
    timeout_seconds: int = Field(ge=1, le=600)
    returncode: int | None
    timed_out: bool = False
    log_capture_strategy: Literal["container_output_file_sandwich"] = "container_output_file_sandwich"
    workspace_transfer: Literal["docker_cp_airgap"] = "docker_cp_airgap"
    metadata_registry_path: str | None = Field(default=None, max_length=4000)
    metadata_registry_schema_version: int | None = Field(default=None, ge=1, le=100)
    metadata_registry_checksum: str | None = Field(default=None, max_length=64)
    preflight_strategy: Literal["static_manifest", "static_manifest_plus_dynamic"] = "static_manifest"
    preflight_refusal_code: str | None = Field(default=None, max_length=120)
    dynamic_check_performed: bool = False
    dynamic_check_tools: list[str] = Field(default_factory=list)
    capability_manifest_tools: list[str] = Field(default_factory=list)
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
    network_mode: Literal["none"] = _DOCKER_NETWORK_MODE
    privileged: bool = False
    docker_socket_exposed: bool = False
    ownership_normalized: bool = False
    orphan_gc_removed: int = Field(ge=0, default=0)
    resource_limits: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "execution_context_id",
        "image",
        "container_name",
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


def execute_containerized_worker_proof(
    *,
    workspace: Path,
    timeout_seconds: int,
    execution_context_id: str | None = None,
    run_id: str | None = None,
    requirements: ExecutionRequirements | None = None,
) -> ContainerizedWorkerReceipt:
    """Run the Step 13 worker proof inside a container with copy-in/out isolation."""

    workspace = workspace.expanduser().resolve()
    if not workspace.exists():
        raise FileNotFoundError(f"Workspace {workspace} does not exist.")
    if not workspace.is_dir():
        raise NotADirectoryError(f"Workspace {workspace} is not a directory.")

    if shutil.which("docker") is None:
        raise ContainerizedWorkerExecutionError("Docker CLI is not installed or not on PATH.")

    execution_context_id = execution_context_id or str(uuid4())
    started_at = utc_now()
    orphan_gc_removed = _garbage_collect_labeled_worker_containers()
    metadata_registry = load_worker_metadata_registry()
    manifest = _load_container_runtime_manifest(metadata_registry)
    _run_static_preflight(manifest, requirements=requirements)
    _ensure_static_image(manifest)
    dynamic_check_performed = False
    if manifest.dynamic_admission_tools:
        _run_dynamic_admission_checks(manifest)
        dynamic_check_performed = True
    image_digest = _inspect_local_image_digest(manifest.worker_image_tag)

    base_file_hashes = _build_base_file_hashes(workspace)
    container_name = f"v2-spring-worker-{execution_context_id[:12]}"
    command = (
        "sh -lc 'rm -rf /workspace && mkdir -p /input-workspace /workspace /output && "
        "cp -R /input-workspace/. /workspace && "
        "chmod -R u+rwX /workspace /output && "
        f"python /opt/v2/container_log_capture.py --workspace {_CONTAINER_EXEC_WORKSPACE} "
        f"--output-dir {_CONTAINER_OUTPUT_DIR} "
        "--head-bytes $V2_SPRING_LOG_HEAD_BYTES "
        "--tail-bytes $V2_SPRING_LOG_TAIL_BYTES "
        "--max-bytes $V2_SPRING_LOG_MAX_BYTES'"
    )

    with tempfile.TemporaryDirectory(prefix="v2-spring-container-proof-") as temp_root:
        temp_root_path = Path(temp_root).resolve()
        staged_workspace = temp_root_path / "workspace-in"
        raw_workspace_after = temp_root_path / _RAW_WORKSPACE_DIR_NAME
        raw_output_after = temp_root_path / _RAW_OUTPUT_DIR_NAME
        normalized_workspace_after = temp_root_path / _NORMALIZED_WORKSPACE_DIR_NAME

        excluded_names = _copy_workspace_into_sandbox(workspace, staged_workspace)
        secret_surface_present = any(path.name.startswith(".env") for path in staged_workspace.rglob(".env*"))

        labels = {
            _WORKER_LABEL_KEY: _WORKER_LABEL_VALUE,
            _EXECUTION_CONTEXT_LABEL: execution_context_id,
        }
        if run_id is not None:
            labels[_RUN_ID_LABEL] = run_id

        _docker_create_container(
            container_name=container_name,
            labels=labels,
            manifest=manifest,
        )
        try:
            _docker_cp_to_container(staged_workspace, container_name, _CONTAINER_INPUT_WORKSPACE)
            _docker_start(container_name)
            returncode, timed_out = _docker_wait_for_exit(container_name, timeout_seconds=timeout_seconds)
            _docker_cp_from_container(container_name, _CONTAINER_OUTPUT_DIR, raw_output_after)
            _docker_cp_from_container(container_name, _CONTAINER_EXEC_WORKSPACE, raw_workspace_after)
        finally:
            _docker_remove_force(container_name)

        stdout_preview, stdout_bytes, stdout_truncated, stderr_preview, stderr_bytes, stderr_truncated = (
            _read_captured_output_preview(raw_output_after)
        )
        ownership_normalized = _normalize_copied_directory(
            raw_workspace_after,
            normalized_workspace_after,
            prefer_child_name="workspace",
        )
        patch_body, changed_files = _build_patch(workspace, normalized_workspace_after)
        finished_at = utc_now()

        if timed_out:
            summary = (
                f"Containerized worker proof timed out after {timeout_seconds}s and was reclaimed synchronously."
            )
        elif returncode not in (0, None):
            summary = f"Containerized worker proof exited with non-zero code {returncode}."
        elif patch_body:
            summary = (
                f"Containerized worker proof produced a bounded patch touching {len(changed_files)} file(s)."
            )
        else:
            summary = "Containerized worker proof completed without producing a patch."

        return ContainerizedWorkerReceipt(
            execution_context_id=execution_context_id,
            image=manifest.worker_image_tag,
            image_digest=image_digest,
            base_image_reference=manifest.base_image_reference,
            container_name=container_name,
            command=command,
            source_workspace=str(workspace),
            sandbox_cwd=_CONTAINER_EXEC_WORKSPACE,
            started_at=started_at,
            finished_at=finished_at,
            timeout_seconds=timeout_seconds,
            returncode=returncode,
            timed_out=timed_out,
            metadata_registry_path=metadata_registry.path,
            metadata_registry_schema_version=metadata_registry.registry.schema_version,
            metadata_registry_checksum=metadata_registry.checksum,
            preflight_strategy=(
                "static_manifest_plus_dynamic" if dynamic_check_performed else "static_manifest"
            ),
            dynamic_check_performed=dynamic_check_performed,
            dynamic_check_tools=list(manifest.dynamic_admission_tools),
            capability_manifest_tools=list(manifest.required_tools),
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
            env_allowlist=[],
            secret_surface_present=secret_surface_present,
            ownership_normalized=ownership_normalized,
            orphan_gc_removed=orphan_gc_removed,
            resource_limits={
                "memory": _RESOURCE_MEMORY_LIMIT,
                "cpus": _RESOURCE_CPU_LIMIT,
                "pids_limit": str(_RESOURCE_PIDS_LIMIT),
            },
        )


def _ensure_static_image(manifest: ContainerRuntimeManifest) -> None:
    inspect_result = subprocess.run(
        ["docker", "image", "inspect", manifest.worker_image_tag],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect_result.returncode == 0:
        return

    runtime_dir = Path(__file__).resolve().parent
    dockerfile = runtime_dir / "containerized_worker.Dockerfile"
    build_result = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(dockerfile),
            "-t",
            manifest.worker_image_tag,
            str(runtime_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if build_result.returncode != 0:
        raise ContainerizedWorkerExecutionError(
            "Failed to build the static container worker image.\n"
            f"stdout:\n{build_result.stdout}\n\nstderr:\n{build_result.stderr}",
        )


def _load_container_runtime_manifest(
    metadata_registry: LoadedWorkerMetadataRegistry,
) -> ContainerRuntimeManifest:
    manifest = metadata_registry.registry.runtimes.get("containerized_worker")
    if manifest is None:
        raise ContainerizedWorkerPreflightRefusal(
            refusal_code="runtime_missing_from_registry",
            message="Metadata registry does not define the containerized_worker runtime.",
        )
    return manifest


def _run_static_preflight(
    manifest: ContainerRuntimeManifest,
    *,
    requirements: ExecutionRequirements | None,
) -> None:
    if "python" not in manifest.required_tools:
        raise ContainerizedWorkerPreflightRefusal(
            refusal_code="required_tool_missing",
            message="Metadata registry does not declare python for the containerized worker runtime.",
        )
    if requirements is None:
        return
    if requirements.requires_network and not manifest.allow_network:
        raise ContainerizedWorkerPreflightRefusal(
            refusal_code="network_not_allowed",
            message="Containerized worker manifest does not allow network access for this lane.",
        )
    if requirements.needs_multi_file_context and not manifest.supports_multi_file_context:
        raise ContainerizedWorkerPreflightRefusal(
            refusal_code="multi_file_context_not_supported",
            message="Containerized worker manifest does not support multi-file context for this lane.",
        )
    if requirements.write_scope.value not in manifest.supported_write_scopes:
        raise ContainerizedWorkerPreflightRefusal(
            refusal_code="write_scope_not_supported",
            message="Containerized worker manifest does not support the requested write scope.",
        )
    if requirements.expected_output_kind.value not in manifest.supported_output_kinds:
        raise ContainerizedWorkerPreflightRefusal(
            refusal_code="output_kind_not_supported",
            message="Containerized worker manifest does not support the requested output kind.",
        )


def _run_dynamic_admission_checks(manifest: ContainerRuntimeManifest) -> None:
    tool_commands = {
        "python": ["python", "--version"],
    }
    for tool_name in manifest.dynamic_admission_tools:
        command = tool_commands.get(tool_name)
        if command is None:
            raise ContainerizedWorkerPreflightRefusal(
                refusal_code="dynamic_check_not_supported",
                message=f"Dynamic admission check is not defined for tool {tool_name}.",
            )
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                _DOCKER_NETWORK_MODE,
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges=true",
                manifest.worker_image_tag,
                *command,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()
            raise ContainerizedWorkerPreflightRefusal(
                refusal_code="dynamic_tool_check_failed",
                message=f"Dynamic admission check failed for {tool_name}: {output or 'unknown error'}",
            )


def _inspect_local_image_digest(image_tag: str) -> str | None:
    result = subprocess.run(
        ["docker", "image", "inspect", image_tag, "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    digest = result.stdout.strip()
    return digest or None


def _garbage_collect_labeled_worker_containers() -> int:
    result = subprocess.run(
        [
            "docker",
            "ps",
            "-aq",
            "--filter",
            f"label={_WORKER_LABEL_KEY}={_WORKER_LABEL_VALUE}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ContainerizedWorkerExecutionError(
            f"Failed to list labeled worker containers: {result.stderr.strip() or result.stdout.strip()}",
        )
    container_ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not container_ids:
        return 0
    remove = subprocess.run(
        ["docker", "rm", "-f", *container_ids],
        capture_output=True,
        text=True,
        check=False,
    )
    if remove.returncode != 0:
        raise ContainerizedWorkerExecutionError(
            f"Failed to reclaim orphan worker containers: {remove.stderr.strip() or remove.stdout.strip()}",
        )
    return len(container_ids)


def _docker_create_container(
    *,
    container_name: str,
    labels: dict[str, str],
    manifest: ContainerRuntimeManifest,
) -> None:
    command = [
        "docker",
        "create",
        "--name",
        container_name,
        "--network",
        _DOCKER_NETWORK_MODE,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--memory",
        _RESOURCE_MEMORY_LIMIT,
        "--cpus",
        _RESOURCE_CPU_LIMIT,
        "--pids-limit",
        str(_RESOURCE_PIDS_LIMIT),
    ]
    for key, value in labels.items():
        command.extend(["--label", f"{key}={value}"])
    command.extend(
        [
            "-e",
            f"V2_SPRING_LOG_HEAD_BYTES={manifest.log_capture.head_bytes}",
            "-e",
            f"V2_SPRING_LOG_TAIL_BYTES={manifest.log_capture.tail_bytes}",
            "-e",
            f"V2_SPRING_LOG_MAX_BYTES={manifest.log_capture.max_bytes}",
        ],
    )
    command.extend(
        [
            manifest.worker_image_tag,
            "sh",
            "-lc",
            (
                f"rm -rf {_CONTAINER_EXEC_WORKSPACE} && "
                f"mkdir -p {_CONTAINER_INPUT_WORKSPACE} {_CONTAINER_EXEC_WORKSPACE} {_CONTAINER_OUTPUT_DIR} && "
                f"cp -R {_CONTAINER_INPUT_WORKSPACE}/. {_CONTAINER_EXEC_WORKSPACE} && "
                f"chmod -R u+rwX {_CONTAINER_EXEC_WORKSPACE} {_CONTAINER_OUTPUT_DIR} && "
                f"python /opt/v2/container_log_capture.py "
                f"--workspace {_CONTAINER_EXEC_WORKSPACE} "
                f"--output-dir {_CONTAINER_OUTPUT_DIR} "
                f"--head-bytes $V2_SPRING_LOG_HEAD_BYTES "
                f"--tail-bytes $V2_SPRING_LOG_TAIL_BYTES "
                f"--max-bytes $V2_SPRING_LOG_MAX_BYTES"
            ),
        ],
    )
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ContainerizedWorkerExecutionError(
            f"Failed to create worker container: {result.stderr.strip() or result.stdout.strip()}",
        )


def _docker_cp_to_container(source: Path, container_name: str, destination: str) -> None:
    result = subprocess.run(
        ["docker", "cp", f"{source}/.", f"{container_name}:{destination}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ContainerizedWorkerExecutionError(
            f"Failed to copy workspace into container: {result.stderr.strip() or result.stdout.strip()}",
        )


def _docker_start(container_name: str) -> None:
    result = subprocess.run(
        ["docker", "start", container_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ContainerizedWorkerExecutionError(
            f"Failed to start worker container: {result.stderr.strip() or result.stdout.strip()}",
        )


def _docker_wait_for_exit(container_name: str, *, timeout_seconds: int) -> tuple[int | None, bool]:
    wait_process = subprocess.Popen(
        ["docker", "wait", container_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = wait_process.communicate(timeout=timeout_seconds)
        if wait_process.returncode not in (0, None):
            raise ContainerizedWorkerExecutionError(
                f"docker wait failed: {(stderr or stdout).strip()}",
            )
        exit_code = int((stdout or "0").strip() or "0")
        return exit_code, False
    except subprocess.TimeoutExpired:
        wait_process.kill()
        _docker_kill(container_name)
        return None, True


def _docker_kill(container_name: str) -> None:
    subprocess.run(
        ["docker", "kill", container_name],
        capture_output=True,
        text=True,
        check=False,
    )


def _docker_cp_from_container(container_name: str, source: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["docker", "cp", f"{container_name}:{source}/.", str(destination)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ContainerizedWorkerExecutionError(
            f"Failed to copy worker outputs from container: {result.stderr.strip() or result.stdout.strip()}",
        )


def _docker_remove_force(container_name: str) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        text=True,
        check=False,
    )


def reclaim_containerized_worker_execution(*, execution_context_id: str) -> bool:
    """Best-effort hard reclaim for one containerized worker execution context."""

    if shutil.which("docker") is None:
        return False
    container_name = f"v2-spring-worker-{execution_context_id[:12]}"
    result = subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _normalize_copied_directory(
    source: Path,
    destination: Path,
    *,
    prefer_child_name: str | None = None,
) -> bool:
    if not source.exists():
        destination.mkdir(parents=True, exist_ok=True)
        return True
    destination.mkdir(parents=True, exist_ok=True)
    effective_source = source
    if prefer_child_name is not None:
        preferred_child = source / prefer_child_name
        if preferred_child.exists() and preferred_child.is_dir():
            effective_source = preferred_child
    try:
        for path in sorted(effective_source.rglob("*")):
            relative = path.relative_to(effective_source)
            target = destination / relative
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        return True
    except OSError:
        return False


def _read_container_log_preview(
    container_name: str,
    *,
    log_path: str,
    manifest: ContainerRuntimeManifest,
) -> tuple[str, int, bool]:
    size = _read_container_file_size(container_name, log_path)
    if size == 0:
        return "", 0, False
    policy = manifest.log_capture
    if size <= policy.max_bytes:
        return _read_container_file_bytes(container_name, log_path, mode="full"), size, False
    head_text = _read_container_file_bytes(
        container_name,
        log_path,
        mode="head",
        count=policy.head_bytes,
    )
    tail_text = _read_container_file_bytes(
        container_name,
        log_path,
        mode="tail",
        count=policy.tail_bytes,
    )
    omitted_bytes = max(size - (policy.head_bytes + policy.tail_bytes), 0)
    preview = (
        f"{head_text.rstrip()}\n\n... [truncated {omitted_bytes} bytes] ...\n\n{tail_text.rstrip()}"
    ).strip()
    return preview, size, True


def _read_container_file_size(container_name: str, log_path: str) -> int:
    result = subprocess.run(
        [
            "docker",
            "exec",
            container_name,
            "sh",
            "-lc",
            f"if [ -f {log_path} ]; then wc -c < {log_path}; else echo 0; fi",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ContainerizedWorkerExecutionError(
            f"Failed to inspect container log size: {result.stderr.strip() or result.stdout.strip()}",
        )
    try:
        return int((result.stdout or "0").strip() or "0")
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ContainerizedWorkerExecutionError(
            f"Container log size was not an integer: {result.stdout!r}",
        ) from exc


def _read_container_file_bytes(
    container_name: str,
    log_path: str,
    *,
    mode: Literal["full", "head", "tail"],
    count: int | None = None,
) -> str:
    if mode == "full":
        shell = f"cat {log_path}"
    elif mode == "head":
        shell = f"head -c {count} {log_path}"
    else:
        shell = f"tail -c {count} {log_path}"
    result = subprocess.run(
        ["docker", "exec", container_name, "sh", "-lc", shell],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        stdout = result.stdout.decode("utf-8", errors="replace")
        raise ContainerizedWorkerExecutionError(
            f"Failed to read bounded container log preview: {(stderr or stdout).strip()}",
        )
    return result.stdout.decode("utf-8", errors="replace").rstrip()


def _read_captured_output_preview(
    output_dir: Path,
) -> tuple[str, int, bool, str, int, bool]:
    stdout_preview_path = output_dir / "stdout.preview.txt"
    stderr_preview_path = output_dir / "stderr.preview.txt"
    metadata_path = output_dir / "capture_meta.json"
    stdout_preview = stdout_preview_path.read_text(encoding="utf-8") if stdout_preview_path.exists() else ""
    stderr_preview = stderr_preview_path.read_text(encoding="utf-8") if stderr_preview_path.exists() else ""
    if not metadata_path.exists():
        return (
            stdout_preview,
            len(stdout_preview.encode("utf-8")),
            False,
            stderr_preview,
            len(stderr_preview.encode("utf-8")),
            False,
        )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    return (
        stdout_preview,
        int(payload.get("stdout_bytes", 0) or 0),
        bool(payload.get("stdout_truncated", False)),
        stderr_preview,
        int(payload.get("stderr_bytes", 0) or 0),
        bool(payload.get("stderr_truncated", False)),
    )
