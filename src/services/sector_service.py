from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import SectorSchedule, SectorUniverse


class SectorService:
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        clean = symbol.strip().upper()
        if not clean:
            return clean
        return clean if "." in clean else f"{clean}.NS"

    def upsert_schedule(self, db: Session, mappings: list[dict]) -> list[SectorSchedule]:
        updated: list[SectorSchedule] = []
        for item in mappings:
            weekday = int(item["weekday"])
            sector_name = str(item["sector_name"]).strip().upper()
            active = bool(item.get("active", True))

            row = db.execute(select(SectorSchedule).where(SectorSchedule.weekday == weekday)).scalar_one_or_none()
            if row is None:
                row = SectorSchedule(weekday=weekday, sector_name=sector_name, active=active)
                db.add(row)
            else:
                row.sector_name = sector_name
                row.active = active
                db.add(row)
            updated.append(row)

        db.commit()
        for row in updated:
            db.refresh(row)
        return updated

    def update_universe(
        self,
        db: Session,
        sector_name: str,
        add_symbols: list[str] | None = None,
        remove_symbols: list[str] | None = None,
    ) -> list[SectorUniverse]:
        sector = sector_name.strip().upper()
        add_symbols = add_symbols or []
        remove_symbols = remove_symbols or []

        for symbol in add_symbols:
            clean = self.normalize_symbol(symbol)
            if not clean:
                continue
            row = db.execute(
                select(SectorUniverse).where(SectorUniverse.sector_name == sector, SectorUniverse.symbol == clean)
            ).scalar_one_or_none()
            if row is None:
                db.add(SectorUniverse(sector_name=sector, symbol=clean, active=True))
            else:
                row.active = True
                db.add(row)

        for symbol in remove_symbols:
            clean = self.normalize_symbol(symbol)
            if not clean:
                continue
            row = db.execute(
                select(SectorUniverse).where(SectorUniverse.sector_name == sector, SectorUniverse.symbol == clean)
            ).scalar_one_or_none()
            if row is None:
                continue
            row.active = False
            db.add(row)

        db.commit()

        return db.execute(
            select(SectorUniverse)
            .where(SectorUniverse.sector_name == sector, SectorUniverse.active.is_(True))
            .order_by(SectorUniverse.symbol.asc())
        ).scalars().all()

    def get_sector_for_date(self, db: Session, trade_date: date, configured_sector: str | None = None) -> str | None:
        if configured_sector:
            return configured_sector.strip().upper()

        row = db.execute(
            select(SectorSchedule)
            .where(SectorSchedule.weekday == trade_date.weekday(), SectorSchedule.active.is_(True))
            .order_by(SectorSchedule.id.desc())
        ).scalar_one_or_none()
        if row is None:
            return None
        return row.sector_name

    def get_active_universe_symbols(self, db: Session, sector_name: str) -> list[str]:
        sector = sector_name.strip().upper()
        rows = db.execute(
            select(SectorUniverse.symbol)
            .where(SectorUniverse.sector_name == sector, SectorUniverse.active.is_(True))
            .order_by(SectorUniverse.symbol.asc())
        ).all()
        return [row[0] for row in rows]
