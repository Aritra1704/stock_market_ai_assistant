from __future__ import annotations

from dataclasses import dataclass

from src.services.market_data_service import MarketDataService, SymbolSnapshot


@dataclass
class RankingItem:
    symbol: str
    rank: int
    score: float
    reasons_json: dict
    features_json: dict
    summary_text: str
    snapshot: SymbolSnapshot


class RankingService:
    def __init__(self, market_data_service: MarketDataService | None = None) -> None:
        self.market_data_service = market_data_service or MarketDataService()

    def rank_symbols(
        self,
        symbols: list[str],
        top_n: int = 5,
        interval: str = "5m",
        period: str = "5d",
    ) -> list[RankingItem]:
        scored: list[SymbolSnapshot] = []
        for symbol in symbols:
            try:
                scored.append(
                    self.market_data_service.analyze_symbol(symbol=symbol, interval=interval, period=period)
                )
            except Exception:
                continue

        scored.sort(key=lambda item: item.score, reverse=True)
        ranked: list[RankingItem] = []
        for idx, snapshot in enumerate(scored[:max(1, top_n)], start=1):
            ranked.append(
                RankingItem(
                    symbol=snapshot.symbol,
                    rank=idx,
                    score=float(snapshot.score),
                    reasons_json=snapshot.reasons_json,
                    features_json=snapshot.features_json,
                    summary_text=snapshot.summary_text,
                    snapshot=snapshot,
                )
            )
        return ranked
