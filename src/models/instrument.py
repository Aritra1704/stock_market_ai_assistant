from pydantic import BaseModel


class Instrument(BaseModel):
    symbol: str
    exchange: str = "NSE"
    sector: str = "Unknown"
    lot_size: int = 1
