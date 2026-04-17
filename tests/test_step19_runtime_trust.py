from __future__ import annotations

from datetime import timedelta
from difflib import unified_diff
import hashlib
from pathlib import Path
import subprocess

from sqlalchemy import select

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.execution_claim import ExecutionClaimRenewalPressure, ExecutionClaimStatus
from v2_spring.domain.routing import ExecutionRuntime
from v2_spring.domain.run import RunCreateInput
from v2_spring.domain.runtime_trust import RuntimeTrustMode
from v2_spring.domain.task import TaskKind, TaskStatus
from v2_spring.ledger.models import EventLedgerRecord, ExecutionClaimRecord, LedgerEventType, TaskRecord, utc_now
from v2_spring.ledger.store import LedgerStore
from v2_spring.runtime.containerized_worker import ContainerizedWorkerReceipt
import v2_spring.ledger.store as store_module


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step19.db'}")


def _create_ready_run(store: LedgerStore, *, goal: str) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal=goal,
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def _init_git_workspace(workspace: Path) -> None:
    subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True, text=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _build_patch(path: str, before: str, after: str) -> str:
    return "".join(
        unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        ),
    )


def _failure_receipt(workspace: Path, *, execution_context_id: str) -> ContainerizedWorkerReceipt:
    now = utc_now()
    readme = workspace / "README.md"
    base_text = readme.read_text(encoding="utf-8")
    return ContainerizedWorkerReceipt(
        execution_context_id=execution_context_id,
        image="demo:static",
        image_digest="sha256:broken",
        container_name=f"demo-{execution_context_id}",
        command="containerized_worker_proof --workspace /workspace",
        source_workspace=str(workspace),
        sandbox_cwd="/workspace",
        started_at=now - timedelta(seconds=1),
        finished_at=now,
        timeout_seconds=10,
        returncode=127,
        timed_out=False,
        stdout_preview="",
        stderr_preview="python: not found",
        stdout_bytes=0,
        stderr_bytes=len("python: not found"),
        changed_files=["README.md"],
        patch_body=None,
        summary="Containerized worker proof exited with non-zero code 127.",
        base_file_hashes={"README.md": _sha256_text(base_text)},
        excluded_names=[],
        env_allowlist=[],
        secret_surface_present=False,
    )


def _success_receipt(
    workspace: Path,
    *,
    execution_context_id: str,
    dynamic_check_performed: bool,
) -> ContainerizedWorkerReceipt:
    now = utc_now()
    readme = workspace / "README.md"
    before = readme.read_text(encoding="utf-8")
    after = before.rstrip("\n") + "\n\npatched by worker\n"
    return ContainerizedWorkerReceipt(
        execution_context_id=execution_context_id,
        image="demo:static",
        image_digest="sha256:healthy",
        container_name=f"demo-{execution_context_id}",
        command="containerized_worker_proof --workspace /workspace",
        source_workspace=str(workspace),
        sandbox_cwd="/workspace",
        started_at=now - timedelta(seconds=1),
        finished_at=now,
        timeout_seconds=10,
        returncode=0,
        timed_out=False,
        preflight_strategy=(
            "static_manifest_plus_dynamic" if dynamic_check_performed else "static_manifest"
        ),
        dynamic_check_performed=dynamic_check_performed,
        dynamic_check_tools=["python"] if dynamic_check_performed else [],
        capability_manifest_tools=["python"],
        stdout_preview="ok",
        stderr_preview="",
        stdout_bytes=2,
        stderr_bytes=0,
        changed_files=["README.md"],
        patch_body=_build_patch("README.md", before, after),
        summary="Containerized worker proof produced a bounded patch touching 1 file(s).",
        base_file_hashes={"README.md": _sha256_text(before)},
        excluded_names=[],
        env_allowlist=[],
        secret_surface_present=False,
    )


