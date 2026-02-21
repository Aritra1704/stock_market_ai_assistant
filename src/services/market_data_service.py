from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from src.integrations.market_data.yfinance_client import YFinanceClient
from src.utils.indicators import rsi


@dataclass
class SymbolSnapshot:
    symbol: str
    candle_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    ema20: float
    rsi14: float
    vol_avg20: float
    ema_slope: float
    score: float
    buy_condition: bool
    reasons_json: dict
    features_json: dict
    summary_text: str


class MarketDataService:
    def __init__(self, client: YFinanceClient | None = None) -> None:
        self.client = client or YFinanceClient()

    @staticmethod
    def _to_float(value, default: float = 0.0) -> float:
        try:
            out = float(value)
        except (TypeError, ValueError):
            return default
        if np.isnan(out) or np.isinf(out):
            return default
        return out

    def analyze_symbol(self, symbol: str, interval: str = "5m", period: str = "5d") -> SymbolSnapshot:
        df = self.client.fetch_ohlcv(symbol=symbol, interval=interval, period=period)
        if df.empty:
            raise ValueError(f"No candles for {symbol}")

        work = df.copy()
        work["ema20"] = work["close"].ewm(span=20, adjust=False).mean()
        work["rsi14"] = rsi(work["close"], 14)
        work["vol_avg20"] = work["volume"].rolling(window=20, min_periods=1).mean()
        work["ema_slope"] = work["ema20"].diff().fillna(0.0)

        latest = work.iloc[-1]
        close = self._to_float(latest.get("close"))
        high = self._to_float(latest.get("high"))
        low = self._to_float(latest.get("low"))
        volume = self._to_float(latest.get("volume"))
        ema20 = self._to_float(latest.get("ema20"), close)
        rsi14 = self._to_float(latest.get("rsi14"), 50.0)
        vol_avg20 = self._to_float(latest.get("vol_avg20"), 0.0)
        ema_slope = self._to_float(latest.get("ema_slope"), 0.0)

        volume_spike = volume > 1.5 * max(vol_avg20, 1.0)
        near_day_high = close >= (0.8 * (high - low) + low)
        score = 0.0
        reasons: list[str] = []

        if close > ema20:
            score += 25
            reasons.append("close_above_ema20")
        if ema_slope > 0:
            score += 20
            reasons.append("ema20_rising")
        if volume_spike:
            score += 25
            reasons.append("volume_spike")
        if 55 <= rsi14 <= 70:
            score += 20
            reasons.append("rsi_in_momentum_band")
        if near_day_high:
            score += 10
            reasons.append("close_near_day_high")

        score = min(100.0, score)
        buy_condition = close > ema20 and ema_slope > 0 and volume_spike and rsi14 > 55

        timestamp = latest.get("timestamp")
        if isinstance(timestamp, pd.Timestamp):
            candle_time = timestamp.to_pydatetime().replace(tzinfo=None)
        elif isinstance(timestamp, datetime):
            candle_time = timestamp.replace(tzinfo=None)
        else:
            candle_time = datetime.utcnow()

        features_json = {
            "close": round(close, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "volume": round(volume, 4),
            "ema20": round(ema20, 4),
            "ema_slope": round(ema_slope, 6),
            "rsi14": round(rsi14, 4),
            "vol_avg20": round(vol_avg20, 4),
            "volume_spike": volume_spike,
            "near_day_high": near_day_high,
            "score": score,
        }
        reasons_json = {
            "rules_triggered": reasons,
            "buy_condition": buy_condition,
            "interval": interval,
        }

        summary_text = (
            f"{symbol}: score={score:.1f}, close={close:.2f}, ema20={ema20:.2f}, "
            f"ema_slope={ema_slope:.4f}, rsi14={rsi14:.2f}, volume_ratio="
            f"{(volume / max(vol_avg20, 1.0)):.2f}."
        )

        return SymbolSnapshot(
            symbol=symbol,
            candle_time=candle_time,
            open=self._to_float(latest.get("open"), close),
            high=high,
            low=low,
            close=close,
            volume=volume,
            ema20=ema20,
            rsi14=rsi14,
            vol_avg20=vol_avg20,
            ema_slope=ema_slope,
            score=score,
            buy_condition=buy_condition,
            reasons_json=reasons_json,
            features_json=features_json,
            summary_text=summary_text,
        )

    def analyze_symbols(self, symbols: list[str], interval: str = "5m", period: str = "5d") -> list[SymbolSnapshot]:
        snapshots: list[SymbolSnapshot] = []
        for symbol in symbols:
            snapshots.append(self.analyze_symbol(symbol=symbol, interval=interval, period=period))
        return snapshots
