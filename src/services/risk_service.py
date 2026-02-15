from __future__ import annotations

from math import floor

from sqlalchemy.orm import Session

from src.config import settings
from src.services.journal_service import JournalService


class RiskService:
    def __init__(self, journal_service: JournalService | None = None) -> None:
        self.journal_service = journal_service or JournalService()

    def budget_remaining(self, db: Session, run_date):
        budget = self.journal_service.get_or_create_budget(db, run_date)
        return budget.remaining

    def can_open_new_position(self, db: Session, run_date) -> bool:
        open_positions = self.journal_service.get_open_position_count(db, run_date)
        return open_positions < settings.max_open_positions

    def size_buy_qty(self, latest_price: float, remaining_budget: float) -> int:
        if latest_price <= 0:
            return 0
        spend_cap = min(remaining_budget, settings.daily_budget_inr)
        return floor(spend_cap / latest_price)
