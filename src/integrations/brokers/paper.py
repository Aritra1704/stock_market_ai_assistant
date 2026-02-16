from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaperFill:
    symbol: str
    side: str
    qty: int
    fill_price: float
    order_type: str = "MARKET"


@dataclass
class PaperGTTOrder:
    symbol: str
    side: str
    qty: int
    trigger_price: float
    limit_price: float | None = None


class PaperBroker:
    name = "paper"

    def place_order(self, symbol: str, side: str, qty: int, price: float, order_type: str = "MARKET") -> PaperFill:
        return PaperFill(symbol=symbol, side=side, qty=qty, fill_price=price, order_type=order_type)

    @staticmethod
    def should_trigger(side: str, trigger_price: float, candle_high: float, candle_low: float) -> bool:
        if side == "BUY":
            return candle_high >= trigger_price
        return candle_low <= trigger_price
