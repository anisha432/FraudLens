"""Core configuration for the Fraud Detection Platform."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "Fraud Detection Platform"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./fraud_detection.db"
    DATABASE_URL_SYNC: str = "sqlite:///./fraud_detection.db"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ML
    MODELS_DIR: str = "./models_artifacts"
    DEFAULT_THRESHOLD: float = 0.5

    # Simulation
    SIMULATION_INTERVAL: float = 3.0
    SIMULATION_ENABLED: bool = True

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
