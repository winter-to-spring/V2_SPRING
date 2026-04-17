from __future__ import annotations

import subprocess
from pathlib import Path

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.patch_intake import PatchIntakeStatus, PatchResolutionCode
from v2_spring.domain.run import RunCreateInput
from v2_spring.ledger.models import LedgerEventType
from v2_spring.ledger.store import LedgerStore
from v2_spring.planner.actions import evaluate_possible_actions


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step12c.db'}")


def _create_ready_run(store: LedgerStore) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove patch intake review",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def _init_git_workspace(workspace: Path) -> None:
    subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True, text=True)


def test_patch_review_and_approve_applies_patch_and_records_validation(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    target = workspace / "src" / "v2_spring" / "ledger" / "demo.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")

    store.dispatch_isolated_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    review = store.build_patch_review(run_id)
    assert review.intake.status == PatchIntakeStatus.PENDING
    assert "demo.py" in review.patch_body
    assert review.intake.validation_artifact_id is None

    resolution = store.approve_patch_intake(str(review.intake.id))
    assert resolution.intake.status == PatchIntakeStatus.APPLIED
    assert resolution.intake.resolution_code == PatchResolutionCode.FOUNDER_APPROVED
    assert resolution.intake.validation_artifact_id is not None
    assert "isolated worker proof" in target.read_text(encoding="utf-8")
    assert store.get_run(run_id).status.value == "completed"  # type: ignore[union-attr]
    assert any(
        event.event_type == LedgerEventType.PATCH_INTAKE_APPLIED
        for event in store.list_events_for_run(run_id)
    )


def test_patch_reject_reopens_planning_without_touching_workspace(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    target = workspace / "src" / "v2_spring" / "ledger" / "demo.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")

    store.dispatch_isolated_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )
    review = store.build_patch_review(run_id)

    resolution = store.reject_patch_intake(
        str(review.intake.id),
        reason="Split this patch into a smaller bounded change first.",
    )

    assert resolution.intake.status == PatchIntakeStatus.REJECTED
    assert resolution.intake.resolution_code == PatchResolutionCode.FOUNDER_REJECTED
    assert "isolated worker proof" not in target.read_text(encoding="utf-8")
    snapshot = store.build_run_snapshot(run_id)
    evaluation = evaluate_possible_actions(snapshot)
    assert any(action.name.value == "replan_from_failed_execution" for action in evaluation.actions)


def test_patch_approve_rejects_when_workspace_drifted_since_dispatch(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    target = workspace / "src" / "v2_spring" / "ledger" / "demo.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")

    store.dispatch_isolated_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )
    review = store.build_patch_review(run_id)
    target.write_text("VALUE = 2\n", encoding="utf-8")

    resolution = store.approve_patch_intake(str(review.intake.id))

    assert resolution.intake.status == PatchIntakeStatus.REJECTED
    assert resolution.intake.resolution_code == PatchResolutionCode.BASE_HASH_CONFLICT
    assert "VALUE = 2" in target.read_text(encoding="utf-8")
