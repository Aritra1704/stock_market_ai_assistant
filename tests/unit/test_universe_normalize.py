from src.universe.normalize import normalize_sector


def test_normalize_sector_known_mapping() -> None:
    trading_sector, confidence = normalize_sector("Technology", "Software - Infrastructure")

    assert trading_sector == "IT"
    assert confidence == 0.8


def test_normalize_sector_unknown_mapping() -> None:
    trading_sector, confidence = normalize_sector("Aerospace", None)

    assert trading_sector == "UNKNOWN"
    assert confidence == 0.5


def test_normalize_sector_missing() -> None:
    trading_sector, confidence = normalize_sector(None, None)

    assert trading_sector == "UNKNOWN"
    assert confidence == 0.2
