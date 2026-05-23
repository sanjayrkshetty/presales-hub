"""Application configuration via Pydantic Settings.

All required env vars are validated at startup — missing values raise immediately,
preventing silent misconfig in production.
"""
from __future__ import annotations

import secrets
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
