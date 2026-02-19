from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.integrations.market_data.yfinance_client import YFinanceClient
from src.models.db import get_db_session
from src.models.schemas import (
    RunRequest,
    RunSummaryResponse,
    SwingJournalTodayResponse,
    SwingTrendResponse,
    TopStockAuditItem,
    TopStockAuditModeResponse,
    TopStocksAuditGenerateRequest,
    TopStocksAuditTodayResponse,
    TrendResponse,
    WatchlistRequest,
    WatchlistResponse,
)
from src.models.tables import DailyBudget, GTTOrder, TopStockAudit, TradePlan, Transaction
from src.services.execution_service import ExecutionService
from src.services.gtt_service import GTTService
from src.services.journal_service import JournalService
from src.services.risk_service import RiskService
from src.services.signal_service import SignalService
from src.services.top_stocks_audit_service import TopStocksAuditService
from src.services.trend_service import TrendService
from src.utils.time import today_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["stock-market-ai-assistant"])

trend_service = TrendService()
signal_service = SignalService()
journal_service = JournalService()
risk_service = RiskService(journal_service)
execution_service = ExecutionService(journal=journal_service)
gtt_service = GTTService(journal=journal_service, execution=execution_service)
market_client = YFinanceClient()
top_stocks_audit_service = TopStocksAuditService()


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


@router.get("/swing/trend", response_model=SwingTrendResponse)
def get_swing_trend(
    symbol: str = Query(..., description="Stock symbol, e.g. RELIANCE.NS"),
    interval: str = Query("1d"),
    period: str = Query("6mo"),
):
    try:
        analysis = trend_service.analyze_swing(symbol=symbol.upper(), interval=interval, period=period)
        return SwingTrendResponse(**TrendService.as_dict(analysis))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/watchlist", response_model=WatchlistResponse)
def set_watchlist(payload: WatchlistRequest, db: Session = Depends(get_db_session)):
    run_date = payload.date or today_utc()
    mode = payload.mode.upper()
    symbols = [s.strip().upper() for s in payload.symbols if s.strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="No valid symbols provided")
    if len(symbols) > settings.max_stocks_per_mode:
        raise HTTPException(
            status_code=400,
            detail=f"Max {settings.max_stocks_per_mode} symbols allowed per request",
        )

    horizon = payload.horizon_days
    if mode == "SWING" and horizon is not None and not (5 <= horizon <= 30):
        raise HTTPException(status_code=400, detail="For SWING mode, horizon_days should be between 5 and 30")

    existing_count = journal_service.get_watchlist_count(db, run_date, mode)
    unique_new = len(set(symbols))
    if existing_count + unique_new > settings.max_stocks_per_mode:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Watchlist limit exceeded for {mode}. "
                f"Existing={existing_count}, new={unique_new}, max={settings.max_stocks_per_mode}"
            ),
        )

    inserted = journal_service.add_watchlist(
        db=db,
        run_date=run_date,
        symbols=symbols,
        reason=payload.reason,
        mode=mode,
        horizon_days=horizon,
    )
    return WatchlistResponse(date=run_date, mode=mode, inserted=inserted, symbols=symbols)


