from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.models.db import get_db_session
from src.universe.schemas import (
    UniverseInstrumentItem,
    UniverseRefreshResponse,
    UniverseSeedRequest,
    UniverseSeedResponse,
    UniverseSectorsResponse,
)
from src.universe.service import UniverseService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/universe", tags=["universe"])


@router.post("/seed", response_model=UniverseSeedResponse)
def seed_universe(
    payload: UniverseSeedRequest | None = Body(default=None),
    db: Session = Depends(get_db_session),
):
    service = UniverseService(db=db)
    req = payload or UniverseSeedRequest()
    try:
        return UniverseSeedResponse(**service.seed_from_file(path=req.path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Universe seed failed", extra={"path": req.path, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Universe seed failed") from exc


@router.post("/refresh", response_model=UniverseRefreshResponse)
def refresh_universe(
    limit: int = Query(100, ge=1, le=5000),
    force: bool = Query(False),
    max_age_days: int = Query(7, ge=0, le=365),
    batch_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db_session),
):
    service = UniverseService(db=db)
    return UniverseRefreshResponse(
        **service.refresh_taxonomy(
            limit=limit,
            force=force,
            max_age_days=max_age_days,
            batch_size=batch_size,
        )
    )


@router.get("/instruments", response_model=list[UniverseInstrumentItem])
def list_universe_instruments(
    limit: int = Query(200, ge=1, le=10000),
    sector: str | None = Query(default=None),
    missing_taxonomy: bool = Query(False),
    db: Session = Depends(get_db_session),
):
    service = UniverseService(db=db)
    rows = service.list_instruments(
        limit=limit,
        sector=sector,
        missing_taxonomy=missing_taxonomy,
    )
    return [UniverseInstrumentItem(**row) for row in rows]


@router.get("/sectors", response_model=UniverseSectorsResponse)
def universe_sector_counts(db: Session = Depends(get_db_session)):
    service = UniverseService(db=db)
    return UniverseSectorsResponse(counts=service.get_sector_counts())
