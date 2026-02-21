from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from src.strategies.intraday_v1 import generate_signal as intraday_generate_signal
from src.strategies.swing_v1 import SwingSignal, generate_signal as swing_generate_signal

IST = ZoneInfo("Asia/Kolkata")


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


@dataclass
class MomentumDecision:
    action: str
    reasons_json: dict
    features_json: dict
    summary_text: str
    stop_price: float | None = None
    target_price: float | None = None


class MomentumSignalService:
    @staticmethod
    def _parse_time_exit(hhmm: str) -> time:
        parts = hhmm.strip().split(":")
        if len(parts) != 2:
            return time(hour=15, minute=20)
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return time(hour=15, minute=20)
        hour = min(max(hour, 0), 23)
        minute = min(max(minute, 0), 59)
        return time(hour=hour, minute=minute)

    @staticmethod
    def compute_risk_prices(entry_price: float, stop_pct: float, target_pct: float) -> tuple[float, float]:
        stop_price = round(entry_price * (1 - (stop_pct / 100.0)), 4)
        target_price = round(entry_price * (1 + (target_pct / 100.0)), 4)
        return stop_price, target_price

    def should_buy(self, snapshot) -> bool:
        return bool(snapshot.buy_condition)

    def should_sell(
        self,
        last_price: float,
        stop_price: float,
        target_price: float,
        now_ist: datetime,
        time_exit_hhmm: str,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if last_price <= stop_price:
            reasons.append("stop_loss_hit")
        if last_price >= target_price:
            reasons.append("target_hit")
        if now_ist.time() >= self._parse_time_exit(time_exit_hhmm):
            reasons.append("time_exit_hit")
        return (len(reasons) > 0), reasons

    def entry_decision(self, symbol: str, snapshot, stop_pct: float, target_pct: float) -> MomentumDecision:
        stop_price, target_price = self.compute_risk_prices(snapshot.close, stop_pct=stop_pct, target_pct=target_pct)
        reasons = list(snapshot.reasons_json.get("rules_triggered", []))
        summary_text = (
            f"BUY {symbol} because close={snapshot.close:.2f} > ema20={snapshot.ema20:.2f}, "
            f"ema_slope={snapshot.ema_slope:.4f}, rsi14={snapshot.rsi14:.2f}, score={snapshot.score:.1f}."
        )
        return MomentumDecision(
            action="BUY",
            reasons_json={"rules_triggered": reasons, "rule_set": "momentum_v1"},
            features_json=snapshot.features_json,
            summary_text=summary_text,
            stop_price=stop_price,
            target_price=target_price,
        )

    def hold_decision(self, symbol: str, snapshot, reason: str) -> MomentumDecision:
        return MomentumDecision(
            action="HOLD",
            reasons_json={"rules_triggered": [reason], "rule_set": "momentum_v1"},
            features_json=snapshot.features_json,
            summary_text=f"HOLD {symbol}: {reason}. score={snapshot.score:.1f}.",
        )

    def exit_decision(self, symbol: str, snapshot, reasons: list[str]) -> MomentumDecision:
        return MomentumDecision(
            action="SELL",
            reasons_json={"rules_triggered": reasons, "rule_set": "momentum_v1"},
            features_json=snapshot.features_json,
            summary_text=f"SELL {symbol}: {', '.join(reasons)} at {snapshot.close:.2f}.",
        )
