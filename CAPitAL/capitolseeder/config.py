from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

class Settings(BaseSettings):
    app_name: str = "CAPitAL"
    environment: str = "development"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///./capitolseeder.db"
    
    # Quantitative Scoring Weights
    weight_conflict: float = 0.35
    weight_cluster: float = 0.25
    weight_winrate: float = 0.15
    weight_size: float = 0.15
    weight_asset: float = 0.10
    
    # Compliance & Violations
    stock_act_grace_days: int = 45
    statutory_fine_base: float = 200.0
    
    # Alert thresholds
    high_alpha_threshold: float = 80.0
    high_conflict_threshold: float = 85.0
    
    # Webhooks
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "capitolseeder" / "data"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    return Settings()
