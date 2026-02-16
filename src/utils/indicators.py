from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    gain_series = pd.Series(gain, index=series.index)
    loss_series = pd.Series(loss, index=series.index)

    avg_gain = gain_series.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss_series.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_prev_close = (df["high"] - df["close"].shift(1)).abs()
    low_prev_close = (df["low"] - df["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return true_range.rolling(window=period, min_periods=period).mean().bfill().fillna(0.0)


def macd(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    macd_line = ema(series, 12) - ema(series, 26)
    signal_line = ema(macd_line, 9)
    return macd_line, signal_line


def attach_intraday_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["sma20"] = sma(out["close"], 20)
    out["ema20"] = ema(out["close"], 20)
    out["rsi14"] = rsi(out["close"], 14)
    out["atr14"] = atr(out, 14)
    return out


def attach_swing_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = attach_intraday_indicators(df)
    out["sma50"] = sma(out["close"], 50)
    out["ema50"] = ema(out["close"], 50)
    macd_line, signal_line = macd(out["close"])
    out["macd"] = macd_line
    out["macd_signal"] = signal_line
    out["high20"] = out["high"].rolling(window=20, min_periods=20).max().shift(1)
    return out
