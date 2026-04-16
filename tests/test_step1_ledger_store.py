from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from v2_spring.domain.artifact import ArtifactStorageKind, ArtifactType
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.decision import DecisionKind
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.run import RunCreateInput
from v2_spring.domain.snapshot import PossibleActionName, SnapshotActionState
from v2_spring.domain.task import TaskKind, TaskStatus
from v2_spring.planner.actions import evaluate_possible_actions
from v2_spring.executor.bounded import BoundedExecutorTimeout
from v2_spring.ledger.models import LedgerEventType
from v2_spring.ledger.store import LedgerStore


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step1.db'}")


def test_create_run_persists_typed_state_and_event(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )

    fetched = store.get_run(str(run.id))
    events = store.list_events_for_run(str(run.id))
    decisions = store.list_decisions_for_run(str(run.id))
    observations = store.list_observations_for_run(str(run.id))
    approvals = store.list_approvals(status=ApprovalStatus.PENDING)

    assert fetched is not None
    assert fetched.project == "demo"
    assert fetched.goal == "Analyze repository structure"
    assert fetched.status.value == "waiting_approval"
    assert len(events) == 4
    assert events[0].event_type == LedgerEventType.RUN_CREATED
    assert {event.event_type for event in events} == {
        LedgerEventType.RUN_CREATED,
        LedgerEventType.OBSERVATION_RECORDED,
        LedgerEventType.DECISION_RECORDED,
        LedgerEventType.APPROVAL_REQUESTED,
    }
    assert len(decisions) == 1
    assert decisions[0].kind == DecisionKind.INTAKE_ACCEPTED
    assert len(observations) == 1
    assert observations[0].kind == ObservationKind.RUN_INTAKE
    assert len(approvals) == 1
    assert approvals[0].status == ApprovalStatus.PENDING


def test_invalid_input_is_rejected_by_validation() -> None:
    with pytest.raises(ValidationError):
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="not-a-real-level",
            risk="medium",
        )


def test_resolving_approval_updates_state_and_ledger(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )

    pending_approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    resolved = store.resolve_approval(str(pending_approval.id), approved=True)
    events = store.list_events_for_run(str(run.id))
    fetched = store.get_run(str(run.id))

    assert resolved.status == ApprovalStatus.APPROVED
    assert fetched is not None
    assert fetched.status.value == "ready"
    assert events[-1].event_type == LedgerEventType.APPROVAL_RESOLVED

    with pytest.raises(ValueError):
        store.resolve_approval(str(pending_approval.id), approved=False)


def test_rejecting_approval_requires_reason_and_records_it(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )
    pending_approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]

    with pytest.raises(ValueError):
        store.resolve_approval(str(pending_approval.id), approved=False)

    resolved = store.resolve_approval(
        str(pending_approval.id),
        approved=False,
        reason="Do not continue until the planner can explain the repository boundary.",
    )
    fetched = store.get_run(str(run.id))
    events = store.list_events_for_run(str(run.id))

    assert resolved.status == ApprovalStatus.REJECTED
    assert resolved.resolution_reason == "Do not continue until the planner can explain the repository boundary."
    assert fetched is not None
    assert fetched.status.value == "rejected"
    assert events[-1].event_type == LedgerEventType.APPROVAL_RESOLVED
    assert events[-1].payload["resolution_reason"] == resolved.resolution_reason


def test_pending_approval_blocks_new_decision_and_observation_until_resolved(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )

    with pytest.raises(PermissionError):
        store.record_decision(
            run_id=str(run.id),
            kind=DecisionKind.FOLLOW_UP,
            summary="Blocked while approval is pending.",
            rationale="This should not be writable before approval resolves.",
        )

    with pytest.raises(PermissionError):
        store.record_observation(
            run_id=str(run.id),
            kind=ObservationKind.FOLLOW_UP,
            summary="Blocked while approval is pending.",
            details="This observation should be prevented until approval resolves.",
        )

    audit_observation = store.record_observation(
        run_id=str(run.id),
        kind=ObservationKind.SYSTEM_AUDIT,
        summary="Approval is still pending and the run remains paused.",
        details="This passive audit note preserves visibility without advancing the run.",
    )
    assert audit_observation.kind == ObservationKind.SYSTEM_AUDIT

    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)

    decision = store.record_decision(
        run_id=str(run.id),
        kind=DecisionKind.FOLLOW_UP,
        summary="Approval completed; the run can continue.",
        rationale="The write barrier should lift after approval is resolved.",
    )
    observation = store.record_observation(
        run_id=str(run.id),
        kind=ObservationKind.FOLLOW_UP,
        summary="Post-approval follow-up recorded.",
        details="This proves that non-approval writes become legal after approval resolves.",
    )

    assert decision.kind == DecisionKind.FOLLOW_UP
    assert observation.kind == ObservationKind.FOLLOW_UP


