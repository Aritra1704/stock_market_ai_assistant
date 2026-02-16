from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_ctx(tmp_path, monkeypatch) -> Generator[dict, None, None]:
    import src.models.db as db_module
    from src.models.db import Base

    db_file = tmp_path / "test.db"
    test_url = f"sqlite:///{db_file}"
    engine = create_engine(test_url, connect_args={"check_same_thread": False}, future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(db_module, "engine", engine, raising=False)
    monkeypatch.setattr(db_module, "SessionLocal", TestingSessionLocal, raising=False)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    from src.app import app

    with TestClient(app) as client:
        yield {
            "client": client,
            "session_local": TestingSessionLocal,
            "engine": engine,
        }

    Base.metadata.drop_all(bind=engine)
