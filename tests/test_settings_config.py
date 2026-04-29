import os
import sys
import pytest
from pathlib import Path


def test_settings_config_file_exists():
    """Test that config.py file exists at expected location."""
    config_file = Path("test/service-backend/app/core/config.py")
    assert config_file.exists(), f"Config file not found at {config_file}"


def test_settings_class_defined():
    """Test that Settings class is properly defined."""
    # Add module to path if needed
    sys.path.insert(0, str(Path.cwd()))
    from test.service_backend.app.core.config import Settings
    
    assert hasattr(Settings, "__annotations__"), "Settings class should have type annotations"
    expected_fields = {
        "DATABASE_URL",
        "REDIS_URL",
        "SLACK_CLIENT_ID",
        "SLACK_CLIENT_SECRET",
        "SLACK_SIGNING_SECRET",
        "OPENAI_API_KEY",
        "JWT_SECRET",
        "JWT_ALGORITHM",
        "JWT_EXPIRE_MINUTES",
        "FRONTEND_URL",
        "BACKEND_URL",
        "ENV",
    }
    actual_fields = set(Settings.model_fields.keys())
    assert expected_fields == actual_fields, f"Settings fields mismatch. Expected {expected_fields}, got {actual_fields}"


def test_settings_defaults():
    """Test that Settings has correct default values."""
    sys.path.insert(0, str(Path.cwd()))
    from test.service_backend.app.core.config import Settings
    
    # Test with environment variables set
    os.environ["DATABASE_URL"] = "postgres://localhost/testdb"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    os.environ["SLACK_CLIENT_ID"] = "test-client-id"
    os.environ["SLACK_CLIENT_SECRET"] = "test-client-secret"
    os.environ["SLACK_SIGNING_SECRET"] = "test-signing-secret"
    os.environ["OPENAI_API_KEY"] = "test-api-key"
    os.environ["JWT_SECRET"] = "test-jwt-secret"
    os.environ["FRONTEND_URL"] = "http://localhost:3000"
    os.environ["BACKEND_URL"] = "http://localhost:8000"
    
    settings = Settings()
    
    assert settings.JWT_ALGORITHM == "HS256", "JWT_ALGORITHM should default to HS256"
    assert settings.JWT_EXPIRE_MINUTES == 1440, "JWT_EXPIRE_MINUTES should default to 1440 (60*24)"
    assert settings.ENV == "dev", "ENV should default to dev"


def test_get_settings_function():
    """Test that get_settings() function exists and is lru_cached."""
    sys.path.insert(0, str(Path.cwd()))
    from test.service_backend.app.core.config import get_settings
    
    assert callable(get_settings), "get_settings should be callable"
    assert hasattr(get_settings, "__wrapped__"), "get_settings should be decorated with lru_cache"
    
    # Set required env vars
    os.environ["DATABASE_URL"] = "postgres://localhost/testdb"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    os.environ["SLACK_CLIENT_ID"] = "test-client-id"
    os.environ["SLACK_CLIENT_SECRET"] = "test-client-secret"
    os.environ["SLACK_SIGNING_SECRET"] = "test-signing-secret"
    os.environ["OPENAI_API_KEY"] = "test-api-key"
    os.environ["JWT_SECRET"] = "test-jwt-secret"
    os.environ["FRONTEND_URL"] = "http://localhost:3000"
    os.environ["BACKEND_URL"] = "http://localhost:8000"
    
    # Clear cache for fresh test
    get_settings.cache_clear()
    
    settings1 = get_settings()
    settings2 = get_settings()
    
    assert settings1 is settings2, "get_settings() should return cached instance"


def test_core_init_files_exist():
    """Test that __init__.py files exist in expected locations."""
    app_init = Path("test/service-backend/app/__init__.py")
    core_init = Path("test/service-backend/app/core/__init__.py")
    
    assert app_init.exists(), f"__init__.py not found at {app_init}"
    assert core_init.exists(), f"__init__.py not found at {core_init}"
