import pytest
import tomllib
from pathlib import Path


def test_pyproject_toml_exists():
    """Verify test/service-backend/pyproject.toml exists."""
    pyproject_path = Path("test/service-backend/pyproject.toml")
    assert pyproject_path.exists(), f"File not found: {pyproject_path}"


def test_pyproject_toml_valid_pep621():
    """Verify pyproject.toml is valid PEP 621 with hatchling."""
    pyproject_path = Path("test/service-backend/pyproject.toml")
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    
    assert "build-system" in data
    assert data["build-system"]["build-backend"] == "hatchling.build"
    assert "project" in data
    assert data["project"]["name"] == "service-backend"


def test_pyproject_required_dependencies():
    """Verify all required dependencies are listed."""
    pyproject_path = Path("test/service-backend/pyproject.toml")
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    
    deps = data["project"]["dependencies"]
    deps_str = " ".join(deps)
    
    required = [
        "fastapi",
        "uvicorn",
        "sqlalchemy>=2",
        "asyncpg",
        "alembic",
        "pgvector",
        "redis",
        "httpx",
        "pydantic>=2",
        "pydantic-settings",
        "python-jose",
        "passlib",
        "slack-sdk",
        "langgraph",
        "langchain-core",
        "langchain-openai",
        "sse-starlette",
        "python-multipart",
        "structlog",
    ]
    
    for dep in required:
        assert dep in deps_str, f"Missing dependency: {dep}"


def test_pyproject_dev_dependencies():
    """Verify dev dependencies are listed."""
    pyproject_path = Path("test/service-backend/pyproject.toml")
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    
    dev_deps = data["project"]["optional-dependencies"]["dev"]
    dev_deps_str = " ".join(dev_deps)
    
    required_dev = ["pytest", "pytest-asyncio", "httpx", "ruff"]
    
    for dep in required_dev:
        assert dep in dev_deps_str, f"Missing dev dependency: {dep}"


def test_env_example_exists():
    """Verify test/service-backend/.env.example exists."""
    env_path = Path("test/service-backend/.env.example")
    assert env_path.exists(), f"File not found: {env_path}"


def test_env_example_contains_required_keys():
    """Verify .env.example has all required environment keys."""
    env_path = Path("test/service-backend/.env.example")
    content = env_path.read_text()
    
    required_keys = [
        "DATABASE_URL",
        "REDIS_URL",
        "SLACK_CLIENT_ID",
        "SLACK_CLIENT_SECRET",
        "SLACK_SIGNING_SECRET",
        "OPENAI_API_KEY",
        "JWT_SECRET",
        "APP_BASE_URL",
    ]
    
    for key in required_keys:
        assert key in content, f"Missing env key: {key}"


def test_readme_exists():
    """Verify test/service-backend/README.md exists."""
    readme_path = Path("test/service-backend/README.md")
    assert readme_path.exists(), f"File not found: {readme_path}"


def test_readme_line_count():
    """Verify README.md is <= 25 lines."""
    readme_path = Path("test/service-backend/README.md")
    lines = readme_path.read_text().splitlines()
    assert len(lines) <= 25, f"README.md has {len(lines)} lines, max 25 allowed"


def test_readme_contains_run_instructions():
    """Verify README.md contains basic run instructions."""
    readme_path = Path("test/service-backend/README.md")
    content = readme_path.read_text().lower()
    
    # Check for run-related keywords
    assert any(keyword in content for keyword in ["run", "install", "setup", "start", "serve"]), \
        "README.md missing run instructions"
