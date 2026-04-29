import pytest
from datetime import datetime
import uuid
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID

from test.service_backend.app.models.workspace import Workspace, Base


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


class TestWorkspaceModel:
    """Test suite for Workspace model definition and constraints."""
    
    def test_workspace_table_exists(self, in_memory_db):
        """Verify the workspaces table is created correctly."""
        inspector = inspect(in_memory_db)
        tables = inspector.get_table_names()
        assert "workspaces" in tables
    
    def test_workspace_columns_exist(self, in_memory_db):
        """Verify all required columns are present."""
        inspector = inspect(in_memory_db)
        columns = {col['name'] for col in inspector.get_columns('workspaces')}
        
        required_columns = {
            'id', 'user_id', 'slack_team_id', 'slack_team_name',
            'access_token', 'bot_user_id', 'scope', 'installed_at', 'is_active'
        }
        assert required_columns.issubset(columns), f"Missing columns: {required_columns - columns}"
    
    def test_workspace_id_is_primary_key(self, in_memory_db):
        """Verify id is the primary key."""
        inspector = inspect(in_memory_db)
        pk_columns = inspector.get_pk_constraint('workspaces')['constrained_columns']
        assert 'id' in pk_columns
    
    def test_workspace_user_id_foreign_key(self, in_memory_db):
        """Verify user_id has a foreign key constraint to users.id."""
        inspector = inspect(in_memory_db)
        fks = inspector.get_foreign_keys('workspaces')
        user_id_fk = [fk for fk in fks if 'user_id' in fk['constrained_columns']]
        assert len(user_id_fk) > 0
        assert user_id_fk[0]['referred_table'] == 'users'
        assert 'id' in user_id_fk[0]['referred_columns']
    
    def test_workspace_unique_constraint(self, in_memory_db):
        """Verify unique constraint on (user_id, slack_team_id)."""
        inspector = inspect(in_memory_db)
        constraints = inspector.get_unique_constraints('workspaces')
        unique_on_user_slack = [
            uc for uc in constraints
            if set(uc['column_names']) == {'user_id', 'slack_team_id'}
        ]
        assert len(unique_on_user_slack) > 0
    
    def test_workspace_column_types(self, in_memory_db):
        """Verify column types match specification."""
        inspector = inspect(in_memory_db)
        columns = {col['name']: col for col in inspector.get_columns('workspaces')}
        
        # id and user_id should be UUID columns
        assert 'UUID' in str(columns['id']['type']) or 'CHAR' in str(columns['id']['type'])
        
        # String columns
        assert 'VARCHAR' in str(columns['slack_team_id']['type'])
        assert 'VARCHAR' in str(columns['slack_team_name']['type'])
        assert 'VARCHAR' in str(columns['access_token']['type'])
        assert 'VARCHAR' in str(columns['bot_user_id']['type'])
        assert 'VARCHAR' in str(columns['scope']['type'])
        
        # Boolean column
        assert 'BOOLEAN' in str(columns['is_active']['type']) or 'INTEGER' in str(columns['is_active']['type'])
        
        # Timestamp column
        assert 'DATETIME' in str(columns['installed_at']['type']) or 'TIMESTAMP' in str(columns['installed_at']['type'])
    
    def test_workspace_defaults(self, in_memory_db):
        """Verify default values for is_active and installed_at."""
        with Session(in_memory_db) as session:
            test_user_id = uuid.uuid4()
            workspace = Workspace(
                user_id=test_user_id,
                slack_team_id="T123456",
                slack_team_name="Test Team",
                access_token="xoxb-token",
                bot_user_id="U789012",
                scope="chat:write,users:read",
            )
            assert workspace.is_active is True
            assert workspace.installed_at is not None
    
    def test_workspace_repr(self):
        """Verify __repr__ method works correctly."""
        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()
        workspace = Workspace(
            id=workspace_id,
            user_id=user_id,
            slack_team_id="T123456",
            slack_team_name="Test Team",
            access_token="xoxb-token",
            bot_user_id="U789012",
            scope="chat:write,users:read",
        )
        repr_str = repr(workspace)
        assert "Workspace" in repr_str
        assert str(workspace_id) in repr_str
        assert str(user_id) in repr_str
        assert "T123456" in repr_str
    
    def test_workspace_model_instantiation(self):
        """Verify Workspace model can be instantiated with all fields."""
        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()
        installed_at = datetime.utcnow()
        
        workspace = Workspace(
            id=workspace_id,
            user_id=user_id,
            slack_team_id="T123456",
            slack_team_name="Test Team",
            access_token="xoxb-token",
            bot_user_id="U789012",
            scope="chat:write,users:read",
            installed_at=installed_at,
            is_active=True,
        )
        
        assert workspace.id == workspace_id
        assert workspace.user_id == user_id
        assert workspace.slack_team_id == "T123456"
        assert workspace.slack_team_name == "Test Team"
        assert workspace.access_token == "xoxb-token"
        assert workspace.bot_user_id == "U789012"
        assert workspace.scope == "chat:write,users:read"
        assert workspace.installed_at == installed_at
        assert workspace.is_active is True
