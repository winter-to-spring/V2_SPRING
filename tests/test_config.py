from __future__ import annotations

from v2_spring.config import load_config


def test_load_config_reads_runtime_and_storage_contract(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://demo:demo@localhost:5432/v2_spring")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("PLANNER_PROVIDER", "scripted")

    config = load_config()

    assert config.app_env == "production"
    assert config.log_level == "warning"
    assert config.database_url == "postgresql+psycopg://demo:demo@localhost:5432/v2_spring"
    assert config.redis_url == "redis://localhost:6379/1"


def test_load_config_uses_documented_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///./.local/test.db")
    monkeypatch.setenv("PLANNER_PROVIDER", "scripted")

    config = load_config()

    assert config.app_env == "local"
    assert config.log_level == "info"
    assert config.redis_url == "redis://localhost:6379/0"
