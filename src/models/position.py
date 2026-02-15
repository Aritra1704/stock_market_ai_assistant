from pydantic import BaseModel


class Position(BaseModel):
    symbol: str
    product: str
    quantity: int
    avg_price: float
    mtm: float
