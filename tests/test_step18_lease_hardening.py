from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.execution_claim import ExecutionClaimStatus
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.run import RunCreateInput, RunStatus
from v2_spring.domain.task import TaskKind, TaskStatus
from v2_spring.ledger.models import (
    EventLedgerRecord,
    ExecutionClaimRecord,
    LedgerEventType,
    ObservationRecord,
    PatchIntakeRecord,
    RunRecord,
    TaskRecord,
    utc_now,
)
from v2_spring.ledger.store import LedgerStore
from v2_spring.runtime.isolated_worker import IsolatedWorkerReceipt


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step18.db'}")


def _create_run(store: LedgerStore, *, ready: bool = True) -> tuple[str, str]:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove Step 18 lease hardening",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    if ready:
        store.resolve_approval(str(approval.id), approved=True)
    return str(run.id), str(approval.id)


def _make_receipt(execution_context_id: str, workspace: Path) -> IsolatedWorkerReceipt:
    now = utc_now()
    return IsolatedWorkerReceipt(
        execution_context_id=execution_context_id,
        command=f"isolated_worker_proof --workspace {workspace}",
        source_workspace=str(workspace),
        sandbox_cwd=str(workspace),
        started_at=now - timedelta(seconds=1),
        finished_at=now,
        timeout_seconds=30,
        returncode=0,
        timed_out=False,
        stdout_preview="ok",
        stderr_preview="",
        stdout_bytes=2,
        stderr_bytes=0,
        stdout_truncated=False,
        stderr_truncated=False,
        changed_files=["README.md"],
        patch_body="--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-demo\n+demo fixed\n",
        summary="completed",
        base_file_hashes={"README.md": "abc"},
        excluded_names=[],
        env_allowlist=[],
        secret_surface_present=False,
    )


def test_claim_renewal_extends_expiry_when_near_threshold(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id, _ = _create_run(store)
    near_expiry = utc_now() + timedelta(seconds=2)

    with store.session() as session:
        task = TaskRecord(
            run_id=run_id,
            decision_id=None,
            kind=TaskKind.ISOLATED_WORKER_PROOF,
            status=TaskStatus.RUNNING,
            summary="Running bounded worker",
            execution_context_id="ctx-renew",
            execution_claim_token="lease-renew",
            execution_claim_fencing_token=3,
            command="isolated_worker_proof --workspace /tmp/demo",
            cwd="/tmp/demo",
            timeout_seconds=30,
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
                lease_token="lease-renew",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now() - timedelta(seconds=20),
                heartbeat_at=utc_now() - timedelta(seconds=20),
                expires_at=near_expiry,
                released_at=None,
                reclaim_reason=None,
                version=3,
            ),
        )

    renewed = store.renew_execution_claim(
        run_id=run_id,
        execution_context_id="ctx-renew",
        lease_token="lease-renew",
        fencing_token=3,
        timeout_seconds=30,
        owner="isolated_worker_dispatch",
    )

    assert renewed is not None
    assert renewed.fencing_token == 3
    assert renewed.expires_at > near_expiry

    with store.session() as session:
        events = list(
            session.scalars(
                select(EventLedgerRecord).where(EventLedgerRecord.run_id == run_id),
            ).all(),
        )
    assert any(event.event_type == LedgerEventType.EXECUTION_CLAIM_RENEWED for event in events)


def test_claim_renewal_skips_write_when_ttl_is_still_healthy(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id, _ = _create_run(store)
    far_expiry = utc_now() + timedelta(seconds=40)

    with store.session() as session:
        task = TaskRecord(
            run_id=run_id,
            decision_id=None,
            kind=TaskKind.ISOLATED_WORKER_PROOF,
            status=TaskStatus.RUNNING,
            summary="Running bounded worker",
            execution_context_id="ctx-no-renew",
            execution_claim_token="lease-no-renew",
            execution_claim_fencing_token=2,
            command="isolated_worker_proof --workspace /tmp/demo",
            cwd="/tmp/demo",
            timeout_seconds=30,
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
                lease_token="lease-no-renew",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now(),
                heartbeat_at=utc_now(),
                expires_at=far_expiry,
                released_at=None,
                reclaim_reason=None,
                version=2,
            ),
        )

    renewed = store.renew_execution_claim(
        run_id=run_id,
        execution_context_id="ctx-no-renew",
        lease_token="lease-no-renew",
        fencing_token=2,
        timeout_seconds=30,
        owner="isolated_worker_dispatch",
    )

    assert renewed is not None
    assert renewed.expires_at == far_expiry

    with store.session() as session:
        events = list(
            session.scalars(
                select(EventLedgerRecord).where(EventLedgerRecord.run_id == run_id),
            ).all(),
        )
    assert not any(event.event_type == LedgerEventType.EXECUTION_CLAIM_RENEWED for event in events)


