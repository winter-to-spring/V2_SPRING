from __future__ import annotations

from pathlib import Path
import json

import pytest

from v2_spring.cli import main
from v2_spring.adapters.langgraph_planner import StructuredTransportResponse
from v2_spring.domain.planner_adapter import PlannerTransportProvider


def test_run_create_and_show_cli_flow(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Analyze repository structure",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    create_output = capsys.readouterr().out

    assert "Created run" in create_output
    created_run_id = create_output.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "show",
            created_run_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    show_output = capsys.readouterr().out

    assert created_run_id in show_output
    assert "status:     waiting_approval" in show_output
    assert "Analyze repository structure" in show_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "events",
            created_run_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    events_output = capsys.readouterr().out

    assert "RUN_CREATED" in events_output
    assert "DECISION_RECORDED" in events_output
    assert "OBSERVATION_RECORDED" in events_output
    assert "APPROVAL_REQUESTED" in events_output
    assert "Run was submitted from the CLI." in events_output
    assert "Run intake accepted." in events_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "list",
            "--database-url",
            database_url,
        ],
    )
    main()
    approval_list_output = capsys.readouterr().out
    approval_id = next(
        line.strip().replace("1. ", "")
        for line in approval_list_output.splitlines()
        if line.startswith("1. ")
    )

    assert "Approvals" in approval_list_output
    assert "pending" in approval_list_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--approve",
            "--database-url",
            database_url,
        ],
    )
    main()
    approval_resolve_output = capsys.readouterr().out

    assert "Approval resolved" in approval_resolve_output
    assert "new_status:       approved" in approval_resolve_output
    assert "resolution_reason:-" in approval_resolve_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "list",
            "--database-url",
            database_url,
        ],
    )
    main()
    empty_pending_output = capsys.readouterr().out
    assert "Tip: use --status all" in empty_pending_output


def test_reject_requires_reason_and_is_visible_in_cli(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-reject.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Reject tracer bullet with feedback",
            "--urgency",
            "normal",
            "--risk",
            "high",
            "--database-url",
            database_url,
        ],
    )
    main()
    create_output = capsys.readouterr().out
    created_run_id = create_output.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "list",
            "--database-url",
            database_url,
        ],
    )
    main()
    approval_output = capsys.readouterr().out
    approval_id = next(
        line.strip().replace("1. ", "")
        for line in approval_output.splitlines()
        if line.startswith("1. ")
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--reject",
            "--database-url",
            database_url,
        ],
    )
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Rejecting without a reason should have failed.")
    missing_reason_output = capsys.readouterr().out
    assert "requires --reason" in missing_reason_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--reject",
            "--reason",
            "Planner boundary is too vague; tighten the repository scope first.",
            "--database-url",
            database_url,
        ],
    )
    main()
    reject_output = capsys.readouterr().out

    assert "new_status:       rejected" in reject_output
    assert "Planner boundary is too vague" in reject_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "show",
            created_run_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    show_output = capsys.readouterr().out

    assert "status:     rejected" in show_output


def test_bounded_execution_cli_flow(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step5.db'}"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Execute a bounded repository scan",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    create_output = capsys.readouterr().out
    run_id = create_output.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "approval", "list", "--database-url", database_url],
    )
    main()
    approval_output = capsys.readouterr().out
    approval_id = next(
        line.strip().replace("1. ", "")
        for line in approval_output.splitlines()
        if line.startswith("1. ")
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--approve",
            "--database-url",
            database_url,
        ],
    )
    main()
    capsys.readouterr()

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "execute",
            run_id,
            "--workspace",
            str(workspace),
            "--artifact-root",
            str(artifact_root),
            "--database-url",
            database_url,
        ],
    )
    main()
    execute_output = capsys.readouterr().out

    assert "Bounded execution finished" in execute_output
    assert "artifact_sha256:" in execute_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "task",
            "list",
            "--run",
            run_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    task_output = capsys.readouterr().out
    assert "repository_scan" in task_output
    assert "completed" in task_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "artifact",
            "list",
            "--run",
            run_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    artifact_output = capsys.readouterr().out
    assert "Repository scan report" in artifact_output
    assert "filesystem_path" in artifact_output


def test_run_execute_requires_approved_run(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step5-guard.db'}"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Fail execution without approval",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    create_output = capsys.readouterr().out
    run_id = create_output.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "execute",
            run_id,
            "--workspace",
            str(workspace),
            "--database-url",
            database_url,
        ],
    )
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("run execute should fail while approval is still pending.")

    execute_output = capsys.readouterr().out
    assert "requires the run to be ready" in execute_output


