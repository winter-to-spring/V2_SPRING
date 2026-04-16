from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.decision import DecisionKind
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.run import RunCreateInput
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
