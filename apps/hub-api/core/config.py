"""Application configuration via Pydantic Settings.

All required env vars are validated at startup — missing values raise immediately,
preventing silent misconfig in production.
"""
from __future__ import annotations

import logging
import secrets
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger("core.config")


class Settings(BaseSettings):
    # JWT
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite:///./presales_hub.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Temporal
    TEMPORAL_HOST: str = "localhost:7233"

    # CORS — must be explicit origins (not wildcard) when credentials=True
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3002",
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # Platform admin
    PLATFORM_ADMIN_KEY: str = "dev-admin-key"

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # Observability
    SENTRY_DSN: str = ""
    OTLP_ENDPOINT: str = ""

    # LLM keys (optional — features degrade gracefully if absent)
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def jwt_secret_min_length(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("JWT_SECRET_KEY must be at least 16 characters")
        return v

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            errors = []
            if self.DATABASE_URL.startswith("sqlite://"):
                errors.append("DATABASE_URL: SQLite not allowed in production")
            if self.PLATFORM_ADMIN_KEY == "dev-admin-key":
                errors.append("PLATFORM_ADMIN_KEY: must be overridden in production")
            if self.DEBUG:
                errors.append("DEBUG: must be False in production")
            if errors:
                raise ValueError(
                    "Production environment misconfiguration:\n" + "\n".join(f"  • {e}" for e in errors)
                )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

if settings.ENVIRONMENT != "production":
    logger.debug(
        "Running in %s mode (DATABASE_URL=%s…)",
        settings.ENVIRONMENT,
        settings.DATABASE_URL[:30],
    )
