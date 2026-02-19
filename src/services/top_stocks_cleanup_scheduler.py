from __future__ import annotations

import logging
import threading

from src.config import settings
from src.models.db import SessionLocal
from src.services.top_stocks_audit_service import TopStocksAuditService

logger = logging.getLogger(__name__)


class TopStocksCleanupScheduler:
    def __init__(self, audit_service: TopStocksAuditService | None = None) -> None:
        self.audit_service = audit_service or TopStocksAuditService()
        self.interval_seconds = max(60, settings.audit_cleanup_interval_minutes * 60)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not settings.audit_cleanup_scheduler_enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._run_once()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="top-stocks-audit-cleanup",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Top-stock cleanup scheduler started",
            extra={
                "interval_seconds": self.interval_seconds,
                "retention_days": settings.audit_retention_days,
            },
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            self._run_once()

    def _run_once(self) -> None:
        db = SessionLocal()
        try:
            purged = self.audit_service.cleanup_expired(db, retention_days=settings.audit_retention_days)
            if purged:
                logger.info(
                    "Top-stock audit cleanup purged old rows",
                    extra={"purged": purged, "retention_days": settings.audit_retention_days},
                )
        except Exception as exc:
            logger.exception("Top-stock audit cleanup failed", extra={"error": str(exc)})
        finally:
            db.close()

