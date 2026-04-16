from __future__ import annotations

from pathlib import Path
import json

import pytest

from v2_spring.cli import main
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.progress import ProgressActionOwner, ProgressSurfaceStatus, ProgressTraceMode
from v2_spring.domain.run import RunCreateInput
from v2_spring.ledger.store import LedgerStore


def _make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step11.db'}")


def _database_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'step11.db'}"


def _create_run(store: LedgerStore, *, goal: str) -> str:
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal=goal,
            urgency="normal",
            risk="medium",
        ),
    )
    return str(run.id)


def _approve_run(store: LedgerStore, run_id: str) -> None:
    approval = next(
        item for item in store.list_approvals(status=ApprovalStatus.PENDING) if str(item.run_id) == run_id
    )
    store.resolve_approval(str(approval.id), approved=True)


def test_progress_summary_is_on_the_fly_and_waiting_on_approval(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    run_id = _create_run(store, goal="Show founder/operator progress without mutating ledger")
    store.record_observation(
        run_id=run_id,
        kind=ObservationKind.SYSTEM_AUDIT,
        summary="Planner transport completed successfully.",
        details="error_code=planner_transport_success; provider=scripted; detail=/Users/changhyeon/Desktop/AI AGENT/tmp.",
    )

    events_before = len(store.list_events_for_run(run_id))
    progress = store.build_run_progress(run_id)
    events_after = len(store.list_events_for_run(run_id))

    assert progress.trace_mode == ProgressTraceMode.SUMMARY
    assert progress.surface_status == ProgressSurfaceStatus.WAITING_ON_APPROVAL
    assert progress.action_required_by == ProgressActionOwner.FOUNDER
    assert progress.pending_approval is not None
    assert progress.recent_audits[-1].error_code == "planner_transport_success"
    assert progress.recent_audits[-1].detail_preview is not None
    assert "[workspace]" in progress.recent_audits[-1].detail_preview
    assert progress.trace_entries == []
    assert events_before == events_after


def test_run_status_cli_trace_and_raw_modes_surface_audit_details(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    run_id = _create_run(store, goal="Render compact and raw founder status views")
    store.record_observation(
        run_id=run_id,
        kind=ObservationKind.SYSTEM_AUDIT,
        summary="Planner transport hit a recoverable network issue.",
        details="error_code=provider_timeout; path=/Users/changhyeon/Desktop/AI AGENT/src/app.py; retry_count=1.",
    )

    database_url = _database_url(tmp_path)

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "run", "status", run_id, "--trace", "--database-url", database_url],
    )
    main()
    trace_output = capsys.readouterr().out

    assert "surface_status:      waiting_on_approval" in trace_output
    assert "Trace details" in trace_output
    assert "[workspace]/src/app.py" in trace_output
    assert "/Users/changhyeon/Desktop/AI AGENT/src/app.py" not in trace_output

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "run", "status", run_id, "--raw", "--database-url", database_url],
    )
    main()
    raw_output = capsys.readouterr().out

    assert "Raw trace" in raw_output
    assert "/Users/changhyeon/Desktop/AI AGENT/src/app.py" in raw_output


def test_run_status_waiting_on_founder_shows_bounded_reply_commands(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    run_id = _create_run(store, goal="Expose pending founder escalation in the progress surface")
    _approve_run(store, run_id)
    snapshot_hash = store.build_run_snapshot(run_id).state_hash
    escalation = store.record_planner_escalation(
        run_id=run_id,
        snapshot_hash=snapshot_hash,
        analysis_summary="The founder should clarify whether approval should be resolved manually.",
        confidence="low_needs_review",
        help_kind="clarification",
        blocking_reason="The next step depends on a founder policy choice.",
        requested_help="Explain whether the founder wants to approve or reject the current gate.",
    )

    monkeypatch.setattr(
        "sys.argv",
            ["v2-spring", "run", "status", run_id, "--database-url", _database_url(tmp_path)],
    )
    main()
    output = capsys.readouterr().out

    assert "surface_status:      waiting_on_founder" in output
    assert "Pending founder escalation" in output
    assert str(escalation.id) in output
    assert "--message-file ./founder_hint.txt" in output
    assert "--reason-file ./override_reason.txt" in output


def test_founder_hint_file_and_status_json_contract(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    run_id = _create_run(store, goal="Accept multiline founder hints from a file")
    _approve_run(store, run_id)
    snapshot_hash = store.build_run_snapshot(run_id).state_hash
    escalation = store.record_planner_escalation(
        run_id=run_id,
        snapshot_hash=snapshot_hash,
        analysis_summary="The founder should provide a bounded hint before the planner tries again.",
        confidence="low_needs_review",
        help_kind="clarification",
        blocking_reason="A more specific founder hint is required.",
        requested_help="Provide one multiline bounded hint for the next planner attempt.",
    )
    hint_file = tmp_path / "founder_hint.txt"
    hint_file.write_text("Line one\nLine two with more context\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "reply",
            "hint",
            run_id,
            "--escalation-id",
            str(escalation.id),
            "--message-file",
            str(hint_file),
            "--database-url",
                _database_url(tmp_path),
        ],
    )
    main()
    hint_output = capsys.readouterr().out

    assert "Founder intervention" in hint_output
    assert "reply_kind:         hint" in hint_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "status",
            run_id,
            "--format",
            "json",
            "--database-url",
            _database_url(tmp_path),
        ],
    )
    main()
    progress_payload = json.loads(capsys.readouterr().out)

    assert progress_payload["surface_status"] == "ready_for_next_action"
    assert progress_payload["action_required_by"] == "system"
    assert progress_payload["trace_mode"] == "summary"
    assert isinstance(progress_payload["recent_audits"], list)
    assert isinstance(progress_payload["suggested_commands"], list)
    assert progress_payload["recent_founder_interventions"][-1]["reply_kind"] == "hint"
