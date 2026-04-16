from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from v2_spring.domain.artifact import ArtifactStorageKind, ArtifactType
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.decision import DecisionKind
from v2_spring.domain.founder_intervention import FOUNDER_REPLY_INPUT_ADAPTER, FounderReplyKind
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.planner_attempt import PlannerAttemptOutcome
from v2_spring.domain.proposal import PlannerProposalInput
from v2_spring.domain.run import RunCreateInput, RunStatus
from v2_spring.domain.snapshot import PossibleActionName, SnapshotActionState
from v2_spring.domain.task import TaskKind, TaskStatus
from v2_spring.planner.actions import POSSIBLE_ACTIONS_ENGINE_VERSION, evaluate_possible_actions
from v2_spring.executor.bounded import BoundedExecutorTimeout
from v2_spring.ledger.models import LedgerEventType
from v2_spring.ledger.store import LedgerStore
from v2_spring.planner.proposals import (
    IllegalPlannerProposalError,
    PlannerPhaseExhaustedError,
    PlannerStaleQuotaExhaustedError,
    StalePlannerProposalError,
    TransportDuplicatePlannerProposalError,
)


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
    assert waiting_snapshot.policy_version == POSSIBLE_ACTIONS_ENGINE_VERSION
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


def test_possible_actions_engine_is_side_effect_free_under_repeated_evaluation(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove possible-actions purity",
            urgency="normal",
            risk="medium",
        ),
    )

    initial_run = store.get_run(str(run.id))
    initial_events = store.list_events_for_run(str(run.id))
    initial_decisions = store.list_decisions_for_run(str(run.id))
    initial_observations = store.list_observations_for_run(str(run.id))

    snapshot_one = store.build_run_snapshot(str(run.id))
    evaluation_one = evaluate_possible_actions(snapshot_one)
    snapshot_two = store.build_run_snapshot(str(run.id))
    evaluation_two = evaluate_possible_actions(snapshot_two)

    final_run = store.get_run(str(run.id))
    final_events = store.list_events_for_run(str(run.id))
    final_decisions = store.list_decisions_for_run(str(run.id))
    final_observations = store.list_observations_for_run(str(run.id))

    assert initial_run is not None
    assert final_run is not None
    assert final_run.status == initial_run.status
    assert snapshot_one.state_hash == snapshot_two.state_hash
    assert evaluation_one.actions == evaluation_two.actions
    assert len(final_events) == len(initial_events)
    assert len(final_decisions) == len(initial_decisions)
    assert len(final_observations) == len(initial_observations)


def test_planner_proposal_accepts_only_current_legal_moves(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prepare planner contract proof",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)

    snapshot = store.build_run_snapshot(str(run.id))
    proposal = PlannerProposalInput(
        snapshot_hash=snapshot.state_hash,
        selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
        rationale="The run is ready and has no bounded execution evidence yet.",
        expected_outcome="One bounded execution task should be recorded for the run.",
    )

    recorded = store.record_planner_proposal(run_id=str(run.id), proposal=proposal)
    proposals = store.list_planner_proposals_for_run(str(run.id))
    decisions = store.list_decisions_for_run(str(run.id))
    events = store.list_events_for_run(str(run.id))

    assert recorded.selected_action == PossibleActionName.EXECUTE_BOUNDED_TASK
    assert recorded.policy_version == POSSIBLE_ACTIONS_ENGINE_VERSION
    assert proposals[-1].decision_id == recorded.decision_id
    assert decisions[-1].kind == DecisionKind.PLANNER_PROPOSAL_ACCEPTED
    assert events[-1].payload["policy_version"] == POSSIBLE_ACTIONS_ENGINE_VERSION
    assert events[-1].payload["legal_action_details"][0]["name"] == PossibleActionName.EXECUTE_BOUNDED_TASK.value


def test_planner_proposal_can_record_pending_approval_resolution_as_non_mutating_evidence(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Record a legal proposal while approval is pending",
            urgency="normal",
            risk="medium",
        ),
    )
    snapshot = store.build_run_snapshot(str(run.id))

    recorded = store.record_planner_proposal(
        run_id=str(run.id),
        proposal=PlannerProposalInput(
            snapshot_hash=snapshot.state_hash,
            selected_action=PossibleActionName.RESOLVE_PENDING_APPROVAL,
            rationale="The run cannot proceed until a human resolves the approval gate.",
            expected_outcome="The founder should approve or reject the pending request.",
        ),
    )

    fetched = store.get_run(str(run.id))
    assert fetched is not None
    assert fetched.status == RunStatus.WAITING_APPROVAL
    assert recorded.selected_action == PossibleActionName.RESOLVE_PENDING_APPROVAL


