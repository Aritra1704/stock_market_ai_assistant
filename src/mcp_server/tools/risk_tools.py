from src.services.portfolio_service import PortfolioService
from src.services.risk_service import RiskService


portfolio_service = PortfolioService()
risk_service = RiskService()


def risk_summary() -> dict:
    summary = portfolio_service.summary()
    risk = risk_service.build_risk_snapshot(summary["holdings"])
    return risk.model_dump()