def _run_intraday(payload: RunRequest, db: Session, run_id: str, run_date):
    symbols = journal_service.get_watchlist_symbols(db, run_date, mode="INTRADAY")[: settings.max_stocks_per_mode]
    if not symbols:
        return RunSummaryResponse(
            run_id=run_id,
            date=run_date,
            mode="INTRADAY",
            symbols_processed=0,
            signals={"BUY": 0, "SELL": 0, "HOLD": 0},
            trades_executed=0,
            remaining_budget=risk_service.budget_remaining(db, run_date, mode="INTRADAY"),
        )

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
            timeframe=payload.interval,
            mode="INTRADAY",
            latest_candle=analysis.latest_candle,
            indicators=analysis.indicators,
            trend=analysis.trend,
        )

        signal = signal_service.decide_intraday(trend=analysis.trend, rsi14=analysis.indicators["RSI_14"])
        signal_counts[signal["signal"]] += 1

        latest_price = float(analysis.latest_candle["close"])
        budget_remaining = risk_service.budget_remaining(db, run_date, mode="INTRADAY")
        if signal["signal"] == "BUY":
            qty = risk_service.size_buy_qty(latest_price, budget_remaining, mode="INTRADAY")
        elif signal["signal"] == "SELL":
            qty = journal_service.get_open_qty_for_symbol(db, run_date, symbol, mode="INTRADAY")
        else:
            qty = 0

        features = {
            "trend": analysis.trend,
            "indicators": analysis.indicators,
            "latest_candle": analysis.latest_candle,
            "explanation": analysis.explanation,
        }

        if signal["signal"] == "HOLD":
            journal_service.log_no_trade(
                db=db,
                run_id=run_id,
                run_date=run_date,
                symbol=symbol,
                mode="INTRADAY",
                rationale=signal["rationale"],
                price_ref=latest_price,
                features=features,
            )
            continue

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
            mode="INTRADAY",
            plan_type="MARKET",
            status="PLANNED",
        )

        if signal["signal"] == "BUY":
            if qty <= 0:
                journal_service.update_trade_plan_status(db, plan.id, "CANCELLED")
                continue
            if not risk_service.can_open_new_position(db, run_date, mode="INTRADAY"):
                journal_service.update_trade_plan_status(db, plan.id, "CANCELLED")
                continue
            result = execution_service.execute_buy(
                db=db,
                trade_plan_id=plan.id,
                run_date=run_date,
                symbol=symbol,
                qty=qty,
                price=latest_price,
                features=features,
                mode="INTRADAY",
            )
            if result.get("executed"):
                trades_executed += 1

        if signal["signal"] == "SELL":
            result = execution_service.execute_sell(
                db=db,
                trade_plan_id=plan.id,
                run_date=run_date,
                symbol=symbol,
                qty=max(qty, 0),
                price=latest_price,
                features=features,
                mode="INTRADAY",
            )
            if result.get("executed"):
                trades_executed += 1

    return RunSummaryResponse(
        run_id=run_id,
        date=run_date,
        mode="INTRADAY",
        symbols_processed=len(symbols),
        signals=signal_counts,
        trades_executed=trades_executed,
        remaining_budget=risk_service.budget_remaining(db, run_date, mode="INTRADAY"),
    )