def test_bounded_execution_persists_task_artifact_and_ledger(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (workspace / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (workspace / ".git").mkdir()
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)

    result = store.execute_bounded_task(
        run_id=str(run.id),
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )
    tasks = store.list_tasks_for_run(str(run.id))
    artifacts = store.list_artifacts_for_run(str(run.id))
    events = store.list_events_for_run(str(run.id))
    fetched = store.get_run(str(run.id))

    assert fetched is not None
    assert fetched.status == fetched.status.COMPLETED
    assert result.task.kind == TaskKind.REPOSITORY_SCAN
    assert result.task.status == TaskStatus.COMPLETED
    assert result.artifact is not None
    assert result.artifact.artifact_type == ArtifactType.TEXT_REPORT
    assert result.artifact.storage_kind == ArtifactStorageKind.FILESYSTEM_PATH
    assert len(result.artifact.sha256) == 64
    assert Path(result.artifact.path).exists()
    assert len(tasks) == 1
    assert len(artifacts) == 1
    assert {event.event_type for event in events}.issuperset(
        {
            LedgerEventType.TASK_CREATED,
            LedgerEventType.TASK_STARTED,
            LedgerEventType.TASK_COMPLETED,
            LedgerEventType.ARTIFACT_RECORDED,
        },
    )
    artifact_body = Path(result.artifact.path).read_text(encoding="utf-8")
    assert "Repository Scan Report" in artifact_body
    assert "- .env" not in artifact_body
    assert "- .git/" not in artifact_body
    assert str(result.task.id) in result.observation.details
    assert str(result.artifact.id) in result.observation.details


def test_bounded_execution_failure_records_failed_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = make_store(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)

    def fail_executor(*, workspace: Path, timeout_seconds: int, execution_context_id: str | None = None):
        raise BoundedExecutorTimeout("Executor timed out while scanning the repository.")

    monkeypatch.setattr("v2_spring.ledger.store.execute_repository_scan", fail_executor)

    result = store.execute_bounded_task(
        run_id=str(run.id),
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=1,
    )
    events = store.list_events_for_run(str(run.id))
    fetched = store.get_run(str(run.id))

    assert fetched is not None
    assert fetched.status == fetched.status.FAILED
    assert result.task.status == TaskStatus.FAILED
    assert result.artifact is None
    assert "timed out" in (result.task.stderr or "").lower()
    assert events[-2].event_type == LedgerEventType.TASK_FAILED
    assert events[-1].event_type == LedgerEventType.OBSERVATION_RECORDED


def test_build_run_replay_includes_linkage_and_integrity(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    execution = store.execute_bounded_task(
        run_id=str(run.id),
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    replay = store.build_run_replay(str(run.id))

    assert replay.run.id == run.id
    assert len(replay.approvals) == 1
    assert any(decision.kind == DecisionKind.BOUNDED_TASK_SELECTED for decision in replay.decisions)
    assert len(replay.tasks) == 1
    task_replay = replay.tasks[0]
    assert task_replay.task.id == execution.task.id
    assert task_replay.decision is not None
    assert len(task_replay.artifacts) == 1
    assert task_replay.artifacts[0].artifact.id == execution.artifact.id
    assert task_replay.artifacts[0].file_exists is True
    assert task_replay.artifacts[0].hash_matches is True
    assert replay.orphan_artifacts == []
    assert replay.consistency_warnings == []


def test_get_artifact_reports_hash_mismatch_when_file_changes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    execution = store.execute_bounded_task(
        run_id=str(run.id),
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    artifact_path = Path(execution.artifact.path)
    artifact_path.write_text("tampered\n", encoding="utf-8")

    inspected = store.get_artifact(str(execution.artifact.id))
    replay = store.build_run_replay(str(run.id))

    assert inspected is not None
    assert inspected.file_exists is True
    assert inspected.hash_matches is False
    assert any("no longer match the stored sha256" in warning for warning in replay.consistency_warnings)


def test_run_snapshot_and_possible_actions_cover_ready_and_terminal_paths(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="medium",
        ),
    )

    waiting_snapshot = store.build_run_snapshot(str(run.id))
    waiting_actions = evaluate_possible_actions(waiting_snapshot)
    assert waiting_snapshot.pending_approval is not None
    assert len(waiting_snapshot.state_hash) == 64
    assert waiting_actions.snapshot.action_state == SnapshotActionState.AVAILABLE
    assert waiting_actions.actions[0].name == PossibleActionName.RESOLVE_PENDING_APPROVAL

    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)

    ready_snapshot = store.build_run_snapshot(str(run.id))
    ready_actions = evaluate_possible_actions(ready_snapshot)
    assert ready_snapshot.pending_approval is None
    assert ready_snapshot.task_summary.created == 0
    assert ready_actions.snapshot.action_state == SnapshotActionState.AVAILABLE
    assert ready_actions.actions[0].name == PossibleActionName.EXECUTE_BOUNDED_TASK

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    store.execute_bounded_task(
        run_id=str(run.id),
        workspace=workspace,
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=5,
    )

    completed_snapshot = store.build_run_snapshot(str(run.id))
    completed_actions = evaluate_possible_actions(completed_snapshot)
    assert completed_snapshot.latest_artifact is not None
    assert completed_actions.snapshot.action_state == SnapshotActionState.TERMINAL
    assert completed_actions.actions == []


def test_run_snapshot_and_possible_actions_capture_rejection_feedback(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="normal",
            risk="high",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(
        str(approval.id),
        approved=False,
        reason="Tighten the repository scope before the next planner loop.",
    )

    snapshot = store.build_run_snapshot(str(run.id))
    actions = evaluate_possible_actions(snapshot)

    assert snapshot.latest_rejection_reason == "Tighten the repository scope before the next planner loop."
    assert actions.snapshot.action_state == SnapshotActionState.AVAILABLE
    assert actions.actions[0].name == PossibleActionName.REPLAN_WITH_REJECTION_FEEDBACK
    assert actions.actions[0].context_hint == snapshot.latest_rejection_reason
