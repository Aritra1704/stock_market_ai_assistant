from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "stock_market_ai_assistant")
    app_debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8003"))

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./stock_market_ai_assistant.db")
    daily_budget_inr: float = float(os.getenv("DAILY_BUDGET_INR", "100"))
    max_open_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", "1"))


settings = Settings()
