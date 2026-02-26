from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.tables import Instrument, InstrumentTaxonomy


class UniverseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        clean = symbol.strip().upper()
        if not clean:
            return clean
        return clean if "." in clean else f"{clean}.NS"

    def upsert_instrument(
        self,
        symbol: str,
        name: str | None = None,
        exchange: str = "NSE",
        active: bool = True,
    ) -> tuple[Instrument, bool]:
        clean_symbol = self.normalize_symbol(symbol)
        row = self.db.get(Instrument, clean_symbol)
        created = row is None
        clean_name = (name or "").strip() or None
        clean_exchange = (exchange or "NSE").strip().upper() or "NSE"

        if row is None:
            row = Instrument(
                symbol=clean_symbol,
                name=clean_name,
                exchange=clean_exchange,
                active=active,
            )
            self.db.add(row)
        else:
            if clean_name:
                row.name = clean_name
            row.exchange = clean_exchange
            row.active = active
            row.updated_at = datetime.utcnow()
            self.db.add(row)

        return row, created

    def upsert_taxonomy(
        self,
        symbol: str,
        yahoo_sector: str | None,
        yahoo_industry: str | None,
        trading_sector: str | None,
        confidence: float,
        raw_json: dict[str, Any] | None,
        provider: str = "yahoo",
    ) -> InstrumentTaxonomy:
        clean_symbol = self.normalize_symbol(symbol)
        row = self.db.get(InstrumentTaxonomy, clean_symbol)
        payload = raw_json or {}
        provider_name = (provider or "yahoo").strip().lower() or "yahoo"

        if row is None:
            row = InstrumentTaxonomy(
                symbol=clean_symbol,
                provider=provider_name,
                yahoo_sector=yahoo_sector,
                yahoo_industry=yahoo_industry,
                trading_sector=trading_sector,
                confidence=float(confidence),
                raw_json=payload,
                updated_at=datetime.utcnow(),
            )
            self.db.add(row)
        else:
            row.provider = provider_name
            row.yahoo_sector = yahoo_sector
            row.yahoo_industry = yahoo_industry
            row.trading_sector = trading_sector
            row.confidence = float(confidence)
            row.raw_json = payload
            row.updated_at = datetime.utcnow()
            self.db.add(row)

        return row

    def get_symbols(self, limit: int, only_missing: bool = False) -> list[str]:
        safe_limit = max(1, int(limit))
        stmt = select(Instrument.symbol).where(Instrument.active.is_(True))

        if only_missing:
            stmt = (
                stmt.outerjoin(InstrumentTaxonomy, InstrumentTaxonomy.symbol == Instrument.symbol).where(
                    InstrumentTaxonomy.symbol.is_(None)
                )
            )

        stmt = stmt.order_by(Instrument.symbol.asc()).limit(safe_limit)
        rows = self.db.execute(stmt).all()
        return [row[0] for row in rows]

    def get_taxonomy(self, symbol: str) -> InstrumentTaxonomy | None:
        clean_symbol = self.normalize_symbol(symbol)
        return self.db.get(InstrumentTaxonomy, clean_symbol)

    def mark_inactive(self, symbol: str) -> bool:
        clean_symbol = self.normalize_symbol(symbol)
        row = self.db.get(Instrument, clean_symbol)
        if row is None:
            return False
        row.active = False
        row.updated_at = datetime.utcnow()
        self.db.add(row)
        return True

    def list_instruments(
        self,
        limit: int = 200,
        sector: str | None = None,
        missing_taxonomy: bool = False,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))
        stmt = (
            select(
                Instrument.symbol,
                Instrument.name,
                InstrumentTaxonomy.trading_sector,
                InstrumentTaxonomy.yahoo_sector,
                InstrumentTaxonomy.yahoo_industry,
                InstrumentTaxonomy.updated_at,
            )
            .select_from(Instrument)
            .outerjoin(InstrumentTaxonomy, InstrumentTaxonomy.symbol == Instrument.symbol)
            .where(Instrument.active.is_(True))
        )

        if sector:
            stmt = stmt.where(InstrumentTaxonomy.trading_sector == sector.strip().upper())
        if missing_taxonomy:
            stmt = stmt.where(InstrumentTaxonomy.symbol.is_(None))

        rows = self.db.execute(stmt.order_by(Instrument.symbol.asc()).limit(safe_limit)).all()
        return [
            {
                "symbol": row.symbol,
                "name": row.name,
                "trading_sector": row.trading_sector,
                "yahoo_sector": row.yahoo_sector,
                "yahoo_industry": row.yahoo_industry,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    def get_sector_counts(self) -> list[dict[str, Any]]:
        trading_sector = func.coalesce(InstrumentTaxonomy.trading_sector, "UNKNOWN")
        stmt = (
            select(
                trading_sector.label("trading_sector"),
                func.count(Instrument.symbol).label("count"),
            )
            .select_from(Instrument)
            .outerjoin(InstrumentTaxonomy, InstrumentTaxonomy.symbol == Instrument.symbol)
            .where(Instrument.active.is_(True))
            .group_by(trading_sector)
            .order_by(trading_sector.asc())
        )
        rows = self.db.execute(stmt).all()
        return [{"trading_sector": row.trading_sector, "count": int(row.count)} for row in rows]
