from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.run import RunCreateInput
from v2_spring.domain.snapshot import SnapshotFreshnessConflictError
from v2_spring.ledger.store import LedgerStore


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step20.db'}")


def _create_ready_run(store: LedgerStore) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove Step 20 snapshot freshness and cancellation reconciliation",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def _init_git_workspace(workspace: Path) -> None:
    subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True, text=True)


def test_dispatch_refuses_stale_snapshot_anchor(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")

    snapshot = store.build_run_snapshot(run_id)
    store.record_observation(
        run_id=run_id,
        kind=ObservationKind.SYSTEM_AUDIT,
        summary="Founder/operator surface changed after a stale snapshot was taken.",
        details="error_code=step20_stale_probe; detail=force freshness generation drift.",
    )

    with pytest.raises(SnapshotFreshnessConflictError) as exc_info:
        store.dispatch_isolated_worker_task(
            run_id=run_id,
            workspace=workspace,
            artifact_root=tmp_path / "artifacts",
            timeout_seconds=5,
            snapshot_hash=snapshot.state_hash,
            freshness_generation=snapshot.freshness_generation,
        )

    refusal = exc_info.value.refusal
    assert refusal.mutation_name == "task dispatch"
    assert refusal.expected.snapshot_hash == snapshot.state_hash
    assert refusal.expected.freshness_generation == snapshot.freshness_generation
    assert refusal.current.freshness_generation > snapshot.freshness_generation


def test_patch_approve_refuses_stale_snapshot_anchor(tmp_path: Path) -> None:
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
    store.record_observation(
        run_id=run_id,
        kind=ObservationKind.SYSTEM_AUDIT,
        summary="Founder/operator surface changed before patch approval.",
        details="error_code=step20_patch_stale_probe; detail=force review freshness drift.",
    )

    with pytest.raises(SnapshotFreshnessConflictError) as exc_info:
        store.approve_patch_intake(
            str(review.intake.id),
            snapshot_hash=review.snapshot_hash,
            freshness_generation=review.freshness_generation,
        )

    refusal = exc_info.value.refusal
    assert refusal.mutation_name == "patch approval"
    assert refusal.expected.snapshot_hash == review.snapshot_hash
    assert refusal.expected.freshness_generation == review.freshness_generation
    assert refusal.current.freshness_generation > review.freshness_generation
