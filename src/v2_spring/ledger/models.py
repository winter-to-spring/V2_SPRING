from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.decision import DecisionKind
from v2_spring.domain.observation import ObservationKind
from v2_spring.domain.run import RiskLevel, RunStatus, UrgencyLevel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class LedgerEventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    OBSERVATION_RECORDED = "OBSERVATION_RECORDED"
    DECISION_RECORDED = "DECISION_RECORDED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_RESOLVED = "APPROVAL_RESOLVED"


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project: Mapped[str] = mapped_column(String(120), nullable=False)
    goal: Mapped[str] = mapped_column(String(4000), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False),
        nullable=False,
        default=RunStatus.CREATED,
    )
    urgency: Mapped[UrgencyLevel] = mapped_column(
        Enum(UrgencyLevel, native_enum=False),
        nullable=False,
    )
    risk: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    ledger_events: Mapped[list["EventLedgerRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    decisions: Mapped[list["DecisionRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    observations: Mapped[list["ObservationRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[list["ApprovalRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class DecisionRecord(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[DecisionKind] = mapped_column(
        Enum(DecisionKind, native_enum=False),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    rationale: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="decisions")


class ObservationRecord(Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[ObservationKind] = mapped_column(
        Enum(ObservationKind, native_enum=False),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    details: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="observations")


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, native_enum=False),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    requested_action: Mapped[str] = mapped_column(String(400), nullable=False)
    reason: Mapped[str] = mapped_column(String(4000), nullable=False)
    approve_effect: Mapped[str] = mapped_column(String(4000), nullable=False)
    reject_effect: Mapped[str] = mapped_column(String(4000), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[RunRecord] = relationship(back_populates="approvals")


class EventLedgerRecord(Base):
    __tablename__ = "event_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[LedgerEventType] = mapped_column(
        Enum(LedgerEventType, native_enum=False),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    run: Mapped[RunRecord] = relationship(back_populates="ledger_events")


def _prevent_mutation(_: Any, __: Any, target: EventLedgerRecord) -> None:
    raise ValueError(
        f"EventLedgerRecord {target.id} is append-only and cannot be mutated or deleted.",
    )


event.listen(EventLedgerRecord, "before_update", _prevent_mutation)
event.listen(EventLedgerRecord, "before_delete", _prevent_mutation)
event.listen(DecisionRecord, "before_update", _prevent_mutation)
event.listen(DecisionRecord, "before_delete", _prevent_mutation)
event.listen(ObservationRecord, "before_update", _prevent_mutation)
event.listen(ObservationRecord, "before_delete", _prevent_mutation)
