from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.db import get_db_session
from src.models.schemas import (
    AuditDecisionItem,
    AuditPositionItem,
    AuditTodayResponse,
    AuditTransactionItem,
    ExitDayRequest,
    ExitDayResponse,
    PlanDayRequest,
    PlanDayResponse,
    PlanDaySelectionItem,
    RunTickRequest,
    RunTickResponse,
    SectorScheduleUpsertRequest,
    SectorUniverseUpdateRequest,
    StrategyConfigCreateRequest,
    StrategyConfigResponse,
)
from src.services.journal_service import TradingJournalService
from src.services.market_data_service import MarketDataService
from src.services.portfolio_service import IntradayPaperPortfolioService
from src.services.ranking_service import RankingService
from src.services.rebalance_service import RebalanceService
from src.services.sector_service import SectorService
from src.services.signal_service import MomentumSignalService

IST = ZoneInfo("Asia/Kolkata")

router = APIRouter(prefix="/api", tags=["trading-mvp1"])

sector_service = SectorService()
market_data_service = MarketDataService()
ranking_service = RankingService(market_data_service=market_data_service)
momentum_signal_service = MomentumSignalService()
portfolio_service = IntradayPaperPortfolioService()
trading_journal = TradingJournalService()
rebalance_service = RebalanceService(
    portfolio_service=portfolio_service,
    journal_service=trading_journal,
    signal_service=momentum_signal_service,
)


def _now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def _is_weekend(run_date: dt.date) -> bool:
    return run_date.weekday() >= 5


def _next_weekday(run_date: dt.date) -> dt.date:
    out = run_date
    while _is_weekend(out):
        out += dt.timedelta(days=1)
    return out


def _to_config_response(config) -> StrategyConfigResponse:
    return StrategyConfigResponse(
        id=config.id,
        active=bool(config.active),
        mode=config.mode,
        strategy_version=config.strategy_version,
        sector=config.sector,
        budget_daily_inr=float(config.budget_daily_inr),
        max_positions=int(config.max_positions),
        monitor_interval_min=int(config.monitor_interval_min),
        warmup_minutes=int(config.warmup_minutes),
        max_entries_per_symbol_per_day=int(config.max_entries_per_symbol_per_day),
        target_pct=float(config.target_pct),
        stop_pct=float(config.stop_pct),
        time_exit_hhmm=config.time_exit_hhmm,
        rebalance_partial_threshold=float(config.rebalance_partial_threshold),
        rebalance_full_threshold=float(config.rebalance_full_threshold),
        rebalance_partial_fraction=float(config.rebalance_partial_fraction),
        fill_model=config.fill_model,
        created_at=config.created_at,
    )


def _effective_config(config) -> SimpleNamespace:
    return SimpleNamespace(
        mode="INTRADAY",
        strategy_version=config.strategy_version,
        sector=config.sector,
        budget_daily_inr=float(config.budget_daily_inr),
        max_positions=min(2, max(1, int(config.max_positions))),
        monitor_interval_min=max(1, int(config.monitor_interval_min)),
        warmup_minutes=max(0, int(config.warmup_minutes)),
        max_entries_per_symbol_per_day=max(1, int(config.max_entries_per_symbol_per_day)),
        target_pct=float(config.target_pct),
        stop_pct=float(config.stop_pct),
        time_exit_hhmm=config.time_exit_hhmm,
        rebalance_partial_threshold=float(config.rebalance_partial_threshold),
        rebalance_full_threshold=float(config.rebalance_full_threshold),
        rebalance_partial_fraction=float(config.rebalance_partial_fraction),
        fill_model=config.fill_model,
    )


def _selection_items_to_schema(rows) -> list[PlanDaySelectionItem]:
    return [
        PlanDaySelectionItem(
            symbol=row.symbol,
            rank=int(row.rank),
            score=float(row.score),
            reasons_json=row.reasons_json or {},
            features_json=row.features_json or {},
            summary_text=row.summary_text or "",
        )
        for row in rows
    ]


