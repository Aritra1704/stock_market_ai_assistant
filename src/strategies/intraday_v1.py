from __future__ import annotations


def generate_signal(trend: str, rsi14: float) -> tuple[str, float, str]:
    if trend == "UPTREND" and rsi14 < 70:
        return "BUY", 0.7, "Trend up and RSI below overbought threshold"
    if trend == "DOWNTREND" and rsi14 > 30:
        return "SELL", 0.7, "Trend down and RSI above oversold threshold"
    return "HOLD", 0.5, "No clear directional edge"
