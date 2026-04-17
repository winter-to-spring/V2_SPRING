from __future__ import annotations

import json
from pathlib import Path

from v2_spring.cli import main
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.artifact import ArtifactType
from v2_spring.domain.run import RunCreateInput
from v2_spring.domain.task import TaskKind, TaskStatus
from v2_spring.ledger.store import LedgerStore


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step12b.db'}")


def _create_ready_run(store: LedgerStore) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove isolated worker dispatch",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def test_dispatch_isolated_worker_proof_returns_patch_and_receipt(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    (workspace / ".env").write_text("SECRET_KEY=dont-copy-me\n", encoding="utf-8")

    result = store.dispatch_isolated_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    assert result.task.kind == TaskKind.ISOLATED_WORKER_PROOF
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
    assert receipt_payload["log_capture_strategy"] == "temp_file_tail"
    assert receipt_payload["secret_surface_present"] is False
    assert ".env" in receipt_payload["excluded_names"]
    assert "README.md" in receipt_payload["changed_files"]


def test_dispatch_isolated_worker_timeout_returns_receipt_only(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "timeout-workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Slow demo\n", encoding="utf-8")
    (workspace / "worker-proof-control.json").write_text(
        json.dumps({"sleep_seconds": 2}),
        encoding="utf-8",
    )

    result = store.dispatch_isolated_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=1,
    )

    assert result.task.status == TaskStatus.FAILED
    assert result.receipt.timed_out is True
    assert [artifact.artifact_type for artifact in result.artifacts] == [ArtifactType.EXECUTION_RECEIPT]
    assert "timed out" in result.observation.details.lower()
    assert "Sleeping for 2s" in result.task.stdout


def test_task_dispatch_cli_supports_json_output(monkeypatch, capsys, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step12b.db'}"
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
            "isolated_worker",
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

    assert payload["task"]["kind"] == "isolated_worker_proof"
    assert payload["receipt"]["runtime"] == "isolated_worker"
    assert payload["receipt"]["log_capture_strategy"] == "temp_file_tail"
    assert any(item["artifact_type"] == "unified_patch" for item in payload["artifacts"])
