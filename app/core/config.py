"""Boot-time settings, validated via pydantic-settings.

Anything required by the runtime (DATABASE_URL, JWT_SECRET) crashes
the process at startup if missing. Better to fail loud than to start
serving with a broken config silently in place.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Order of precedence: explicit env var > `.env` > field default.
    Anything without a default is REQUIRED — startup fails if absent.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str
    DATABASE_SSL: str = ""

    JWT_SECRET: str = Field(min_length=32)

    CORS_ORIGINS: str = ""
    CSRF_ALLOWED_ORIGINS: str = ""

    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str = ""

    LOG_LEVEL: str = "info"

    @property
    def cors_origin_list(self) -> list[str]:
        """Comma-separated allowlist, stripped + de-empty'd. Refuses '*'
        because we set allow_credentials=True and the CORS spec forbids
        that combination."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip() and o.strip() != "*"]

    @property
    def csrf_origin_list(self) -> list[str]:
        """CSRF allowlist falls back to CORS allowlist when unset — 9/10
        deployments want the same origins gating both reads and writes."""
        explicit = [
            o.strip()
            for o in self.CSRF_ALLOWED_ORIGINS.split(",")
            if o.strip() and o.strip() != "*"
        ]
        return explicit or self.cors_origin_list

    @property
    def use_ssl(self) -> bool:
        return self.DATABASE_SSL == "1"


@lru_cache
def get_settings() -> Settings:
    """Singleton accessor — env is read once, cached. Tests that need to
    override settings can call `get_settings.cache_clear()` between
    cases."""
    return Settings()  # type: ignore[call-arg]
