from __future__ import annotations

import logging
from collections.abc import Iterable

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class YFinanceClient:
    def fetch_ohlcv(self, symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
        logger.info("Fetching yfinance candles", extra={"symbol": symbol, "interval": interval, "period": period})
        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, period=period, auto_adjust=False)
        if df.empty:
            raise ValueError(f"No OHLCV data returned for {symbol}")

        renamed = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        out = renamed.reset_index().rename(columns={"Datetime": "timestamp", "Date": "timestamp"})

        required_cols = ["timestamp", "open", "high", "low", "close"]
        missing = [c for c in required_cols if c not in out.columns]
        if missing:
            raise ValueError(f"Missing OHLC columns for {symbol}: {missing}")

        if "volume" not in out.columns:
            out["volume"] = 0
        out["volume"] = out["volume"].fillna(0)

        for col in ["open", "high", "low", "close", "volume"]:
            out[col] = pd.to_numeric(out[col], errors="coerce")

        out = out.dropna(subset=["open", "high", "low", "close"]).sort_values("timestamp").reset_index(drop=True)
        if out.empty:
            raise ValueError(f"No valid candles after cleaning for {symbol}")
        return out

    def fetch_daily(self, symbol: str, period: str = "6mo") -> pd.DataFrame:
        return self.fetch_ohlcv(symbol=symbol, interval="1d", period=period)

    def fetch_latest_candle(self, symbol: str, interval: str = "5m", period: str = "5d") -> dict:
        df = self.fetch_ohlcv(symbol=symbol, interval=interval, period=period)
        latest = df.iloc[-1]
        return {
            "timestamp": latest["timestamp"],
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "close": float(latest["close"]),
            "volume": float(latest.get("volume", 0.0)),
        }

    def fetch_many_ohlcv(
        self,
        symbols: Iterable[str],
        interval: str = "5m",
        period: str = "5d",
    ) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            clean = symbol.strip().upper()
            if not clean:
                continue
            try:
                out[clean] = self.fetch_ohlcv(symbol=clean, interval=interval, period=period)
            except Exception as exc:
                logger.warning("Skipping symbol due to yfinance fetch failure", extra={"symbol": clean, "error": str(exc)})
        return out
