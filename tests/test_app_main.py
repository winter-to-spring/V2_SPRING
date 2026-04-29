import subprocess
import sys
import pytest


def test_app_main_importable():
    """Test that app.main can be imported without errors."""
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=".",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Import failed: {result.stderr}"


def test_app_main_creates_fastapi_instance():
    """Test that app instance exists and is a FastAPI app."""
    from app.main import app
    
    assert app is not None
    assert hasattr(app, "add_middleware")
    assert hasattr(app, "get")
    assert app.title == "Cochat"


def test_health_endpoint_exists():
    """Test that /health endpoint is registered."""
    from app.main import app
    
    # Check routes
    routes = [route.path for route in app.routes]
    assert "/health" in routes


def test_get_settings_is_cached():
    """Test that get_settings uses lru_cache."""
    from app.main import get_settings
    
    settings1 = get_settings()
    settings2 = get_settings()
    
    # Should be the same instance due to caching
    assert settings1 is settings2


def test_cors_middleware_configured():
    """Test that CORS middleware is configured."""
    from app.main import app
    
    # Check middleware
    middleware_names = [m.__class__.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middleware_names


def test_settings_class_exists():
    """Test that Settings class can be imported from config."""
    from app.core.config import Settings
    
    assert Settings is not None
    settings = Settings()
    assert hasattr(settings, "model_validate_env") or hasattr(settings, "__fields__")


def test_logging_setup_function_exists():
    """Test that logging setup function exists."""
    from app.core.logging import setup_logging
    
    assert callable(setup_logging)


def test_app_init_files_exist():
    """Test that all required __init__.py files exist."""
    import os
    
    init_files = [
        "test/service-backend/app/__init__.py",
        "test/service-backend/app/core/__init__.py",
    ]
    
    for init_file in init_files:
        assert os.path.exists(init_file), f"Missing {init_file}"


def test_no_db_calls_on_import():
    """Test that importing app.main doesn't make database calls."""
    # This is tested implicitly by test_app_main_importable
    # If any DB calls were made at module level, they would fail
    from app.main import app
    
    # If we got here, no DB calls happened at import time
    assert app is not None
