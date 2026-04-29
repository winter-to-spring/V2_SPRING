import os
import tomllib
from pathlib import Path


def test_pyproject_toml_exists():
    """Test that pyproject.toml exists."""
    pyproject_path = Path("test/service-backend/pyproject.toml")
    assert pyproject_path.exists(), f"Missing {pyproject_path}"


def test_pyproject_toml_has_required_dependencies():
    """Test that pyproject.toml contains all required dependencies."""
    pyproject_path = Path("test/service-backend/pyproject.toml")
    
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
    
    required_deps = [
        "fastapi",
        "uvicorn[standard]",
        "sqlalchemy>=2",
        "asyncpg",
        "alembic",
        "pydantic>=2",
        "pydantic-settings",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "httpx",
        "redis",
        "langgraph",
        "langchain-openai",
        "sse-starlette",
        "python-multipart",
        "structlog",
    ]
    
    dependencies = config.get("project", {}).get("dependencies", [])
    
    for dep in required_deps:
        assert any(dep in d for d in dependencies), \
            f"Required dependency '{dep}' not found in pyproject.toml"


def test_pyproject_toml_has_dev_dependencies():
    """Test that pyproject.toml contains all required dev dependencies."""
    pyproject_path = Path("test/service-backend/pyproject.toml")
    
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
    
    required_dev_deps = [
        "pytest",
        "pytest-asyncio",
        "httpx",
        "pytest-mock",
    ]
    
    dev_deps = config.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    
    for dep in required_dev_deps:
        assert any(dep in d for d in dev_deps), \
            f"Required dev dependency '{dep}' not found in pyproject.toml"


def test_pyproject_toml_python_version():
    """Test that pyproject.toml requires Python 3.12+."""
    pyproject_path = Path("test/service-backend/pyproject.toml")
    
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
    
    requires_python = config.get("project", {}).get("requires-python")
    assert requires_python == ">=3.12", \
        f"Expected requires-python '>=3.12', got '{requires_python}'"


def test_dockerfile_exists():
    """Test that Dockerfile exists."""
    dockerfile_path = Path("test/service-backend/Dockerfile")
    assert dockerfile_path.exists(), f"Missing {dockerfile_path}"


def test_dockerfile_content():
    """Test that Dockerfile has required content."""
    dockerfile_path = Path("test/service-backend/Dockerfile")
    
    with open(dockerfile_path, "r") as f:
        content = f.read()
    
    assert "python:3.12-slim" in content, "Dockerfile must use python:3.12-slim"
    assert "uvicorn app.main:app" in content, "Dockerfile must have uvicorn command"
    assert "--host 0.0.0.0" in content, "Dockerfile must expose on 0.0.0.0"
    assert "--port 8000" in content, "Dockerfile must use port 8000"


def test_dockerignore_exists():
    """Test that .dockerignore exists."""
    dockerignore_path = Path("test/service-backend/.dockerignore")
    assert dockerignore_path.exists(), f"Missing {dockerignore_path}"


def test_readme_exists():
    """Test that README.md exists."""
    readme_path = Path("test/service-backend/README.md")
    assert readme_path.exists(), f"Missing {readme_path}"


def test_readme_has_run_instructions():
    """Test that README.md contains run instructions."""
    readme_path = Path("test/service-backend/README.md")
    
    with open(readme_path, "r") as f:
        content = f.read().lower()
    
    assert "install" in content or "setup" in content or "dependencies" in content, \
        "README.md should contain installation instructions"
    assert "run" in content or "start" in content or "uvicorn" in content, \
        "README.md should contain run instructions"
