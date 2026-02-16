from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "stock_market_ai_assistant")
    app_debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8003"))

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
    )
    db_schema: str = os.getenv("DB_SCHEMA", "stock_ai_lab")

    intraday_daily_budget_inr: float = float(os.getenv("INTRADAY_DAILY_BUDGET_INR", "100"))
    intraday_max_open_positions: int = int(os.getenv("INTRADAY_MAX_OPEN_POSITIONS", "1"))

    swing_allocation_inr: float = float(os.getenv("SWING_ALLOCATION_INR", "1000"))
    swing_max_open_positions: int = int(os.getenv("SWING_MAX_OPEN_POSITIONS", "2"))
    swing_default_horizon_days: int = int(os.getenv("SWING_DEFAULT_HORIZON_DAYS", "20"))


settings = Settings()
