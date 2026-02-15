from __future__ import annotations

import numpy as np
import pandas as pd


class AnalyticsService:
    def compute_returns(self, close_series: pd.Series, window: int = 20) -> dict:
        returns = close_series.pct_change().dropna()
        rolling = returns.rolling(window=window)
        return {
            "daily_mean_return": float(returns.mean()) if not returns.empty else 0.0,
            "daily_volatility": float(returns.std()) if not returns.empty else 0.0,
            "rolling_return": float((1 + returns.tail(window)).prod() - 1) if len(returns) >= window else 0.0,
            "rolling_volatility": float(rolling.std().iloc[-1]) if len(returns) >= window else 0.0,
        }

    def max_drawdown(self, close_series: pd.Series) -> float:
        cumulative_max = close_series.cummax()
        drawdown = (close_series - cumulative_max) / cumulative_max
        return float(drawdown.min()) if not drawdown.empty else 0.0

    def momentum(self, close_series: pd.Series, lookback: int = 30) -> float:
        if len(close_series) < lookback + 1:
            return 0.0
        start = close_series.iloc[-lookback - 1]
        end = close_series.iloc[-1]
        return float((end / start) - 1)

    def annualized_volatility(self, close_series: pd.Series) -> float:
        returns = close_series.pct_change().dropna()
        if returns.empty:
            return 0.0
        return float(np.sqrt(252) * returns.std())
