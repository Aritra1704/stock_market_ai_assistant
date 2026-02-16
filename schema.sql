-- stock_market_ai_assistant PostgreSQL schema
-- This script creates objects ONLY in stock_ai_lab schema.

CREATE SCHEMA IF NOT EXISTS stock_ai_lab AUTHORIZATION postgres;
SET search_path TO stock_ai_lab;

CREATE TABLE IF NOT EXISTS watchlist_daily (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    reason VARCHAR(120),
    mode VARCHAR(16) NOT NULL DEFAULT 'INTRADAY',
    horizon_days INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_watchlist_date_symbol_mode
ON watchlist_daily (date, symbol, mode);

CREATE INDEX IF NOT EXISTS ix_watchlist_daily_date ON watchlist_daily (date);
CREATE INDEX IF NOT EXISTS ix_watchlist_daily_symbol ON watchlist_daily (symbol);
CREATE INDEX IF NOT EXISTS ix_watchlist_daily_mode ON watchlist_daily (mode);

CREATE TABLE IF NOT EXISTS daily_budget (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    mode VARCHAR(16) NOT NULL,
    budget_total DOUBLE PRECISION NOT NULL,
    spent DOUBLE PRECISION NOT NULL DEFAULT 0,
    remaining DOUBLE PRECISION NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_budget_date_mode
ON daily_budget (date, mode);

CREATE INDEX IF NOT EXISTS ix_daily_budget_date ON daily_budget (date);
CREATE INDEX IF NOT EXISTS ix_daily_budget_mode ON daily_budget (mode);

CREATE TABLE IF NOT EXISTS market_snapshot (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    date DATE NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    interval VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT '5m',
    mode VARCHAR(16) NOT NULL DEFAULT 'INTRADAY',
    close DOUBLE PRECISION NOT NULL,
    sma20 DOUBLE PRECISION NOT NULL DEFAULT 0,
    ema20 DOUBLE PRECISION NOT NULL DEFAULT 0,
    sma50 DOUBLE PRECISION,
    ema50 DOUBLE PRECISION,
    rsi14 DOUBLE PRECISION NOT NULL DEFAULT 0,
    atr14 DOUBLE PRECISION NOT NULL DEFAULT 0,
    macd DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    trend VARCHAR(20) NOT NULL,
    indicators_json JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_market_snapshot_run_id ON market_snapshot (run_id);
CREATE INDEX IF NOT EXISTS ix_market_snapshot_date ON market_snapshot (date);
CREATE INDEX IF NOT EXISTS ix_market_snapshot_symbol ON market_snapshot (symbol);
CREATE INDEX IF NOT EXISTS ix_market_snapshot_mode ON market_snapshot (mode);

CREATE TABLE IF NOT EXISTS trade_plan (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    date DATE NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    mode VARCHAR(16) NOT NULL DEFAULT 'INTRADAY',
    plan_type VARCHAR(16) NOT NULL DEFAULT 'MARKET',
    side VARCHAR(12) NOT NULL,
    qty INTEGER NOT NULL,
    price_ref DOUBLE PRECISION NOT NULL,
    stop_loss DOUBLE PRECISION NOT NULL,
    take_profit DOUBLE PRECISION NOT NULL,
    gtt_buy_trigger DOUBLE PRECISION,
    gtt_sell_trigger DOUBLE PRECISION,
    holding_horizon_days INTEGER,
    exit_rules_json JSON NOT NULL DEFAULT '{}'::json,
    confidence DOUBLE PRECISION NOT NULL,
    rationale TEXT NOT NULL,
    source_portal VARCHAR(32) NOT NULL DEFAULT 'yfinance',
    status VARCHAR(30) NOT NULL DEFAULT 'PLANNED',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_trade_plan_run_id ON trade_plan (run_id);
CREATE INDEX IF NOT EXISTS ix_trade_plan_date ON trade_plan (date);
CREATE INDEX IF NOT EXISTS ix_trade_plan_symbol ON trade_plan (symbol);
CREATE INDEX IF NOT EXISTS ix_trade_plan_mode ON trade_plan (mode);
CREATE INDEX IF NOT EXISTS ix_trade_plan_source_portal ON trade_plan (source_portal);

CREATE TABLE IF NOT EXISTS gtt_orders (
    id BIGSERIAL PRIMARY KEY,
    date_created DATE NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    side VARCHAR(10) NOT NULL,
    qty INTEGER NOT NULL,
    trigger_price DOUBLE PRECISION NOT NULL,
    limit_price DOUBLE PRECISION,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    linked_trade_plan_id BIGINT NOT NULL REFERENCES trade_plan(id) ON DELETE CASCADE,
    triggered_at TIMESTAMP,
    executed_price DOUBLE PRECISION,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_gtt_orders_date_created ON gtt_orders (date_created);
CREATE INDEX IF NOT EXISTS ix_gtt_orders_symbol ON gtt_orders (symbol);
CREATE INDEX IF NOT EXISTS ix_gtt_orders_status ON gtt_orders (status);
CREATE INDEX IF NOT EXISTS ix_gtt_orders_linked_trade_plan_id ON gtt_orders (linked_trade_plan_id);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    trade_plan_id BIGINT NOT NULL REFERENCES trade_plan(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    side VARCHAR(10) NOT NULL,
    qty INTEGER NOT NULL,
    mode VARCHAR(16) NOT NULL DEFAULT 'INTRADAY',
    order_type VARCHAR(20) NOT NULL DEFAULT 'MARKET',
    source_portal VARCHAR(32) NOT NULL DEFAULT 'yfinance',
    execution_portal VARCHAR(32) NOT NULL DEFAULT 'paper',
    gtt_id BIGINT REFERENCES gtt_orders(id) ON DELETE SET NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_price DOUBLE PRECISION,
    pnl DOUBLE PRECISION,
    notes TEXT,
    features_json JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_transactions_trade_plan_id ON transactions (trade_plan_id);
CREATE INDEX IF NOT EXISTS ix_transactions_date ON transactions (date);
CREATE INDEX IF NOT EXISTS ix_transactions_symbol ON transactions (symbol);
CREATE INDEX IF NOT EXISTS ix_transactions_mode ON transactions (mode);
CREATE INDEX IF NOT EXISTS ix_transactions_gtt_id ON transactions (gtt_id);
CREATE INDEX IF NOT EXISTS ix_transactions_source_portal ON transactions (source_portal);
CREATE INDEX IF NOT EXISTS ix_transactions_execution_portal ON transactions (execution_portal);
