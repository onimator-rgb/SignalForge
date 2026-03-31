from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://marketpulse:marketpulse@localhost:5432/marketpulse"
    )

    # Redis (future-ready)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Binance
    BINANCE_BASE_URL: str = "https://api.binance.com"

    # CoinGecko
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"

    # Ingestion
    INGESTION_INTERVAL_MINUTES: int = 5
    INGESTION_BACKFILL_DAYS: int = 7

    # Scheduler (disabled by default — use manual trigger for testing)
    SCHEDULER_ENABLED: bool = False

    # Anomaly thresholds
    ANOMALY_PRICE_ZSCORE_THRESHOLD: float = 2.5
    ANOMALY_VOLUME_ZSCORE_THRESHOLD: float = 3.0
    ANOMALY_RSI_UPPER: float = 80.0
    ANOMALY_RSI_LOWER: float = 20.0

    # LLM
    LLM_PROVIDER: str = "local"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = ""

    # Strategy
    STRATEGY_PROFILE: str = "balanced"
    STRATEGY_AUTO_SWITCH: bool = False

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"


settings = Settings()
