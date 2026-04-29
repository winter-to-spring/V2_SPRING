from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Workspace(Base):
    """
    Workspace model representing a Slack workspace installation.
    
    Stores Slack team metadata and access credentials for a user.
    access_token is encrypted-at-rest (TODO: implement encryption layer).
    """
    __tablename__ = "workspaces"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    slack_team_id = Column(String(255), nullable=False)
    slack_team_name = Column(String(255), nullable=False)
    access_token = Column(String(512), nullable=False)  # encrypted-at-rest TODO
    bot_user_id = Column(String(255), nullable=False)
    scope = Column(String(1024), nullable=False)
    installed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    
    __table_args__ = (
        UniqueConstraint("user_id", "slack_team_id", name="uq_workspace_user_slack_team"),
    )
    
    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, user_id={self.user_id}, slack_team_id={self.slack_team_id}, is_active={self.is_active})>"
