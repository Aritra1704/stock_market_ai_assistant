from __future__ import annotations

import re

from sqlalchemy import event
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings


Base = declarative_base()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _safe_schema_name(schema: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise ValueError(f"Invalid DB_SCHEMA: {schema}")
    return schema


if settings.database_url.startswith("postgresql"):
    _schema = _safe_schema_name(settings.db_schema)

    @event.listens_for(engine, "connect")
    def set_postgres_search_path(dbapi_connection, _connection_record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET search_path TO {_schema}")


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _recreate_watchlist_if_needed(conn, insp) -> None:
    if "watchlist_daily" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("watchlist_daily")}
    if "mode" in cols and "horizon_days" in cols:
        return

    conn.execute(text("ALTER TABLE watchlist_daily RENAME TO watchlist_daily_legacy"))
    conn.execute(
        text(
            """
            CREATE TABLE watchlist_daily (
                id INTEGER PRIMARY KEY,
                date DATE NOT NULL,
                symbol VARCHAR(30) NOT NULL,
                reason VARCHAR(120),
                mode VARCHAR(16) NOT NULL DEFAULT 'INTRADAY',
                horizon_days INTEGER,
                created_at DATETIME NOT NULL
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO watchlist_daily (id, date, symbol, reason, mode, horizon_days, created_at)
            SELECT id, date, symbol, reason, 'INTRADAY', NULL, created_at
            FROM watchlist_daily_legacy
            """
        )
    )
    conn.execute(text("DROP TABLE watchlist_daily_legacy"))
    conn.execute(text("CREATE UNIQUE INDEX uq_watchlist_date_symbol_mode ON watchlist_daily(date, symbol, mode)"))


def _recreate_daily_budget_if_needed(conn, insp) -> None:
    if "daily_budget" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("daily_budget")}
    if "mode" in cols and "id" in cols:
        return

    conn.execute(text("ALTER TABLE daily_budget RENAME TO daily_budget_legacy"))
    conn.execute(
        text(
            """
            CREATE TABLE daily_budget (
                id INTEGER PRIMARY KEY,
                date DATE NOT NULL,
                mode VARCHAR(16) NOT NULL,
                budget_total FLOAT NOT NULL,
                spent FLOAT NOT NULL DEFAULT 0,
                remaining FLOAT NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    )
    if "mode" in cols:
        conn.execute(
            text(
                """
                INSERT INTO daily_budget (date, mode, budget_total, spent, remaining, updated_at)
                SELECT date, COALESCE(mode, 'INTRADAY'), budget_total, spent, remaining, updated_at
                FROM daily_budget_legacy
                """
            )
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO daily_budget (date, mode, budget_total, spent, remaining, updated_at)
                SELECT date, 'INTRADAY', budget_total, spent, remaining, updated_at
                FROM daily_budget_legacy
                """
            )
        )
    conn.execute(text("DROP TABLE daily_budget_legacy"))
    conn.execute(text("CREATE UNIQUE INDEX uq_daily_budget_date_mode ON daily_budget(date, mode)"))


def _ensure_sqlite_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    insp = inspect(engine)
    with engine.begin() as conn:
        _recreate_watchlist_if_needed(conn, insp)
        insp = inspect(engine)
        _recreate_daily_budget_if_needed(conn, insp)
        insp = inspect(engine)

        expected = {
            "market_snapshot": {
                "timeframe": "VARCHAR(10) DEFAULT '5m'",
                "mode": "VARCHAR(16) DEFAULT 'INTRADAY'",
                "sma50": "FLOAT",
                "ema50": "FLOAT",
                "macd": "FLOAT",
                "macd_signal": "FLOAT",
                "indicators_json": "JSON",
            },
            "trade_plan": {
                "mode": "VARCHAR(16) DEFAULT 'INTRADAY'",
                "plan_type": "VARCHAR(16) DEFAULT 'MARKET'",
                "gtt_buy_trigger": "FLOAT",
                "gtt_sell_trigger": "FLOAT",
                "holding_horizon_days": "INTEGER",
                "exit_rules_json": "JSON",
                "source_portal": "VARCHAR(32) DEFAULT 'yfinance'",
            },
            "transactions": {
                "mode": "VARCHAR(16) DEFAULT 'INTRADAY'",
                "order_type": "VARCHAR(20) DEFAULT 'MARKET'",
                "source_portal": "VARCHAR(32) DEFAULT 'yfinance'",
                "execution_portal": "VARCHAR(32) DEFAULT 'paper'",
                "gtt_id": "INTEGER",
                "notes": "TEXT",
            },
        }

        for table_name, cols in expected.items():
            if table_name not in insp.get_table_names():
                continue
            existing = {col["name"] for col in insp.get_columns(table_name)}
            for col_name, col_type in cols.items():
                if col_name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))


def init_db() -> None:
    from src.models import tables  # noqa: F401

    if settings.database_url.startswith("postgresql"):
        schema = _safe_schema_name(settings.db_schema)
        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            conn.execute(text(f"SET search_path TO {schema}"))

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