def _run_swing(payload: RunRequest, db: Session, run_id: str, run_date):
    interval = "1d" if payload.interval == "5m" else payload.interval
    period = "6mo" if payload.period == "5d" else payload.period

    symbols = journal_service.get_watchlist_symbols(db, run_date, mode="SWING")[: settings.max_stocks_per_mode]
    if not symbols:
        return RunSummaryResponse(
            run_id=run_id,
            date=run_date,
            mode="SWING",
            symbols_processed=0,
            signals={"BUY_SETUP": 0, "EXIT": 0, "HOLD": 0, "NO_TRADE": 0},
            trades_executed=0,
            remaining_budget=risk_service.budget_remaining(db, run_date, mode="SWING"),
        )

    entry_triggers = gtt_service.process_pending_buy_gtts(db, run_date)
    exit_triggers = gtt_service.process_open_positions(db, run_date)

    signal_counts = {"BUY_SETUP": 0, "EXIT": exit_triggers, "HOLD": 0, "NO_TRADE": 0}
    trades_executed = entry_triggers + exit_triggers

    watchlist_rows = journal_service.get_watchlist_rows(db, run_date, mode="SWING")[: settings.max_stocks_per_mode]

    for row in watchlist_rows:
        symbol = row.symbol
        horizon_days = row.horizon_days or 20

        try:
            swing_trend = trend_service.analyze_swing(symbol=symbol, interval=interval, period=period)
            raw = market_client.fetch_ohlcv(symbol=symbol, interval=interval, period=period)
            swing_signal = signal_service.decide_swing(df=raw, entry_style="breakout", horizon_days=horizon_days)
        except Exception as exc:
            logger.exception("Swing analysis failed", extra={"symbol": symbol, "error": str(exc)})
            continue

        journal_service.add_market_snapshot(
            db=db,
            run_id=run_id,
            run_date=run_date,
            symbol=symbol,
            interval=interval,
            timeframe="1d",
            mode="SWING",
            latest_candle=swing_trend.latest_candle,
            indicators=swing_trend.indicators,
            trend=swing_trend.trend,
        )

        signal_counts[swing_signal.action] = signal_counts.get(swing_signal.action, 0) + 1
        price_ref = float(swing_trend.latest_candle["close"])
        features = {
            "trend": swing_trend.trend,
            "readiness_score": swing_trend.readiness_score,
            "indicators": swing_trend.indicators,
            "latest_candle": swing_trend.latest_candle,
            "signal": {
                "action": swing_signal.action,
                "confidence": swing_signal.confidence,
                "rationale": swing_signal.rationale,
                "params": swing_signal.params,
            },
        }

        if swing_signal.action != "BUY_SETUP":
            journal_service.log_no_trade(
                db=db,
                run_id=run_id,
                run_date=run_date,
                symbol=symbol,
                mode="SWING",
                rationale=swing_signal.rationale,
                price_ref=price_ref,
                features=features,
            )
            signal_counts["NO_TRADE"] += 1
            continue

        active_plan = db.execute(
            select(TradePlan).where(
                TradePlan.symbol == symbol,
                TradePlan.mode == "SWING",
                TradePlan.status.in_(["GTT_PLACED", "OPEN"]),
            )
        ).scalar_one_or_none()
        if active_plan:
            signal_counts["NO_TRADE"] += 1
            journal_service.log_no_trade(
                db=db,
                run_id=run_id,
                run_date=run_date,
                symbol=symbol,
                mode="SWING",
                rationale="Active swing plan already exists",
                price_ref=price_ref,
                features=features,
            )
            continue

        if not risk_service.can_open_new_position(db, run_date, mode="SWING"):
            signal_counts["NO_TRADE"] += 1
            journal_service.log_no_trade(
                db=db,
                run_id=run_id,
                run_date=run_date,
                symbol=symbol,
                mode="SWING",
                rationale="Max open swing positions reached",
                price_ref=price_ref,
                features=features,
            )
            continue

        trigger = float(swing_signal.params["gtt_buy_trigger"])
        remaining_budget = risk_service.budget_remaining(db, run_date, mode="SWING")
        qty = risk_service.size_buy_qty(trigger, remaining_budget, mode="SWING")
        if qty <= 0:
            signal_counts["NO_TRADE"] += 1
            journal_service.log_no_trade(
                db=db,
                run_id=run_id,
                run_date=run_date,
                symbol=symbol,
                mode="SWING",
                rationale="Qty became zero under swing allocation",
                price_ref=trigger,
                features=features,
            )
            continue

        plan = journal_service.create_trade_plan(
            db=db,
            run_id=run_id,
            run_date=run_date,
            symbol=symbol,
            side="BUY",
            qty=qty,
            price_ref=trigger,
            confidence=swing_signal.confidence,
            rationale=swing_signal.rationale,
            mode="SWING",
            plan_type="GTT",
            stop_loss=float(swing_signal.params["stop_loss"]),
            take_profit=float(swing_signal.params["take_profit"]),
            gtt_buy_trigger=trigger,
            gtt_sell_trigger=float(swing_signal.params["stop_loss"]),
            holding_horizon_days=horizon_days,
            exit_rules_json={
                "trailing_stop": float(swing_signal.params["stop_loss"]),
                "horizon_days": horizon_days,
                "entry_style": swing_signal.params.get("entry_style"),
            },
            status="GTT_PLACED",
        )
        gtt_service.place_entry_gtt(
            db=db,
            run_date=run_date,
            trade_plan_id=plan.id,
            symbol=symbol,
            qty=qty,
            trigger_price=trigger,
        )

    return RunSummaryResponse(
        run_id=run_id,
        date=run_date,
        mode="SWING",
        symbols_processed=len(symbols),
        signals=signal_counts,
        trades_executed=trades_executed,
        remaining_budget=risk_service.budget_remaining(db, run_date, mode="SWING"),
    )


@router.post("/run", response_model=RunSummaryResponse)
def run_strategy(payload: RunRequest, db: Session = Depends(get_db_session)):
    run_date = payload.date or today_utc()
    run_id = uuid.uuid4().hex
    mode = payload.mode.upper()

    logger.info("Starting run", extra={"run_id": run_id, "date": str(run_date), "mode": mode})

    if mode == "SWING":
        return _run_swing(payload, db, run_id, run_date)
    return _run_intraday(payload, db, run_id, run_date)


