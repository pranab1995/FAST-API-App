# =============================================================================
# app/core/config.py
#
# PURPOSE:
#   Centralised configuration management using Pydantic's BaseSettings.
#   All environment variables are read ONCE here and imported wherever needed.
#
# DRF EQUIVALENT:
#   This replaces Django's settings.py. However, unlike Django's flat settings
#   module, Pydantic validates types at startup and raises clear errors if
#   a required env var is missing — no more silent mis-configurations.
#
# WHY A SEPARATE FILE?
#   In Django you might import settings anywhere (django.conf.settings).
#   FastAPI has no built-in settings system, so this is the idiomatic way.
#   Centralising config here means changing a value in .env is enough —
#   no need to hunt through the codebase.
# =============================================================================

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables (or .env file).

    Pydantic automatically:
      - Type-casts values (e.g., "30" → int for ACCESS_TOKEN_EXPIRE_MINUTES)
      - Raises a clear ValidationError on startup if a required value is missing
      - Supports .env files via the inner Config class
    """

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str  # e.g. postgresql://user:pass@localhost:5432/dbname

    # ------------------------------------------------------------------
    # JWT / Security
    # ------------------------------------------------------------------
    SECRET_KEY: str        # Random hex string; keep this secret!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ------------------------------------------------------------------
    # Application metadata
    # ------------------------------------------------------------------
    APP_NAME: str = "Task Management API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    class Config:
        # Tell Pydantic to read from a .env file at project root
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Case-insensitive key matching (DATABASE_URL == database_url)
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached singleton instance of Settings.

    @lru_cache ensures Settings() is only created ONCE across the entire
    application lifetime, even though get_settings() may be called many times.

    Usage:
        from app.core.config import get_settings
        settings = get_settings()
        print(settings.SECRET_KEY)
    """
    return Settings()


# Convenience alias — most modules just do `from app.core.config import settings`
settings = get_settings()
