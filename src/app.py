from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from src.api.routes import router
from src.config import settings
from src.models.db import init_db
from src.services.top_stocks_cleanup_scheduler import TopStocksCleanupScheduler

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
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
top_stocks_cleanup_scheduler = TopStocksCleanupScheduler()


@app.on_event("startup")
def startup_event() -> None:
    max_attempts = 8
    delay_seconds = 3
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            init_db()
            logging.info("Database initialization completed", extra={"attempt": attempt, "schema": settings.db_schema})
            top_stocks_cleanup_scheduler.start()
            return
        except SQLAlchemyError as exc:
            last_error = exc
            logging.exception(
                "Database initialization failed",
                extra={"attempt": attempt, "max_attempts": max_attempts},
            )
            if attempt < max_attempts:
                time.sleep(delay_seconds)
            continue

    raise RuntimeError("Database initialization failed after retries") from last_error


@app.on_event("shutdown")
def shutdown_event() -> None:
    top_stocks_cleanup_scheduler.stop()


app.include_router(router)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
