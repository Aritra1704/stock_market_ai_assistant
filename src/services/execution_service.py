from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.integrations.brokers.paper import PaperBroker
from src.models.tables import Transaction
from src.services.journal_service import JournalService

logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(self, broker: PaperBroker | None = None, journal: JournalService | None = None) -> None:
        self.broker = broker or PaperBroker()
        self.journal = journal or JournalService()

    def execute_buy(
        self,
        db: Session,
        trade_plan_id: int,
        run_date,
        symbol: str,
        qty: int,
        price: float,
        features: dict,
        mode: str,
        order_type: str = "MARKET",
        gtt_id: int | None = None,
        source_portal: str = "yfinance",
    ) -> dict:
        fill = self.broker.place_order(symbol=symbol, side="BUY", qty=qty, price=price, order_type=order_type)
        self.journal.add_transaction(
            db=db,
            trade_plan_id=trade_plan_id,
            run_date=run_date,
            symbol=symbol,
            side="BUY",
            qty=fill.qty,
            mode=mode,
            order_type=fill.order_type,
            source_portal=source_portal,
            execution_portal=self.broker.name,
            gtt_id=gtt_id,
            entry_price=fill.fill_price,
            features_json=features,
            notes="paper fill",
        )
        self.journal.update_budget_spent(db, run_date, mode, fill.qty * fill.fill_price)
        self.journal.update_trade_plan_status(db, trade_plan_id, "OPEN")
        logger.info("Paper BUY executed", extra={"mode": mode, "symbol": symbol, "qty": qty, "price": price})
        return {"executed": True, "side": "BUY", "qty": fill.qty, "price": fill.fill_price}

    def execute_sell(
        self,
        db: Session,
        trade_plan_id: int,
        run_date,
        symbol: str,
        qty: int,
        price: float,
        features: dict,
        mode: str,
        order_type: str = "MARKET",
        gtt_id: int | None = None,
        source_portal: str = "yfinance",
    ) -> dict:
        mode = mode.upper()
        if mode == "SWING":
            open_plan = self.journal.get_trade_plan(db, trade_plan_id)
            if not open_plan:
                return {"executed": False, "reason": "No trade plan found"}
            entry_tx = db.execute(
                select(Transaction)
                .where(Transaction.trade_plan_id == trade_plan_id, Transaction.side == "BUY")
                .order_by(Transaction.id.desc())
            ).scalars().first()
        else:
            entry_tx = self.journal.get_latest_open_buy(db, run_date, symbol, mode)

        if not entry_tx:
            self.journal.update_trade_plan_status(db, trade_plan_id, "CANCELLED")
            return {"executed": False, "reason": "No open BUY position to close"}

        sell_qty = min(qty, entry_tx.qty)
        fill = self.broker.place_order(symbol=symbol, side="SELL", qty=sell_qty, price=price, order_type=order_type)
        pnl = round((fill.fill_price - entry_tx.entry_price) * sell_qty, 4)

        self.journal.add_transaction(
            db=db,
            trade_plan_id=trade_plan_id,
            run_date=run_date,
            symbol=symbol,
            side="SELL",
            qty=sell_qty,
            mode=mode,
            order_type=fill.order_type,
            source_portal=source_portal,
            execution_portal=self.broker.name,
            gtt_id=gtt_id,
            entry_price=entry_tx.entry_price,
            exit_price=fill.fill_price,
            pnl=pnl,
            features_json=features,
            notes="paper fill",
        )
        self.journal.update_trade_plan_status(db, trade_plan_id, "CLOSED")
        logger.info(
            "Paper SELL executed",
            extra={"mode": mode, "symbol": symbol, "qty": sell_qty, "price": price, "pnl": pnl},
        )
        return {"executed": True, "side": "SELL", "qty": sell_qty, "price": fill.fill_price, "pnl": pnl}
