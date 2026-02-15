from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.tables import DailyBudget, MarketSnapshot, TradePlan, Transaction, WatchlistDaily
from src.utils.time import utc_now

logger = logging.getLogger(__name__)


class JournalService:
    def add_watchlist(self, db: Session, run_date: date, symbols: list[str], reason: str) -> int:
        inserted = 0
        for symbol in symbols:
            clean = symbol.strip().upper()
            exists = db.execute(
                select(WatchlistDaily).where(WatchlistDaily.date == run_date, WatchlistDaily.symbol == clean)
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(WatchlistDaily(date=run_date, symbol=clean, reason=reason))
            inserted += 1
        db.commit()
        return inserted

    def get_watchlist_symbols(self, db: Session, run_date: date) -> list[str]:
        rows = db.execute(select(WatchlistDaily.symbol).where(WatchlistDaily.date == run_date)).all()
        return [row[0] for row in rows]

    def get_or_create_budget(self, db: Session, run_date: date) -> DailyBudget:
        budget = db.get(DailyBudget, run_date)
        if budget:
            return budget
        budget = DailyBudget(
            date=run_date,
            budget_total=settings.daily_budget_inr,
            spent=0.0,
            remaining=settings.daily_budget_inr,
            updated_at=utc_now().replace(tzinfo=None),
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)
        return budget

    def update_budget_spent(self, db: Session, run_date: date, amount: float) -> DailyBudget:
        budget = self.get_or_create_budget(db, run_date)
        budget.spent = round(budget.spent + amount, 2)
        budget.remaining = round(max(0.0, budget.budget_total - budget.spent), 2)
        budget.updated_at = utc_now().replace(tzinfo=None)
        db.add(budget)
        db.commit()
        db.refresh(budget)
        return budget

    def add_market_snapshot(
        self,
        db: Session,
        run_id: str,
        run_date: date,
        symbol: str,
        interval: str,
        latest_candle: dict,
        indicators: dict,
        trend: str,
    ) -> None:
        ts_raw = latest_candle.get("timestamp")
        if isinstance(ts_raw, datetime):
            snapshot_ts = ts_raw.replace(tzinfo=None)
        else:
            try:
                snapshot_ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                snapshot_ts = utc_now().replace(tzinfo=None)

        db.add(
            MarketSnapshot(
                run_id=run_id,
                date=run_date,
                symbol=symbol,
                timestamp=snapshot_ts,
                interval=interval,
                close=latest_candle["close"],
                sma20=indicators["SMA_20"],
                ema20=indicators["EMA_20"],
                rsi14=indicators["RSI_14"],
                atr14=indicators["ATR_14"],
                trend=trend,
            )
        )
        db.commit()

    def create_trade_plan(
        self,
        db: Session,
        run_id: str,
        run_date: date,
        symbol: str,
        side: str,
        qty: int,
        price_ref: float,
        confidence: float,
        rationale: str,
        status: str = "PLANNED",
    ) -> TradePlan:
        plan = TradePlan(
            run_id=run_id,
            date=run_date,
            symbol=symbol,
            side=side,
            qty=qty,
            price_ref=price_ref,
            stop_loss=round(price_ref * 0.99, 4),
            take_profit=round(price_ref * 1.01, 4),
            confidence=confidence,
            rationale=rationale,
            status=status,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    def update_trade_plan_status(self, db: Session, trade_plan_id: int, status: str) -> None:
        plan = db.get(TradePlan, trade_plan_id)
        if not plan:
            return
        plan.status = status
        db.add(plan)
        db.commit()

    def add_transaction(
        self,
        db: Session,
        trade_plan_id: int,
        run_date: date,
        symbol: str,
        side: str,
        qty: int,
        entry_price: float,
        features_json: dict,
        exit_price: float | None = None,
        pnl: float | None = None,
        mode: str = "paper",
    ) -> Transaction:
        tx = Transaction(
            trade_plan_id=trade_plan_id,
            date=run_date,
            symbol=symbol,
            side=side,
            qty=qty,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            mode=mode,
            features_json=features_json,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

    def get_open_position_count(self, db: Session, run_date: date) -> int:
        buys = db.execute(
            select(Transaction.qty).where(Transaction.date == run_date, Transaction.side == "BUY")
        ).all()
        sells = db.execute(
            select(Transaction.qty).where(Transaction.date == run_date, Transaction.side == "SELL")
        ).all()
        net_qty = sum(row[0] for row in buys) - sum(row[0] for row in sells)
        return 1 if net_qty > 0 else 0

    def get_open_qty_for_symbol(self, db: Session, run_date: date, symbol: str) -> int:
        buys = db.execute(
            select(Transaction.qty).where(
                Transaction.date == run_date,
                Transaction.symbol == symbol,
                Transaction.side == "BUY",
            )
        ).all()
        sells = db.execute(
            select(Transaction.qty).where(
                Transaction.date == run_date,
                Transaction.symbol == symbol,
                Transaction.side == "SELL",
            )
        ).all()
        return max(0, sum(row[0] for row in buys) - sum(row[0] for row in sells))

    def get_latest_open_buy(self, db: Session, run_date: date, symbol: str) -> Transaction | None:
        if self.get_open_qty_for_symbol(db, run_date, symbol) <= 0:
            return None
        buys = db.execute(
            select(Transaction)
            .where(Transaction.date == run_date, Transaction.symbol == symbol, Transaction.side == "BUY")
            .order_by(Transaction.id.desc())
        ).scalars().first()
        return buys
