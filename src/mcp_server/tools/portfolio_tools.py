from src.services.portfolio_service import PortfolioService


portfolio_service = PortfolioService()


def get_portfolio_snapshot() -> dict:
    return portfolio_service.summary()