def _to_top_stock_mode_response(mode: str, rows: list[TopStockAudit]) -> TopStockAuditModeResponse:
    return TopStockAuditModeResponse(
        mode=mode,
        count=len(rows),
        items=[
            TopStockAuditItem(
                rank=row.rank,
                symbol=row.symbol,
                score=row.score,
                metric=row.metric,
                details=row.details_json or {},
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


@router.post("/audit/top-stocks/generate", response_model=TopStocksAuditTodayResponse)
def generate_top_stocks_audit(payload: TopStocksAuditGenerateRequest, db: Session = Depends(get_db_session)):
    run_date = payload.date or today_utc()
    requested_mode = payload.mode.upper()

    if requested_mode == "BOTH":
        needs_refresh = payload.force_refresh or not top_stocks_audit_service.has_complete_snapshot(
            db, run_date, "INTRADAY"
        ) or not top_stocks_audit_service.has_complete_snapshot(db, run_date, "SWING")
        if needs_refresh:
            refreshed = top_stocks_audit_service.refresh_modes(db, run_date, ["INTRADAY", "SWING"])
            intraday_rows = refreshed["INTRADAY"]
            swing_rows = refreshed["SWING"]
        else:
            intraday_rows = top_stocks_audit_service.get_mode_rows(db, run_date, "INTRADAY")
            swing_rows = top_stocks_audit_service.get_mode_rows(db, run_date, "SWING")
    elif requested_mode == "INTRADAY":
        intraday_rows = top_stocks_audit_service.get_or_build_mode_rows(
            db,
            run_date,
            "INTRADAY",
            force_refresh=payload.force_refresh,
            build_if_missing=True,
        )
        swing_rows = top_stocks_audit_service.get_mode_rows(db, run_date, "SWING")
    else:  # SWING
        intraday_rows = top_stocks_audit_service.get_mode_rows(db, run_date, "INTRADAY")
        swing_rows = top_stocks_audit_service.get_or_build_mode_rows(
            db,
            run_date,
            "SWING",
            force_refresh=payload.force_refresh,
            build_if_missing=True,
        )

    return TopStocksAuditTodayResponse(
        date=run_date,
        intraday=_to_top_stock_mode_response("INTRADAY", intraday_rows),
        swing=_to_top_stock_mode_response("SWING", swing_rows),
    )


@router.get("/audit/top-stocks/today", response_model=TopStocksAuditTodayResponse)
def top_stocks_audit_today(
    refresh_if_missing: bool = Query(True),
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db_session),
):
    run_date = today_utc()
    needs_refresh = force_refresh
    if refresh_if_missing and not needs_refresh:
        needs_refresh = not top_stocks_audit_service.has_complete_snapshot(
            db, run_date, "INTRADAY"
        ) or not top_stocks_audit_service.has_complete_snapshot(db, run_date, "SWING")

    if needs_refresh:
        refreshed = top_stocks_audit_service.refresh_modes(db, run_date, ["INTRADAY", "SWING"])
        intraday_rows = refreshed["INTRADAY"]
        swing_rows = refreshed["SWING"]
    else:
        intraday_rows = top_stocks_audit_service.get_mode_rows(db, run_date, "INTRADAY")
        swing_rows = top_stocks_audit_service.get_mode_rows(db, run_date, "SWING")

    return TopStocksAuditTodayResponse(
        date=run_date,
        intraday=_to_top_stock_mode_response("INTRADAY", intraday_rows),
        swing=_to_top_stock_mode_response("SWING", swing_rows),
    )


@router.get("/journal/swing/today", response_model=SwingJournalTodayResponse)
def swing_journal_today(db: Session = Depends(get_db_session)):
    run_date = today_utc()
    watchlist = journal_service.get_watchlist_symbols(db, run_date, mode="SWING")

    open_plans = journal_service.get_open_swing_plans(db)
    pending = journal_service.get_today_pending_gtt(db, run_date)
    txs = journal_service.get_today_transactions(db, run_date, mode="SWING")

    return SwingJournalTodayResponse(
        date=run_date,
        watchlist=watchlist,
        open_positions=[
            {
                "trade_plan_id": p.id,
                "symbol": p.symbol,
                "qty": p.qty,
                "entry_ref": p.price_ref,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "horizon_days": p.holding_horizon_days,
                "source_portal": p.source_portal,
                "status": p.status,
            }
            for p in open_plans
        ],
        pending_gtt_orders=[
            {
                "gtt_id": g.id,
                "symbol": g.symbol,
                "side": g.side,
                "qty": g.qty,
                "trigger_price": g.trigger_price,
                "status": g.status,
                "linked_trade_plan_id": g.linked_trade_plan_id,
            }
            for g in pending
        ],
        transactions=[
            {
                "id": t.id,
                "trade_plan_id": t.trade_plan_id,
                "symbol": t.symbol,
                "side": t.side,
                "qty": t.qty,
                "order_type": t.order_type,
                "source_portal": t.source_portal,
                "execution_portal": t.execution_portal,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
            }
            for t in txs
        ],
    )


@router.get("/dashboard/today")
def dashboard_today(db: Session = Depends(get_db_session)):
    run_date = today_utc()

    intraday_watchlist = journal_service.get_watchlist_symbols(db, run_date, mode="INTRADAY")
    swing_watchlist = journal_service.get_watchlist_symbols(db, run_date, mode="SWING")

    intraday_budget = journal_service.get_or_create_budget(db, run_date, "INTRADAY")
    swing_budget = journal_service.get_or_create_budget(db, run_date, "SWING")

    plans = db.execute(select(TradePlan).where(TradePlan.date == run_date).order_by(TradePlan.created_at.desc())).scalars().all()
    txs = db.execute(select(Transaction).where(Transaction.date == run_date).order_by(Transaction.created_at.desc())).scalars().all()
    gtts = db.execute(select(GTTOrder).where(GTTOrder.date_created == run_date).order_by(GTTOrder.created_at.desc())).scalars().all()

    intraday_picks = [
        p.symbol
        for p in plans
        if p.mode == "INTRADAY" and p.side in {"BUY", "SELL"} and p.status not in {"CANCELLED"}
    ]
    swing_picks = [
        p.symbol
        for p in plans
        if p.mode == "SWING" and p.side == "BUY" and p.status in {"GTT_PLACED", "OPEN", "CLOSED"}
    ]

    return {
        "date": str(run_date),
        "watchlist": {
            "intraday": intraday_watchlist,
            "swing": swing_watchlist,
        },
        "picked_stocks": {
            "intraday": sorted(list(set(intraday_picks))),
            "swing": sorted(list(set(swing_picks))),
        },
        "budget": {
            "intraday": {
                "total": intraday_budget.budget_total,
                "spent": intraday_budget.spent,
                "remaining": intraday_budget.remaining,
            },
            "swing": {
                "total": swing_budget.budget_total,
                "spent": swing_budget.spent,
                "remaining": swing_budget.remaining,
            },
        },
        "trade_plans": [
            {
                "id": p.id,
                "mode": p.mode,
                "symbol": p.symbol,
                "side": p.side,
                "status": p.status,
                "plan_type": p.plan_type,
                "qty": p.qty,
                "price_ref": p.price_ref,
                "buy_trigger": p.gtt_buy_trigger,
                "sell_trigger": p.gtt_sell_trigger,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "source_portal": p.source_portal,
                "confidence": p.confidence,
                "rationale": p.rationale,
                "justification": p.exit_rules_json,
                "created_at": p.created_at.isoformat(),
            }
            for p in plans
        ],
        "gtt_orders": [
            {
                "id": g.id,
                "symbol": g.symbol,
                "side": g.side,
                "qty": g.qty,
                "trigger_price": g.trigger_price,
                "status": g.status,
                "linked_trade_plan_id": g.linked_trade_plan_id,
                "triggered_at": g.triggered_at.isoformat() if g.triggered_at else None,
                "executed_price": g.executed_price,
            }
            for g in gtts
        ],
        "transactions": [
            {
                "id": t.id,
                "trade_plan_id": t.trade_plan_id,
                "mode": t.mode,
                "symbol": t.symbol,
                "side": t.side,
                "qty": t.qty,
                "order_type": t.order_type,
                "source_portal": t.source_portal,
                "execution_portal": t.execution_portal,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "reason": t.notes,
                "features": t.features_json,
                "created_at": t.created_at.isoformat(),
            }
            for t in txs
        ],
    }
