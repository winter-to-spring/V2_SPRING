from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from v2_spring.cli import main
from v2_spring.ledger.store import LedgerStore


def make_sqlite_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step22.db'}")


def _docker_available() -> bool:
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _start_postgres_container() -> tuple[str, str]:
    name = f"v2-spring-step22-{uuid4().hex[:10]}"
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-e",
            "POSTGRES_USER=postgres",
            "-e",
            "POSTGRES_PASSWORD=postgres",
            "-e",
            "POSTGRES_DB=v2spring_step22",
            "-p",
            "127.0.0.1::5432",
            "postgres:16-alpine",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    port_result = subprocess.run(
        ["docker", "port", name, "5432/tcp"],
        check=True,
        capture_output=True,
        text=True,
    )
    host = port_result.stdout.strip().split(":")[-1]
    database_url = f"postgresql+psycopg://postgres:postgres@127.0.0.1:{host}/v2spring_step22"
    return name, database_url


def _wait_for_postgres(container_name: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "pg_isready",
                "-U",
                "postgres",
                "-d",
                "v2spring_step22",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise AssertionError("Postgres container did not become ready in time.")


def _stop_container(container_name: str) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_alembic_upgrade(root: Path, database_url: str) -> None:
    full_env = {**os.environ, "DATABASE_URL": database_url}
    candidates = [
        shutil.which("alembic"),
        str(Path(sys.executable).with_name("alembic")),
        str(root / ".venv" / "bin" / "alembic"),
    ]
    alembic_cmd = next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)
    if alembic_cmd is None:
        raise AssertionError("Alembic executable was not found in PATH, interpreter bin, or project .venv.")
    subprocess.run(
        [alembic_cmd, "upgrade", "head"],
        cwd=root,
        env=full_env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_inspect_database_doctor_includes_controller_boundary(tmp_path: Path) -> None:
    store = make_sqlite_store(tmp_path)

    report = store.inspect_database_doctor()

    assert report.schema.dialect_name == "sqlite"
    assert report.controller_db_boundary == "controller_mediated"
    assert "DATABASE_URL" in report.blocked_worker_env_vars
    assert "REDIS_URL" in report.blocked_worker_env_vars
    assert report.postgres_contention is None


def test_live_postgres_doctor_and_contention_smoke(monkeypatch, capsys, tmp_path: Path) -> None:
    if not _docker_available():
        pytest.skip("Docker daemon is not available for Step 22 live Postgres smoke.")

    root = Path(__file__).resolve().parents[1]
    container_name, database_url = _start_postgres_container()
    try:
        _wait_for_postgres(container_name)
        _run_alembic_upgrade(root, database_url)
        store = LedgerStore(database_url)

        report = store.inspect_database_doctor()
        assert report.schema.dialect_name == "postgresql"
        assert report.schema.ready is True
        assert report.postgres_pool is not None
        assert report.postgres_contention is not None
        assert report.controller_db_boundary == "controller_mediated"

        smoke = store.run_postgres_contention_smoke(hold_seconds=1.0)
        assert smoke.renewed_successfully is True
        assert smoke.lock_waiting_observed is True
        assert smoke.peak_lock_waiting_connections >= 1
        assert smoke.contender_latency_ms >= 500

        monkeypatch.setattr(
            "sys.argv",
            [
                "v2-spring",
                "doctor",
                "--database-url",
                database_url,
                "--format",
                "json",
                "--contention-smoke",
                "--hold-seconds",
                "0.6",
            ],
        )
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema"]["dialect_name"] == "postgresql"
        assert payload["controller_db_boundary"] == "controller_mediated"
        assert payload["postgres_contention"]["lock_waiting_connections"] >= 0
        assert payload["contention_smoke"]["lock_waiting_observed"] is True
    finally:
        _stop_container(container_name)
