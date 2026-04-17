from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.dialects.postgresql import JSONB

from v2_spring.cli import main
from v2_spring.ledger.models import Base, EventLedgerRecord, PatchIntakeRecord
from v2_spring.ledger.store import LedgerStore, SchemaBootstrapRequiredError


def test_postgres_store_enables_transaction_friendly_engine_flags() -> None:
    store = LedgerStore("postgresql+psycopg://demo:demo@localhost:5432/v2_spring")

    assert store.dialect_name == "postgresql"
    assert store.supports_row_level_locking is True
    assert store.supports_jsonb is True
    assert getattr(store._engine.pool, "_pre_ping", False) is True  # noqa: SLF001


def test_execution_claim_select_uses_for_update_on_postgres() -> None:
    statement = LedgerStore._build_execution_claim_select(
        "run-123",
        for_update=True,
        skip_locked=True,
        dialect_name="postgresql",
    )

    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ),
    )

    assert "FOR UPDATE" in compiled
    assert "SKIP LOCKED" in compiled


def test_execution_claim_select_omits_for_update_on_sqlite() -> None:
    statement = LedgerStore._build_execution_claim_select(
        "run-123",
        for_update=True,
        skip_locked=True,
        dialect_name="sqlite",
    )

    compiled = str(
        statement.compile(
            dialect=sqlite.dialect(),
            compile_kwargs={"literal_binds": True},
        ),
    )

    assert "FOR UPDATE" not in compiled
    assert "SKIP LOCKED" not in compiled


def test_postgres_json_columns_promote_to_jsonb() -> None:
    payload_type = EventLedgerRecord.__table__.c.payload.type.dialect_impl(postgresql.dialect())
    changed_files_type = PatchIntakeRecord.__table__.c.changed_files.type.dialect_impl(postgresql.dialect())

    assert isinstance(payload_type, JSONB)
    assert isinstance(changed_files_type, JSONB)


def test_alembic_baseline_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "alembic.ini").exists()
    assert (root / "alembic" / "env.py").exists()
    assert (root / "alembic" / "script.py.mako").exists()
    assert (root / "alembic" / "versions" / "20260417_000001_baseline.py").exists()


def test_postgres_schema_requires_migration_control(tmp_path: Path) -> None:
    store = LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step21-schema.db'}")
    store._dialect_name = "postgresql"  # noqa: SLF001

    status = store.inspect_schema_status()

    assert status.bootstrap_required is True
    assert status.migration_controlled is False
    with pytest.raises(SchemaBootstrapRequiredError):
        store.ensure_schema()


def test_postgres_schema_status_accepts_migrated_layout(tmp_path: Path) -> None:
    store = LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step21-ready.db'}")
    Base.metadata.create_all(store._engine)  # noqa: SLF001
    with store._engine.begin() as connection:  # noqa: SLF001
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260417_000001')"))
    store._dialect_name = "postgresql"  # noqa: SLF001

    status = store.inspect_schema_status()

    assert status.ready is True
    assert status.bootstrap_required is False
    assert status.current_revision == "20260417_000001"
    store.ensure_schema()


def test_doctor_reports_schema_status(capsys, monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'doctor.db'}"

    monkeypatch.setattr(
        "sys.argv",
        [
            "v2-spring",
            "doctor",
            "--database-url",
            database_url,
        ],
    )
    main()
    output = capsys.readouterr().out

    assert "Database doctor" in output
    assert "dialect:" in output
    assert "sqlite" in output
