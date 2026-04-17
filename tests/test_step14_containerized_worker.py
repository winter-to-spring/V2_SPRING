from __future__ import annotations

import json
from pathlib import Path

import pytest

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.routing import (
    ExecutionRequirements,
    ExpectedOutputKind,
    TaskComplexity,
    WriteScope,
)
from v2_spring.domain.run import RunCreateInput
from v2_spring.domain.task import TaskStatus
from v2_spring.ledger.store import LedgerStore
import v2_spring.ledger.store as store_module
from v2_spring.runtime.containerized_worker import (
    ContainerizedWorkerPreflightRefusal,
    _read_container_log_preview,
    execute_containerized_worker_proof,
)
from v2_spring.runtime.worker_metadata import ContainerRuntimeManifest, WorkerLogCapturePolicy


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step14.db'}")


def _create_ready_run(store: LedgerStore) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove Step 14 container metadata guardrails",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def _write_manifest(
    path: Path,
    *,
    dynamic_admission_tools: list[str] | None = None,
    max_bytes: int = 4000,
    head_bytes: int = 1000,
    tail_bytes: int = 3000,
) -> None:
    payload = {
        "schema_version": 1,
        "registry_name": "test_registry",
        "runtimes": {
            "containerized_worker": {
                "runtime": "containerized_worker",
                "worker_image_tag": "v2-spring/container-worker-proof:test",
                "base_image_reference": (
                    "docker.io/library/python:3.12-slim@"
                    "sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286"
                ),
                "required_tools": ["python"],
                "allow_network": False,
                "supports_multi_file_context": False,
                "supported_write_scopes": ["single_file"],
                "supported_output_kinds": ["unified_patch"],
                "log_capture": {
                    "strategy": "sandwich",
                    "max_bytes": max_bytes,
                    "head_bytes": head_bytes,
                    "tail_bytes": tail_bytes,
                },
                "dynamic_admission_tools": dynamic_admission_tools or [],
            },
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_execute_containerized_worker_proof_records_metadata_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")

    manifest_path = tmp_path / "worker_manifest.json"
    _write_manifest(manifest_path, dynamic_admission_tools=["python"])
    monkeypatch.setenv("V2_SPRING_WORKER_MANIFEST_PATH", str(manifest_path))

    call_order: list[str] = []

    monkeypatch.setattr("v2_spring.runtime.containerized_worker.shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._garbage_collect_labeled_worker_containers",
        lambda: 0,
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._ensure_static_image",
        lambda manifest: call_order.append("ensure"),
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._run_dynamic_admission_checks",
        lambda manifest: call_order.append("dynamic"),
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._inspect_local_image_digest",
        lambda image_tag: "sha256:localproof",
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._docker_create_container",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._docker_cp_to_container",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._docker_start",
        lambda container_name: None,
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._docker_wait_for_exit",
        lambda container_name, timeout_seconds: (0, False),
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._read_container_log_preview",
        lambda *args, **kwargs: ("proof-log", 9, False),
    )

    def fake_cp_from_container(container_name: str, source: str, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        if source == "/output":
            (destination / "stdout.preview.txt").write_text("proof-log", encoding="utf-8")
            (destination / "stderr.preview.txt").write_text("", encoding="utf-8")
            (destination / "capture_meta.json").write_text(
                json.dumps(
                    {
                        "stdout_bytes": 9,
                        "stderr_bytes": 0,
                        "stdout_truncated": False,
                        "stderr_truncated": False,
                    },
                ),
                encoding="utf-8",
            )
            return
        copied_workspace = destination / "workspace"
        copied_workspace.mkdir(parents=True, exist_ok=True)
        (copied_workspace / "README.md").write_text("# Demo\n\nchanged inside container\n", encoding="utf-8")

    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._docker_cp_from_container",
        fake_cp_from_container,
    )
    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._docker_remove_force",
        lambda container_name: None,
    )

    receipt = execute_containerized_worker_proof(
        workspace=workspace,
        timeout_seconds=10,
        execution_context_id="ctx-step14",
        run_id="run-step14",
        requirements=ExecutionRequirements(
            task_complexity=TaskComplexity.LOW,
            needs_isolation=True,
            requires_network=False,
            needs_multi_file_context=False,
            write_scope=WriteScope.SINGLE_FILE,
            expected_output_kind=ExpectedOutputKind.UNIFIED_PATCH,
        ),
    )

    assert call_order == ["ensure", "dynamic"]
    assert receipt.image == "v2-spring/container-worker-proof:test"
    assert receipt.image_digest == "sha256:localproof"
    assert receipt.metadata_registry_path == str(manifest_path.resolve())
    assert receipt.metadata_registry_schema_version == 1
    assert len(receipt.metadata_registry_checksum) == 64
    assert receipt.preflight_strategy == "static_manifest_plus_dynamic"
    assert receipt.dynamic_check_performed is True
    assert receipt.dynamic_check_tools == ["python"]
    assert receipt.capability_manifest_tools == ["python"]
    assert receipt.patch_body is not None
    assert "changed inside container" in receipt.patch_body
    assert receipt.base_image_reference is not None
    assert "sha256:" in receipt.base_image_reference


def test_read_container_log_preview_uses_sandwich_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_text = "HEAD-ERROR\n" + ("x" * 700) + "\nTAIL-TRACE\n"
    manifest = ContainerRuntimeManifest(
        runtime="containerized_worker",
        worker_image_tag="demo:test",
        base_image_reference="docker.io/library/python:3.12-slim@sha256:demo",
        required_tools=["python"],
        allow_network=False,
        supports_multi_file_context=False,
        supported_write_scopes=["single_file"],
        supported_output_kinds=["unified_patch"],
        log_capture=WorkerLogCapturePolicy(
            strategy="sandwich",
            max_bytes=512,
            head_bytes=128,
            tail_bytes=256,
        ),
        dynamic_admission_tools=[],
    )

    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._read_container_file_size",
        lambda container_name, log_path: len(log_text.encode("utf-8")),
    )

    def fake_read_bytes(
        container_name: str,
        log_path: str,
        *,
        mode: str,
        count: int | None = None,
    ) -> str:
        if mode == "full":
            return log_text
        if mode == "head":
            return log_text[:count]
        return log_text[-count:]

    monkeypatch.setattr(
        "v2_spring.runtime.containerized_worker._read_container_file_bytes",
        fake_read_bytes,
    )

    preview, total_size, truncated = _read_container_log_preview(
        "container",
        log_path="/output/stdout.log",
        manifest=manifest,
    )

    assert total_size == len(log_text.encode("utf-8"))
    assert truncated is True
    assert "HEAD-ERR" in preview
    assert "TAIL-TRACE" in preview
    assert "[truncated" in preview


def test_dispatch_containerized_worker_preflight_refusal_returns_failed_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")

    def refuse(**kwargs) -> None:
        raise ContainerizedWorkerPreflightRefusal(
            refusal_code="write_scope_not_supported",
            message="Container image does not support the requested write scope.",
        )

    monkeypatch.setattr(store_module, "execute_containerized_worker_proof", refuse)

    result = store.dispatch_containerized_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    assert result.task.status == TaskStatus.FAILED
    assert result.receipt.preflight_refusal_code == "write_scope_not_supported"
    assert result.receipt.preflight_strategy == "static_manifest"
    assert result.receipt.metadata_registry_path is not None
    assert result.receipt.image == "v2-spring/container-worker-proof:static-v2"
    assert [artifact.artifact_type.value for artifact in result.artifacts] == ["execution_receipt"]
