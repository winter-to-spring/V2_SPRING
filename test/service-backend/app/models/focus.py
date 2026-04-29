"""
FocusSession and Briefing ORM models.

Defines SQLAlchemy models for focus session tracking and briefing generation.
"""

from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
import uuid
from enum import Enum as PyEnum

Base = declarative_base()


class FocusSessionStatus(PyEnum):
    """Status enum for focus sessions."""
    active = "active"
    completed = "completed"
    aborted = "aborted"


class BriefingKind(PyEnum):
    """Kind enum for briefings."""
    morning = "morning"
    session_end = "session_end"
    manual = "manual"


class FocusSession(Base):
    """
    Represents a user focus session.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key reference to user
        started_at: Session start timestamp with timezone
        ended_at: Optional session end timestamp with timezone
        planned_minutes: Planned session duration in minutes
        status: Session status (active, completed, aborted)
        feedback: Optional JSON feedback from user
    """
    __tablename__ = "focus_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    planned_minutes = Column(Integer, nullable=False)
    status = Column(Enum(FocusSessionStatus), nullable=False, default=FocusSessionStatus.active)
    feedback = Column(JSONB, nullable=True)


class Briefing(Base):
    """
    Represents an AI-generated briefing for a user.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key reference to user
        generated_at: Timestamp when briefing was generated
        content: Text content of the briefing
        source_notification_ids: JSON array of notification IDs that informed this briefing
        kind: Briefing type (morning, session_end, manual)
    """
    __tablename__ = "briefings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    generated_at = Column(TIMESTAMP(timezone=True), nullable=False)
    content = Column(Text, nullable=False)
    source_notification_ids = Column(JSONB, nullable=True)
    kind = Column(Enum(BriefingKind), nullable=False)
