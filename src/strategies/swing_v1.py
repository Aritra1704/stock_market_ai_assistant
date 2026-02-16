from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.utils.indicators import attach_swing_indicators


@dataclass
class SwingSignal:
    action: str
    confidence: float
    rationale: str
    params: dict


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    return attach_swing_indicators(df)


def generate_signal(df: pd.DataFrame, entry_style: str = "breakout", horizon_days: int = 20) -> SwingSignal:
    data = compute_indicators(df)
    if len(data) < 60:
        return SwingSignal("HOLD", 0.4, "Not enough daily candles for stable swing setup", {"horizon_days": horizon_days})

    latest = data.iloc[-1]
    prev = data.iloc[-2]

    close = float(latest["close"])
    ema20 = float(latest["ema20"])
    sma50 = float(latest["sma50"])
    prev_sma50 = float(prev["sma50"])
    rsi14 = float(latest["rsi14"])
    atr14 = max(float(latest["atr14"]), 0.01)

    uptrend = close > sma50 and sma50 > prev_sma50
    near_ema20 = abs(close - ema20) / max(ema20, 1e-9) <= 0.012
    breakout_high = float(latest.get("high20", 0.0) or 0.0)

    if uptrend and entry_style == "breakout" and breakout_high > 0 and close > breakout_high and 50 <= rsi14 <= 70:
        trigger = round(breakout_high * 1.002, 4)
        stop_loss = round(trigger - 1.5 * atr14, 4)
        take_profit = round(trigger + 2.0 * atr14, 4)
        return SwingSignal(
            "BUY_SETUP",
            0.76,
            "Breakout above 20-day high in uptrend with healthy RSI",
            {
                "entry_style": "breakout",
                "gtt_buy_trigger": trigger,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "horizon_days": horizon_days,
            },
        )

    if uptrend and entry_style in {"pullback", "breakout"} and near_ema20 and rsi14 > 45:
        trigger = round(max(ema20 * 1.001, close * 1.001), 4)
        stop_loss = round(trigger - 1.5 * atr14, 4)
        take_profit = round(trigger + 2.0 * atr14, 4)
        return SwingSignal(
            "BUY_SETUP",
            0.68,
            "Pullback near EMA20 in uptrend with RSI support",
            {
                "entry_style": "pullback",
                "gtt_buy_trigger": trigger,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "horizon_days": horizon_days,
            },
        )

    return SwingSignal("HOLD", 0.5, "No swing entry setup", {"horizon_days": horizon_days})


def generate_exit_signal(
    latest_row: pd.Series,
    entry_price: float,
    trailing_stop: float,
    take_profit: float,
    holding_days: int,
    horizon_days: int,
) -> SwingSignal:
    close = float(latest_row["close"])
    atr14 = max(float(latest_row.get("atr14", 0.0)), 0.01)
    new_trailing = max(trailing_stop, close - 1.5 * atr14)

    if holding_days > horizon_days:
        return SwingSignal("EXIT", 0.7, "Time-stop reached for swing horizon", {"new_trailing_stop": new_trailing})

    if close >= take_profit:
        return SwingSignal("EXIT", 0.74, "Take-profit reached", {"new_trailing_stop": new_trailing})

    if close < new_trailing:
        return SwingSignal("EXIT", 0.72, "Close breached trailing stop", {"new_trailing_stop": new_trailing})

    return SwingSignal("HOLD", 0.55, "Position remains within swing exit bounds", {"new_trailing_stop": new_trailing})
