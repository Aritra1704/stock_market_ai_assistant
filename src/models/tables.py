from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db import Base


class WatchlistDaily(Base):
    __tablename__ = "watchlist_daily"
    __table_args__ = (UniqueConstraint("date", "symbol", "mode", name="uq_watchlist_date_symbol_mode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(120), default="manual")
    mode: Mapped[str] = mapped_column(String(16), default="INTRADAY", nullable=False, index=True)
    horizon_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DailyBudget(Base):
    __tablename__ = "daily_budget"
    __table_args__ = (UniqueConstraint("date", "mode", name="uq_daily_budget_date_mode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    budget_total: Mapped[float] = mapped_column(Float, nullable=False)
    spent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    run_tick_id: Mapped[int | None] = mapped_column(ForeignKey("run_tick.id"), nullable=True, index=True)
    candle_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, default="5m")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="INTRADAY", index=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma20: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ema20: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sma50: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema50: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi14: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    atr14: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vol_avg20: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_slope: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend: Mapped[str] = mapped_column(String(20), nullable=False)
    indicators_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    features_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TradePlan(Base):
    __tablename__ = "trade_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="INTRADAY", nullable=False, index=True)
    plan_type: Mapped[str] = mapped_column(String(16), default="MARKET", nullable=False)
    side: Mapped[str] = mapped_column(String(12), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price_ref: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    gtt_buy_trigger: Mapped[float | None] = mapped_column(Float, nullable=True)
    gtt_sell_trigger: Mapped[float | None] = mapped_column(Float, nullable=True)
    holding_horizon_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_rules_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_portal: Mapped[str] = mapped_column(String(32), default="yfinance", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="PLANNED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trade_plan_id: Mapped[int] = mapped_column(ForeignKey("trade_plan.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), default="INTRADAY", nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(20), default="MARKET", nullable=False)
    source_portal: Mapped[str] = mapped_column(String(32), default="yfinance", nullable=False, index=True)
    execution_portal: Mapped[str] = mapped_column(String(32), default="paper", nullable=False, index=True)
    gtt_id: Mapped[int | None] = mapped_column(ForeignKey("gtt_orders.id"), nullable=True, index=True)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    features_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class GTTOrder(Base):
    __tablename__ = "gtt_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date_created: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_price: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    linked_trade_plan_id: Mapped[int] = mapped_column(ForeignKey("trade_plan.id"), nullable=False, index=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TopStockAudit(Base):
    __tablename__ = "top_stock_audit"
    __table_args__ = (
        UniqueConstraint("date", "mode", "symbol", name="uq_top_stock_audit_date_mode_symbol"),
        UniqueConstraint("date", "mode", "rank", name="uq_top_stock_audit_date_mode_rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class StrategyConfig(Base):
    __tablename__ = "strategy_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="INTRADAY", index=True)
    strategy_version: Mapped[str] = mapped_column(String(40), nullable=False, default="momentum_v1")
    sector: Mapped[str | None] = mapped_column(String(60), nullable=True)
    budget_daily_inr: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    max_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    monitor_interval_min: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    warmup_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_entries_per_symbol_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    target_pct: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    stop_pct: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    time_exit_hhmm: Mapped[str] = mapped_column(String(5), nullable=False, default="15:20")
    rebalance_partial_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    rebalance_full_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    rebalance_partial_fraction: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    fill_model: Mapped[str] = mapped_column(String(20), nullable=False, default="close")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class SectorSchedule(Base):
    __tablename__ = "sector_schedule"
    __table_args__ = (UniqueConstraint("weekday", name="uq_sector_schedule_weekday"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(60), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class SectorUniverse(Base):
    __tablename__ = "sector_universe"
    __table_args__ = (UniqueConstraint("sector_name", "symbol", name="uq_sector_universe_sector_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sector_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Instrument(Base):
    __tablename__ = "instruments"

    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(20), nullable=True, default="NSE")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class InstrumentTaxonomy(Base):
    __tablename__ = "instrument_taxonomy"

    symbol: Mapped[str] = mapped_column(ForeignKey("instruments.symbol"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="yahoo", index=True)
    yahoo_sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    yahoo_industry: Mapped[str | None] = mapped_column(String(160), nullable=True)
    trading_sector: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class DayPlan(Base):
    __tablename__ = "day_plan"
    __table_args__ = (UniqueConstraint("date", name="uq_day_plan_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DayUniverseSnapshot(Base):
    __tablename__ = "day_universe_snapshot"
    __table_args__ = (UniqueConstraint("day_plan_id", "symbol", name="uq_day_universe_snapshot_plan_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    day_plan_id: Mapped[int] = mapped_column(ForeignKey("day_plan.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DaySelection(Base):
    __tablename__ = "day_selection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    day_plan_id: Mapped[int] = mapped_column(ForeignKey("day_plan.id"), nullable=False, index=True)
    selected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ranking_version: Mapped[str] = mapped_column(String(40), nullable=False, default="momentum_v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DaySelectionItem(Base):
    __tablename__ = "day_selection_item"
    __table_args__ = (
        UniqueConstraint("day_selection_id", "symbol", name="uq_day_selection_item_selection_symbol"),
        UniqueConstraint("day_selection_id", "rank", name="uq_day_selection_item_selection_rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    day_selection_id: Mapped[int] = mapped_column(ForeignKey("day_selection.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reasons_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RunTick(Base):
    __tablename__ = "run_tick"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    day_plan_id: Mapped[int] = mapped_column(ForeignKey("day_plan.id"), nullable=False, index=True)
    tick_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    interval: Mapped[str] = mapped_column(String(10), nullable=False, default="5m")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TradeDecision(Base):
    __tablename__ = "trade_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_tick_id: Mapped[int] = mapped_column(ForeignKey("run_tick.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    intended_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    intended_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PaperPosition(Base):
    __tablename__ = "paper_position"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="OPEN", index=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stop_price: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PaperTransaction(Base):
    __tablename__ = "paper_transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("paper_position.id"), nullable=False, index=True)
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("trade_decision.id"), nullable=True, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="paper")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DayBudget(Base):
    __tablename__ = "day_budget"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    budget_total: Mapped[float] = mapped_column(Float, nullable=False)
    used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
