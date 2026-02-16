from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.tables import DailyBudget, GTTOrder, MarketSnapshot, TradePlan, Transaction, WatchlistDaily
from src.utils.time import utc_now

logger = logging.getLogger(__name__)


class JournalService:
    @staticmethod
    def _normalize_mode(mode: str) -> str:
        return mode.strip().upper()

    def add_watchlist(
        self,
        db: Session,
        run_date: date,
        symbols: list[str],
        reason: str,
        mode: str = "INTRADAY",
        horizon_days: int | None = None,
    ) -> int:
        mode = self._normalize_mode(mode)
        inserted = 0
        for symbol in symbols:
            clean = symbol.strip().upper()
            exists = db.execute(
                select(WatchlistDaily).where(
                    WatchlistDaily.date == run_date,
                    WatchlistDaily.symbol == clean,
                    WatchlistDaily.mode == mode,
                )
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(
                WatchlistDaily(
                    date=run_date,
                    symbol=clean,
                    reason=reason,
                    mode=mode,
                    horizon_days=horizon_days,
                )
            )
            inserted += 1
        db.commit()
        return inserted

    def get_watchlist_rows(self, db: Session, run_date: date, mode: str) -> list[WatchlistDaily]:
        mode = self._normalize_mode(mode)
        return db.execute(
            select(WatchlistDaily).where(WatchlistDaily.date == run_date, WatchlistDaily.mode == mode)
        ).scalars().all()

    def get_watchlist_symbols(self, db: Session, run_date: date, mode: str) -> list[str]:
        return [row.symbol for row in self.get_watchlist_rows(db, run_date, mode)]

    def _default_budget_total(self, mode: str) -> float:
        mode = self._normalize_mode(mode)
        if mode == "SWING":
            return settings.swing_allocation_inr
        return settings.intraday_daily_budget_inr

    def get_or_create_budget(self, db: Session, run_date: date, mode: str) -> DailyBudget:
        mode = self._normalize_mode(mode)
        budget = db.execute(
            select(DailyBudget).where(DailyBudget.date == run_date, DailyBudget.mode == mode)
        ).scalar_one_or_none()
        if budget:
            return budget
        total = self._default_budget_total(mode)
        budget = DailyBudget(
            date=run_date,
            mode=mode,
            budget_total=total,
            spent=0.0,
            remaining=total,
            updated_at=utc_now().replace(tzinfo=None),
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)
        return budget

    def update_budget_spent(self, db: Session, run_date: date, mode: str, amount: float) -> DailyBudget:
        budget = self.get_or_create_budget(db, run_date, mode)
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
        timeframe: str,
        mode: str,
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
                timeframe=timeframe,
                mode=self._normalize_mode(mode),
                close=float(latest_candle["close"]),
                sma20=float(indicators.get("SMA_20", 0.0)),
                ema20=float(indicators.get("EMA_20", 0.0)),
                sma50=float(indicators.get("SMA_50")) if indicators.get("SMA_50") is not None else None,
                ema50=float(indicators.get("EMA_50")) if indicators.get("EMA_50") is not None else None,
                rsi14=float(indicators.get("RSI_14", 0.0)),
                atr14=float(indicators.get("ATR_14", 0.0)),
                macd=float(indicators.get("MACD")) if indicators.get("MACD") is not None else None,
                macd_signal=float(indicators.get("MACD_SIGNAL")) if indicators.get("MACD_SIGNAL") is not None else None,
                trend=trend,
                indicators_json=indicators,
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
        mode: str,
        source_portal: str = "yfinance",
        plan_type: str = "MARKET",
        stop_loss: float | None = None,
        take_profit: float | None = None,
        gtt_buy_trigger: float | None = None,
        gtt_sell_trigger: float | None = None,
        holding_horizon_days: int | None = None,
        exit_rules_json: dict | None = None,
        status: str = "PLANNED",
    ) -> TradePlan:
        ref = float(price_ref)
        plan = TradePlan(
            run_id=run_id,
            date=run_date,
            symbol=symbol,
            side=side,
            qty=qty,
            mode=self._normalize_mode(mode),
            plan_type=plan_type,
            price_ref=ref,
            stop_loss=float(stop_loss) if stop_loss is not None else round(ref * 0.99, 4),
            take_profit=float(take_profit) if take_profit is not None else round(ref * 1.01, 4),
            gtt_buy_trigger=gtt_buy_trigger,
            gtt_sell_trigger=gtt_sell_trigger,
            holding_horizon_days=holding_horizon_days,
            exit_rules_json=exit_rules_json or {},
            confidence=float(confidence),
            rationale=rationale,
            source_portal=source_portal.strip().lower(),
            status=status,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    def log_no_trade(
        self,
        db: Session,
        run_id: str,
        run_date: date,
        symbol: str,
        mode: str,
        rationale: str,
        price_ref: float,
        features: dict,
    ) -> TradePlan:
        return self.create_trade_plan(
            db=db,
            run_id=run_id,
            run_date=run_date,
            symbol=symbol,
            side="HOLD",
            qty=0,
            price_ref=price_ref,
            confidence=0.5,
            rationale=rationale,
            mode=mode,
            plan_type="MARKET",
            status="CANCELLED",
            exit_rules_json={"features": features},
        )

    def update_trade_plan_status(self, db: Session, trade_plan_id: int, status: str) -> None:
        plan = db.get(TradePlan, trade_plan_id)
        if not plan:
            return
        plan.status = status
        db.add(plan)
        db.commit()

    def get_trade_plan(self, db: Session, trade_plan_id: int) -> TradePlan | None:
        return db.get(TradePlan, trade_plan_id)

    def add_transaction(
        self,
        db: Session,
        trade_plan_id: int,
        run_date: date,
        symbol: str,
        side: str,
        qty: int,
        mode: str,
        order_type: str,
        source_portal: str,
        execution_portal: str,
        entry_price: float,
        features_json: dict,
        exit_price: float | None = None,
        pnl: float | None = None,
        gtt_id: int | None = None,
        notes: str | None = None,
    ) -> Transaction:
        tx = Transaction(
            trade_plan_id=trade_plan_id,
            date=run_date,
            symbol=symbol,
            side=side,
            qty=qty,
            mode=self._normalize_mode(mode),
            order_type=order_type,
            source_portal=source_portal.strip().lower(),
            execution_portal=execution_portal.strip().lower(),
            gtt_id=gtt_id,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            notes=notes,
            features_json=features_json,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

    def create_gtt_order(
        self,
        db: Session,
        run_date: date,
        symbol: str,
        side: str,
        qty: int,
        trigger_price: float,
        linked_trade_plan_id: int,
        limit_price: float | None = None,
        status: str = "PENDING",
    ) -> GTTOrder:
        gtt = GTTOrder(
            date_created=run_date,
            symbol=symbol,
            side=side,
            qty=qty,
            trigger_price=trigger_price,
            limit_price=limit_price,
            status=status,
            linked_trade_plan_id=linked_trade_plan_id,
        )
        db.add(gtt)
        db.commit()
        db.refresh(gtt)
        return gtt

    def update_gtt(
        self,
        db: Session,
        gtt_id: int,
        *,
        trigger_price: float | None = None,
        status: str | None = None,
        executed_price: float | None = None,
        triggered_at: datetime | None = None,
    ) -> GTTOrder | None:
        gtt = db.get(GTTOrder, gtt_id)
        if not gtt:
            return None
        if trigger_price is not None:
            gtt.trigger_price = trigger_price
        if status is not None:
            gtt.status = status
        if executed_price is not None:
            gtt.executed_price = executed_price
        if triggered_at is not None:
            gtt.triggered_at = triggered_at
        db.add(gtt)
        db.commit()
        db.refresh(gtt)
        return gtt

    def get_pending_gtt_orders(self, db: Session, side: str | None = None) -> list[GTTOrder]:
        query = select(GTTOrder).where(GTTOrder.status == "PENDING")
        if side:
            query = query.where(GTTOrder.side == side)
        return db.execute(query).scalars().all()

    def cancel_pending_gtt_for_plan(self, db: Session, trade_plan_id: int) -> None:
        gt_orders = db.execute(
            select(GTTOrder).where(GTTOrder.linked_trade_plan_id == trade_plan_id, GTTOrder.status == "PENDING")
        ).scalars().all()
        for row in gt_orders:
            row.status = "CANCELLED"
            db.add(row)
        db.commit()

    def get_open_position_count(self, db: Session, run_date: date, mode: str) -> int:
        mode = self._normalize_mode(mode)
        if mode == "SWING":
            rows = db.execute(select(TradePlan).where(TradePlan.mode == "SWING", TradePlan.status == "OPEN")).scalars().all()
            return len(rows)

        buys = db.execute(
            select(Transaction.qty).where(
                Transaction.date == run_date,
                Transaction.mode == "INTRADAY",
                Transaction.side == "BUY",
            )
        ).all()
        sells = db.execute(
            select(Transaction.qty).where(
                Transaction.date == run_date,
                Transaction.mode == "INTRADAY",
                Transaction.side == "SELL",
            )
        ).all()
        net_qty = sum(row[0] for row in buys) - sum(row[0] for row in sells)
        return 1 if net_qty > 0 else 0

    def get_open_qty_for_symbol(self, db: Session, run_date: date, symbol: str, mode: str) -> int:
        mode = self._normalize_mode(mode)
        if mode == "SWING":
            plan = db.execute(
                select(TradePlan).where(TradePlan.mode == "SWING", TradePlan.symbol == symbol, TradePlan.status == "OPEN")
            ).scalar_one_or_none()
            return plan.qty if plan else 0

        buys = db.execute(
            select(Transaction.qty).where(
                Transaction.date == run_date,
                Transaction.symbol == symbol,
                Transaction.mode == "INTRADAY",
                Transaction.side == "BUY",
            )
        ).all()
        sells = db.execute(
            select(Transaction.qty).where(
                Transaction.date == run_date,
                Transaction.symbol == symbol,
                Transaction.mode == "INTRADAY",
                Transaction.side == "SELL",
            )
        ).all()
        return max(0, sum(row[0] for row in buys) - sum(row[0] for row in sells))

    def get_latest_open_buy(self, db: Session, run_date: date, symbol: str, mode: str) -> Transaction | None:
        if self.get_open_qty_for_symbol(db, run_date, symbol, mode) <= 0:
            return None
        return db.execute(
            select(Transaction)
            .where(
                Transaction.date == run_date,
                Transaction.symbol == symbol,
                Transaction.mode == self._normalize_mode(mode),
                Transaction.side == "BUY",
            )
            .order_by(Transaction.id.desc())
        ).scalars().first()

    def get_open_swing_plans(self, db: Session) -> list[TradePlan]:
        return db.execute(select(TradePlan).where(TradePlan.mode == "SWING", TradePlan.status == "OPEN")).scalars().all()

    def get_today_transactions(self, db: Session, run_date: date, mode: str) -> list[Transaction]:
        return db.execute(
            select(Transaction).where(Transaction.date == run_date, Transaction.mode == self._normalize_mode(mode))
        ).scalars().all()

    def get_today_pending_gtt(self, db: Session, run_date: date) -> list[GTTOrder]:
        return db.execute(
            select(GTTOrder).where(GTTOrder.date_created == run_date, GTTOrder.status == "PENDING")
        ).scalars().all()
