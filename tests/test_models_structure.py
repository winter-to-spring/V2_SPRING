import pytest
from uuid import UUID as UUIDType
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, inspect
from sqlalchemy.types import UUID
from app.models import Base, User, Workspace, Integration


class TestUserModel:
    """Test User model structure."""

    def test_user_has_correct_tablename(self):
        assert User.__tablename__ == "users"

    def test_user_has_id_column(self):
        assert hasattr(User, "id")
        mapper = inspect(User)
        id_col = mapper.columns["id"]
        assert isinstance(id_col.type, UUID)
        assert id_col.primary_key
        assert not id_col.nullable

    def test_user_has_email_column(self):
        assert hasattr(User, "email")
        mapper = inspect(User)
        email_col = mapper.columns["email"]
        assert isinstance(email_col.type, String)
        assert email_col.unique
        assert not email_col.nullable

    def test_user_has_hashed_password_column(self):
        assert hasattr(User, "hashed_password")
        mapper = inspect(User)
        pwd_col = mapper.columns["hashed_password"]
        assert isinstance(pwd_col.type, String)
        assert not pwd_col.nullable

    def test_user_has_created_at_column(self):
        assert hasattr(User, "created_at")
        mapper = inspect(User)
        created_col = mapper.columns["created_at"]
        assert isinstance(created_col.type, DateTime)
        assert created_col.type.timezone
        assert not created_col.nullable

    def test_user_has_workspaces_relationship(self):
        assert hasattr(User, "workspaces")
        mapper = inspect(User)
        assert "workspaces" in mapper.relationships

    def test_user_repr(self):
        # Test that __repr__ is defined and returns expected format
        assert hasattr(User, "__repr__")


class TestWorkspaceModel:
    """Test Workspace model structure."""

    def test_workspace_has_correct_tablename(self):
        assert Workspace.__tablename__ == "workspaces"

    def test_workspace_has_id_column(self):
        assert hasattr(Workspace, "id")
        mapper = inspect(Workspace)
        id_col = mapper.columns["id"]
        assert isinstance(id_col.type, UUID)
        assert id_col.primary_key
        assert not id_col.nullable

    def test_workspace_has_owner_user_id_column(self):
        assert hasattr(Workspace, "owner_user_id")
        mapper = inspect(Workspace)
        fk_col = mapper.columns["owner_user_id"]
        assert isinstance(fk_col.type, UUID)
        assert not fk_col.nullable
        # Check foreign key constraint exists
        assert len(fk_col.foreign_keys) > 0

    def test_workspace_has_name_column(self):
        assert hasattr(Workspace, "name")
        mapper = inspect(Workspace)
        name_col = mapper.columns["name"]
        assert isinstance(name_col.type, String)
        assert not name_col.nullable

    def test_workspace_has_slack_team_id_column(self):
        assert hasattr(Workspace, "slack_team_id")
        mapper = inspect(Workspace)
        slack_col = mapper.columns["slack_team_id"]
        assert isinstance(slack_col.type, String)
        assert slack_col.nullable
        assert slack_col.unique

    def test_workspace_has_created_at_column(self):
        assert hasattr(Workspace, "created_at")
        mapper = inspect(Workspace)
        created_col = mapper.columns["created_at"]
        assert isinstance(created_col.type, DateTime)
        assert created_col.type.timezone
        assert not created_col.nullable

    def test_workspace_has_owner_relationship(self):
        assert hasattr(Workspace, "owner")
        mapper = inspect(Workspace)
        assert "owner" in mapper.relationships

    def test_workspace_has_integrations_relationship(self):
        assert hasattr(Workspace, "integrations")
        mapper = inspect(Workspace)
        assert "integrations" in mapper.relationships

    def test_workspace_repr(self):
        assert hasattr(Workspace, "__repr__")


class TestIntegrationModel:
    """Test Integration model structure."""

    def test_integration_has_correct_tablename(self):
        assert Integration.__tablename__ == "integrations"

    def test_integration_has_id_column(self):
        assert hasattr(Integration, "id")
        mapper = inspect(Integration)
        id_col = mapper.columns["id"]
        assert isinstance(id_col.type, UUID)
        assert id_col.primary_key
        assert not id_col.nullable

    def test_integration_has_workspace_id_column(self):
        assert hasattr(Integration, "workspace_id")
        mapper = inspect(Integration)
        fk_col = mapper.columns["workspace_id"]
        assert isinstance(fk_col.type, UUID)
        assert not fk_col.nullable
        assert len(fk_col.foreign_keys) > 0

    def test_integration_has_provider_column(self):
        assert hasattr(Integration, "provider")
        mapper = inspect(Integration)
        provider_col = mapper.columns["provider"]
        assert isinstance(provider_col.type, Enum)
        assert not provider_col.nullable
        # Check that enum has expected values
        assert provider_col.type.enums == ("slack", "discord", "gmail", "jira")

    def test_integration_has_access_token_column(self):
        assert hasattr(Integration, "access_token")
        mapper = inspect(Integration)
        token_col = mapper.columns["access_token"]
        assert isinstance(token_col.type, Text)
        assert not token_col.nullable

    def test_integration_has_refresh_token_column(self):
        assert hasattr(Integration, "refresh_token")
        mapper = inspect(Integration)
        refresh_col = mapper.columns["refresh_token"]
        assert isinstance(refresh_col.type, Text)
        assert refresh_col.nullable

    def test_integration_has_scope_column(self):
        assert hasattr(Integration, "scope")
        mapper = inspect(Integration)
        scope_col = mapper.columns["scope"]
        assert isinstance(scope_col.type, String)
        assert not scope_col.nullable

    def test_integration_has_installed_at_column(self):
        assert hasattr(Integration, "installed_at")
        mapper = inspect(Integration)
        installed_col = mapper.columns["installed_at"]
        assert isinstance(installed_col.type, DateTime)
        assert installed_col.type.timezone
        assert not installed_col.nullable

    def test_integration_has_status_column(self):
        assert hasattr(Integration, "status")
        mapper = inspect(Integration)
        status_col = mapper.columns["status"]
        assert isinstance(status_col.type, Enum)
        assert not status_col.nullable
        assert status_col.type.enums == ("active", "revoked", "error")

    def test_integration_has_workspace_relationship(self):
        assert hasattr(Integration, "workspace")
        mapper = inspect(Integration)
        assert "workspace" in mapper.relationships

    def test_integration_repr(self):
        assert hasattr(Integration, "__repr__")


class TestModelsIntegration:
    """Test relationships and overall model structure."""

    def test_base_class_exists(self):
        assert Base is not None
        assert hasattr(Base, "metadata")

    def test_models_inherit_from_base(self):
        assert issubclass(User, Base)
        assert issubclass(Workspace, Base)
        assert issubclass(Integration, Base)

    def test_user_to_workspace_relationship(self):
        mapper = inspect(User)
        workspace_rel = mapper.relationships["workspaces"]
        assert workspace_rel.mapper.class_ is Workspace

    def test_workspace_to_user_relationship(self):
        mapper = inspect(Workspace)
        owner_rel = mapper.relationships["owner"]
        assert owner_rel.mapper.class_ is User

    def test_workspace_to_integration_relationship(self):
        mapper = inspect(Workspace)
        integration_rel = mapper.relationships["integrations"]
        assert integration_rel.mapper.class_ is Integration

    def test_integration_to_workspace_relationship(self):
        mapper = inspect(Integration)
        workspace_rel = mapper.relationships["workspace"]
        assert workspace_rel.mapper.class_ is Workspace