def test_planner_proposal_rejects_stale_hash_and_illegal_action(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Reject stale and illegal planner proposals",
            urgency="normal",
            risk="medium",
        ),
    )
    waiting_snapshot = store.build_run_snapshot(str(run.id))

    with pytest.raises(IllegalPlannerProposalError) as illegal_exc:
        store.record_planner_proposal(
            run_id=str(run.id),
            proposal=PlannerProposalInput(
                snapshot_hash=waiting_snapshot.state_hash,
                selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
                rationale="This should fail because approval is still pending.",
                expected_outcome="Execution should not be allowed.",
            ),
        )
    assert "action_state=available" in str(illegal_exc.value).lower()
    assert "resolve_pending_approval" in str(illegal_exc.value)
    illegal_observation = store.list_observations_for_run(str(run.id))[-1]
    assert illegal_observation.kind == ObservationKind.SYSTEM_AUDIT
    assert "selected action was not legal" in illegal_observation.summary.lower()
    assert not any(
        decision.kind == DecisionKind.PLANNER_PROPOSAL_ACCEPTED
        for decision in store.list_decisions_for_run(str(run.id))
    )

    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)

    with pytest.raises(StalePlannerProposalError):
        store.record_planner_proposal(
            run_id=str(run.id),
            proposal=PlannerProposalInput(
                snapshot_hash=waiting_snapshot.state_hash,
                selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
                rationale="The hash is stale because approval already changed the run.",
                expected_outcome="The proposal should be rejected as stale.",
            ),
        )
    stale_observation = store.list_observations_for_run(str(run.id))[-1]
    assert stale_observation.kind == ObservationKind.SYSTEM_AUDIT
    assert "snapshot hash was stale" in stale_observation.summary.lower()


def test_planner_phase_budget_exhausts_after_three_budget_consuming_failures(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prove planner phase exhaustion",
            urgency="normal",
            risk="medium",
        ),
    )
    for index in range(3):
        snapshot = store.build_run_snapshot(str(run.id))
        with pytest.raises(IllegalPlannerProposalError):
            store.record_planner_proposal(
                run_id=str(run.id),
                proposal=PlannerProposalInput(
                    snapshot_hash=snapshot.state_hash,
                    selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
                    rationale=f"Illegal attempt {index + 1}",
                    expected_outcome="Should be rejected while approval is pending.",
                ),
            )

    attempts = store.list_planner_attempts_for_run(str(run.id))
    exhausted_snapshot = store.build_run_snapshot(str(run.id))

    assert [attempt.outcome for attempt in attempts][-1] == PlannerAttemptOutcome.PHASE_EXHAUSTED
    assert exhausted_snapshot.planner_phase_exhausted is True
    assert exhausted_snapshot.planner_budget_used == 3
    assert exhausted_snapshot.planner_budget_remaining == 0

    with pytest.raises(PlannerPhaseExhaustedError):
        store.record_planner_proposal(
            run_id=str(run.id),
            proposal=PlannerProposalInput(
                snapshot_hash=exhausted_snapshot.state_hash,
                selected_action=PossibleActionName.RESOLVE_PENDING_APPROVAL,
                rationale="Try again after exhaustion",
                expected_outcome="This should be blocked until a recharge happens.",
            ),
        )


