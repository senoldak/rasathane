import os
from typing import Optional

def _load_dotenv(dotenv_path: str = ".env"):
    """Lightweight .env reader that does not require external dependencies."""
    if not os.path.exists(dotenv_path):
        # Also check parent directory if running from a subdirectory
        parent_dotenv = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(parent_dotenv):
            dotenv_path = parent_dotenv
        else:
            return

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass

# Attempt to load .env on module import
_load_dotenv()

class Settings:
    """Centralized configuration settings loaded from environment variables."""

    # Database
    DB_PATH: str = os.getenv("INSEEDER_DB_PATH", "inseeder.db")

    # SEC Ingestion
    SEC_USER_AGENT: str = os.getenv("SEC_USER_AGENT", "INseeder Research admin@inseeder.local")
    POLL_INTERVAL_SEC: float = float(os.getenv("POLL_INTERVAL_SEC", "30.0"))

    # Alerting
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN") or None
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID") or None
    DISCORD_WEBHOOK_URL: Optional[str] = os.getenv("DISCORD_WEBHOOK_URL") or None

    # Broker Configuration
    DEFAULT_BROKER: str = os.getenv("DEFAULT_BROKER", "paper").lower()

    # Alpaca Markets
    ALPACA_API_KEY: Optional[str] = os.getenv("ALPACA_API_KEY") or None
    ALPACA_API_SECRET: Optional[str] = os.getenv("ALPACA_API_SECRET") or None
    ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    # Interactive Brokers
    IBKR_BASE_URL: str = os.getenv("IBKR_BASE_URL", "https://localhost:5000/v1/api")
    IBKR_ACCOUNT_ID: Optional[str] = os.getenv("IBKR_ACCOUNT_ID") or None

    # Server Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()]

settings = Settings()
