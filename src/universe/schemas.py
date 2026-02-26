from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UniverseSeedRequest(BaseModel):
    path: str = "data/nifty100.txt"


class UniverseSeedResponse(BaseModel):
    seeded: int
    already_present: int
    invalid_lines: int


class UniverseRefreshResponse(BaseModel):
    processed: int
    updated: int
    skipped_recent: int
    missing_sector: int
    failed: int


class UniverseInstrumentItem(BaseModel):
    symbol: str
    name: str | None = None
    trading_sector: str | None = None
    yahoo_sector: str | None = None
    yahoo_industry: str | None = None
    updated_at: datetime | None = None


class UniverseSectorCount(BaseModel):
    trading_sector: str
    count: int


class UniverseSectorsResponse(BaseModel):
    counts: list[UniverseSectorCount] = Field(default_factory=list)