def _today_selection_payload(db: Session, run_date: dt.date) -> dict:
    plan = trading_journal.get_day_plan(db, run_date)
    if plan is None:
        return {
            "date": run_date,
            "sector_name": None,
            "day_plan_id": None,
            "day_selection_id": None,
            "top5": [],
        }

    selection = trading_journal.get_latest_day_selection(db=db, day_plan_id=plan.id)
    if selection is None:
        return {
            "date": run_date,
            "sector_name": plan.sector_name,
            "day_plan_id": plan.id,
            "day_selection_id": None,
            "top5": [],
        }

    items = trading_journal.get_selection_items(db=db, day_selection_id=selection.id)
    return {
        "date": run_date,
        "sector_name": plan.sector_name,
        "day_plan_id": plan.id,
        "day_selection_id": selection.id,
        "top5": _selection_items_to_schema(items[:5]),
    }


def _plan_day_internal(
    db: Session,
    run_date: dt.date,
    force_replan: bool = False,
    notes: str | None = None,
):
    config = trading_journal.get_active_config(db)
    cfg = _effective_config(config)

    sector_name = sector_service.get_sector_for_date(db, run_date, configured_sector=cfg.sector)
    if not sector_name:
        raise HTTPException(status_code=400, detail="No active sector configured for this weekday")

    universe = sector_service.get_active_universe_symbols(db, sector_name)
    if not universe:
        raise HTTPException(status_code=400, detail=f"No active symbols configured for sector {sector_name}")

    plan = trading_journal.upsert_day_plan(
        db=db,
        run_date=run_date,
        sector_name=sector_name,
        notes=notes,
        force_replan=force_replan,
    )
    trading_journal.save_universe_snapshot(db=db, day_plan_id=plan.id, symbols=universe)

    ranked = ranking_service.rank_symbols(
        symbols=universe,
        top_n=5,
        interval=f"{cfg.monitor_interval_min}m",
        period="5d",
    )
    if not ranked:
        raise HTTPException(status_code=400, detail="Unable to rank symbols from configured universe")

    selection = trading_journal.create_day_selection(
        db=db,
        day_plan_id=plan.id,
        ranking_version=cfg.strategy_version,
        ranked_items=ranked,
    )
    items = trading_journal.get_selection_items(db=db, day_selection_id=selection.id)
    return cfg, plan, selection, items


@router.get("/config/active", response_model=StrategyConfigResponse)
def get_active_config(db: Session = Depends(get_db_session)):
    config = trading_journal.get_active_config(db)
    return _to_config_response(config)


@router.post("/config", response_model=StrategyConfigResponse)
def create_config(payload: StrategyConfigCreateRequest, db: Session = Depends(get_db_session)):
    data = payload.model_dump()
    data["mode"] = "INTRADAY"
    parsed_time = momentum_signal_service._parse_time_exit(data.get("time_exit_hhmm", "15:20"))
    data["time_exit_hhmm"] = parsed_time.strftime("%H:%M")

    row = trading_journal.create_strategy_config(db=db, payload=data)
    return _to_config_response(row)


