"""
Application configuration via pydantic-settings.
All sensitive values are loaded from environment variables / .env file.
Never import settings from here and mutate them — treat as read-only.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str  # postgresql+asyncpg://user:pw@host/db

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str  # redis://user:pw@host:port

    # ── JWT RS256 ─────────────────────────────────────────────────────────────
    JWT_PRIVATE_KEY: str  # PEM string — signs tokens (keep secret)
    JWT_PUBLIC_KEY: str  # PEM string — verifies tokens (safe to share)
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24  # 24h demo | 1h prod

    # ── App ───────────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"  # development | production | test
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5500"

    # ── NLP ───────────────────────────────────────────────────────────────────
    SPACY_MODEL: str = "en_core_web_sm"
    NLP_CONFIDENCE_THRESHOLD: float = 0.6  # below → for_review=true
    FUZZY_SCORE_CUTOFF: int = 75  # rapidfuzz menu-match threshold

    # ── Validators ───────────────────────────────────────────────────────────
    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "production", "test"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}, got '{v}'")
        return v

    @field_validator("ACCESS_TOKEN_EXPIRE_HOURS")
    @classmethod
    def validate_token_ttl(cls, v: int) -> int:
        if v < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_HOURS must be ≥ 1")
        return v

    # ── Computed properties ───────────────────────────────────────────────────
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton. Re-reads env on first call only."""
    return Settings()


# Module-level singleton — import this throughout the app.
settings: Settings = get_settings()
