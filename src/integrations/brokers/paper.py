from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PaperFill:
    symbol: str
    side: str
    qty: float
    fill_price: float
    order_type: str = "MARKET"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PaperGTTOrder:
    symbol: str
    side: str
    qty: float
    trigger_price: float
    limit_price: float | None = None


class PaperBroker:
    name = "paper"

    def place_order(self, symbol: str, side: str, qty: float, price: float, order_type: str = "MARKET") -> PaperFill:
        return PaperFill(
            symbol=symbol,
            side=side,
            qty=float(qty),
            fill_price=float(price),
            order_type=order_type,
            timestamp=datetime.utcnow(),
        )

    def place_order_from_candle(
        self,
        symbol: str,
        side: str,
        qty: float,
        candle: dict,
        fill_model: str = "close",
        order_type: str = "MARKET",
    ) -> PaperFill:
        model = fill_model.strip().lower()
        if model != "close":
            model = "close"
        fill_price = float(candle.get(model, candle.get("close", 0.0)))
        return self.place_order(symbol=symbol, side=side, qty=qty, price=fill_price, order_type=order_type)

    @staticmethod
    def should_trigger(side: str, trigger_price: float, candle_high: float, candle_low: float) -> bool:
        if side == "BUY":
            return candle_high >= trigger_price
        return candle_low <= trigger_price