def test_container_runtime_trust_promotes_to_dynamic_after_three_failures(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    def fake_execute(**kwargs):
        return _failure_receipt(
            Path(kwargs["workspace"]),
            execution_context_id=kwargs["execution_context_id"],
        )

    monkeypatch.setattr(store_module, "execute_containerized_worker_proof", fake_execute)

    for idx in range(3):
        workspace = tmp_path / f"workspace-fail-{idx}"
        workspace.mkdir()
        _init_git_workspace(workspace)
        (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
        run_id = _create_ready_run(store, goal=f"Trigger runtime trust strike {idx}")
        result = store.dispatch_containerized_worker_task(
            run_id=run_id,
            workspace=workspace,
            artifact_root=tmp_path / "artifacts",
            timeout_seconds=10,
        )
        assert result.task.status == TaskStatus.FAILED

    trust = store.get_runtime_trust(ExecutionRuntime.CONTAINERIZED_WORKER)
    assert trust.mode == RuntimeTrustMode.DYNAMIC_PROMOTED
    assert trust.dynamic_preflight_required is True
    assert trust.consecutive_mismatch_failures == 3
    assert trust.total_mismatch_failures == 3
    assert trust.last_failure_reason == "runtime_tool_missing_or_broken"


def test_container_runtime_trust_recovers_after_two_dynamic_successes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    forced_dynamic_flags: list[bool] = []
    call_count = {"value": 0}

    def fake_execute(**kwargs):
        call_count["value"] += 1
        forced_dynamic_flags.append(bool(kwargs.get("force_dynamic_preflight")))
        workspace = Path(kwargs["workspace"])
        if call_count["value"] <= 3:
            return _failure_receipt(
                workspace,
                execution_context_id=kwargs["execution_context_id"],
            )
        return _success_receipt(
            workspace,
            execution_context_id=kwargs["execution_context_id"],
            dynamic_check_performed=bool(kwargs.get("force_dynamic_preflight")),
        )

    monkeypatch.setattr(store_module, "execute_containerized_worker_proof", fake_execute)

    for idx in range(5):
        workspace = tmp_path / f"workspace-mixed-{idx}"
        workspace.mkdir()
        _init_git_workspace(workspace)
        (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
        run_id = _create_ready_run(store, goal=f"Runtime trust recovery {idx}")
        store.dispatch_containerized_worker_task(
            run_id=run_id,
            workspace=workspace,
            artifact_root=tmp_path / "artifacts",
            timeout_seconds=10,
        )

    trust = store.get_runtime_trust(ExecutionRuntime.CONTAINERIZED_WORKER)
    assert forced_dynamic_flags[:3] == [False, False, False]
    assert forced_dynamic_flags[3:] == [True, True]
    assert trust.mode == RuntimeTrustMode.STATIC_MANIFEST
    assert trust.dynamic_preflight_required is False
    assert trust.consecutive_mismatch_failures == 0
    assert trust.recovery_success_streak == 0
    assert trust.last_success_at is not None


def test_claim_renewal_is_coalesced_inside_cadence_window(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store, goal="Prove heartbeat hygiene")
    near_expiry = utc_now() + timedelta(seconds=2)

    with store.session() as session:
        task = TaskRecord(
            run_id=run_id,
            decision_id=None,
            kind=TaskKind.CONTAINERIZED_WORKER_PROOF,
            status=TaskStatus.RUNNING,
            summary="Running bounded containerized worker",
            execution_context_id="ctx-step19-renew",
            execution_claim_token="lease-step19",
            execution_claim_fencing_token=4,
            command="containerized_worker_proof --workspace /tmp/demo",
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
                runtime="containerized_worker",
                owner="containerized_worker_dispatch",
                lease_token="lease-step19",
                status=ExecutionClaimStatus.ACTIVE,
                acquired_at=utc_now() - timedelta(seconds=20),
                heartbeat_at=utc_now(),
                expires_at=near_expiry,
                released_at=None,
                reclaim_reason=None,
                version=4,
            ),
        )

    renewed = store.renew_execution_claim(
        run_id=run_id,
        execution_context_id="ctx-step19-renew",
        lease_token="lease-step19",
        fencing_token=4,
        timeout_seconds=30,
        owner="containerized_worker_dispatch",
    )
    assert renewed is not None
    assert renewed.renewal_pressure == ExecutionClaimRenewalPressure.COALESCED

    with store.session() as session:
        renewed_events = list(
            session.scalars(
                select(EventLedgerRecord).where(
                    EventLedgerRecord.run_id == run_id,
                    EventLedgerRecord.event_type == LedgerEventType.EXECUTION_CLAIM_RENEWED,
                ),
            ).all(),
        )
    assert len(renewed_events) == 0