def test_stale_result_is_rejected_after_reclaim(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id, _ = _create_run(store)
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()

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
            execution_context_id="ctx-stale",
            execution_claim_token="lease-stale",
            execution_claim_fencing_token=1,
            command="isolated_worker_proof --workspace /tmp/demo",
            cwd="/tmp/demo",
            timeout_seconds=30,
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
                lease_token="lease-stale",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now() - timedelta(minutes=1),
                heartbeat_at=utc_now() - timedelta(minutes=1),
                expires_at=utc_now() - timedelta(seconds=1),
                released_at=None,
                reclaim_reason=None,
                version=1,
            ),
        )
        task_id = task.id

    store.reclaim_execution_claims(run_id)
    result = store._finalize_completed_isolated_task(
        run_id=run_id,
        task_id=task_id,
        artifact_root=artifact_root,
        receipt=_make_receipt("ctx-stale", tmp_path),
    )

    assert "rejected" in result.observation.summary.lower()
    assert result.task.status == TaskStatus.FAILED

    with store.session() as session:
        events = list(
            session.scalars(
                select(EventLedgerRecord).where(EventLedgerRecord.run_id == run_id),
            ).all(),
        )
        patch_intakes = list(
            session.scalars(
                select(PatchIntakeRecord).where(PatchIntakeRecord.run_id == run_id),
            ).all(),
        )
    assert any(event.event_type == LedgerEventType.EXECUTION_RESULT_REJECTED for event in events)
    assert patch_intakes == []


def test_stale_fencing_token_is_rejected_when_new_owner_has_taken_claim(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id, _ = _create_run(store)

    with store.session() as session:
        old_task = TaskRecord(
            run_id=run_id,
            decision_id=None,
            kind=TaskKind.ISOLATED_WORKER_PROOF,
            status=TaskStatus.RUNNING,
            summary="Old bounded worker",
            execution_context_id="ctx-old",
            execution_claim_token="lease-old",
            execution_claim_fencing_token=1,
            command="isolated_worker_proof --workspace /tmp/old",
            cwd="/tmp/old",
            timeout_seconds=30,
            started_at=utc_now(),
        )
        new_task = TaskRecord(
            run_id=run_id,
            decision_id=None,
            kind=TaskKind.CONTAINERIZED_WORKER_PROOF,
            status=TaskStatus.RUNNING,
            summary="New bounded worker",
            execution_context_id="ctx-new",
            execution_claim_token="lease-new",
            execution_claim_fencing_token=2,
            command="containerized_worker_proof --workspace /tmp/new",
            cwd="/tmp/new",
            timeout_seconds=30,
            started_at=utc_now(),
        )
        session.add(old_task)
        session.add(new_task)
        session.flush()
        session.add(
            ExecutionClaimRecord(
                run_id=run_id,
                task_id=new_task.id,
                runtime="containerized_worker",
                owner="containerized_worker_dispatch",
                lease_token="lease-new",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now(),
                heartbeat_at=utc_now(),
                expires_at=utc_now() + timedelta(seconds=20),
                released_at=None,
                reclaim_reason=None,
                version=2,
            ),
        )

    renewed = store.renew_execution_claim(
        run_id=run_id,
        execution_context_id="ctx-old",
        lease_token="lease-old",
        fencing_token=1,
        timeout_seconds=30,
        owner="isolated_worker_dispatch",
    )

    assert renewed is None

    with store.session() as session:
        observations = list(
            session.scalars(
                select(ObservationRecord).where(ObservationRecord.run_id == run_id),
            ).all(),
        )
    assert not any(
        observation.kind == ObservationKind.SYSTEM_AUDIT and "execution_claim_renewed" in observation.details
        for observation in observations
    )
