from __future__ import annotations

from src.config import get_settings


class ZerodhaClient:
    """Mock-ready client boundary for Zerodha Kite APIs."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def get_holdings(self) -> list[dict]:
        return [
            {"symbol": "TCS", "quantity": 10, "avg_price": 3550.0},
            {"symbol": "INFY", "quantity": 18, "avg_price": 1540.0},
            {"symbol": "RELIANCE", "quantity": 8, "avg_price": 2860.0},
            {"symbol": "HDFCBANK", "quantity": 12, "avg_price": 1620.0},
        ]

    def get_positions(self) -> list[dict]:
        return [
            {"symbol": "NIFTYBEES", "product": "CNC", "quantity": 25, "avg_price": 245.0},
        ]

    def get_orders(self) -> list[dict]:
        return [
            {"order_id": "A1", "symbol": "TCS", "status": "COMPLETE"},
            {"order_id": "A2", "symbol": "INFY", "status": "COMPLETE"},
        ]
