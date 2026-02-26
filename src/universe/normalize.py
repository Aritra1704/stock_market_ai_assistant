from __future__ import annotations

SECTOR_MAPPING: dict[str, str] = {
    "Financial Services": "BANKING",
    "Technology": "IT",
    "Healthcare": "PHARMA",
    "Consumer Defensive": "FMCG",
    "Consumer Cyclical": "CONSUMER",
    "Industrials": "INDUSTRIALS",
    "Energy": "ENERGY",
    "Basic Materials": "METALS",
    "Real Estate": "REALTY",
    "Utilities": "UTILITIES",
    "Communication Services": "MEDIA",
}


def normalize_sector(yahoo_sector: str | None, yahoo_industry: str | None) -> tuple[str, float]:
    _ = yahoo_industry
    clean_sector = (yahoo_sector or "").strip()
    if not clean_sector:
        return "UNKNOWN", 0.2

    mapped = SECTOR_MAPPING.get(clean_sector)
    if mapped:
        return mapped, 0.8

    return "UNKNOWN", 0.5
