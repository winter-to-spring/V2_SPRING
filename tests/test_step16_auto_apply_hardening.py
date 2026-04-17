from __future__ import annotations

from pathlib import Path
import subprocess
from textwrap import dedent

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.patch_intake import (
    PatchIntakeStatus,
    PatchResolutionCode,
    PatchRiskClass,
    PatchWarningCode,
)
from v2_spring.domain.run import RunCreateInput, RunStatus
from v2_spring.ledger.models import ArtifactRecord, PatchIntakeRecord, RunRecord
from v2_spring.ledger.store import LedgerStore


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step16.db'}")


def _create_ready_run(store: LedgerStore) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove Step 16 auto-apply hardening",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def _init_git_workspace(workspace: Path) -> None:
    subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True, text=True)


def _set_run_status(store: LedgerStore, run_id: str, status: RunStatus) -> None:
    with store.session() as session:
        run = session.get(RunRecord, run_id)
        assert run is not None
        run.status = status


def _overwrite_patch_with_invalid_python(store: LedgerStore, intake_id: str) -> None:
    with store.session() as session:
        intake = session.get(PatchIntakeRecord, intake_id)
        assert intake is not None
        patch_artifact = session.get(ArtifactRecord, intake.patch_artifact_id)
        assert patch_artifact is not None
        Path(patch_artifact.path).write_text(
            dedent(
                """\
                --- a/src/v2_spring/ledger/demo.py
                +++ b/src/v2_spring/ledger/demo.py
                @@ -1 +1,2 @@
                 VALUE = 1
                +if True print("oops")
                """,
            ),
            encoding="utf-8",
        )


def test_central_file_patch_forces_founder_review(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    target = workspace / "src" / "v2_spring" / "domain" / "base.py"
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
    assert intake.risk_class == PatchRiskClass.HIGH
    assert intake.auto_apply_eligible is False
    assert any(warning.code == PatchWarningCode.CENTRAL_FILE for warning in intake.warnings)
    assert "waiting on founder patch review" in result.observation.summary.lower()


def test_repeated_auto_apply_on_same_file_falls_back_to_founder_review(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _init_git_workspace(workspace)
    readme = workspace / "README.md"
    readme.write_text("# Demo\n", encoding="utf-8")

    for _ in range(2):
        result = store.dispatch_isolated_worker_task(
            run_id=run_id,
            workspace=workspace,
            artifact_root=tmp_path / "artifacts",
            timeout_seconds=5,
        )
        assert "auto-applied" in result.observation.summary.lower()
        readme.write_text("# Demo\n", encoding="utf-8")
        _set_run_status(store, run_id, RunStatus.READY)

    result = store.dispatch_isolated_worker_task(
        run_id=run_id,
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    intake = store.list_patch_intakes_for_run(run_id)[-1]
    assert intake.status == PatchIntakeStatus.PENDING
    assert intake.auto_apply_eligible is False
    assert any(warning.code == PatchWarningCode.AUTO_APPLY_BURST for warning in intake.warnings)
    assert "waiting on founder patch review" in result.observation.summary.lower()


def test_structural_scan_catches_obfuscated_dangerous_pattern(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)

    with store.session() as session:
        warnings, risk_class, auto_apply_eligible, summary = store._build_patch_review_policy(  # noqa: SLF001
            session=session,
            run_id=run_id,
            patch_body=dedent(
                """\
                --- a/demo.py
                +++ b/demo.py
                @@ -1 +1,3 @@
                 VALUE = 1
                +import os
                +runner = getattr(os, "sys" + "tem")
                +runner("echo hi")
                """,
            ),
            changed_files=["demo.py"],
        )

    assert risk_class == PatchRiskClass.HIGH
    assert auto_apply_eligible is False
    assert "founder review is required" in summary.lower()
    assert any(warning.code == PatchWarningCode.STRUCTURAL_DANGER for warning in warnings)


def test_repeated_patch_repair_failures_open_founder_escalation_with_detailed_feedback(tmp_path: Path) -> None:
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
    intake = store.list_patch_intakes_for_run(run_id)[-1]
    _overwrite_patch_with_invalid_python(store, str(intake.id))
    resolution = store.approve_patch_intake(str(intake.id))
    assert resolution.intake.status == PatchIntakeStatus.REJECTED
    assert resolution.intake.resolution_code == PatchResolutionCode.VALIDATION_FAILED
    assert "validation_returncode=" in (resolution.intake.resolution_reason or "")
    assert "syntaxerror" in (resolution.intake.resolution_reason or "").lower()

    with store.session() as session:
        base_record = session.get(PatchIntakeRecord, str(intake.id))
        run = session.get(RunRecord, run_id)
        assert base_record is not None
        assert run is not None
        for _ in range(2):
            session.add(
                PatchIntakeRecord(
                    run_id=base_record.run_id,
                    task_id=base_record.task_id,
                    patch_artifact_id=base_record.patch_artifact_id,
                    receipt_artifact_id=base_record.receipt_artifact_id,
                    validation_artifact_id=base_record.validation_artifact_id,
                    status=PatchIntakeStatus.REJECTED,
                    summary=base_record.summary,
                    source_workspace=base_record.source_workspace,
                    changed_files=list(base_record.changed_files),
                    touched_file_count=base_record.touched_file_count,
                    patch_size_bytes=base_record.patch_size_bytes,
                    patch_sha256=base_record.patch_sha256,
                    risk_class=base_record.risk_class,
                    auto_apply_eligible=base_record.auto_apply_eligible,
                    warnings=list(base_record.warnings or []),
                    resolution_code=PatchResolutionCode.VALIDATION_FAILED,
                    resolution_reason=base_record.resolution_reason,
                    validation_command=base_record.validation_command,
                    resolved_at=base_record.resolved_at,
                ),
            )
        session.flush()
        failure_count = store._count_patch_repair_failures(  # noqa: SLF001
            session=session,
            run_id=run_id,
            changed_files=list(base_record.changed_files),
        )
        assert failure_count >= 3
        store._maybe_record_patch_repair_escalation(  # noqa: SLF001
            session=session,
            run=run,
            patch_intake=base_record,
            repair_failure_count=failure_count,
        )

    snapshot = store.build_run_snapshot(run_id)
    assert snapshot.pending_founder_escalation is not None
    assert "repair failures" in snapshot.pending_founder_escalation.summary.lower()

    failure_report = store.build_failure_report(run_id)
    assert failure_report is not None
    assert failure_report.error_code == PatchResolutionCode.VALIDATION_FAILED.value
    assert failure_report.short_traceback is not None
    assert "syntaxerror" in failure_report.short_traceback.lower()
    assert failure_report.repeated_failure_streak >= 3
