import pandas as pd

from src.services.analytics_service import AnalyticsService


def test_analytics_metrics_do_not_crash() -> None:
    service = AnalyticsService()
    prices = pd.Series([100, 102, 101, 104, 108, 110, 109, 115])

    returns = service.compute_returns(prices, window=3)
    dd = service.max_drawdown(prices)
    momentum = service.momentum(prices, lookback=3)
    vol = service.annualized_volatility(prices)

    assert "daily_mean_return" in returns
    assert dd <= 0
    assert momentum != 0
    assert vol >= 0
