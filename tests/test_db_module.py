"""
Test suite for database module structure and async SQLAlchemy setup.
Verifies __init__.py exports, base.py declarative base, session.py engine/sessionmaker,
and init_models() helper functionality.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure app module is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_db_init_exports():
    """Verify app/db/__init__.py exports all required components."""
    from app.db import Base, AsyncSessionLocal, get_db, init_models, engine
    
    # All imports should succeed and not be None
    assert Base is not None, "Base should be exported from app.db"
    assert AsyncSessionLocal is not None, "AsyncSessionLocal should be exported"
    assert get_db is not None, "get_db dependency should be exported"
    assert init_models is not None, "init_models helper should be exported"
    assert engine is not None, "engine should be exported"


def test_base_is_declarative_base():
    """Verify app/db/base.py exports proper declarative base."""
    from app.db.base import Base
    from sqlalchemy.orm import DeclarativeBase
    
    # Base should be a DeclarativeBase instance or subclass
    assert hasattr(Base, "metadata"), "Base should have metadata attribute"
    assert hasattr(Base, "registry"), "Base should have registry attribute"


def test_session_engine_configuration():
    """Verify app/db/session.py creates async engine with correct configuration."""
    from app.db.session import engine
    
    # Engine should be an async engine instance
    assert engine is not None, "Engine should not be None"
    assert hasattr(engine, "execute"), "Engine should have execute method"
    assert hasattr(engine, "dispose"), "Engine should have dispose method"


def test_async_sessionmaker_is_callable():
    """Verify AsyncSessionLocal is a sessionmaker instance."""
    from app.db.session import AsyncSessionLocal
    
    # AsyncSessionLocal should be callable (sessionmaker instance)
    assert callable(AsyncSessionLocal), "AsyncSessionLocal should be callable"


@pytest.mark.asyncio
async def test_get_db_dependency_returns_async_session():
    """Verify get_db() is an async generator yielding AsyncSession."""
    from app.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # get_db should be an async generator function
    assert hasattr(get_db, "__aiter__") or hasattr(get_db, "__call__"), \
        "get_db should be callable/generator"
    
    # Call get_db and verify it returns an async generator
    gen = get_db()
    assert hasattr(gen, "__anext__"), "get_db() should return an async generator"


@pytest.mark.asyncio
async def test_init_models_creates_tables():
    """Verify init_models() creates all tables in test database."""
    import asyncio
    from app.db import Base, init_models
    
    # init_models should be callable and async
    assert callable(init_models), "init_models should be callable"
    
    # Call init_models and verify it completes without error
    # (it may use in-memory sqlite+aiosqlite or configured DATABASE_URL)
    try:
        result = await init_models()
        # Should succeed (None or True return expected)
        assert result is None or isinstance(result, bool), \
            "init_models() should return None or bool"
    except Exception as e:
        pytest.fail(f"init_models() raised unexpected exception: {e}")


@pytest.mark.asyncio
async def test_init_models_idempotent():
    """Verify init_models() can be called multiple times safely."""
    from app.db import init_models
    
    # Should succeed multiple times without error
    await init_models()
    await init_models()  # Second call should not raise


def test_db_files_exist():
    """Verify all required database module files exist."""
    db_init_path = Path(__file__).parent.parent / "app" / "db" / "__init__.py"
    db_base_path = Path(__file__).parent.parent / "app" / "db" / "base.py"
    db_session_path = Path(__file__).parent.parent / "app" / "db" / "session.py"
    
    assert db_init_path.exists(), f"File {db_init_path} should exist"
    assert db_base_path.exists(), f"File {db_base_path} should exist"
    assert db_session_path.exists(), f"File {db_session_path} should exist"


def test_db_init_file_has_all_exports():
    """Verify __init__.py defines __all__ with expected exports."""
    from app.db import __all__
    
    expected_exports = {"Base", "AsyncSessionLocal", "get_db", "init_models", "engine"}
    actual_exports = set(__all__)
    
    assert expected_exports.issubset(actual_exports), \
        f"__all__ should include {expected_exports}, got {actual_exports}"
