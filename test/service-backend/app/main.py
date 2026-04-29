import logging
import os
from functools import lru_cache

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.logging import setup_logging

# Setup logging at module import time
setup_logging()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from environment and .env.example file."""
    return Settings()  # type: ignore


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(title="Cochat")
    
    # Configure CORS for localhost:3000
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "ok"}
    
    return app


# Create app instance at module level but ensure no DB calls
app = create_app()

logger.info("FastAPI app initialized", extra={"app_title": "Cochat"})
