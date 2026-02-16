from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


StrategyMode = Literal["INTRADAY", "SWING"]


class TrendResponse(BaseModel):
    symbol: str
    interval: str
    period: str
    latest_candle: dict
    indicators: dict
    trend: str
    explanation: str


class SwingTrendResponse(BaseModel):
    symbol: str
    interval: str
    period: str
    latest_candle: dict
    indicators: dict
    trend: str
    readiness_score: float
    explanation: str


class WatchlistRequest(BaseModel):
    date: date | None = None
    symbols: list[str] = Field(min_length=1)
    reason: str = "manual"
    mode: StrategyMode = "INTRADAY"
    horizon_days: int | None = None


class RunRequest(BaseModel):
    mode: StrategyMode = "INTRADAY"
    date: date | None = None
    interval: str = "5m"
    period: str = "5d"


class WatchlistResponse(BaseModel):
    date: date
    mode: StrategyMode
    inserted: int
    symbols: list[str]


class RunSummaryResponse(BaseModel):
    run_id: str
    date: date
    mode: StrategyMode
    symbols_processed: int
    signals: dict[str, int]
    trades_executed: int
    remaining_budget: float


class SwingJournalTodayResponse(BaseModel):
    date: date
    watchlist: list[str]
    open_positions: list[dict]
    pending_gtt_orders: list[dict]
    transactions: list[dict]
