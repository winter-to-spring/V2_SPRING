from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import subprocess

import pytest

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.execution_claim import ExecutionClaimRefusalCode, ExecutionClaimStatus
from v2_spring.domain.progress import ProgressSurfaceStatus
from v2_spring.domain.run import RunCreateInput, RunStatus
from v2_spring.domain.task import TaskKind, TaskStatus
from v2_spring.ledger.models import ExecutionClaimRecord, RunRecord, TaskRecord, utc_now
from v2_spring.ledger.store import ExecutionClaimConflictError, LedgerStore


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step17.db'}")


def _create_run(store: LedgerStore, *, ready: bool = True) -> tuple[str, str]:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove Step 17 execution leases",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    if ready:
        store.resolve_approval(str(approval.id), approved=True)
    return str(run.id), str(approval.id)


def _init_git_workspace(workspace: Path) -> None:
    subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True, text=True)


def test_competing_dispatch_is_refused_when_live_claim_exists(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id, _ = _create_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")

    with store.session() as session:
        session.add(
            ExecutionClaimRecord(
                run_id=run_id,
                task_id=None,
                runtime="isolated_worker",
                owner="test-owner",
                lease_token="lease-1",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now(),
                heartbeat_at=utc_now(),
                expires_at=utc_now() + timedelta(minutes=5),
                released_at=None,
                reclaim_reason=None,
                version=1,
            ),
        )

    with pytest.raises(ExecutionClaimConflictError) as exc_info:
        store.dispatch_isolated_worker_task(
            run_id=run_id,
            workspace=workspace,
            artifact_root=tmp_path / "artifacts",
            timeout_seconds=5,
        )

    assert exc_info.value.refusal.code == ExecutionClaimRefusalCode.ACTIVE_CLAIM_HELD
    assert exc_info.value.refusal.existing_claim.owner == "test-owner"


def test_reconcile_expired_claim_marks_task_failed_and_run_ready(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id, _ = _create_run(store)

    with store.session() as session:
        run = session.get(RunRecord, run_id)
        assert run is not None
        run.status = RunStatus.RUNNING
        task = TaskRecord(
            run_id=run_id,
            decision_id=None,
            kind=TaskKind.ISOLATED_WORKER_PROOF,
            status=TaskStatus.RUNNING,
            summary="Running bounded worker",
            execution_context_id="ctx-123",
            command="isolated_worker_proof --workspace /tmp/demo",
            cwd="/tmp/demo",
            timeout_seconds=5,
            started_at=utc_now(),
        )
        session.add(task)
        session.flush()
        session.add(
            ExecutionClaimRecord(
                run_id=run_id,
                task_id=task.id,
                runtime="isolated_worker",
                owner="isolated_worker_dispatch",
                lease_token="lease-2",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now() - timedelta(minutes=2),
                heartbeat_at=utc_now() - timedelta(minutes=2),
                expires_at=utc_now() - timedelta(seconds=1),
                released_at=None,
                reclaim_reason=None,
                version=1,
            ),
        )

    reclaimed = store.reclaim_execution_claims(run_id)
    assert len(reclaimed) == 1
    assert reclaimed[0].status == ExecutionClaimStatus.RECLAIMED

    task = store.list_tasks_for_run(run_id)[-1]
    assert task.status == TaskStatus.FAILED
    assert store.get_run(run_id).status == RunStatus.READY
    assert store.build_run_snapshot(run_id).active_execution_claim is None


def test_snapshot_and_progress_surface_include_active_execution_claim(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id, _ = _create_run(store)

    with store.session() as session:
        session.add(
            ExecutionClaimRecord(
                run_id=run_id,
                task_id=None,
                runtime="containerized_worker",
                owner="containerized_worker_dispatch",
                lease_token="lease-3",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now(),
                heartbeat_at=utc_now(),
                expires_at=utc_now() + timedelta(minutes=5),
                released_at=None,
                reclaim_reason=None,
                version=1,
            ),
        )

    snapshot = store.build_run_snapshot(run_id)
    assert snapshot.active_execution_claim is not None
    assert snapshot.active_execution_claim.runtime == "containerized_worker"

    progress = store.build_run_progress(run_id)
    assert progress.active_execution_claim is not None
    assert progress.surface_status == ProgressSurfaceStatus.RUNNING_EXECUTION
    assert any("task claim" in hint.command for hint in progress.suggested_commands)


def test_approval_resolution_is_blocked_by_live_execution_claim(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id, approval_id = _create_run(store, ready=False)

    with store.session() as session:
        session.add(
            ExecutionClaimRecord(
                run_id=run_id,
                task_id=None,
                runtime="isolated_worker",
                owner="test-owner",
                lease_token="lease-4",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now(),
                heartbeat_at=utc_now(),
                expires_at=utc_now() + timedelta(minutes=5),
                released_at=None,
                reclaim_reason=None,
                version=1,
            ),
        )

    with pytest.raises(ExecutionClaimConflictError) as exc_info:
        store.resolve_approval(approval_id, approved=True)

    assert exc_info.value.refusal.code == ExecutionClaimRefusalCode.ACTIVE_CLAIM_HELD
