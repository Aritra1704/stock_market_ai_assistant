from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, default="5m")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="INTRADAY", index=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    sma20: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ema20: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sma50: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema50: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi14: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    atr14: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    macd: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend: Mapped[str] = mapped_column(String(20), nullable=False)
    indicators_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
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
