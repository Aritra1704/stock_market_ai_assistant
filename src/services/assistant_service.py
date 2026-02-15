from __future__ import annotations

from src.services.analytics_service import AnalyticsService
from src.services.market_service import MarketService
from src.services.portfolio_service import PortfolioService
from src.services.risk_service import RiskService


class AssistantService:
    def __init__(self) -> None:
        self.portfolio_service = PortfolioService()
        self.market_service = MarketService()
        self.analytics_service = AnalyticsService()
        self.risk_service = RiskService()

    def portfolio_brief(self) -> dict:
        summary = self.portfolio_service.summary()
        risk = self.risk_service.build_risk_snapshot(summary["holdings"]) 
        return {"summary": summary, "risk": risk.model_dump()}

    def analyze_stock(self, symbol: str) -> dict:
        quote = self.market_service.get_quote(symbol)
        hist = self.market_service.get_historical(symbol, days=180)
        close = hist["close"]
        returns = self.analytics_service.compute_returns(close, window=20)
        return {
            "symbol": symbol,
            "quote": quote,
            "returns": returns,
            "max_drawdown": self.analytics_service.max_drawdown(close),
            "momentum_30d": self.analytics_service.momentum(close, lookback=30),
            "annualized_volatility": self.analytics_service.annualized_volatility(close),
        }

    def chat(self, query: str) -> dict:
        lowered = query.lower()
        if "portfolio" in lowered or "risk" in lowered:
            payload = self.portfolio_brief()
            summary = payload["summary"]
            risk = payload["risk"]
            message = (
                f"Portfolio value is {summary['total_value']:.2f} with PnL {summary['total_pnl']:.2f}. "
                f"Top concentration is {risk['top_5_concentration'] * 100:.2f}% across top holdings."
            )
            return {"answer": message, "data": payload}

        symbol = next((token for token in query.upper().split() if token.isalpha() and len(token) >= 3), "TCS")
        analysis = self.analyze_stock(symbol)
        message = (
            f"{symbol}: price {analysis['quote']['ltp']}, "
            f"30d momentum {analysis['momentum_30d']:.2%}, "
            f"annualized volatility {analysis['annualized_volatility']:.2%}."
        )
        return {"answer": message, "data": analysis}
