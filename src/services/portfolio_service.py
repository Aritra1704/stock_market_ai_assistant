from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.integrations.zerodha_client import ZerodhaClient
from src.models.tables import DayBudget, PaperPosition, PaperTransaction
from src.models.holding import Holding
from src.services.market_service import MarketService


class PortfolioService:
    def __init__(self, broker_client: ZerodhaClient | None = None, market_service: MarketService | None = None) -> None:
        self.broker_client = broker_client or ZerodhaClient()
        self.market_service = market_service or MarketService()

    def get_holdings(self) -> list[Holding]:
        holdings: list[Holding] = []
        for raw in self.broker_client.get_holdings():
            quote = self.market_service.get_quote(raw["symbol"])
            ltp = quote["ltp"]
            market_value = raw["quantity"] * ltp
            pnl = (ltp - raw["avg_price"]) * raw["quantity"]
            holdings.append(
                Holding(
                    symbol=raw["symbol"],
                    quantity=raw["quantity"],
                    avg_price=raw["avg_price"],
                    ltp=ltp,
                    market_value=market_value,
                    pnl=pnl,
                )
            )
        return holdings

    def summary(self) -> dict:
        holdings = self.get_holdings()
        total_value = sum(h.market_value for h in holdings)
        total_pnl = sum(h.pnl for h in holdings)
        return {
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "holdings": [h.model_dump() for h in holdings],
            "positions": self.broker_client.get_positions(),
            "orders": self.broker_client.get_orders(),
        }


class IntradayPaperPortfolioService:
    def get_or_create_day_budget(self, db: Session, run_date: date, budget_total: float) -> DayBudget:
        row = db.get(DayBudget, run_date)
        if row is not None:
            return row

        row = DayBudget(
            date=run_date,
            budget_total=float(budget_total),
            used=0.0,
            remaining=float(budget_total),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def get_open_positions(self, db: Session, run_date: date) -> list[PaperPosition]:
        return db.execute(
            select(PaperPosition)
            .where(PaperPosition.date == run_date, PaperPosition.status == "OPEN")
            .order_by(PaperPosition.entry_time.asc())
        ).scalars().all()

    def get_open_position_for_symbol(self, db: Session, run_date: date, symbol: str) -> PaperPosition | None:
        return db.execute(
            select(PaperPosition)
            .where(PaperPosition.date == run_date, PaperPosition.symbol == symbol, PaperPosition.status == "OPEN")
            .order_by(PaperPosition.entry_time.asc())
        ).scalars().first()

    def count_open_positions(self, db: Session, run_date: date) -> int:
        return len(self.get_open_positions(db, run_date))

    def entries_for_symbol(self, db: Session, run_date: date, symbol: str) -> int:
        rows = db.execute(
            select(PaperTransaction.id)
            .join(PaperPosition, PaperTransaction.position_id == PaperPosition.id)
            .where(
                PaperPosition.date == run_date,
                PaperPosition.symbol == symbol,
                PaperTransaction.side == "BUY",
            )
        ).all()
        return len(rows)

    def available_cash(self, db: Session, run_date: date, budget_total: float) -> float:
        budget = self.get_or_create_day_budget(db, run_date, budget_total=budget_total)
        return float(budget.remaining)

    @staticmethod
    def qty_from_cash(price: float, cash: float) -> float:
        if price <= 0 or cash <= 0:
            return 0.0
        return round(cash / price, 6)

    def allocation_for_new_position(
        self,
        db: Session,
        run_date: date,
        budget_total: float,
        max_positions: int,
    ) -> float:
        open_count = self.count_open_positions(db, run_date)
        slots_left = max(1, max_positions - open_count)
        available = self.available_cash(db, run_date, budget_total=budget_total)
        if available <= 0:
            return 0.0
        return round(available / slots_left, 4)

    def open_position(
        self,
        db: Session,
        run_date: date,
        symbol: str,
        qty: float,
        price: float,
        stop_price: float,
        target_price: float,
        decision_id: int | None = None,
        timestamp: datetime | None = None,
    ) -> PaperPosition:
        ts = (timestamp or datetime.utcnow()).replace(tzinfo=None)
        position = PaperPosition(
            date=run_date,
            symbol=symbol,
            status="OPEN",
            entry_time=ts,
            entry_price=float(price),
            qty=float(qty),
            stop_price=float(stop_price),
            target_price=float(target_price),
        )
        db.add(position)
        db.flush()

        db.add(
            PaperTransaction(
                position_id=position.id,
                decision_id=decision_id,
                side="BUY",
                qty=float(qty),
                price=float(price),
                timestamp=ts,
                mode="paper",
            )
        )

        budget = db.get(DayBudget, run_date)
        if budget is not None:
            cost = float(qty) * float(price)
            budget.used = round(float(budget.used) + cost, 4)
            budget.remaining = round(float(budget.remaining) - cost, 4)
            budget.updated_at = datetime.utcnow()
            db.add(budget)

        db.add(position)
        db.commit()
        db.refresh(position)
        return position

    def close_position(
        self,
        db: Session,
        position: PaperPosition,
        qty: float,
        price: float,
        decision_id: int | None = None,
        exit_reason: str | None = None,
        timestamp: datetime | None = None,
    ) -> dict:
        ts = (timestamp or datetime.utcnow()).replace(tzinfo=None)
        sell_qty = min(float(qty), float(position.qty))
        if sell_qty <= 0:
            return {"sold_qty": 0.0, "proceeds": 0.0, "position_closed": False}

        db.add(
            PaperTransaction(
                position_id=position.id,
                decision_id=decision_id,
                side="SELL",
                qty=sell_qty,
                price=float(price),
                timestamp=ts,
                mode="paper",
            )
        )

        proceeds = round(sell_qty * float(price), 4)
        realized_pnl = round((float(price) - float(position.entry_price)) * sell_qty, 4)

        position.qty = round(float(position.qty) - sell_qty, 6)
        position.pnl = round(float(position.pnl or 0.0) + realized_pnl, 4)
        position.exit_reason = exit_reason or position.exit_reason
        if position.qty <= 0:
            position.status = "CLOSED"
            position.qty = 0.0
            position.exit_time = ts
            position.exit_price = float(price)
            position.exit_reason = exit_reason or "manual"

        budget = db.get(DayBudget, position.date)
        if budget is not None:
            budget.used = round(max(0.0, float(budget.used) - proceeds), 4)
            budget.remaining = round(float(budget.remaining) + proceeds, 4)
            budget.updated_at = datetime.utcnow()
            db.add(budget)

        db.add(position)
        db.commit()
        db.refresh(position)
        return {
            "sold_qty": sell_qty,
            "proceeds": proceeds,
            "position_closed": position.status == "CLOSED",
            "realized_pnl": realized_pnl,
        }
