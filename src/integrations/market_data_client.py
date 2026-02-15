from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from src.utils.time_utils import utc_now


class MarketDataClient:
    def get_quote(self, symbol: str) -> dict:
        base = 100 + (sum(ord(ch) for ch in symbol) % 3000)
        ltp = round(base * 1.03, 2)
        prev_close = round(base, 2)
        change_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
        return {
            "symbol": symbol,
            "ltp": ltp,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "timestamp": utc_now().isoformat(),
        }

    def get_historical(self, symbol: str, days: int = 120) -> pd.DataFrame:
        rng = np.random.default_rng(seed=sum(ord(ch) for ch in symbol))
        dates = pd.date_range(end=utc_now(), periods=days, freq="B")
        noise = rng.normal(loc=0.0008, scale=0.015, size=days)
        closes = 100 * np.exp(np.cumsum(noise))
        highs = closes * (1 + rng.uniform(0.001, 0.02, size=days))
        lows = closes * (1 - rng.uniform(0.001, 0.02, size=days))
        opens = closes * (1 + rng.normal(0, 0.004, size=days))
        volumes = rng.integers(100000, 500000, size=days)

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )
        return df

    def get_intraday(self, symbol: str, points: int = 60) -> pd.DataFrame:
        rng = np.random.default_rng(seed=sum(ord(ch) for ch in symbol) + 7)
        end = utc_now().replace(second=0, microsecond=0)
        timestamps = [end - timedelta(minutes=i) for i in range(points)][::-1]
        returns = rng.normal(0.0, 0.002, size=points)
        prices = 100 * np.exp(np.cumsum(returns))
        return pd.DataFrame({"timestamp": timestamps, "close": prices})
