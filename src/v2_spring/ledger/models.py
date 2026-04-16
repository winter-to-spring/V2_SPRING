from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from v2_spring.domain.run import RiskLevel, RunStatus, UrgencyLevel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class LedgerEventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"


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
