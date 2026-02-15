from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class TrendResponse(BaseModel):
    symbol: str
    interval: str
    period: str
    latest_candle: dict
    indicators: dict
    trend: str
    explanation: str


class WatchlistRequest(BaseModel):
    date: date | None = None
    symbols: list[str] = Field(min_length=1)
    reason: str = "manual"


class RunRequest(BaseModel):
    date: date | None = None
    interval: str = "5m"
    period: str = "5d"


class WatchlistResponse(BaseModel):
    date: date
    inserted: int
    symbols: list[str]


class RunSummaryResponse(BaseModel):
    run_id: str
    date: date
    symbols_processed: int
    signals: dict[str, int]
    trades_executed: int
    remaining_budget: float