def test_transport_duplicate_does_not_consume_phase_budget(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Separate transport duplicates from cognitive retries",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)

    snapshot = store.build_run_snapshot(str(run.id))
    accepted = store.record_planner_proposal(
        run_id=str(run.id),
        proposal=PlannerProposalInput(
            snapshot_hash=snapshot.state_hash,
            selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
            submission_key="transport-1",
            rationale="Take the one legal bounded execution step.",
            expected_outcome="A bounded task can be executed next.",
        ),
    )
    assert accepted.submission_key == "transport-1"

    with pytest.raises(TransportDuplicatePlannerProposalError):
        store.record_planner_proposal(
            run_id=str(run.id),
            proposal=PlannerProposalInput(
                snapshot_hash=snapshot.state_hash,
                selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
                submission_key="transport-1",
                rationale="Retry the same packet after a transport glitch.",
                expected_outcome="This should be rejected explicitly but not consume budget.",
            ),
        )

    snapshot_after = store.build_run_snapshot(str(run.id))
    attempts = store.list_planner_attempts_for_run(str(run.id))

    assert snapshot_after.planner_budget_used == 0
    assert snapshot_after.planner_budget_remaining == 3
    assert [attempt.outcome for attempt in attempts] == [
        PlannerAttemptOutcome.ACCEPTED,
        PlannerAttemptOutcome.REJECTED_DUPLICATE_TRANSPORT,
    ]


def test_manual_planner_recharge_reopens_exhausted_phase(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Allow a founder to reopen one exhausted planner phase",
            urgency="normal",
            risk="medium",
        ),
    )
    for index in range(3):
        snapshot = store.build_run_snapshot(str(run.id))
        with pytest.raises(IllegalPlannerProposalError):
            store.record_planner_proposal(
                run_id=str(run.id),
                proposal=PlannerProposalInput(
                    snapshot_hash=snapshot.state_hash,
                    selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
                    rationale=f"Illegal attempt before recharge {index + 1}",
                    expected_outcome="Should still be blocked on approval.",
                ),
            )

    recharge = store.record_planner_recharge(
        run_id=str(run.id),
        reason="The founder wants one more planning pass after reviewing the failed attempts.",
    )
    recharged_snapshot = store.build_run_snapshot(str(run.id))
    accepted = store.record_planner_proposal(
        run_id=str(run.id),
        proposal=PlannerProposalInput(
            snapshot_hash=recharged_snapshot.state_hash,
            selected_action=PossibleActionName.RESOLVE_PENDING_APPROVAL,
            rationale="The next legal move is still to resolve the human approval gate.",
            expected_outcome="The founder should approve or reject the run explicitly.",
        ),
    )

    replay = store.build_run_replay(str(run.id))

    assert recharge.outcome == PlannerAttemptOutcome.MANUAL_RECHARGE
    assert recharged_snapshot.planner_phase_exhausted is False
    assert recharged_snapshot.planner_budget_used == 0
    assert accepted.selected_action == PossibleActionName.RESOLVE_PENDING_APPROVAL
    assert any(
        attempt.outcome == PlannerAttemptOutcome.MANUAL_RECHARGE
        for attempt in replay.planner_attempts
    )


