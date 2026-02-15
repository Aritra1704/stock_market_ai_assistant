from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.integrations.brokers.paper import PaperBroker
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
    ) -> dict:
        fill = self.broker.place_order(symbol=symbol, side="BUY", qty=qty, price=price)
        self.journal.add_transaction(
            db=db,
            trade_plan_id=trade_plan_id,
            run_date=run_date,
            symbol=symbol,
            side="BUY",
            qty=fill.qty,
            entry_price=fill.fill_price,
            features_json=features,
            mode=fill.mode,
        )
        self.journal.update_budget_spent(db, run_date, fill.qty * fill.fill_price)
        self.journal.update_trade_plan_status(db, trade_plan_id, "EXECUTED")
        logger.info("Paper BUY executed", extra={"symbol": symbol, "qty": qty, "price": price})
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
    ) -> dict:
        open_buy = self.journal.get_latest_open_buy(db, run_date, symbol)
        if not open_buy:
            self.journal.update_trade_plan_status(db, trade_plan_id, "REJECTED_NO_OPEN_POSITION")
            return {"executed": False, "reason": "No open BUY position to close"}

        sell_qty = min(qty, open_buy.qty)
        fill = self.broker.place_order(symbol=symbol, side="SELL", qty=sell_qty, price=price)
        pnl = round((fill.fill_price - open_buy.entry_price) * sell_qty, 4)

        self.journal.add_transaction(
            db=db,
            trade_plan_id=trade_plan_id,
            run_date=run_date,
            symbol=symbol,
            side="SELL",
            qty=sell_qty,
            entry_price=open_buy.entry_price,
            exit_price=fill.fill_price,
            pnl=pnl,
            features_json=features,
            mode=fill.mode,
        )
        self.journal.update_trade_plan_status(db, trade_plan_id, "EXECUTED")
        logger.info("Paper SELL executed", extra={"symbol": symbol, "qty": sell_qty, "price": price, "pnl": pnl})
        return {"executed": True, "side": "SELL", "qty": sell_qty, "price": fill.fill_price, "pnl": pnl}
