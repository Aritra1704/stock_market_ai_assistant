from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
from sqlalchemy import select

from src.models.tables import GTTOrder, TradePlan
from src.strategies.swing_v1 import SwingSignal


def test_run_swing_creates_gtt_plan(test_ctx, monkeypatch) -> None:
    client = test_ctx["client"]
    SessionLocal = test_ctx["session_local"]

    from src.api import routes

    monkeypatch.setattr(routes.gtt_service, "process_pending_buy_gtts", lambda db, run_date: 0)
    monkeypatch.setattr(routes.gtt_service, "process_open_positions", lambda db, run_date: 0)

    monkeypatch.setattr(
        routes.trend_service,
        "analyze_swing",
        lambda symbol, interval="1d", period="6mo": SimpleNamespace(
            symbol=symbol,
            interval=interval,
            period=period,
            latest_candle={
                "timestamp": "2025-01-10 00:00:00",
                "open": 100.0,
                "high": 103.0,
                "low": 99.0,
                "close": 102.0,
                "volume": 100000,
            },
            indicators={
                "SMA_20": 98.0,
                "SMA_50": 95.0,
                "EMA_20": 99.0,
                "EMA_50": 96.0,
                "RSI_14": 58.0,
                "ATR_14": 2.0,
                "MACD": 1.2,
                "MACD_SIGNAL": 0.8,
            },
            trend="UPTREND",
            readiness_score=0.82,
            explanation="Mock swing trend",
        ),
    )

    monkeypatch.setattr(
        routes.market_client,
        "fetch_ohlcv",
        lambda symbol, interval="1d", period="6mo": pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=70, freq="D"),
                "open": [100.0] * 70,
                "high": [102.0] * 70,
                "low": [99.0] * 70,
                "close": [101.0] * 70,
                "volume": [100000] * 70,
            }
        ),
    )

    monkeypatch.setattr(
        routes.signal_service,
        "decide_swing",
        lambda df, entry_style="breakout", horizon_days=20: SwingSignal(
            action="BUY_SETUP",
            confidence=0.8,
            rationale="Mock BUY_SETUP",
            params={
                "entry_style": "breakout",
                "gtt_buy_trigger": 101.0,
                "stop_loss": 98.0,
                "take_profit": 105.0,
                "horizon_days": horizon_days,
            },
        ),
    )

    w = client.post(
        "/api/watchlist",
        json={"symbols": ["RELIANCE.NS"], "reason": "test", "mode": "SWING", "horizon_days": 20},
    )
    assert w.status_code == 200

    r = client.post("/api/run", json={"mode": "SWING", "interval": "1d", "period": "6mo"})
    assert r.status_code == 200
    body = r.json()

    assert body["mode"] == "SWING"
    assert body["symbols_processed"] == 1
    assert body["signals"]["BUY_SETUP"] >= 1

    with SessionLocal() as db:
        plan = db.execute(select(TradePlan).where(TradePlan.mode == "SWING")).scalars().first()
        assert plan is not None
        assert plan.plan_type == "GTT"
        assert plan.status == "GTT_PLACED"

        gtt = db.execute(select(GTTOrder).where(GTTOrder.side == "BUY")).scalars().first()
        assert gtt is not None
        assert gtt.status == "PENDING"
