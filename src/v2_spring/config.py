from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """Configuration required by the Step 1 tracer bullet."""

    database_url: str


def load_config(database_url_override: str | None = None) -> AppConfig:
    """Load application config from an explicit override or the environment."""

    database_url = database_url_override or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in the environment or pass --database-url.",
        )

    return AppConfig(database_url=database_url)
