from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from v2_spring.domain.planner_adapter import PlannerTransportProvider


load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """Configuration required by the current CLI slices."""

    app_env: str
    log_level: str
    database_url: str
    redis_url: str
    planner_provider: PlannerTransportProvider
    planner_openai_model: str
    planner_anthropic_model: str
    planner_timeout_seconds: float
    planner_max_retries: int
    planner_max_context_chars: int
    openai_api_key: str | None
    anthropic_api_key: str | None


def load_config(database_url_override: str | None = None) -> AppConfig:
    """Load application config from an explicit override or the environment."""

    database_url = database_url_override or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in the environment or pass --database-url.",
        )

    provider_name = (os.getenv("PLANNER_PROVIDER") or PlannerTransportProvider.SCRIPTED.value).strip()
    try:
        planner_provider = PlannerTransportProvider(provider_name)
    except ValueError as exc:
        raise RuntimeError(
            "PLANNER_PROVIDER is invalid. Expected one of: "
            + ", ".join(item.value for item in PlannerTransportProvider),
        ) from exc

    return AppConfig(
        app_env=(os.getenv("APP_ENV") or "local").strip(),
        log_level=(os.getenv("LOG_LEVEL") or "info").strip(),
        database_url=database_url,
        redis_url=(os.getenv("REDIS_URL") or "redis://localhost:6379/0").strip(),
        planner_provider=planner_provider,
        planner_openai_model=(os.getenv("PLANNER_OPENAI_MODEL") or "gpt-4o").strip(),
        planner_anthropic_model=(os.getenv("PLANNER_ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest").strip(),
        planner_timeout_seconds=float(os.getenv("PLANNER_TIMEOUT_SECONDS") or "30"),
        planner_max_retries=int(os.getenv("PLANNER_MAX_RETRIES") or "2"),
        planner_max_context_chars=int(os.getenv("PLANNER_MAX_CONTEXT_CHARS") or "12000"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
