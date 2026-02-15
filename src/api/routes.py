from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.models.db import get_db_session
from src.models.schemas import RunRequest, RunSummaryResponse, TrendResponse, WatchlistRequest, WatchlistResponse
from src.services.execution_service import ExecutionService
from src.services.journal_service import JournalService
from src.services.risk_service import RiskService
from src.services.signal_service import SignalService
from src.services.trend_service import TrendService
from src.utils.time import today_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["stock-market-ai-assistant"])

trend_service = TrendService()
signal_service = SignalService()
journal_service = JournalService()
risk_service = RiskService(journal_service)
execution_service = ExecutionService(journal=journal_service)


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/trend", response_model=TrendResponse)
def get_trend(
    symbol: str = Query(..., description="Stock symbol, e.g. RELIANCE.NS"),
    interval: str = Query("5m"),
    period: str = Query("5d"),
):
    try:
        analysis = trend_service.analyze(symbol=symbol.upper(), interval=interval, period=period)
        return TrendResponse(**TrendService.as_dict(analysis))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/watchlist", response_model=WatchlistResponse)
def set_watchlist(payload: WatchlistRequest, db: Session = Depends(get_db_session)):
    run_date = payload.date or today_utc()
    symbols = [s.strip().upper() for s in payload.symbols if s.strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="No valid symbols provided")
    inserted = journal_service.add_watchlist(db, run_date, symbols, payload.reason)
    return WatchlistResponse(date=run_date, inserted=inserted, symbols=symbols)


@router.post("/run", response_model=RunSummaryResponse)
def run_strategy(payload: RunRequest, db: Session = Depends(get_db_session)):
    run_date = payload.date or today_utc()
    run_id = uuid.uuid4().hex

    symbols = journal_service.get_watchlist_symbols(db, run_date)
    if not symbols:
        return RunSummaryResponse(
            run_id=run_id,
            date=run_date,
            symbols_processed=0,
            signals={"BUY": 0, "SELL": 0, "HOLD": 0},
            trades_executed=0,
            remaining_budget=risk_service.budget_remaining(db, run_date),
        )

    logger.info("Starting run", extra={"run_id": run_id, "date": str(run_date), "symbols": symbols})
    signal_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    trades_executed = 0

    for symbol in symbols:
        try:
            analysis = trend_service.analyze(symbol=symbol, interval=payload.interval, period=payload.period)
        except Exception as exc:
            logger.exception("Trend analysis failed", extra={"symbol": symbol, "error": str(exc)})
            continue

        journal_service.add_market_snapshot(
            db=db,
            run_id=run_id,
            run_date=run_date,
            symbol=symbol,
            interval=payload.interval,
            latest_candle=analysis.latest_candle,
            indicators=analysis.indicators,
            trend=analysis.trend,
        )

        signal = signal_service.decide(trend=analysis.trend, rsi14=analysis.indicators["RSI_14"])
        signal_counts[signal["signal"]] += 1

        latest_price = float(analysis.latest_candle["close"])
        budget_remaining = risk_service.budget_remaining(db, run_date)
        if signal["signal"] == "BUY":
            qty = risk_service.size_buy_qty(latest_price, budget_remaining)
        elif signal["signal"] == "SELL":
            qty = journal_service.get_open_qty_for_symbol(db, run_date, symbol)
        else:
            qty = 0

        features = {
            "trend": analysis.trend,
            "indicators": analysis.indicators,
            "latest_candle": analysis.latest_candle,
            "explanation": analysis.explanation,
        }

        if signal["signal"] in {"BUY", "SELL"}:
            plan = journal_service.create_trade_plan(
                db=db,
                run_id=run_id,
                run_date=run_date,
                symbol=symbol,
                side=signal["signal"],
                qty=max(qty, 0),
                price_ref=latest_price,
                confidence=signal["confidence"],
                rationale=signal["rationale"],
            )

            if signal["signal"] == "BUY":
                if qty <= 0:
                    journal_service.update_trade_plan_status(db, plan.id, "REJECTED_QTY_ZERO")
                    continue
                if not risk_service.can_open_new_position(db, run_date):
                    journal_service.update_trade_plan_status(db, plan.id, "REJECTED_MAX_OPEN_POSITIONS")
                    continue
                result = execution_service.execute_buy(
                    db=db,
                    trade_plan_id=plan.id,
                    run_date=run_date,
                    symbol=symbol,
                    qty=qty,
                    price=latest_price,
                    features=features,
                )
                if result.get("executed"):
                    trades_executed += 1

            if signal["signal"] == "SELL":
                result = execution_service.execute_sell(
                    db=db,
                    trade_plan_id=plan.id,
                    run_date=run_date,
                    symbol=symbol,
                    qty=qty,
                    price=latest_price,
                    features=features,
                )
                if result.get("executed"):
                    trades_executed += 1

    remaining_budget = risk_service.budget_remaining(db, run_date)
    return RunSummaryResponse(
        run_id=run_id,
        date=run_date,
        symbols_processed=len(symbols),
        signals=signal_counts,
        trades_executed=trades_executed,
        remaining_budget=remaining_budget,
    )
