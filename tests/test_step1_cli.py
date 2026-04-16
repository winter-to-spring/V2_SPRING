from __future__ import annotations

from pathlib import Path

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
