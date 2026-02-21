from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from src.api.routes import router
from src.api.routes_trading import router as trading_router
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
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
top_stocks_cleanup_scheduler = TopStocksCleanupScheduler()


@app.on_event("startup")
def startup_event() -> None:
    try:
        init_db()
        logging.info("Database initialization completed", extra={"schema": settings.db_schema})
    except SQLAlchemyError:
        logging.exception("Database initialization failed; app will continue for non-DB routes")
    except Exception:
        logging.exception("Unexpected startup error during DB initialization")

    try:
        top_stocks_cleanup_scheduler.start()
    except Exception:
        logging.exception("Failed to start cleanup scheduler")


@app.on_event("shutdown")
def shutdown_event() -> None:
    top_stocks_cleanup_scheduler.stop()


app.include_router(router)
app.include_router(trading_router)


def _render_ui(request: Request, template_name: str, active_page: str, page_title: str):
    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "active_page": active_page,
            "page_title": page_title,
        },
    )


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/ui/dashboard", status_code=307)


@app.get("/ui/dashboard", response_class=HTMLResponse, include_in_schema=False)
def ui_dashboard(request: Request):
    return _render_ui(request, "dashboard.html", "dashboard", "Dashboard")


@app.get("/ui/plan", response_class=HTMLResponse, include_in_schema=False)
def ui_plan(request: Request):
    return _render_ui(request, "plan.html", "plan", "Plan")


@app.get("/ui/positions", response_class=HTMLResponse, include_in_schema=False)
def ui_positions(request: Request):
    return _render_ui(request, "positions.html", "positions", "Positions")


@app.get("/ui/decisions", response_class=HTMLResponse, include_in_schema=False)
def ui_decisions(request: Request):
    return _render_ui(request, "decisions.html", "decisions", "Decisions")


@app.get("/ui/transactions", response_class=HTMLResponse, include_in_schema=False)
def ui_transactions(request: Request):
    return _render_ui(request, "transactions.html", "transactions", "Transactions")


@app.get("/ui/audit", response_class=HTMLResponse, include_in_schema=False)
def ui_audit(request: Request):
    return _render_ui(request, "audit.html", "audit", "Audit")


@app.get("/ui/sectors", response_class=HTMLResponse, include_in_schema=False)
def ui_sectors(request: Request):
    return _render_ui(request, "sectors.html", "sectors", "Sectors")


@app.get("/ui/settings", response_class=HTMLResponse, include_in_schema=False)
def ui_settings(request: Request):
    return _render_ui(request, "settings.html", "settings", "Settings")
