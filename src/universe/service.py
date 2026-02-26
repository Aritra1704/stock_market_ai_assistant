from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.universe.normalize import normalize_sector
from src.universe.providers.taxonomy_yahoo import TaxonomyProviderError, YahooTaxonomyProvider
from src.universe.repo import UniverseRepository

logger = logging.getLogger(__name__)

_VALID_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9&-]{0,28}(?:\.NS)?$")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class UniverseService:
    def __init__(
        self,
        db: Session,
        provider: YahooTaxonomyProvider | None = None,
        pause_between_batches_seconds: float = 0.25,
    ) -> None:
        self.db = db
        self.repo = UniverseRepository(db=db)
        self.provider = provider or YahooTaxonomyProvider()
        self.pause_between_batches_seconds = max(0.0, pause_between_batches_seconds)

    @staticmethod
    def _resolve_path(path: str) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return (_PROJECT_ROOT / candidate).resolve()

    @staticmethod
    def _normalize_file_symbol(raw_value: str) -> str | None:
        clean = raw_value.strip().upper()
        if not clean:
            return None
        if not _VALID_SYMBOL_PATTERN.fullmatch(clean):
            return None
        if "." not in clean:
            clean = f"{clean}.NS"
        elif not clean.endswith(".NS"):
            return None
        return clean

    @staticmethod
    def _chunk(items: list[str], size: int) -> list[list[str]]:
        safe_size = max(1, int(size))
        return [items[idx : idx + safe_size] for idx in range(0, len(items), safe_size)]

    def seed_from_file(self, path: str = "data/nifty100.txt", exchange: str = "NSE") -> dict[str, int]:
        file_path = self._resolve_path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Universe seed file not found: {file_path}")

        seeded = 0
        already_present = 0
        invalid_lines = 0

        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            symbol = self._normalize_file_symbol(stripped)
            if symbol is None:
                invalid_lines += 1
                continue

            _, created = self.repo.upsert_instrument(
                symbol=symbol,
                name=None,
                exchange=exchange,
                active=True,
            )
            if created:
                seeded += 1
            else:
                already_present += 1

        self.db.commit()
        return {
            "seeded": seeded,
            "already_present": already_present,
            "invalid_lines": invalid_lines,
        }

    def refresh_taxonomy(
        self,
        limit: int = 100,
        force: bool = False,
        max_age_days: int = 7,
        batch_size: int = 20,
    ) -> dict[str, int]:
        symbols = self.repo.get_symbols(limit=max(1, int(limit)))
        if not symbols:
            return {
                "processed": 0,
                "updated": 0,
                "skipped_recent": 0,
                "missing_sector": 0,
                "failed": 0,
            }

        summary = {
            "processed": 0,
            "updated": 0,
            "skipped_recent": 0,
            "missing_sector": 0,
            "failed": 0,
        }
        cutoff = datetime.utcnow() - timedelta(days=max(0, int(max_age_days)))

        symbol_batches = self._chunk(symbols, batch_size)
        total_batches = len(symbol_batches)
        for batch_idx, symbol_batch in enumerate(symbol_batches):
            for symbol in symbol_batch:
                summary["processed"] += 1

                taxonomy = self.repo.get_taxonomy(symbol)
                if (
                    not force
                    and taxonomy is not None
                    and taxonomy.updated_at is not None
                    and taxonomy.updated_at >= cutoff
                ):
                    summary["skipped_recent"] += 1
                    continue

                try:
                    tax = self.provider.get_taxonomy(symbol)
                    yahoo_sector = tax.get("yahoo_sector")
                    yahoo_industry = tax.get("yahoo_industry")
                    trading_sector, confidence = normalize_sector(yahoo_sector, yahoo_industry)

                    if not yahoo_sector:
                        summary["missing_sector"] += 1

                    self.repo.upsert_instrument(
                        symbol=symbol,
                        name=tax.get("name"),
                        exchange="NSE",
                        active=True,
                    )
                    self.repo.upsert_taxonomy(
                        symbol=symbol,
                        yahoo_sector=yahoo_sector,
                        yahoo_industry=yahoo_industry,
                        trading_sector=trading_sector,
                        confidence=confidence,
                        raw_json=tax.get("raw_json") or {},
                        provider="yahoo",
                    )
                    summary["updated"] += 1
                except TaxonomyProviderError as exc:
                    summary["failed"] += 1
                    logger.warning("Universe taxonomy fetch failed", extra={"symbol": symbol, "error": str(exc)})
                except Exception as exc:
                    summary["failed"] += 1
                    logger.exception("Universe taxonomy refresh error", extra={"symbol": symbol, "error": str(exc)})

            self.db.commit()
            has_more_batches = batch_idx < total_batches - 1
            if has_more_batches and self.pause_between_batches_seconds > 0:
                time.sleep(self.pause_between_batches_seconds)

        return summary

    def list_instruments(
        self,
        limit: int = 200,
        sector: str | None = None,
        missing_taxonomy: bool = False,
    ) -> list[dict[str, Any]]:
        return self.repo.list_instruments(limit=limit, sector=sector, missing_taxonomy=missing_taxonomy)

    def get_sector_counts(self) -> list[dict[str, Any]]:
        return self.repo.get_sector_counts()
