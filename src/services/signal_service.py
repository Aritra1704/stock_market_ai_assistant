from __future__ import annotations

from src.strategies.intraday_v1 import generate_signal


class SignalService:
    def decide(self, trend: str, rsi14: float) -> dict:
        side, confidence, rationale = generate_signal(trend=trend, rsi14=rsi14)
        return {
            "signal": side,
            "confidence": confidence,
            "rationale": rationale,
        }
