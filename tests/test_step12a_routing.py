from __future__ import annotations

from pathlib import Path
import json

from v2_spring.cli import main
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.routing import (
    ExecutionRequirements,
    ExecutionRuntime,
    ExpectedOutputKind,
    RoutingDecision,
    RoutingRefusalCode,
    RoutingRefusalReceipt,
    SystemLimits,
    TaskComplexity,
    WriteScope,
    route_task,
)
from v2_spring.domain.run import RunCreateInput
from v2_spring.ledger.store import LedgerStore


def make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step12a.db'}")


def _create_ready_run(store: LedgerStore) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Inspect execution routing",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return str(run.id)


def test_route_task_downgrades_obvious_read_only_overestimation() -> None:
    outcome = route_task(
        ExecutionRequirements(
            task_complexity=TaskComplexity.HIGH,
            needs_isolation=False,
            requires_network=False,
            needs_multi_file_context=False,
            write_scope=WriteScope.NONE,
            expected_output_kind=ExpectedOutputKind.ARTIFACT_ONLY,
        ),
        SystemLimits(),
    )

    assert isinstance(outcome, RoutingDecision)
    assert outcome.runtime == ExecutionRuntime.BOUNDED_LOCAL
    assert outcome.normalized_requirements.task_complexity == TaskComplexity.LOW
    assert any("downgraded from high to low" in note for note in outcome.guard_notes)


def test_route_task_rejects_capability_escalation_beyond_system_limits() -> None:
    outcome = route_task(
        ExecutionRequirements(
            task_complexity=TaskComplexity.LOW,
            needs_isolation=False,
            requires_network=True,
            needs_multi_file_context=False,
            write_scope=WriteScope.NONE,
            expected_output_kind=ExpectedOutputKind.ARTIFACT_ONLY,
        ),
        SystemLimits(),
    )

    assert isinstance(outcome, RoutingRefusalReceipt)
    assert outcome.refusal_code == RoutingRefusalCode.CAPABILITY_EXCEEDED
    assert "network access" in outcome.message.lower()


def test_route_task_returns_typed_no_matching_runtime_refusal() -> None:
    outcome = route_task(
        ExecutionRequirements(
            task_complexity=TaskComplexity.MEDIUM,
            needs_isolation=True,
            requires_network=False,
            needs_multi_file_context=True,
            write_scope=WriteScope.MULTI_FILE,
            expected_output_kind=ExpectedOutputKind.UNIFIED_PATCH,
        ),
        SystemLimits(available_runtimes=(ExecutionRuntime.BOUNDED_LOCAL,)),
    )

    assert isinstance(outcome, RoutingRefusalReceipt)
    assert outcome.refusal_code == RoutingRefusalCode.NO_MATCHING_RUNTIME
    assert "no currently registered execution runtime" in outcome.message.lower()


def test_store_inspect_task_route_records_audit_for_ready_run(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    run_id = _create_ready_run(store)

    inspection = store.inspect_task_route(run_id, record=True)
    events = store.list_events_for_run(run_id)

    assert isinstance(inspection.outcome, RoutingDecision)
    assert inspection.outcome.runtime == ExecutionRuntime.BOUNDED_LOCAL
    assert inspection.recorded_observation_id is not None
    assert any(
        event.payload.get("summary") == "Execution routing selected bounded_local for execute_bounded_task."
        for event in events
        if event.event_type.value == "OBSERVATION_RECORDED"
    )


def test_task_route_cli_supports_explicit_requirements_and_json(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step12a.db'}"
    store = LedgerStore(database_url)
    run_id = _create_ready_run(store)

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "task",
            "route",
            run_id,
            "--task-complexity",
            "high",
            "--needs-isolation",
            "--no-requires-network",
            "--no-needs-multi-file-context",
            "--write-scope",
            "none",
            "--expected-output-kind",
            "artifact_only",
            "--format",
            "json",
            "--database-url",
            database_url,
        ],
    )
    main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["outcome"]["kind"] == "decision"
    assert payload["outcome"]["runtime"] == "isolated_worker"
    assert payload["outcome"]["normalized_requirements"]["task_complexity"] == "low"
    assert payload["outcome"]["normalized_requirements"]["needs_isolation"] is True


def test_task_route_cli_refuses_when_run_has_no_legal_execution_lane(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step12a-blocked.db'}"
    store = LedgerStore(database_url)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Blocked run should not route execution",
            urgency="normal",
            risk="medium",
        ),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "task",
            "route",
            str(run.id),
            "--format",
            "json",
            "--database-url",
            database_url,
        ],
    )
    main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["outcome"]["kind"] == "refusal"
    assert payload["outcome"]["refusal_code"] == "no_routable_work"
