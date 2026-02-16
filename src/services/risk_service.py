from __future__ import annotations

from math import floor

from sqlalchemy.orm import Session

from src.config import settings
from src.services.journal_service import JournalService


class RiskService:
    def __init__(self, journal_service: JournalService | None = None) -> None:
        self.journal_service = journal_service or JournalService()

    def budget_remaining(self, db: Session, run_date, mode: str) -> float:
        budget = self.journal_service.get_or_create_budget(db, run_date, mode)
        return float(budget.remaining)

    def can_open_new_position(self, db: Session, run_date, mode: str) -> bool:
        mode = mode.upper()
        open_positions = self.journal_service.get_open_position_count(db, run_date, mode)
        if mode == "SWING":
            return open_positions < settings.swing_max_open_positions
        return open_positions < settings.intraday_max_open_positions

    def size_buy_qty(self, latest_price: float, remaining_budget: float, mode: str) -> int:
        if latest_price <= 0:
            return 0
        if mode.upper() == "SWING":
            spend_cap = min(remaining_budget, settings.swing_allocation_inr)
        else:
            spend_cap = min(remaining_budget, settings.intraday_daily_budget_inr)
        return floor(spend_cap / latest_price)
