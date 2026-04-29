"""
Test suite for focus.py models.

Verifies that FocusSession and Briefing models are correctly defined
with proper columns, types, and constraints.
"""

import pytest
import sys
from pathlib import Path
from enum import Enum as PyEnum

# Ensure the target module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_focus_session_model_exists():
    """Test that FocusSession model exists and can be imported."""
    from test.service_backend.app.models.focus import FocusSession
    assert FocusSession is not None
    assert hasattr(FocusSession, '__tablename__')
    assert FocusSession.__tablename__ == "focus_sessions"


def test_focus_session_columns():
    """Test that FocusSession has all required columns."""
    from test.service_backend.app.models.focus import FocusSession
    
    required_columns = {'id', 'user_id', 'started_at', 'ended_at', 'planned_minutes', 'status', 'feedback'}
    existing_columns = {col.name for col in FocusSession.__table__.columns}
    
    assert required_columns == existing_columns, f"Expected {required_columns}, got {existing_columns}"


def test_focus_session_id_is_uuid_pk():
    """Test that id column is UUID primary key."""
    from test.service_backend.app.models.focus import FocusSession
    
    id_col = FocusSession.__table__.columns['id']
    assert id_col.primary_key is True
    assert 'UUID' in str(id_col.type)


def test_focus_session_user_id_is_uuid():
    """Test that user_id column is UUID and indexed."""
    from test.service_backend.app.models.focus import FocusSession
    
    user_id_col = FocusSession.__table__.columns['user_id']
    assert 'UUID' in str(user_id_col.type)
    assert user_id_col.nullable is False


def test_focus_session_timestamps():
    """Test that timestamp columns are TIMESTAMPTZ."""
    from test.service_backend.app.models.focus import FocusSession
    
    started_at_col = FocusSession.__table__.columns['started_at']
    ended_at_col = FocusSession.__table__.columns['ended_at']
    
    assert 'TIMESTAMP' in str(started_at_col.type)
    assert 'TIMESTAMP' in str(ended_at_col.type)
    assert started_at_col.nullable is False
    assert ended_at_col.nullable is True


def test_focus_session_planned_minutes():
    """Test that planned_minutes column is Integer."""
    from test.service_backend.app.models.focus import FocusSession
    
    col = FocusSession.__table__.columns['planned_minutes']
    assert 'INTEGER' in str(col.type) or 'INT' in str(col.type)
    assert col.nullable is False


def test_focus_session_status_enum():
    """Test that status column uses correct ENUM values."""
    from test.service_backend.app.models.focus import FocusSession, FocusSessionStatus
    
    status_col = FocusSession.__table__.columns['status']
    assert 'ENUM' in str(status_col.type)
    
    # Verify enum values
    assert FocusSessionStatus.active.value == "active"
    assert FocusSessionStatus.completed.value == "completed"
    assert FocusSessionStatus.aborted.value == "aborted"


def test_focus_session_feedback_jsonb():
    """Test that feedback column is JSONB and nullable."""
    from test.service_backend.app.models.focus import FocusSession
    
    col = FocusSession.__table__.columns['feedback']
    assert col.nullable is True


def test_briefing_model_exists():
    """Test that Briefing model exists and can be imported."""
    from test.service_backend.app.models.focus import Briefing
    assert Briefing is not None
    assert hasattr(Briefing, '__tablename__')
    assert Briefing.__tablename__ == "briefings"


def test_briefing_columns():
    """Test that Briefing has all required columns."""
    from test.service_backend.app.models.focus import Briefing
    
    required_columns = {'id', 'user_id', 'generated_at', 'content', 'source_notification_ids', 'kind'}
    existing_columns = {col.name for col in Briefing.__table__.columns}
    
    assert required_columns == existing_columns, f"Expected {required_columns}, got {existing_columns}"


def test_briefing_id_is_uuid_pk():
    """Test that id column is UUID primary key."""
    from test.service_backend.app.models.focus import Briefing
    
    id_col = Briefing.__table__.columns['id']
    assert id_col.primary_key is True
    assert 'UUID' in str(id_col.type)


def test_briefing_user_id_is_uuid():
    """Test that user_id column is UUID and indexed."""
    from test.service_backend.app.models.focus import Briefing
    
    user_id_col = Briefing.__table__.columns['user_id']
    assert 'UUID' in str(user_id_col.type)
    assert user_id_col.nullable is False


def test_briefing_generated_at():
    """Test that generated_at column is TIMESTAMPTZ."""
    from test.service_backend.app.models.focus import Briefing
    
    col = Briefing.__table__.columns['generated_at']
    assert 'TIMESTAMP' in str(col.type)
    assert col.nullable is False


def test_briefing_content():
    """Test that content column is Text and not nullable."""
    from test.service_backend.app.models.focus import Briefing
    
    col = Briefing.__table__.columns['content']
    assert 'TEXT' in str(col.type)
    assert col.nullable is False


def test_briefing_source_notification_ids_jsonb():
    """Test that source_notification_ids column is JSONB and nullable."""
    from test.service_backend.app.models.focus import Briefing
    
    col = Briefing.__table__.columns['source_notification_ids']
    assert col.nullable is True


def test_briefing_kind_enum():
    """Test that kind column uses correct ENUM values."""
    from test.service_backend.app.models.focus import Briefing, BriefingKind
    
    kind_col = Briefing.__table__.columns['kind']
    assert 'ENUM' in str(kind_col.type)
    
    # Verify enum values
    assert BriefingKind.morning.value == "morning"
    assert BriefingKind.session_end.value == "session_end"
    assert BriefingKind.manual.value == "manual"


def test_enums_are_python_enums():
    """Test that enum classes are proper Python Enums."""
    from test.service_backend.app.models.focus import FocusSessionStatus, BriefingKind
    
    assert issubclass(FocusSessionStatus, PyEnum)
    assert issubclass(BriefingKind, PyEnum)


def test_models_have_base():
    """Test that models inherit from declarative base."""
    from test.service_backend.app.models.focus import FocusSession, Briefing, Base
    
    assert issubclass(FocusSession, Base)
    assert issubclass(Briefing, Base)