def test_run_replay_and_detail_queries_cli(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step6.db'}"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Replay one bounded execution",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "approval", "list", "--database-url", database_url],
    )
    main()
    approval_output = capsys.readouterr().out
    approval_id = next(
        line.strip().replace("1. ", "")
        for line in approval_output.splitlines()
        if line.startswith("1. ")
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--approve",
            "--database-url",
            database_url,
        ],
    )
    main()
    capsys.readouterr()

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "execute",
            run_id,
            "--workspace",
            str(workspace),
            "--artifact-root",
            str(artifact_root),
            "--database-url",
            database_url,
        ],
    )
    main()
    execute_output = capsys.readouterr().out
    task_id = next(
        line.split(":", maxsplit=1)[1].strip()
        for line in execute_output.splitlines()
        if line.startswith("task_id:")
    )

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "run", "replay", run_id, "--database-url", database_url],
    )
    main()
    replay_output = capsys.readouterr().out
    assert "Run replay" in replay_output
    assert "Approval summary" in replay_output
    assert "Execution path" in replay_output
    assert "Repository scan report" in replay_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "replay",
            run_id,
            "--format",
            "json",
            "--database-url",
            database_url,
        ],
    )
    main()
    replay_json_output = capsys.readouterr().out
    replay_payload = json.loads(replay_json_output)
    assert replay_payload["run"]["id"] == run_id
    assert replay_payload["tasks"][0]["task"]["id"] == task_id
    artifact_id = replay_payload["tasks"][0]["artifacts"][0]["artifact"]["id"]

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "task",
            "show",
            task_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    task_output = capsys.readouterr().out
    assert "Decision linkage" in task_output
    assert "Artifacts" in task_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "artifact",
            "show",
            artifact_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    artifact_output = capsys.readouterr().out
    assert "Artifact" in artifact_output
    assert "hash_matches:       True" in artifact_output


def test_run_snapshot_and_actions_cli(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step7.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Prepare a planner-ready snapshot",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "run", "snapshot", run_id, "--database-url", database_url],
    )
    main()
    snapshot_output = capsys.readouterr().out
    assert "Run snapshot" in snapshot_output
    assert "state_hash:" in snapshot_output
    assert "action_state:        available" in snapshot_output
    assert "Pending approval" in snapshot_output

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "run", "actions", run_id, "--database-url", database_url],
    )
    main()
    actions_output = capsys.readouterr().out
    assert "Run actions" in actions_output
    assert "resolve_pending_approval" in actions_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "actions",
            run_id,
            "--format",
            "json",
            "--database-url",
            database_url,
        ],
    )
    main()
    actions_payload = json.loads(capsys.readouterr().out)
    assert actions_payload["snapshot"]["run"]["id"] == run_id
    assert actions_payload["actions"][0]["name"] == "resolve_pending_approval"


def test_planner_propose_and_show_cli(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step8.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Validate planner proposal contract",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "approval", "list", "--database-url", database_url],
    )
    main()
    approval_output = capsys.readouterr().out
    approval_id = next(
        line.strip().replace("1. ", "")
        for line in approval_output.splitlines()
        if line.startswith("1. ")
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--approve",
            "--database-url",
            database_url,
        ],
    )
    main()
    capsys.readouterr()

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "snapshot",
            run_id,
            "--format",
            "json",
            "--database-url",
            database_url,
        ],
    )
    main()
    snapshot_payload = json.loads(capsys.readouterr().out)
    assert snapshot_payload["policy_version"] == "v1"
    snapshot_hash = snapshot_payload["state_hash"]

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "propose",
            run_id,
            "--snapshot-hash",
            snapshot_hash,
            "--action",
            "execute_bounded_task",
            "--rationale",
            "The run is approved and has not executed any bounded task yet.",
            "--expected-outcome",
            "One legal bounded execution should be ready for the next executor step.",
            "--database-url",
            database_url,
        ],
    )
    main()
    proposal_output = capsys.readouterr().out
    assert "Planner proposal accepted" in proposal_output
    assert "policy_version:     v1" in proposal_output
    assert "selected_action:    execute_bounded_task" in proposal_output

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "planner", "show", run_id, "--database-url", database_url],
    )
    main()
    show_output = capsys.readouterr().out
    assert "Planner proposals" in show_output
    assert "policy_version:    v1" in show_output
    assert "execute_bounded_task" in show_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "propose",
            run_id,
            "--snapshot-hash",
            "0" * 64,
            "--action",
            "execute_bounded_task",
            "--rationale",
            "This should fail because the snapshot hash is stale.",
            "--expected-outcome",
            "Nothing should be recorded.",
            "--database-url",
            database_url,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    stale_output = capsys.readouterr().out
    assert "snapshot hash is stale" in stale_output


