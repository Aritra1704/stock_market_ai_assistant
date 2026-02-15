from pydantic import BaseModel


class Holding(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    ltp: float
    market_value: float
    pnl: float
