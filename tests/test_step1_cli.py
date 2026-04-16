from __future__ import annotations

from pathlib import Path
import json

from v2_spring.cli import main


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
