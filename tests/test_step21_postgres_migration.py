from __future__ import annotations

from pathlib import Path

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.dialects.postgresql import JSONB

from v2_spring.ledger.models import EventLedgerRecord, PatchIntakeRecord
from v2_spring.ledger.store import LedgerStore


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