def test_stale_proposals_use_separate_stale_quota(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Verify stale quota fairness",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)

    for _ in range(2):
        with pytest.raises(StalePlannerProposalError):
            store.record_planner_proposal(
                run_id=str(run.id),
                proposal=PlannerProposalInput(
                    snapshot_hash="0" * 64,
                    selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
                    rationale="This snapshot is stale on purpose.",
                    expected_outcome="The stale quota should increase without consuming the main budget.",
                ),
            )

    snapshot = store.build_run_snapshot(str(run.id))
    assert snapshot.planner_budget_used == 0
    assert snapshot.planner_stale_quota_used == 2
    assert snapshot.planner_stale_quota_remaining == 1

    with pytest.raises(PlannerStaleQuotaExhaustedError):
        store.record_planner_proposal(
            run_id=str(run.id),
            proposal=PlannerProposalInput(
                snapshot_hash="0" * 64,
                selected_action=PossibleActionName.EXECUTE_BOUNDED_TASK,
                rationale="One more stale attempt should exhaust the separate stale quota.",
                expected_outcome="The system should now block repeated stale retries.",
            ),
        )

    exhausted_snapshot = store.build_run_snapshot(str(run.id))
    assert exhausted_snapshot.planner_budget_used == 0
    assert exhausted_snapshot.planner_stale_quota_exhausted is True


def test_build_planner_context_includes_structured_failure_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = make_store(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Prepare planner feedback after execution failure",
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
    context = store.build_planner_context(str(run.id))

    assert result.task.status == TaskStatus.FAILED
    assert context.failure_report is not None
    assert context.failure_report.error_code == "timeout"
    assert context.failure_report.previous_rationale is None
    assert context.failure_report.repeated_failure_streak == 1
    assert context.legal_actions[0].name == PossibleActionName.REPLAN_FROM_FAILED_EXECUTION


def test_founder_hint_clears_pending_escalation_and_reopens_planner_lane(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Allow founder hints to unblock a planner escalation",
            urgency="normal",
            risk="medium",
        ),
    )
    initial_snapshot = store.build_run_snapshot(str(run.id))
    escalation = store.record_planner_escalation(
        run_id=str(run.id),
        snapshot_hash=initial_snapshot.state_hash,
        analysis_summary="Approval is still pending, so a founder policy call is required.",
        confidence="low_needs_review",
        help_kind="policy_decision",
        blocking_reason="A pending approval gate blocks every other legal move.",
        requested_help="Approve or reject the run before bounded execution can continue.",
    )
    blocked_snapshot = store.build_run_snapshot(str(run.id))

    with pytest.raises(PermissionError):
        store.record_planner_proposal(
            run_id=str(run.id),
            proposal=PlannerProposalInput(
                snapshot_hash=blocked_snapshot.state_hash,
                selected_action=PossibleActionName.RESOLVE_PENDING_APPROVAL,
                rationale="This should stay blocked until the founder replies to the open escalation.",
                expected_outcome="Nothing should be accepted yet.",
            ),
        )

    intervention = store.record_founder_reply(
        run_id=str(run.id),
        target_escalation_id=str(escalation.id),
        reply=FOUNDER_REPLY_INPUT_ADAPTER.validate_python(
            {
                "kind": "hint",
                "message": "Use the founder-help lane only for explicit approval guidance.",
            },
        ),
    )
    reopened_snapshot = store.build_run_snapshot(str(run.id))
    accepted = store.record_planner_proposal(
        run_id=str(run.id),
        proposal=PlannerProposalInput(
            snapshot_hash=reopened_snapshot.state_hash,
            selected_action=PossibleActionName.RESOLVE_PENDING_APPROVAL,
            rationale="The founder confirmed that approval resolution is still the right next step.",
            expected_outcome="The founder should now approve or reject the intake gate explicitly.",
        ),
    )

    assert intervention.reply_kind == FounderReplyKind.HINT
    assert blocked_snapshot.pending_founder_escalation is not None
    assert reopened_snapshot.pending_founder_escalation is None
    assert reopened_snapshot.planner_phase_exhausted is False
    assert reopened_snapshot.planner_phase_key == initial_snapshot.planner_phase_key
    assert reopened_snapshot.latest_founder_intervention_summary == intervention.summary
    assert accepted.selected_action == PossibleActionName.RESOLVE_PENDING_APPROVAL


def test_founder_reject_exhausts_current_phase_and_records_intervention(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Stop the founder-help lane after a reject",
            urgency="normal",
            risk="medium",
        ),
    )
    snapshot = store.build_run_snapshot(str(run.id))
    escalation = store.record_planner_escalation(
        run_id=str(run.id),
        snapshot_hash=snapshot.state_hash,
        analysis_summary="The founder must decide whether approval should be resolved manually.",
        confidence="low_needs_review",
        help_kind="policy_decision",
        blocking_reason="Approval is still pending.",
        requested_help="Please decide whether to approve or reject the run.",
    )

    intervention = store.record_founder_reply(
        run_id=str(run.id),
        target_escalation_id=str(escalation.id),
        reply=FOUNDER_REPLY_INPUT_ADAPTER.validate_python(
            {
                "kind": "reject",
                "reason": "Do not escalate this again; the planner must stop here for now.",
            },
        ),
    )
    rejected_snapshot = store.build_run_snapshot(str(run.id))
    replay = store.build_run_replay(str(run.id))

    assert intervention.reply_kind == FounderReplyKind.REJECT
    assert rejected_snapshot.pending_founder_escalation is None
    assert rejected_snapshot.planner_phase_exhausted is True
    assert replay.founder_interventions[-1].reply_kind == FounderReplyKind.REJECT
    assert replay.planner_attempts[-1].outcome == PlannerAttemptOutcome.PHASE_EXHAUSTED

    with pytest.raises(PlannerPhaseExhaustedError):
        store.record_planner_proposal(
            run_id=str(run.id),
            proposal=PlannerProposalInput(
                snapshot_hash=rejected_snapshot.state_hash,
                selected_action=PossibleActionName.RESOLVE_PENDING_APPROVAL,
                rationale="This should fail because the founder rejected more help in this phase.",
                expected_outcome="No new planner proposal should be accepted.",
            ),
        )


