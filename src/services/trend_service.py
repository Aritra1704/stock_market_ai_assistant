from __future__ import annotations

from dataclasses import asdict, dataclass

from src.integrations.market_data.yfinance_client import YFinanceClient
from src.strategies.swing_v1 import compute_indicators as compute_swing_indicators
from src.utils.indicators import attach_intraday_indicators


@dataclass
class TrendAnalysis:
    symbol: str
    interval: str
    period: str
    latest_candle: dict
    indicators: dict
    trend: str
    explanation: str


@dataclass
class SwingTrendAnalysis:
    symbol: str
    interval: str
    period: str
    latest_candle: dict
    indicators: dict
    trend: str
    readiness_score: float
    explanation: str


class TrendService:
    def __init__(self, market_client: YFinanceClient | None = None) -> None:
        self.market_client = market_client or YFinanceClient()

    def analyze(self, symbol: str, interval: str = "5m", period: str = "5d") -> TrendAnalysis:
        raw = self.market_client.fetch_ohlcv(symbol=symbol, interval=interval, period=period)
        data = attach_intraday_indicators(raw)

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

    def analyze_swing(self, symbol: str, interval: str = "1d", period: str = "6mo") -> SwingTrendAnalysis:
        raw = self.market_client.fetch_ohlcv(symbol=symbol, interval=interval, period=period)
        data = compute_swing_indicators(raw)
        if len(data) < 60:
            raise ValueError(f"Not enough daily candles to compute swing trend for {symbol}")

        latest = data.iloc[-1]
        prev = data.iloc[-2]
        close = float(latest["close"])
        sma20 = float(latest["sma20"])
        sma50 = float(latest["sma50"])
        ema20 = float(latest["ema20"])
        ema50 = float(latest["ema50"])
        rsi14 = float(latest["rsi14"])
        atr14 = float(latest["atr14"])
        macd = float(latest["macd"])
        macd_signal = float(latest["macd_signal"])

        sma50_up = sma50 > float(prev["sma50"])
        uptrend = close > sma50 and sma50_up
        if uptrend and 50 <= rsi14 <= 70:
            trend = "UPTREND"
            explanation = "Close above rising SMA50 with healthy RSI"
        elif close < sma20 and rsi14 < 45:
            trend = "DOWNTREND"
            explanation = "Close below SMA20 and weak RSI"
        else:
            trend = "SIDEWAYS"
            explanation = "Daily trend not aligned for strong swing bias"

        readiness = 0.0
        readiness += 0.35 if uptrend else 0.1
        readiness += 0.25 if 50 <= rsi14 <= 70 else 0.1
        readiness += 0.2 if macd > macd_signal else 0.05
        readiness += 0.2 if close > ema20 else 0.05
        readiness_score = round(min(readiness, 1.0), 2)

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
            "SMA_50": sma50,
            "EMA_20": ema20,
            "EMA_50": ema50,
            "RSI_14": rsi14,
            "ATR_14": atr14,
            "MACD": macd,
            "MACD_SIGNAL": macd_signal,
        }

        return SwingTrendAnalysis(
            symbol=symbol,
            interval=interval,
            period=period,
            latest_candle=latest_candle,
            indicators=indicators,
            trend=trend,
            readiness_score=readiness_score,
            explanation=explanation,
        )

    @staticmethod
    def as_dict(analysis: TrendAnalysis | SwingTrendAnalysis) -> dict:
        return asdict(analysis)
