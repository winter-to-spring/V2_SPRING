import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class FocusSessionStatus(PyEnum):
    """Enumeration for focus session status."""
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class FocusSession(Base):
    """
    FocusSession model representing a focused work session.
    
    Attributes:
        id: UUID primary key
        user_id: UUID foreign key to users table
        started_at: Timestamp when session started (default: current time)
        ended_at: Nullable timestamp when session ended
        status: Session status enum (active, completed, cancelled)
        briefing_id: Optional UUID foreign key to briefings table (string ref)
    """
    __tablename__ = "focus_sessions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    ended_at = Column(
        DateTime(timezone=True),
        nullable=True
    )
    status = Column(
        Enum(FocusSessionStatus),
        default=FocusSessionStatus.active,
        nullable=False
    )
    briefing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("briefings.id"),
        nullable=True
    )

    # Relationships (using string references to avoid circular imports)
    user = relationship("User", back_populates="focus_sessions")
    briefing = relationship("Briefing", back_populates="focus_sessions")
