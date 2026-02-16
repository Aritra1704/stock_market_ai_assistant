from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.integrations.brokers.paper import PaperBroker
from src.integrations.market_data.yfinance_client import YFinanceClient
from src.models.tables import GTTOrder, TradePlan
from src.services.execution_service import ExecutionService
from src.services.journal_service import JournalService
from src.strategies.swing_v1 import compute_indicators, generate_exit_signal
from src.utils.time import utc_now

logger = logging.getLogger(__name__)


class GTTService:
    def __init__(
        self,
        journal: JournalService | None = None,
        execution: ExecutionService | None = None,
        market: YFinanceClient | None = None,
        broker: PaperBroker | None = None,
    ) -> None:
        self.journal = journal or JournalService()
        self.execution = execution or ExecutionService(journal=self.journal)
        self.market = market or YFinanceClient()
        self.broker = broker or PaperBroker()

    def place_entry_gtt(
        self,
        db: Session,
        run_date: date,
        trade_plan_id: int,
        symbol: str,
        qty: int,
        trigger_price: float,
    ) -> GTTOrder:
        gtt = self.journal.create_gtt_order(
            db=db,
            run_date=run_date,
            symbol=symbol,
            side="BUY",
            qty=qty,
            trigger_price=trigger_price,
            linked_trade_plan_id=trade_plan_id,
        )
        self.journal.update_trade_plan_status(db, trade_plan_id, "GTT_PLACED")
        return gtt

    def _latest_daily_row(self, symbol: str):
        raw = self.market.fetch_daily(symbol=symbol, period="6mo")
        with_ind = compute_indicators(raw)
        return with_ind.iloc[-1], with_ind

    def process_pending_buy_gtts(self, db: Session, run_date: date) -> int:
        triggered_count = 0
        pending = db.execute(select(GTTOrder).where(GTTOrder.status == "PENDING", GTTOrder.side == "BUY")).scalars().all()
        for gtt in pending:
            latest, with_ind = self._latest_daily_row(gtt.symbol)
            high = float(latest["high"])
            if not self.broker.should_trigger("BUY", gtt.trigger_price, candle_high=high, candle_low=float(latest["low"])):
                continue

            plan = self.journal.get_trade_plan(db, gtt.linked_trade_plan_id)
            if not plan:
                self.journal.update_gtt(db, gtt.id, status="CANCELLED")
                continue

            features = {
                "trigger": gtt.trigger_price,
                "latest": {
                    "close": float(latest["close"]),
                    "high": high,
                    "low": float(latest["low"]),
                },
                "indicators": {
                    "SMA_20": float(latest["sma20"]),
                    "SMA_50": float(latest["sma50"]),
                    "EMA_20": float(latest["ema20"]),
                    "RSI_14": float(latest["rsi14"]),
                    "ATR_14": float(latest["atr14"]),
                },
            }

            result = self.execution.execute_buy(
                db=db,
                trade_plan_id=plan.id,
                run_date=run_date,
                symbol=plan.symbol,
                qty=plan.qty,
                price=gtt.trigger_price,
                features=features,
                mode="SWING",
                order_type="GTT_TRIGGER",
                gtt_id=gtt.id,
            )
            if not result.get("executed"):
                continue

            self.journal.update_gtt(
                db,
                gtt.id,
                status="TRIGGERED",
                executed_price=gtt.trigger_price,
                triggered_at=utc_now().replace(tzinfo=None),
            )

            trailing_stop = float(plan.stop_loss)
            exit_rules = plan.exit_rules_json or {}
            exit_rules["trailing_stop"] = trailing_stop
            plan.exit_rules_json = exit_rules
            plan.gtt_sell_trigger = trailing_stop
            db.add(plan)
            db.commit()

            self.journal.create_gtt_order(
                db=db,
                run_date=run_date,
                symbol=plan.symbol,
                side="SELL",
                qty=plan.qty,
                trigger_price=trailing_stop,
                linked_trade_plan_id=plan.id,
            )
            triggered_count += 1
        return triggered_count

    def _process_open_plan(self, db: Session, plan: TradePlan, run_date: date) -> bool:
        latest, _ = self._latest_daily_row(plan.symbol)
        close = float(latest["close"])
        low = float(latest["low"])
        holding_days = max(0, (run_date - plan.date).days)

        exit_rules = plan.exit_rules_json or {}
        trailing = float(exit_rules.get("trailing_stop", plan.stop_loss))
        horizon_days = int(plan.holding_horizon_days or 20)

        exit_signal = generate_exit_signal(
            latest_row=latest,
            entry_price=plan.price_ref,
            trailing_stop=trailing,
            take_profit=plan.take_profit,
            holding_days=holding_days,
            horizon_days=horizon_days,
        )

        new_trailing = float(exit_signal.params.get("new_trailing_stop", trailing))
        plan.stop_loss = new_trailing
        plan.gtt_sell_trigger = new_trailing
        plan.exit_rules_json = {**exit_rules, "trailing_stop": new_trailing}
        db.add(plan)
        db.commit()

        pending_sell = db.execute(
            select(GTTOrder).where(
                GTTOrder.linked_trade_plan_id == plan.id,
                GTTOrder.side == "SELL",
                GTTOrder.status == "PENDING",
            )
        ).scalars().first()
        if pending_sell:
            self.journal.update_gtt(db, pending_sell.id, trigger_price=new_trailing)
            if self.broker.should_trigger("SELL", new_trailing, candle_high=close, candle_low=low):
                features = {"reason": "Trailing stop GTT triggered", "close": close, "low": low}
                res = self.execution.execute_sell(
                    db=db,
                    trade_plan_id=plan.id,
                    run_date=run_date,
                    symbol=plan.symbol,
                    qty=plan.qty,
                    price=new_trailing,
                    features=features,
                    mode="SWING",
                    order_type="GTT_TRIGGER",
                    gtt_id=pending_sell.id,
                )
                if res.get("executed"):
                    self.journal.update_gtt(
                        db,
                        pending_sell.id,
                        status="TRIGGERED",
                        executed_price=new_trailing,
                        triggered_at=utc_now().replace(tzinfo=None),
                    )
                    self.journal.cancel_pending_gtt_for_plan(db, plan.id)
                    return True

        if exit_signal.action == "EXIT":
            features = {"reason": exit_signal.rationale, "close": close, "trailing_stop": new_trailing}
            res = self.execution.execute_sell(
                db=db,
                trade_plan_id=plan.id,
                run_date=run_date,
                symbol=plan.symbol,
                qty=plan.qty,
                price=close,
                features=features,
                mode="SWING",
                order_type="MARKET",
            )
            if res.get("executed"):
                self.journal.cancel_pending_gtt_for_plan(db, plan.id)
                return True

        return False

    def process_open_positions(self, db: Session, run_date: date) -> int:
        executed = 0
        open_plans = self.journal.get_open_swing_plans(db)
        for plan in open_plans:
            try:
                if self._process_open_plan(db, plan, run_date):
                    executed += 1
            except Exception as exc:  # pragma: no cover
                logger.exception("Failed processing open swing plan", extra={"plan_id": plan.id, "error": str(exc)})
        return executed