def test_planner_invoke_cli_accepts_action_and_escalation(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step10.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Attach a bounded planner adapter",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "approval", "list", "--database-url", database_url],
    )
    main()
    approval_output = capsys.readouterr().out
    approval_id = next(line.strip().replace("1. ", "") for line in approval_output.splitlines() if line.startswith("1. "))

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--approve",
            "--database-url",
            database_url,
        ],
    )
    main()
    capsys.readouterr()

    action_response = json.dumps(
        {
            "kind": "action",
            "analysis_summary": "The run is approved and bounded execution has not happened yet.",
            "confidence": "medium",
            "selected_action": "execute_bounded_task",
            "expected_outcome": "The system should accept one bounded execution proposal.",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            run_id,
            "--scripted-response-json",
            action_response,
            "--database-url",
            database_url,
        ],
    )
    main()
    invoke_output = capsys.readouterr().out
    assert "Planner invocation" in invoke_output
    assert "provider:             scripted" in invoke_output
    assert "selected_action:     execute_bounded_task" in invoke_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Force an escalation proposal",
            "--urgency",
            "normal",
            "--risk",
            "high",
            "--database-url",
            database_url,
        ],
    )
    main()
    escalated_run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    escalation_response = json.dumps(
        {
            "kind": "escalation",
            "analysis_summary": "The run is waiting for approval, so the founder must decide how to proceed.",
            "confidence": "low_needs_review",
            "escalation_target": "founder",
            "help_kind": "policy_decision",
            "blocking_reason": "A pending approval gate prevents further progress.",
            "requested_help": "Approve or reject the run before the planner can choose a legal action.",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            escalated_run_id,
            "--scripted-response-json",
            escalation_response,
            "--database-url",
            database_url,
        ],
    )
    main()
    escalation_output = capsys.readouterr().out
    assert "provider:             scripted" in escalation_output
    assert "kind:                escalation" in escalation_output
    assert "help_kind:           policy_decision" in escalation_output


def test_planner_invoke_cli_records_format_failure(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step10-format.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Prove malformed planner responses are bounded",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "approval", "list", "--database-url", database_url],
    )
    main()
    approval_output = capsys.readouterr().out
    approval_id = next(line.strip().replace("1. ", "") for line in approval_output.splitlines() if line.startswith("1. "))

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--approve",
            "--database-url",
            database_url,
        ],
    )
    main()
    capsys.readouterr()

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            run_id,
            "--scripted-response-json",
            '{"kind":"action","selected_action":"execute_bounded_task"}',
            "--database-url",
            database_url,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "could not parse a schema-valid structured response" in output


def test_planner_invoke_cli_accepts_openai_provider_path_without_network(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step10c-openai.db'}"

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("PLANNER_OPENAI_MODEL", "gpt-4o-test")

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Exercise the openai transport seam without a real network call",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        ["v2-spring", "approval", "list", "--database-url", database_url],
    )
    main()
    approval_output = capsys.readouterr().out
    approval_id = next(line.strip().replace("1. ", "") for line in approval_output.splitlines() if line.startswith("1. "))

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "approval",
            "resolve",
            approval_id,
            "--approve",
            "--database-url",
            database_url,
        ],
    )
    main()
    capsys.readouterr()

    class FakeOpenAITransport:
        def __init__(self, **kwargs) -> None:
            self.model = kwargs["model"]

        def invoke(self, *, system_prompt: str, user_prompt: str, output_schema: dict[str, object]):
            return StructuredTransportResponse(
                raw_response=json.dumps(
                    {
                        "kind": "action",
                        "analysis_summary": "The openai seam should still choose bounded execution.",
                        "confidence": "medium",
                        "selected_action": "execute_bounded_task",
                        "expected_outcome": "One accepted proposal should be recorded without a network call.",
                    },
                ),
                provider=PlannerTransportProvider.OPENAI,
                model=self.model,
                response_id="resp_test_openai",
                retry_count=1,
                input_tokens=50,
                output_tokens=20,
                total_tokens=70,
            )

    monkeypatch.setattr("v2_spring.cli.OpenAIStructuredPlannerTransport", FakeOpenAITransport)
    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            run_id,
            "--provider",
            "openai",
            "--database-url",
            database_url,
        ],
    )
    main()
    output = capsys.readouterr().out
    assert "provider:             openai" in output
    assert "model:                gpt-4o-test" in output
    assert "selected_action:     execute_bounded_task" in output


