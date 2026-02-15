from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class YFinanceClient:
    def fetch_ohlcv(self, symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
        logger.info("Fetching yfinance data", extra={"symbol": symbol, "interval": interval, "period": period})
        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, period=period, auto_adjust=False)
        if df.empty:
            raise ValueError(f"No OHLCV data returned for {symbol}")

        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        df = df.reset_index().rename(columns={"Datetime": "timestamp", "Date": "timestamp"})

        required_cols = ["timestamp", "open", "high", "low", "close"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing OHLC columns for {symbol}: {missing}")

        if "volume" not in df.columns:
            df["volume"] = 0
        df["volume"] = df["volume"].fillna(0)

        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"])

        if df.empty:
            raise ValueError(f"No valid candles after cleaning for {symbol}")

        return df
