from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaperFill:
    symbol: str
    side: str
    qty: int
    fill_price: float
    mode: str = "paper"


class PaperBroker:
    def place_order(self, symbol: str, side: str, qty: int, price: float) -> PaperFill:
        return PaperFill(symbol=symbol, side=side, qty=qty, fill_price=price)
