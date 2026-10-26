from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "biOF"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # Hybrid persistence: SQLite (aiosqlite) default, PostgreSQL supported via DATABASE_URL
    DATABASE_URL: str = "sqlite+aiosqlite:///./bioseeder.db"
    DATABASE_ECHO: bool = False

    # Regulatory & Market Data Collector Configurations
    CLINICALTRIALS_BASE_URL: str = "https://clinicaltrials.gov/api/v2"
    OPENFDA_BASE_URL: str = "https://api.fda.gov"
    OPENFDA_API_KEY: Optional[str] = None

    # Rate limiting & exponential backoff settings
    COLLECTOR_RATE_LIMIT_HZ: float = 5.0  # requests per second
    COLLECTOR_MAX_RETRIES: int = 4
    COLLECTOR_BACKOFF_BASE_SEC: float = 1.0
    COLLECTOR_TIMEOUT_SEC: float = 15.0

    # Security & Administration
    ADMIN_API_KEY: Optional[str] = None

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
