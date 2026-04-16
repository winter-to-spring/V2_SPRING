from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_env: str
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_port: int
    redis_port: int
    n8n_port: int
    timezone: str


def load_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        postgres_db=os.getenv("POSTGRES_DB", "agent_studio"),
        postgres_user=os.getenv("POSTGRES_USER", "agent_studio"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "change_me_postgres"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        n8n_port=int(os.getenv("N8N_PORT", "5678")),
        timezone=os.getenv("TZ", "Asia/Seoul"),
    )