@router.post("/sector/schedule")
def upsert_sector_schedule(payload: SectorScheduleUpsertRequest, db: Session = Depends(get_db_session)):
    rows = sector_service.upsert_schedule(db=db, mappings=[item.model_dump() for item in payload.mappings])
    return {
        "mappings": [
            {
                "id": row.id,
                "weekday": row.weekday,
                "sector_name": row.sector_name,
                "active": row.active,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.post("/sector/universe")
def update_sector_universe(payload: SectorUniverseUpdateRequest, db: Session = Depends(get_db_session)):
    rows = sector_service.update_universe(
        db=db,
        sector_name=payload.sector_name,
        add_symbols=payload.add_symbols,
        remove_symbols=payload.remove_symbols,
    )
    return {
        "sector_name": payload.sector_name.strip().upper(),
        "active_symbols": [row.symbol for row in rows],
        "count": len(rows),
    }


@router.post("/plan/day", response_model=PlanDayResponse)
def plan_day(payload: PlanDayRequest, db: Session = Depends(get_db_session)):
    requested = payload.date or _now_ist().date()
    run_date = _next_weekday(requested)

    _, plan, selection, items = _plan_day_internal(
        db=db,
        run_date=run_date,
        force_replan=payload.force_replan,
        notes=payload.notes,
    )
    return PlanDayResponse(
        date=run_date,
        sector_name=plan.sector_name,
        day_plan_id=plan.id,
        day_selection_id=selection.id,
        top5=_selection_items_to_schema(items[:5]),
    )


@router.get("/selection/today")
def selection_today(db: Session = Depends(get_db_session)):
    run_date = _now_ist().date()
    return _today_selection_payload(db=db, run_date=run_date)


@router.post("/run/tick", response_model=RunTickResponse)
def run_tick(payload: RunTickRequest, db: Session = Depends(get_db_session)):
    run_date = payload.date or _now_ist().date()
    if _is_weekend(run_date):
        return RunTickResponse(
            date=run_date,
            day_plan_id=0,
            run_tick_id=0,
            interval="0m",
            symbols_checked=0,
            buys=0,
            sells=0,
            holds=0,
            rebalances=0,
            skipped_weekend=True,
        )

    config = _effective_config(trading_journal.get_active_config(db))
    interval_min = payload.interval_min or config.monitor_interval_min
    interval = f"{interval_min}m"

    plan = trading_journal.get_day_plan(db, run_date)
    if plan is None:
        _, plan, selection, items = _plan_day_internal(db=db, run_date=run_date, force_replan=False, notes=None)
    else:
        selection = trading_journal.get_latest_day_selection(db=db, day_plan_id=plan.id)
        if selection is None:
            _, _, selection, items = _plan_day_internal(db=db, run_date=run_date, force_replan=False, notes=None)
        else:
            items = trading_journal.get_selection_items(db=db, day_selection_id=selection.id)

    symbols = [row.symbol for row in items[:5]]
    if not symbols:
        raise HTTPException(status_code=400, detail="No top-5 symbols available for the day")

    portfolio_service.get_or_create_day_budget(db, run_date=run_date, budget_total=config.budget_daily_inr)
    run_tick_row = trading_journal.create_run_tick(db=db, day_plan_id=plan.id, interval=interval)

    snapshots_by_symbol: dict[str, object] = {}
    for symbol in symbols:
        try:
            snapshot = market_data_service.analyze_symbol(symbol=symbol, interval=interval, period="5d")
        except Exception:
            continue
        snapshots_by_symbol[symbol] = snapshot
        trading_journal.add_market_snapshot_for_tick(
            db=db,
            run_date=run_date,
            run_tick_id=run_tick_row.id,
            interval=interval,
            snapshot=snapshot,
        )

    now_ist = _now_ist()
    buys = 0
    sells = 0
    holds = 0

    open_positions = portfolio_service.get_open_positions(db, run_date)
    for position in open_positions:
        snapshot = snapshots_by_symbol.get(position.symbol)
        if snapshot is None:
            try:
                snapshot = market_data_service.analyze_symbol(symbol=position.symbol, interval=interval, period="5d")
            except Exception:
                continue
            snapshots_by_symbol[position.symbol] = snapshot
            trading_journal.add_market_snapshot_for_tick(
                db=db,
                run_date=run_date,
                run_tick_id=run_tick_row.id,
                interval=interval,
                snapshot=snapshot,
            )

        should_exit, reasons = momentum_signal_service.should_sell(
            last_price=float(snapshot.close),
            stop_price=float(position.stop_price),
            target_price=float(position.target_price),
            now_ist=now_ist,
            time_exit_hhmm=config.time_exit_hhmm,
        )
        if should_exit:
            decision = trading_journal.add_trade_decision(
                db=db,
                run_tick_id=run_tick_row.id,
                symbol=position.symbol,
                action="SELL",
                intended_qty=float(position.qty),
                intended_price=float(snapshot.close),
                stop_price=float(position.stop_price),
                target_price=float(position.target_price),
                reasons_json={"rules_triggered": reasons, "rule_set": "momentum_v1"},
                features_json=snapshot.features_json,
                summary_text=f"SELL {position.symbol} due to {', '.join(reasons)}.",
            )
            portfolio_service.close_position(
                db=db,
                position=position,
                qty=float(position.qty),
                price=float(snapshot.close),
                decision_id=decision.id,
                exit_reason=",".join(reasons),
            )
            sells += 1
        else:
            hold_decision = momentum_signal_service.hold_decision(position.symbol, snapshot, "position_open_no_exit")
            trading_journal.add_trade_decision(
                db=db,
                run_tick_id=run_tick_row.id,
                symbol=position.symbol,
                action="HOLD",
                intended_qty=0.0,
                intended_price=float(snapshot.close),
                stop_price=float(position.stop_price),
                target_price=float(position.target_price),
                reasons_json=hold_decision.reasons_json,
                features_json=hold_decision.features_json,
                summary_text=hold_decision.summary_text,
            )
            holds += 1

    after_time_exit = now_ist.time() >= momentum_signal_service._parse_time_exit(config.time_exit_hhmm)
    open_symbols = {row.symbol for row in portfolio_service.get_open_positions(db, run_date)}

    for symbol in symbols:
        snapshot = snapshots_by_symbol.get(symbol)
        if snapshot is None:
            trading_journal.add_trade_decision(
                db=db,
                run_tick_id=run_tick_row.id,
                symbol=symbol,
                action="HOLD",
                intended_qty=0.0,
                intended_price=0.0,
                stop_price=None,
                target_price=None,
                reasons_json={"rules_triggered": ["market_data_unavailable"], "rule_set": "momentum_v1"},
                features_json={},
                summary_text=f"HOLD {symbol}: market data unavailable.",
            )
            holds += 1
            continue

        if symbol in open_symbols:
            continue

        if after_time_exit:
            hold_decision = momentum_signal_service.hold_decision(symbol, snapshot, "after_time_exit")
            trading_journal.add_trade_decision(
                db=db,
                run_tick_id=run_tick_row.id,
                symbol=symbol,
                action="HOLD",
                intended_qty=0.0,
                intended_price=float(snapshot.close),
                stop_price=None,
                target_price=None,
                reasons_json=hold_decision.reasons_json,
                features_json=hold_decision.features_json,
                summary_text=hold_decision.summary_text,
            )
            holds += 1
            continue

        if portfolio_service.entries_for_symbol(db, run_date, symbol) >= config.max_entries_per_symbol_per_day:
            hold_decision = momentum_signal_service.hold_decision(symbol, snapshot, "max_entries_reached")
            trading_journal.add_trade_decision(
                db=db,
                run_tick_id=run_tick_row.id,
                symbol=symbol,
                action="HOLD",
                intended_qty=0.0,
                intended_price=float(snapshot.close),
                stop_price=None,
                target_price=None,
                reasons_json=hold_decision.reasons_json,
                features_json=hold_decision.features_json,
                summary_text=hold_decision.summary_text,
            )
            holds += 1
            continue

        if portfolio_service.count_open_positions(db, run_date) >= config.max_positions:
            hold_decision = momentum_signal_service.hold_decision(symbol, snapshot, "max_positions_reached")
            trading_journal.add_trade_decision(
                db=db,
                run_tick_id=run_tick_row.id,
                symbol=symbol,
                action="HOLD",
                intended_qty=0.0,
                intended_price=float(snapshot.close),
                stop_price=None,
                target_price=None,
                reasons_json=hold_decision.reasons_json,
                features_json=hold_decision.features_json,
                summary_text=hold_decision.summary_text,
            )
            holds += 1
            continue

        if not momentum_signal_service.should_buy(snapshot):
            hold_decision = momentum_signal_service.hold_decision(symbol, snapshot, "buy_rules_not_met")
            trading_journal.add_trade_decision(
                db=db,
                run_tick_id=run_tick_row.id,
                symbol=symbol,
                action="HOLD",
                intended_qty=0.0,
                intended_price=float(snapshot.close),
                stop_price=None,
                target_price=None,
                reasons_json=hold_decision.reasons_json,
                features_json=hold_decision.features_json,
                summary_text=hold_decision.summary_text,
            )
            holds += 1
            continue

        allocation = portfolio_service.allocation_for_new_position(
            db=db,
            run_date=run_date,
            budget_total=config.budget_daily_inr,
            max_positions=config.max_positions,
        )
        qty = portfolio_service.qty_from_cash(price=float(snapshot.close), cash=float(allocation))
        if qty <= 0:
            hold_decision = momentum_signal_service.hold_decision(symbol, snapshot, "insufficient_budget")
            trading_journal.add_trade_decision(
                db=db,
                run_tick_id=run_tick_row.id,
                symbol=symbol,
                action="HOLD",
                intended_qty=0.0,
                intended_price=float(snapshot.close),
                stop_price=None,
                target_price=None,
                reasons_json=hold_decision.reasons_json,
                features_json=hold_decision.features_json,
                summary_text=hold_decision.summary_text,
            )
            holds += 1
            continue

        entry_decision = momentum_signal_service.entry_decision(
            symbol=symbol,
            snapshot=snapshot,
            stop_pct=config.stop_pct,
            target_pct=config.target_pct,
        )
        decision = trading_journal.add_trade_decision(
            db=db,
            run_tick_id=run_tick_row.id,
            symbol=symbol,
            action="BUY",
            intended_qty=float(qty),
            intended_price=float(snapshot.close),
            stop_price=entry_decision.stop_price,
            target_price=entry_decision.target_price,
            reasons_json=entry_decision.reasons_json,
            features_json=entry_decision.features_json,
            summary_text=entry_decision.summary_text,
        )
        portfolio_service.open_position(
            db=db,
            run_date=run_date,
            symbol=symbol,
            qty=float(qty),
            price=float(snapshot.close),
            stop_price=float(entry_decision.stop_price or 0.0),
            target_price=float(entry_decision.target_price or 0.0),
            decision_id=decision.id,
            timestamp=snapshot.candle_time,
        )
        buys += 1

    ranked_for_rebalance = []
    for symbol in symbols:
        snapshot = snapshots_by_symbol.get(symbol)
        if snapshot is None:
            continue
        ranked_for_rebalance.append(
            SimpleNamespace(
                symbol=symbol,
                score=float(snapshot.score),
                features_json=snapshot.features_json,
                snapshot=snapshot,
            )
        )
    ranked_for_rebalance.sort(key=lambda item: item.score, reverse=True)

    rebalances = 0
    if not after_time_exit and ranked_for_rebalance:
        rebalance_actions = rebalance_service.apply(
            db=db,
            run_date=run_date,
            run_tick_id=run_tick_row.id,
            ranked_items=ranked_for_rebalance,
            snapshots_by_symbol=snapshots_by_symbol,
            config=config,
        )
        if rebalance_actions:
            rebalances = 1
            if rebalance_actions >= 1:
                sells += 1
            if rebalance_actions >= 2:
                buys += 1

    return RunTickResponse(
        date=run_date,
        day_plan_id=plan.id,
        run_tick_id=run_tick_row.id,
        interval=interval,
        symbols_checked=len(symbols),
        buys=buys,
        sells=sells,
        holds=holds,
        rebalances=rebalances,
        skipped_weekend=False,
    )


@router.post("/exit/day", response_model=ExitDayResponse)
def exit_day(payload: ExitDayRequest, db: Session = Depends(get_db_session)):
    run_date = payload.date or _now_ist().date()
    if _is_weekend(run_date):
        return ExitDayResponse(date=run_date, closed_positions=0, skipped_weekend=True)

    cfg = _effective_config(trading_journal.get_active_config(db))
    plan = trading_journal.get_day_plan(db, run_date)
    if plan is None:
        sector_name = sector_service.get_sector_for_date(db, run_date, configured_sector=cfg.sector) or "UNASSIGNED"
        plan = trading_journal.upsert_day_plan(db, run_date, sector_name=sector_name, notes="auto exit day", force_replan=False)

    run_tick_row = trading_journal.create_run_tick(db=db, day_plan_id=plan.id, interval="force_exit")

    closed = 0
    open_positions = portfolio_service.get_open_positions(db, run_date)
    for position in open_positions:
        try:
            snapshot = market_data_service.analyze_symbol(
                symbol=position.symbol,
                interval=f"{cfg.monitor_interval_min}m",
                period="5d",
            )
            price = float(snapshot.close)
            features = snapshot.features_json
        except Exception:
            price = float(position.entry_price)
            features = {
                "fallback_price": price,
                "reason": "market_data_unavailable",
            }

        decision = trading_journal.add_trade_decision(
            db=db,
            run_tick_id=run_tick_row.id,
            symbol=position.symbol,
            action="SELL",
            intended_qty=float(position.qty),
            intended_price=price,
            stop_price=float(position.stop_price),
            target_price=float(position.target_price),
            reasons_json={"rules_triggered": ["force_exit_day"], "rule_set": "momentum_v1"},
            features_json=features,
            summary_text=f"Force exit {position.symbol} at {price:.2f}.",
        )
        portfolio_service.close_position(
            db=db,
            position=position,
            qty=float(position.qty),
            price=price,
            decision_id=decision.id,
            exit_reason="force_exit_day",
        )
        closed += 1

    return ExitDayResponse(date=run_date, closed_positions=closed, skipped_weekend=False)


@router.get("/positions/today")
def positions_today(db: Session = Depends(get_db_session)):
    run_date = _now_ist().date()
    rows = trading_journal.get_positions(db, run_date)
    return {
        "date": run_date,
        "count": len(rows),
        "positions": [
            {
                "id": row.id,
                "symbol": row.symbol,
                "status": row.status,
                "qty": float(row.qty),
                "entry_price": float(row.entry_price),
                "stop_price": float(row.stop_price),
                "target_price": float(row.target_price),
                "entry_time": row.entry_time,
                "exit_time": row.exit_time,
                "exit_price": float(row.exit_price) if row.exit_price is not None else None,
                "exit_reason": row.exit_reason,
                "pnl": float(row.pnl) if row.pnl is not None else None,
            }
            for row in rows
        ],
    }


@router.get("/transactions/today")
def transactions_today(db: Session = Depends(get_db_session)):
    run_date = _now_ist().date()
    rows = trading_journal.get_transactions(db, run_date)
    return {
        "date": run_date,
        "count": len(rows),
        "transactions": [
            {
                "id": row.id,
                "position_id": row.position_id,
                "decision_id": row.decision_id,
                "side": row.side,
                "qty": float(row.qty),
                "price": float(row.price),
                "timestamp": row.timestamp,
                "mode": row.mode,
            }
            for row in rows
        ],
    }


@router.get("/audit/today", response_model=AuditTodayResponse)
def audit_today(db: Session = Depends(get_db_session)):
    run_date = _now_ist().date()
    config = _effective_config(trading_journal.get_active_config(db))

    selection_payload = _today_selection_payload(db=db, run_date=run_date)
    sector_name = selection_payload["sector_name"] or config.sector

    decisions = []
    day_plan_id = selection_payload.get("day_plan_id")
    if day_plan_id is not None:
        decisions = trading_journal.get_decisions(db, day_plan_id=day_plan_id)

    budget = portfolio_service.get_or_create_day_budget(db, run_date=run_date, budget_total=config.budget_daily_inr)
    positions = trading_journal.get_positions(db, run_date)
    transactions = trading_journal.get_transactions(db, run_date)
    tick_ids = sorted({row.run_tick_id for row in decisions if row.run_tick_id is not None})
    tick_map: dict[int, dt.datetime] = {}
    if tick_ids:
        from src.models.tables import RunTick

        tick_rows = db.execute(select(RunTick.id, RunTick.tick_time).where(RunTick.id.in_(tick_ids))).all()
        tick_map = {int(row[0]): row[1] for row in tick_rows}

    return AuditTodayResponse(
        date=run_date,
        sector_name=sector_name,
        top5=selection_payload["top5"],
        budget={
            "budget_total": float(budget.budget_total),
            "used": float(budget.used),
            "remaining": float(budget.remaining),
            "updated_at": budget.updated_at.isoformat() if budget.updated_at else None,
        },
        positions=[
            AuditPositionItem(
                id=row.id,
                symbol=row.symbol,
                status=row.status,
                qty=float(row.qty),
                entry_price=float(row.entry_price),
                stop_price=float(row.stop_price),
                target_price=float(row.target_price),
                entry_time=row.entry_time,
                exit_time=row.exit_time,
                exit_price=float(row.exit_price) if row.exit_price is not None else None,
                exit_reason=row.exit_reason,
                pnl=float(row.pnl) if row.pnl is not None else None,
            )
            for row in positions
        ],
        transactions=[
            AuditTransactionItem(
                id=row.id,
                position_id=row.position_id,
                decision_id=row.decision_id,
                side=row.side,
                qty=float(row.qty),
                price=float(row.price),
                timestamp=row.timestamp,
                mode=row.mode,
            )
            for row in transactions
        ],
        decisions=[
            AuditDecisionItem(
                id=row.id,
                symbol=row.symbol,
                action=row.action,
                intended_qty=float(row.intended_qty),
                intended_price=float(row.intended_price),
                stop_price=float(row.stop_price) if row.stop_price is not None else None,
                target_price=float(row.target_price) if row.target_price is not None else None,
                run_tick_id=row.run_tick_id,
                tick_time=tick_map.get(int(row.run_tick_id)) if row.run_tick_id is not None else None,
                reasons_json=row.reasons_json or {},
                features_json=row.features_json or {},
                summary_text=row.summary_text,
                created_at=row.created_at,
            )
            for row in decisions
        ],
    )
