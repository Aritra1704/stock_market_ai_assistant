from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from src.services.journal_service import TradingJournalService
from src.services.portfolio_service import IntradayPaperPortfolioService
from src.services.signal_service import MomentumSignalService


class RebalanceService:
    def __init__(
        self,
        portfolio_service: IntradayPaperPortfolioService | None = None,
        journal_service: TradingJournalService | None = None,
        signal_service: MomentumSignalService | None = None,
    ) -> None:
        self.portfolio_service = portfolio_service or IntradayPaperPortfolioService()
        self.journal_service = journal_service or TradingJournalService()
        self.signal_service = signal_service or MomentumSignalService()

    @staticmethod
    def _improvement_pct(best_score: float, weakest_score: float) -> float:
        if weakest_score <= 0:
            return 100.0 if best_score > 0 else 0.0
        return ((best_score - weakest_score) / weakest_score) * 100.0

    def apply(
        self,
        db: Session,
        run_date: date,
        run_tick_id: int,
        ranked_items: list,
        snapshots_by_symbol: dict,
        config,
    ) -> int:
        open_positions = self.portfolio_service.get_open_positions(db, run_date)
        if not open_positions:
            return 0

        score_by_symbol = {item.symbol: float(item.score) for item in ranked_items}
        held_symbols = {pos.symbol for pos in open_positions}
        candidates = [item for item in ranked_items if item.symbol not in held_symbols and item.snapshot.buy_condition]
        if not candidates:
            return 0

        weakest = min(open_positions, key=lambda pos: score_by_symbol.get(pos.symbol, 0.0))
        weakest_score = float(score_by_symbol.get(weakest.symbol, 0.0))

        best_candidate = max(candidates, key=lambda item: float(item.score))
        best_score = float(best_candidate.score)
        improvement = self._improvement_pct(best_score=best_score, weakest_score=weakest_score)

        partial_threshold = float(config.rebalance_partial_threshold)
        full_threshold = float(config.rebalance_full_threshold)
        partial_fraction = float(config.rebalance_partial_fraction)

        if improvement <= partial_threshold:
            return 0

        full_replace = improvement > full_threshold
        if full_replace:
            fraction = 1.0
        else:
            fraction = partial_fraction
            if len(open_positions) >= int(config.max_positions):
                # Partial rebalance would increase simultaneous position count.
                return 0

        sell_snapshot = snapshots_by_symbol.get(weakest.symbol)
        sell_price = float(sell_snapshot.close if sell_snapshot is not None else weakest.entry_price)
        sell_qty = round(float(weakest.qty) * fraction, 6)
        if sell_qty <= 0:
            return 0

        sell_reason = "rebalance_full" if full_replace else "rebalance_partial"
        sell_summary = (
            f"{sell_reason}: weakest={weakest.symbol}({weakest_score:.2f}) -> "
            f"best={best_candidate.symbol}({best_score:.2f}), improvement={improvement:.2f}%"
        )
        sell_features = {
            "weakest_symbol": weakest.symbol,
            "weakest_score": weakest_score,
            "best_symbol": best_candidate.symbol,
            "best_score": best_score,
            "improvement_pct": improvement,
        }
        sell_decision = self.journal_service.add_trade_decision(
            db=db,
            run_tick_id=run_tick_id,
            symbol=weakest.symbol,
            action="SELL",
            intended_qty=sell_qty,
            intended_price=sell_price,
            stop_price=None,
            target_price=None,
            reasons_json={"rules_triggered": [sell_reason], "rule_set": "momentum_v1"},
            features_json=sell_features,
            summary_text=sell_summary,
        )
        sell_result = self.portfolio_service.close_position(
            db=db,
            position=weakest,
            qty=sell_qty,
            price=sell_price,
            decision_id=sell_decision.id,
            exit_reason=sell_reason,
        )

        proceeds = float(sell_result.get("proceeds", 0.0))
        if proceeds <= 0:
            return 1

        entry_count = self.portfolio_service.entries_for_symbol(db, run_date, best_candidate.symbol)
        if entry_count >= int(config.max_entries_per_symbol_per_day):
            return 1

        buy_price = float(best_candidate.snapshot.close)
        buy_qty = self.portfolio_service.qty_from_cash(price=buy_price, cash=proceeds)
        if buy_qty <= 0:
            return 1

        stop_price, target_price = self.signal_service.compute_risk_prices(
            entry_price=buy_price,
            stop_pct=float(config.stop_pct),
            target_pct=float(config.target_pct),
        )
        buy_summary = (
            f"BUY {best_candidate.symbol} from rebalance proceeds {proceeds:.2f}; "
            f"score={best_score:.2f}, qty={buy_qty:.6f}."
        )
        buy_decision = self.journal_service.add_trade_decision(
            db=db,
            run_tick_id=run_tick_id,
            symbol=best_candidate.symbol,
            action="BUY",
            intended_qty=buy_qty,
            intended_price=buy_price,
            stop_price=stop_price,
            target_price=target_price,
            reasons_json={"rules_triggered": [sell_reason, "rebalance_candidate_best"], "rule_set": "momentum_v1"},
            features_json=best_candidate.features_json,
            summary_text=buy_summary,
        )
        self.portfolio_service.open_position(
            db=db,
            run_date=run_date,
            symbol=best_candidate.symbol,
            qty=buy_qty,
            price=buy_price,
            stop_price=stop_price,
            target_price=target_price,
            decision_id=buy_decision.id,
        )
        return 2
