from __future__ import annotations

from src.strategies.intraday_v1 import generate_signal as intraday_generate_signal
from src.strategies.swing_v1 import SwingSignal, generate_signal as swing_generate_signal


class SignalService:
    def decide_intraday(self, trend: str, rsi14: float) -> dict:
        side, confidence, rationale = intraday_generate_signal(trend=trend, rsi14=rsi14)
        return {
            "signal": side,
            "confidence": confidence,
            "rationale": rationale,
        }

    def decide_swing(self, df, entry_style: str = "breakout", horizon_days: int = 20) -> SwingSignal:
        return swing_generate_signal(df=df, entry_style=entry_style, horizon_days=horizon_days)
