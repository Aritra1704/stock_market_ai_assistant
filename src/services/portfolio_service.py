from __future__ import annotations

from src.integrations.zerodha_client import ZerodhaClient
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
