from __future__ import annotations

from dataclasses import asdict, dataclass

from src.integrations.market_data.yfinance_client import YFinanceClient
from src.utils.indicators import attach_indicators


@dataclass
class TrendAnalysis:
    symbol: str
    interval: str
    period: str
    latest_candle: dict
    indicators: dict
    trend: str
    explanation: str


class TrendService:
    def __init__(self, market_client: YFinanceClient | None = None) -> None:
        self.market_client = market_client or YFinanceClient()

    def analyze(self, symbol: str, interval: str = "5m", period: str = "5d") -> TrendAnalysis:
        raw = self.market_client.fetch_ohlcv(symbol=symbol, interval=interval, period=period)
        data = attach_indicators(raw)

        if len(data) < 21:
            raise ValueError(f"Not enough candles to compute trend for {symbol}")

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        close = float(latest["close"])
        sma20 = float(latest["sma20"])
        ema20 = float(latest["ema20"])
        rsi14 = float(latest["rsi14"])
        atr14 = float(latest["atr14"])
        ema_up = float(latest["ema20"]) > float(prev["ema20"])

        if close > sma20 and ema_up and rsi14 > 55:
            trend = "UPTREND"
            explanation = "Price above SMA20, EMA20 rising, RSI above 55"
        elif close < sma20 and not ema_up and rsi14 < 45:
            trend = "DOWNTREND"
            explanation = "Price below SMA20, EMA20 falling, RSI below 45"
        else:
            trend = "SIDEWAYS"
            explanation = "Mixed momentum signals without directional confirmation"

        latest_candle = {
            "timestamp": str(latest["timestamp"]),
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "close": close,
            "volume": float(latest.get("volume", 0.0)),
        }
        indicators = {
            "SMA_20": sma20,
            "EMA_20": ema20,
            "RSI_14": rsi14,
            "ATR_14": atr14,
        }

        return TrendAnalysis(
            symbol=symbol,
            interval=interval,
            period=period,
            latest_candle=latest_candle,
            indicators=indicators,
            trend=trend,
            explanation=explanation,
        )

    @staticmethod
    def as_dict(analysis: TrendAnalysis) -> dict:
        return asdict(analysis)
