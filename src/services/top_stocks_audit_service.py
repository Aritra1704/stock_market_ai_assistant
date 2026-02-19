from __future__ import annotations

import csv
import logging
import math
from datetime import date, timedelta
from io import StringIO
from urllib.request import Request, urlopen

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.config import settings
from src.data.nifty100_fallback import NIFTY100_FALLBACK_SYMBOLS
from src.integrations.market_data.yfinance_client import YFinanceClient
from src.models.tables import TopStockAudit
from src.utils.indicators import attach_swing_indicators
from src.utils.time import today_utc

logger = logging.getLogger(__name__)


class TopStocksAuditService:
    def __init__(self, market_client: YFinanceClient | None = None) -> None:
        self.market_client = market_client or YFinanceClient()

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        clean = mode.strip().upper()
        if clean not in {"INTRADAY", "SWING"}:
            raise ValueError(f"Unsupported mode: {mode}")
        return clean

    @staticmethod
    def _to_yahoo_symbol(symbol: str) -> str:
        clean = symbol.strip().upper()
        if not clean:
            return clean
        return clean if "." in clean else f"{clean}.NS"

    @staticmethod
    def _as_float(value, default: float = 0.0) -> float:
        try:
            out = float(value)
        except (TypeError, ValueError):
            return default
        if math.isnan(out) or math.isinf(out):
            return default
        return out

    def _fetch_live_universe_symbols(self) -> list[str]:
        req = Request(
            settings.audit_universe_csv_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/csv,*/*",
            },
        )
        with urlopen(req, timeout=settings.audit_universe_timeout_seconds) as resp:
            payload = resp.read().decode("utf-8", errors="ignore").lstrip("\ufeff")

        rows = csv.DictReader(StringIO(payload))
        symbols: list[str] = []
        seen: set[str] = set()
        for row in rows:
            raw_symbol = str(row.get("Symbol", "")).strip()
            if not raw_symbol:
                continue
            symbol = self._to_yahoo_symbol(raw_symbol)
            if symbol in seen:
                continue
            seen.add(symbol)
            symbols.append(symbol)
        return symbols

    def _get_universe_symbols(self) -> list[str]:
        limit = max(1, settings.audit_top_stocks_limit)
        live_symbols: list[str] = []
        try:
            live_symbols = self._fetch_live_universe_symbols()
        except Exception as exc:
            logger.warning("Live top-stock universe fetch failed, using fallback", extra={"error": str(exc)})

        combined: list[str] = []
        seen: set[str] = set()
        for symbol in [*live_symbols, *NIFTY100_FALLBACK_SYMBOLS]:
            clean = self._to_yahoo_symbol(symbol)
            if not clean or clean in seen:
                continue
            seen.add(clean)
            combined.append(clean)
            if len(combined) >= limit:
                break
        return combined

    def _collect_metrics(self, symbol: str) -> dict:
        try:
            raw = self.market_client.fetch_ohlcv(symbol=symbol, interval="1d", period="6mo")
            latest = raw.iloc[-1]
            close = self._as_float(latest.get("close"))
            volume = self._as_float(latest.get("volume"))
            turnover = round(close * volume, 4)

            data = attach_swing_indicators(raw)
            if len(data) < 2:
                raise ValueError(f"Insufficient candles for swing metrics: {symbol}")

            latest_i = data.iloc[-1]
            prev_i = data.iloc[-2]

            sma20 = self._as_float(latest_i.get("sma20"), close)
            sma50 = self._as_float(latest_i.get("sma50"), close)
            prev_sma50 = self._as_float(prev_i.get("sma50"), sma50)
            ema20 = self._as_float(latest_i.get("ema20"), close)
            rsi14 = self._as_float(latest_i.get("rsi14"), 50.0)
            macd = self._as_float(latest_i.get("macd"), 0.0)
            macd_signal = self._as_float(latest_i.get("macd_signal"), 0.0)

            uptrend = close > sma50 and sma50 > prev_sma50
            readiness = 0.0
            readiness += 0.35 if uptrend else 0.1
            readiness += 0.25 if 50 <= rsi14 <= 70 else 0.1
            readiness += 0.2 if macd > macd_signal else 0.05
            readiness += 0.2 if close > ema20 else 0.05
            readiness_score = round(min(readiness, 1.0), 4)

            if uptrend and 50 <= rsi14 <= 70:
                trend = "UPTREND"
            elif close < sma20 and rsi14 < 45:
                trend = "DOWNTREND"
            else:
                trend = "SIDEWAYS"

            return {
                "symbol": symbol,
                "close": close,
                "volume": volume,
                "turnover": turnover,
                "readiness_score": readiness_score,
                "trend": trend,
                "error": None,
            }
        except Exception as exc:
            logger.warning("Top-stock metric collection failed", extra={"symbol": symbol, "error": str(exc)})
            return {
                "symbol": symbol,
                "close": 0.0,
                "volume": 0.0,
                "turnover": -1.0,
                "readiness_score": -1.0,
                "trend": "UNKNOWN",
                "error": str(exc),
            }

    def _rows_for_mode(self, metrics: list[dict], mode: str) -> list[dict]:
        normalized = self._normalize_mode(mode)
        items = sorted(metrics, key=lambda item: item["symbol"])
        if normalized == "INTRADAY":
            items.sort(key=lambda item: (item["turnover"], item["volume"]), reverse=True)
            metric_name = "turnover"
            score_key = "turnover"
        else:
            items.sort(key=lambda item: (item["readiness_score"], item["turnover"]), reverse=True)
            metric_name = "readiness_score"
            score_key = "readiness_score"

        rows: list[dict] = []
        for idx, item in enumerate(items[: settings.audit_top_stocks_limit], start=1):
            rows.append(
                {
                    "rank": idx,
                    "symbol": item["symbol"],
                    "score": self._as_float(item.get(score_key)),
                    "metric": metric_name,
                    "details": {
                        "turnover": self._as_float(item.get("turnover")),
                        "readiness_score": self._as_float(item.get("readiness_score")),
                        "close": self._as_float(item.get("close")),
                        "volume": self._as_float(item.get("volume")),
                        "trend": item.get("trend"),
                        "source": "yfinance",
                        "error": item.get("error"),
                    },
                }
            )
        return rows

    def _replace_mode_rows(self, db: Session, run_date: date, mode: str, rows: list[dict]) -> None:
        normalized = self._normalize_mode(mode)
        db.execute(delete(TopStockAudit).where(TopStockAudit.date == run_date, TopStockAudit.mode == normalized))

        for row in rows:
            db.add(
                TopStockAudit(
                    date=run_date,
                    mode=normalized,
                    rank=row["rank"],
                    symbol=row["symbol"],
                    score=row["score"],
                    metric=row["metric"],
                    details_json=row["details"],
                )
            )

    def _build_metrics(self) -> list[dict]:
        symbols = self._get_universe_symbols()
        return [self._collect_metrics(symbol) for symbol in symbols]

    def refresh_mode(self, db: Session, run_date: date, mode: str) -> list[TopStockAudit]:
        normalized = self._normalize_mode(mode)
        metrics = self._build_metrics()
        ranked_rows = self._rows_for_mode(metrics, normalized)
        self._replace_mode_rows(db, run_date, normalized, ranked_rows)
        db.commit()
        return self.get_mode_rows(db, run_date, normalized)

    def refresh_modes(self, db: Session, run_date: date, modes: list[str]) -> dict[str, list[TopStockAudit]]:
        normalized_modes = [self._normalize_mode(mode) for mode in modes]
        metrics = self._build_metrics()
        for mode in normalized_modes:
            ranked_rows = self._rows_for_mode(metrics, mode)
            self._replace_mode_rows(db, run_date, mode, ranked_rows)
        db.commit()
        return {mode: self.get_mode_rows(db, run_date, mode) for mode in normalized_modes}

    def get_mode_rows(self, db: Session, run_date: date, mode: str) -> list[TopStockAudit]:
        normalized = self._normalize_mode(mode)
        return db.execute(
            select(TopStockAudit)
            .where(TopStockAudit.date == run_date, TopStockAudit.mode == normalized)
            .order_by(TopStockAudit.rank.asc())
        ).scalars().all()

    def get_or_build_mode_rows(
        self,
        db: Session,
        run_date: date,
        mode: str,
        *,
        force_refresh: bool = False,
        build_if_missing: bool = True,
    ) -> list[TopStockAudit]:
        existing = self.get_mode_rows(db, run_date, mode)
        if force_refresh:
            return self.refresh_mode(db, run_date, mode)
        if len(existing) >= settings.audit_top_stocks_limit:
            return existing
        if build_if_missing:
            return self.refresh_mode(db, run_date, mode)
        return existing

    def has_complete_snapshot(self, db: Session, run_date: date, mode: str) -> bool:
        return len(self.get_mode_rows(db, run_date, mode)) >= settings.audit_top_stocks_limit

    def cleanup_expired(self, db: Session, retention_days: int | None = None) -> int:
        days = retention_days if retention_days is not None else settings.audit_retention_days
        cutoff = today_utc() - timedelta(days=max(1, days))
        result = db.execute(delete(TopStockAudit).where(TopStockAudit.date < cutoff))
        db.commit()
        return int(result.rowcount or 0)
