from pydantic import BaseModel


class RiskSnapshot(BaseModel):
    gross_exposure: float
    net_exposure: float
    top_5_concentration: float
    portfolio_volatility: float
    diversification_score: float
