from __future__ import annotations

import json
import logging
import time
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


class TaxonomyProviderError(RuntimeError):
    def __init__(self, symbol: str, message: str) -> None:
        super().__init__(message)
        self.symbol = symbol


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class YahooTaxonomyProvider:
    def __init__(self, max_retries: int = 2, backoff_seconds: float = 1.0) -> None:
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = max(0.0, backoff_seconds)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        clean = symbol.strip().upper()
        if not clean:
            return clean
        return clean if "." in clean else f"{clean}.NS"

    def get_taxonomy(self, symbol: str) -> dict[str, Any]:
        clean_symbol = self._normalize_symbol(symbol)
        if not clean_symbol:
            raise TaxonomyProviderError(symbol=symbol, message="Symbol cannot be empty")

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                info = yf.Ticker(clean_symbol).info or {}
                if not isinstance(info, dict):
                    info = {}

                raw_json = json.loads(json.dumps(info, default=str))
                return {
                    "symbol": clean_symbol,
                    "name": _clean_text(
                        info.get("longName")
                        or info.get("shortName")
                        or info.get("displayName")
                        or info.get("symbol")
                    ),
                    "yahoo_sector": _clean_text(info.get("sector")),
                    "yahoo_industry": _clean_text(info.get("industry")),
                    "raw_json": raw_json,
                }
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break

                sleep_for = self.backoff_seconds * (2**attempt)
                logger.warning(
                    "Yahoo taxonomy fetch failed, retrying",
                    extra={"symbol": clean_symbol, "attempt": attempt + 1, "error": str(exc)},
                )
                time.sleep(sleep_for)

        raise TaxonomyProviderError(
            symbol=clean_symbol,
            message=f"Failed to fetch Yahoo taxonomy for {clean_symbol}: {last_error}",
        )
