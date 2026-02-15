from __future__ import annotations

from src.models.risk_snapshot import RiskSnapshot


class RiskService:
    def build_risk_snapshot(self, holdings: list[dict], portfolio_volatility: float = 0.0) -> RiskSnapshot:
        if not holdings:
            return RiskSnapshot(
                gross_exposure=0.0,
                net_exposure=0.0,
                top_5_concentration=0.0,
                portfolio_volatility=0.0,
                diversification_score=0.0,
            )

        total = sum(h["market_value"] for h in holdings)
        weights = sorted([(h["market_value"] / total) for h in holdings], reverse=True)
        top_5 = sum(weights[:5])
        diversification = max(0.0, round((1 - top_5) * 100, 2))

        return RiskSnapshot(
            gross_exposure=round(total, 2),
            net_exposure=round(total, 2),
            top_5_concentration=round(top_5, 4),
            portfolio_volatility=round(portfolio_volatility, 4),
            diversification_score=diversification,
        )
