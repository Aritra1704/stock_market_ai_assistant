from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, Field


StrategyMode = Literal["INTRADAY", "SWING"]
AuditFetchMode = Literal["INTRADAY", "SWING", "BOTH"]


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
    date: Optional[dt.date] = None
    symbols: list[str] = Field(min_length=1)
    reason: str = "manual"
    mode: StrategyMode = "INTRADAY"
    horizon_days: int | None = None


class RunRequest(BaseModel):
    mode: StrategyMode = "INTRADAY"
    date: Optional[dt.date] = None
    interval: str = "5m"
    period: str = "5d"


class WatchlistResponse(BaseModel):
    date: dt.date
    mode: StrategyMode
    inserted: int
    symbols: list[str]


class RunSummaryResponse(BaseModel):
    run_id: str
    date: dt.date
    mode: StrategyMode
    symbols_processed: int
    signals: dict[str, int]
    trades_executed: int
    remaining_budget: float


class SwingJournalTodayResponse(BaseModel):
    date: dt.date
    watchlist: list[str]
    open_positions: list[dict]
    pending_gtt_orders: list[dict]
    transactions: list[dict]


class TopStockAuditItem(BaseModel):
    rank: int
    symbol: str
    score: float
    metric: str
    details: dict = Field(default_factory=dict)
    created_at: dt.datetime


class TopStockAuditModeResponse(BaseModel):
    mode: StrategyMode
    count: int
    items: list[TopStockAuditItem]


class TopStocksAuditTodayResponse(BaseModel):
    date: dt.date
    intraday: TopStockAuditModeResponse
    swing: TopStockAuditModeResponse


class TopStocksAuditGenerateRequest(BaseModel):
    date: Optional[dt.date] = None
    mode: AuditFetchMode = "BOTH"
    force_refresh: bool = False
