from __future__ import annotations

from src.integrations.market_data_client import MarketDataClient
from src.utils.validation import validate_symbol


class MarketService:
    def __init__(self, client: MarketDataClient | None = None) -> None:
        self.client = client or MarketDataClient()

    def get_quote(self, symbol: str) -> dict:
        return self.client.get_quote(validate_symbol(symbol))

    def get_historical(self, symbol: str, days: int = 120):
        return self.client.get_historical(validate_symbol(symbol), days=days)

    def get_intraday(self, symbol: str, points: int = 60):
        return self.client.get_intraday(validate_symbol(symbol), points=points)
