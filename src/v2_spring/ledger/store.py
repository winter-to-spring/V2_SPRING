from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from v2_spring.domain.decision import DecisionKind, DecisionView
from v2_spring.domain.observation import ObservationKind, ObservationView
from v2_spring.domain.run import RunCreateInput, RunView
from v2_spring.ledger.models import (
    Base,
    DecisionRecord,
    EventLedgerRecord,
    LedgerEventType,
    ObservationRecord,
    RunRecord,
)


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

            session.add(self._build_run_created_event(record))

            observation = ObservationRecord(
                run_id=record.id,
                kind=ObservationKind.RUN_INTAKE,
                summary="Run was submitted from the CLI.",
                details=(
                    f"Project '{run_input.project}' submitted a new run with "
                    f"urgency '{run_input.urgency.value}' and risk '{run_input.risk.value}'."
                ),
            )
            session.add(observation)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=record.id,
                    event_type=LedgerEventType.OBSERVATION_RECORDED,
                    payload={
                        "observation_id": observation.id,
                        "kind": observation.kind.value,
                        "summary": observation.summary,
                    },
                ),
            )

            decision = DecisionRecord(
                run_id=record.id,
                kind=DecisionKind.INTAKE_ACCEPTED,
                summary="Run intake accepted.",
                rationale=(
                    "The CLI input passed typed validation, so the run was persisted "
                    "and the system recorded bootstrap evidence for the next planner step."
                ),
            )
            session.add(decision)
            session.flush()
            session.add(
                EventLedgerRecord(
                    run_id=record.id,
                    event_type=LedgerEventType.DECISION_RECORDED,
                    payload={
                        "decision_id": decision.id,
                        "kind": decision.kind.value,
                        "summary": decision.summary,
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

    @staticmethod
    def _build_run_created_event(record: RunRecord) -> EventLedgerRecord:
        return EventLedgerRecord(
            run_id=record.id,
            event_type=LedgerEventType.RUN_CREATED,
            payload={
                "project": record.project,
                "goal": record.goal,
                "urgency": record.urgency.value,
                "risk": record.risk.value,
                "status": record.status.value,
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

    def list_decisions_for_run(self, run_id: str) -> list[DecisionView]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(DecisionRecord)
                .where(DecisionRecord.run_id == run_id)
                .order_by(DecisionRecord.created_at.asc())
            )
            records = list(session.scalars(statement).all())
            return [
                DecisionView.model_validate(
                    {
                        "id": record.id,
                        "run_id": record.run_id,
                        "kind": record.kind,
                        "summary": record.summary,
                        "rationale": record.rationale,
                        "created_at": record.created_at,
                    },
                )
                for record in records
            ]

    def list_observations_for_run(self, run_id: str) -> list[ObservationView]:
        self.ensure_schema()
        with self.session() as session:
            statement = (
                select(ObservationRecord)
                .where(ObservationRecord.run_id == run_id)
                .order_by(ObservationRecord.created_at.asc())
            )
            records = list(session.scalars(statement).all())
            return [
                ObservationView.model_validate(
                    {
                        "id": record.id,
                        "run_id": record.run_id,
                        "kind": record.kind,
                        "summary": record.summary,
                        "details": record.details,
                        "created_at": record.created_at,
                    },
                )
                for record in records
            ]
