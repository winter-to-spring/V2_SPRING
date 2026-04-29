"""Tests for FocusSession model definition."""
import ast
import uuid
from pathlib import Path


def test_focus_session_model_exists():
    """Verify focus_session.py file exists."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    assert target_path.exists(), f"File {target_path} does not exist"


def test_focus_session_imports():
    """Verify required imports are present."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    required_imports = [
        "import uuid",
        "from datetime import datetime",
        "from enum import Enum as PyEnum",
        "from sqlalchemy import",
        "from sqlalchemy.dialects.postgresql import UUID",
        "from sqlalchemy.orm import relationship",
    ]
    
    for import_str in required_imports:
        assert import_str in content, f"Missing import: {import_str}"


def test_focus_session_status_enum():
    """Verify FocusSessionStatus enum is defined correctly."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    assert "class FocusSessionStatus(PyEnum):" in content
    assert 'active = "active"' in content
    assert 'completed = "completed"' in content
    assert 'cancelled = "cancelled"' in content


def test_focus_session_class_definition():
    """Verify FocusSession class exists with correct table name."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    assert "class FocusSession(Base):" in content
    assert '__tablename__ = "focus_sessions"' in content


def test_focus_session_id_field():
    """Verify id field is UUID primary key."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    assert "id = Column(" in content
    assert "UUID(as_uuid=True)" in content
    assert "primary_key=True" in content
    assert "default=uuid.uuid4" in content


def test_focus_session_user_id_field():
    """Verify user_id is UUID foreign key to users table."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    assert "user_id = Column(" in content
    assert 'ForeignKey("users.id")' in content
    assert "UUID(as_uuid=True)" in content


def test_focus_session_timestamps():
    """Verify timestamp fields are properly defined."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    assert "started_at = Column(" in content
    assert "DateTime(timezone=True)" in content
    assert "server_default=func.now()" in content
    
    assert "ended_at = Column(" in content
    assert "nullable=True" in content


def test_focus_session_status_field():
    """Verify status field is enum with correct default."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    assert "status = Column(" in content
    assert "Enum(FocusSessionStatus)" in content
    assert "default=FocusSessionStatus.active" in content


def test_focus_session_briefing_id_field():
    """Verify briefing_id is nullable UUID foreign key."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    assert "briefing_id = Column(" in content
    assert 'ForeignKey("briefings.id")' in content
    assert "UUID(as_uuid=True)" in content
    assert "nullable=True" in content


def test_focus_session_relationships():
    """Verify relationships use string references to avoid circular imports."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    assert 'user = relationship("User"' in content
    assert 'briefing = relationship("Briefing"' in content
    assert 'back_populates=' in content


def test_focus_session_no_circular_imports():
    """Verify string references are used for relationships (no direct class imports)."""
    target_path = Path("test/service-backend/app/models/focus_session.py")
    content = target_path.read_text()
    
    # Should NOT import User or Briefing classes directly
    assert "from app.models.user import User" not in content
    assert "from app.models.briefing import Briefing" not in content
    
    # Should use string references in relationship() calls
    assert 'relationship("User"' in content
    assert 'relationship("Briefing"' in content
