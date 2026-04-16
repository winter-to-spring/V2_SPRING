from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from v2_spring.domain.run import RunCreateInput, RunView
from v2_spring.ledger.models import Base, EventLedgerRecord, LedgerEventType, RunRecord


class LedgerStore:
    """Typed persistence boundary for Step 1 state and events."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

    def ensure_schema(self) -> None:
        Base.metadata.create_all(self._engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_run(self, run_input: RunCreateInput) -> RunView:
        self.ensure_schema()
        with self.session() as session:
            record = RunRecord(
                project=run_input.project,
                goal=run_input.goal,
                urgency=run_input.urgency,
                risk=run_input.risk,
            )
            session.add(record)
            session.flush()

            session.add(
                EventLedgerRecord(
                    run_id=record.id,
                    event_type=LedgerEventType.RUN_CREATED,
                    payload={
                        "project": run_input.project,
                        "goal": run_input.goal,
                        "urgency": run_input.urgency.value,
                        "risk": run_input.risk.value,
                        "status": record.status.value,
                    },
                ),
            )
            session.flush()

            return RunView.model_validate(
                {
                    "id": record.id,
                    "project": record.project,
                    "goal": record.goal,
                    "status": record.status,
                    "urgency": record.urgency,
                    "risk": record.risk,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                },
            )

    def get_run(self, run_id: str) -> RunView | None:
        self.ensure_schema()
        with self.session() as session:
            record = session.get(RunRecord, run_id)
            if record is None:
                return None
            return RunView.model_validate(
                {
                    "id": record.id,
                    "project": record.project,
                    "goal": record.goal,
                    "status": record.status,
                    "urgency": record.urgency,
                    "risk": record.risk,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                },
            )

    def list_events_for_run(self, run_id: str) -> list[EventLedgerRecord]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(EventLedgerRecord)
                .where(EventLedgerRecord.run_id == run_id)
                .order_by(EventLedgerRecord.recorded_at.asc())
            )
            return list(session.scalars(statement).all())
