from typing import TYPE_CHECKING

from sqlalchemy import UUID, Column, DateTime, Enum, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID as UUIDType

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password: str = Column(String(255), nullable=False)
    created_at: "datetime" = Column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    workspaces: list["Workspace"] = relationship(
        "Workspace", back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    owner_user_id: UUIDType = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: str = Column(String(255), nullable=False)
    slack_team_id: str | None = Column(String(255), unique=True, nullable=True)
    created_at: "datetime" = Column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    owner: User = relationship("User", back_populates="workspaces")
    integrations: list["Integration"] = relationship(
        "Integration", back_populates="workspace", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name}, owner_user_id={self.owner_user_id})>"


class Integration(Base):
    __tablename__ = "integrations"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    workspace_id: UUIDType = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    provider: str = Column(
        Enum("slack", "discord", "gmail", "jira", name="provider_enum"),
        nullable=False,
    )
    access_token: str = Column(Text, nullable=False)
    refresh_token: str | None = Column(Text, nullable=True)
    scope: str = Column(String(1000), nullable=False)
    installed_at: "datetime" = Column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    status: str = Column(
        Enum("active", "revoked", "error", name="status_enum"), nullable=False
    )

    workspace: Workspace = relationship("Workspace", back_populates="integrations")

    def __repr__(self) -> str:
        return f"<Integration(id={self.id}, workspace_id={self.workspace_id}, provider={self.provider}, status={self.status})>"
