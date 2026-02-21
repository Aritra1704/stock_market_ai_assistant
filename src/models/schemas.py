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


class StrategyConfigCreateRequest(BaseModel):
    active: bool = True
    set_active: bool = True
    mode: str = "INTRADAY"
    strategy_version: str = "momentum_v1"
    sector: str | None = None
    budget_daily_inr: float = Field(default=10000.0, gt=0)
    max_positions: int = Field(default=2, ge=1, le=2)
    monitor_interval_min: int = Field(default=5, ge=1, le=60)
    warmup_minutes: int = Field(default=20, ge=0, le=120)
    max_entries_per_symbol_per_day: int = Field(default=1, ge=1, le=10)
    target_pct: float = Field(default=1.5, gt=0)
    stop_pct: float = Field(default=1.0, gt=0)
    time_exit_hhmm: str = "15:20"
    rebalance_partial_threshold: float = Field(default=15.0, gt=0)
    rebalance_full_threshold: float = Field(default=20.0, gt=0)
    rebalance_partial_fraction: float = Field(default=0.5, gt=0, le=1)
    fill_model: str = "close"


class StrategyConfigResponse(BaseModel):
    id: int
    active: bool
    mode: str
    strategy_version: str
    sector: str | None
    budget_daily_inr: float
    max_positions: int
    monitor_interval_min: int
    warmup_minutes: int
    max_entries_per_symbol_per_day: int
    target_pct: float
    stop_pct: float
    time_exit_hhmm: str
    rebalance_partial_threshold: float
    rebalance_full_threshold: float
    rebalance_partial_fraction: float
    fill_model: str
    created_at: dt.datetime


class SectorScheduleItem(BaseModel):
    weekday: int = Field(ge=0, le=6)
    sector_name: str = Field(min_length=1)
    active: bool = True


class SectorScheduleUpsertRequest(BaseModel):
    mappings: list[SectorScheduleItem] = Field(min_length=1)


class SectorUniverseUpdateRequest(BaseModel):
    sector_name: str = Field(min_length=1)
    add_symbols: list[str] = Field(default_factory=list)
    remove_symbols: list[str] = Field(default_factory=list)


class PlanDayRequest(BaseModel):
    date: Optional[dt.date] = None
    notes: str | None = None
    force_replan: bool = False


class PlanDaySelectionItem(BaseModel):
    symbol: str
    rank: int
    score: float
    reasons_json: dict
    features_json: dict
    summary_text: str


class PlanDayResponse(BaseModel):
    date: dt.date
    sector_name: str
    day_plan_id: int
    day_selection_id: int
    top5: list[PlanDaySelectionItem]


class RunTickRequest(BaseModel):
    date: Optional[dt.date] = None
    interval_min: int | None = Field(default=None, ge=1, le=60)


class RunTickResponse(BaseModel):
    date: dt.date
    day_plan_id: int
    run_tick_id: int
    interval: str
    symbols_checked: int
    buys: int
    sells: int
    holds: int
    rebalances: int
    skipped_weekend: bool = False


class ExitDayRequest(BaseModel):
    date: Optional[dt.date] = None


class ExitDayResponse(BaseModel):
    date: dt.date
    closed_positions: int
    skipped_weekend: bool = False


class AuditPositionItem(BaseModel):
    id: int
    symbol: str
    status: str
    qty: float
    entry_price: float
    stop_price: float
    target_price: float
    entry_time: dt.datetime
    exit_time: dt.datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    pnl: float | None = None


class AuditTransactionItem(BaseModel):
    id: int
    position_id: int
    decision_id: int | None
    side: str
    qty: float
    price: float
    timestamp: dt.datetime
    mode: str


class AuditDecisionItem(BaseModel):
    id: int
    symbol: str
    action: str
    intended_qty: float
    intended_price: float
    stop_price: float | None = None
    target_price: float | None = None
    run_tick_id: int | None = None
    tick_time: dt.datetime | None = None
    reasons_json: dict
    features_json: dict
    summary_text: str
    created_at: dt.datetime


class AuditTodayResponse(BaseModel):
    date: dt.date
    sector_name: str | None
    top5: list[PlanDaySelectionItem]
    budget: dict
    positions: list[AuditPositionItem]
    transactions: list[AuditTransactionItem]
    decisions: list[AuditDecisionItem]