def test_founder_hint_cli_reopens_pending_escalation_and_lists_interventions(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step10b-hint.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Route one founder hint back into the planner loop",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    escalation_response = json.dumps(
        {
            "kind": "escalation",
            "analysis_summary": "The founder should clarify how approval handling should proceed.",
            "confidence": "low_needs_review",
            "escalation_target": "founder",
            "help_kind": "clarification",
            "blocking_reason": "The planner wants a founder hint before choosing another move.",
            "requested_help": "Confirm that the approval lane remains the intended next step.",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            run_id,
            "--scripted-response-json",
            escalation_response,
            "--database-url",
            database_url,
        ],
    )
    main()
    escalation_output = capsys.readouterr().out
    escalation_id = next(
        line.split(":", maxsplit=1)[1].strip()
        for line in escalation_output.splitlines()
        if line.startswith("escalation_obs_id:")
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            run_id,
            "--scripted-response-json",
            escalation_response,
            "--database-url",
            database_url,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    blocked_output = capsys.readouterr().out
    assert "Founder reply is still required" in blocked_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "reply",
            "hint",
            run_id,
            "--escalation-id",
            escalation_id,
            "--message",
            "Keep the next move inside the existing approval boundary.",
            "--database-url",
            database_url,
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
            "planner",
            "interventions",
            run_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    interventions_output = capsys.readouterr().out
    assert "Founder interventions" in interventions_output
    assert "hint" in interventions_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "snapshot",
            run_id,
            "--database-url",
            database_url,
        ],
    )
    main()
    snapshot_output = capsys.readouterr().out
    assert f"pending_escalation:  -" in snapshot_output
    assert "Recent founder interventions" in snapshot_output


def test_founder_reject_and_override_cli_follow_bounded_policy(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli-step10b-reject-override.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Exercise founder reject and override contracts",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    rejected_run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    escalation_response = json.dumps(
        {
            "kind": "escalation",
            "analysis_summary": "The founder must decide how to proceed.",
            "confidence": "low_needs_review",
            "escalation_target": "founder",
            "help_kind": "policy_decision",
            "blocking_reason": "Approval is still pending.",
            "requested_help": "Decide whether this phase should continue at all.",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            rejected_run_id,
            "--scripted-response-json",
            escalation_response,
            "--database-url",
            database_url,
        ],
    )
    main()
    escalation_output = capsys.readouterr().out
    rejection_escalation_id = next(
        line.split(":", maxsplit=1)[1].strip()
        for line in escalation_output.splitlines()
        if line.startswith("escalation_obs_id:")
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "reply",
            "reject",
            rejected_run_id,
            "--escalation-id",
            rejection_escalation_id,
            "--reason",
            "Do not reopen this founder-help lane right now.",
            "--database-url",
            database_url,
        ],
    )
    main()
    reject_output = capsys.readouterr().out
    assert "reply_kind:         reject" in reject_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            rejected_run_id,
            "--scripted-response-json",
            escalation_response,
            "--database-url",
            database_url,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    exhausted_output = capsys.readouterr().out
    assert "Planner phase budget is exhausted" in exhausted_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "create",
            "--project",
            "demo",
            "--goal",
            "Allow one bounded founder override",
            "--urgency",
            "normal",
            "--risk",
            "medium",
            "--database-url",
            database_url,
        ],
    )
    main()
    override_run_id = capsys.readouterr().out.splitlines()[0].split()[-1]

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "invoke",
            override_run_id,
            "--scripted-response-json",
            escalation_response,
            "--database-url",
            database_url,
        ],
    )
    main()
    override_escalation_output = capsys.readouterr().out
    override_escalation_id = next(
        line.split(":", maxsplit=1)[1].strip()
        for line in override_escalation_output.splitlines()
        if line.startswith("escalation_obs_id:")
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "planner",
            "reply",
            "override",
            override_run_id,
            "--escalation-id",
            override_escalation_id,
            "--action",
            "resolve_pending_approval",
            "--reason",
            "The founder wants to force the current legal approval action.",
            "--database-url",
            database_url,
        ],
    )
    main()
    override_output = capsys.readouterr().out
    assert "reply_kind:         override" in override_output
    assert "override_action:    resolve_pending_approval" in override_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "run",
            "replay",
            override_run_id,
            "--verbose",
            "--database-url",
            database_url,
        ],
    )
    main()
    replay_output = capsys.readouterr().out
    assert "Founder interventions" in replay_output
    assert "Detailed founder interventions" in replay_output
    assert "override: Founder overrode the planner and selected resolve_pending_approval." in replay_output
