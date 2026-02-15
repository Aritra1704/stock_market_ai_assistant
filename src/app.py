from __future__ import annotations

import logging

from fastapi import FastAPI

from src.api.routes import router
from src.config import settings
from src.models.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="stock_market_ai_assistant",
    description="Paper-trading assistant with yfinance market analysis and journaling",
    version="0.1.0",
    debug=settings.app_debug,
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()


app.include_router(router)
