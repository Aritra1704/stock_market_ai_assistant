from src.services.market_service import MarketService


market_service = MarketService()


def get_stock_quote(symbol: str) -> dict:
    return market_service.get_quote(symbol)


def get_historical_candles(symbol: str, days: int = 180) -> list[dict]:
    df = market_service.get_historical(symbol, days=days)
    return df.tail(50).to_dict(orient="records")