def test_founder_override_is_bounded_and_records_founder_override_decision(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Allow a bounded founder override",
            urgency="normal",
            risk="medium",
        ),
    )
    snapshot = store.build_run_snapshot(str(run.id))
    escalation = store.record_planner_escalation(
        run_id=str(run.id),
        snapshot_hash=snapshot.state_hash,
        analysis_summary="The founder may want to force a currently legal move.",
        confidence="medium",
        help_kind="manual_override_request",
        blocking_reason="Approval is pending and the founder might prefer a manual decision.",
        requested_help="Choose the current legal action explicitly if you want to override the planner.",
    )

    with pytest.raises(ValueError):
        store.record_founder_reply(
            run_id=str(run.id),
            target_escalation_id=str(escalation.id),
            reply=FOUNDER_REPLY_INPUT_ADAPTER.validate_python(
                {
                    "kind": "override",
                    "selected_action": "execute_bounded_task",
                    "reason": "This should fail because bounded execution is not legal before approval.",
                },
            ),
        )

    intervention = store.record_founder_reply(
        run_id=str(run.id),
        target_escalation_id=str(escalation.id),
        reply=FOUNDER_REPLY_INPUT_ADAPTER.validate_python(
            {
                "kind": "override",
                "selected_action": "resolve_pending_approval",
                "reason": "The founder wants to force the current legal approval action.",
            },
        ),
    )
    snapshot_after = store.build_run_snapshot(str(run.id))
    decisions = store.list_decisions_for_run(str(run.id))

    assert intervention.reply_kind == FounderReplyKind.OVERRIDE
    assert intervention.override_action == PossibleActionName.RESOLVE_PENDING_APPROVAL
    assert snapshot_after.planner_phase_exhausted is True
    assert decisions[-1].kind == DecisionKind.FOUNDER_OVERRIDE_ACCEPTED


def test_founder_hint_quota_exhausts_after_two_replies_in_one_phase(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Bound repeated founder hint ping-pong in one phase",
            urgency="normal",
            risk="medium",
        ),
    )
    for index in range(2):
        snapshot = store.build_run_snapshot(str(run.id))
        escalation = store.record_planner_escalation(
            run_id=str(run.id),
            snapshot_hash=snapshot.state_hash,
            analysis_summary=f"Founder help request {index + 1}",
            confidence="low_needs_review",
            help_kind="clarification",
            blocking_reason="The founder keeps being asked to clarify the same policy boundary.",
            requested_help="Confirm whether the approval lane should remain the only legal move.",
        )
        store.record_founder_reply(
            run_id=str(run.id),
            target_escalation_id=str(escalation.id),
            reply=FOUNDER_REPLY_INPUT_ADAPTER.validate_python(
                {
                    "kind": "hint",
                    "message": f"Hint {index + 1}: stay inside the current approval boundary.",
                },
            ),
        )

    third_snapshot = store.build_run_snapshot(str(run.id))
    with pytest.raises(PlannerPhaseExhaustedError):
        store.record_planner_escalation(
            run_id=str(run.id),
            snapshot_hash=third_snapshot.state_hash,
            analysis_summary="A third founder escalation should exhaust the phase.",
            confidence="low_needs_review",
            help_kind="clarification",
            blocking_reason="The planner should stop instead of ping-ponging forever.",
            requested_help="This should not open a third founder-help lane in the same phase.",
        )

    exhausted_snapshot = store.build_run_snapshot(str(run.id))
    attempts = store.list_planner_attempts_for_run(str(run.id))

    assert exhausted_snapshot.planner_phase_exhausted is True
    assert attempts[-1].outcome == PlannerAttemptOutcome.PHASE_EXHAUSTED
