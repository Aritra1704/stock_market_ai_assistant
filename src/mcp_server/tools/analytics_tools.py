from src.services.analytics_service import AnalyticsService
from src.services.market_service import MarketService


analytics_service = AnalyticsService()
market_service = MarketService()


def compute_stock_metrics(symbol: str) -> dict:
    df = market_service.get_historical(symbol, days=180)
    close = df["close"]
    return {
        "returns": analytics_service.compute_returns(close),
        "max_drawdown": analytics_service.max_drawdown(close),
        "momentum_30d": analytics_service.momentum(close),
        "annualized_volatility": analytics_service.annualized_volatility(close),
    }
