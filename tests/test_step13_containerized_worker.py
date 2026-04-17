from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from v2_spring.cli import main
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.artifact import ArtifactType
from v2_spring.domain.run import RunCreateInput
from v2_spring.domain.task import TaskKind, TaskStatus
from v2_spring.ledger.store import LedgerStore


_CONTAINER_LABEL = "v2_spring.worker_kind=containerized_worker_proof"


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step13.db'}")


def _create_ready_run(store: LedgerStore) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove containerized worker dispatch",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _count_labeled_containers() -> int:
    result = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"label={_CONTAINER_LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0
    return len([line for line in result.stdout.splitlines() if line.strip()])


def test_dispatch_containerized_worker_proof_returns_patch_and_receipt(tmp_path: Path) -> None:
    if not _docker_available():
        pytest.skip("Docker daemon is not available for Step 13 proof tests.")

    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    (workspace / ".env").write_text("SECRET_KEY=dont-copy-me\n", encoding="utf-8")

    result = store.dispatch_containerized_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=20,
    )

    assert result.task.kind == TaskKind.CONTAINERIZED_WORKER_PROOF
    assert result.task.status == TaskStatus.COMPLETED
    artifact_types = {artifact.artifact_type for artifact in result.artifacts}
    assert artifact_types == {ArtifactType.UNIFIED_PATCH, ArtifactType.EXECUTION_RECEIPT}

    patch_artifact = next(artifact for artifact in result.artifacts if artifact.artifact_type == ArtifactType.UNIFIED_PATCH)
    receipt_artifact = next(
        artifact for artifact in result.artifacts if artifact.artifact_type == ArtifactType.EXECUTION_RECEIPT
    )
    patch_text = Path(patch_artifact.path).read_text(encoding="utf-8")
    assert "README.md" in patch_text
    assert "isolated worker proof" in patch_text

    receipt_payload = json.loads(Path(receipt_artifact.path).read_text(encoding="utf-8"))
    assert receipt_payload["runtime"] == "containerized_worker"
    assert receipt_payload["workspace_transfer"] == "docker_cp_airgap"
    assert receipt_payload["network_mode"] == "none"
    assert receipt_payload["privileged"] is False
    assert receipt_payload["docker_socket_exposed"] is False
    assert receipt_payload["ownership_normalized"] is True
    assert receipt_payload["secret_surface_present"] is False
    assert ".env" in receipt_payload["excluded_names"]


def test_dispatch_containerized_worker_timeout_returns_receipt_only_and_cleans_container(tmp_path: Path) -> None:
    if not _docker_available():
        pytest.skip("Docker daemon is not available for Step 13 proof tests.")

    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "timeout-workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Slow demo\n", encoding="utf-8")
    (workspace / "worker-proof-control.json").write_text(
        json.dumps({"sleep_seconds": 3}),
        encoding="utf-8",
    )

    result = store.dispatch_containerized_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=1,
    )

    assert result.task.status == TaskStatus.FAILED
    assert result.receipt.timed_out is True
    assert [artifact.artifact_type for artifact in result.artifacts] == [ArtifactType.EXECUTION_RECEIPT]
    assert _count_labeled_containers() == 0


def test_task_dispatch_cli_supports_containerized_worker_json(monkeypatch, capsys, tmp_path: Path) -> None:
    if not _docker_available():
        pytest.skip("Docker daemon is not available for Step 13 proof tests.")

    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step13.db'}"
    store = LedgerStore(database_url)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "cli-workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# CLI Demo\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "task",
            "dispatch",
            run_id,
            "--runtime",
            "containerized_worker",
            "--workspace",
            str(workspace),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--format",
            "json",
            "--database-url",
            database_url,
        ],
    )
    main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["task"]["kind"] == "containerized_worker_proof"
    assert payload["receipt"]["runtime"] == "containerized_worker"
    assert payload["receipt"]["workspace_transfer"] == "docker_cp_airgap"
    assert any(item["artifact_type"] == "unified_patch" for item in payload["artifacts"])
