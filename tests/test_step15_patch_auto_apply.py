from __future__ import annotations

from pathlib import Path
import subprocess

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.patch_intake import PatchIntakeStatus, PatchResolutionCode
from v2_spring.domain.run import RunCreateInput
from v2_spring.ledger.store import LedgerStore


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step15.db'}")


def _create_ready_run(store: LedgerStore) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove risk-based patch intake routing",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def _init_git_workspace(workspace: Path) -> None:
    subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True, text=True)


def test_low_risk_single_file_patch_is_auto_applied(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    readme = workspace / "README.md"
    readme.write_text("# Demo\n", encoding="utf-8")

    result = store.dispatch_isolated_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    assert any(artifact.artifact_type.value == "validation_receipt" for artifact in result.artifacts)
    assert "auto-applied" in result.observation.summary.lower()
    intake = store.list_patch_intakes_for_run(run_id)[0]
    assert intake.status == PatchIntakeStatus.APPLIED
    assert intake.resolution_code == PatchResolutionCode.AUTO_APPLIED
    assert intake.validation_artifact_id is not None
    assert "isolated worker proof" in readme.read_text(encoding="utf-8")
    assert store.get_run(run_id).status.value == "completed"  # type: ignore[union-attr]


def test_sensitive_patch_still_waits_for_founder_review(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    target = workspace / "src" / "v2_spring" / "ledger" / "demo.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")

    result = store.dispatch_isolated_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    intake = store.list_patch_intakes_for_run(run_id)[0]
    assert intake.status == PatchIntakeStatus.PENDING
    assert intake.auto_apply_eligible is False
    assert intake.resolution_code is None
    assert "waiting on founder patch review" in result.observation.summary.lower()
