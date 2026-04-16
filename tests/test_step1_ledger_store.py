from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

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

    assert fetched is not None
    assert fetched.project == "demo"
    assert fetched.goal == "Analyze repository structure"
    assert len(events) == 1
    assert events[0].event_type == LedgerEventType.RUN_CREATED
    assert events[0].payload["status"] == "created"


def test_invalid_input_is_rejected_by_validation() -> None:
    with pytest.raises(ValidationError):
        RunCreateInput(
            project="demo",
            goal="Analyze repository structure",
            urgency="not-a-real-level",
            risk="medium",
        )
