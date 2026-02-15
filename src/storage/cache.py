from __future__ import annotations

import time
from typing import Any


class TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        record = self._data.get(key)
        if not record:
            return None
        value, expiry = record
        if time.time() > expiry:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int = 30) -> None:
        self._data[key] = (value, time.time() + ttl_seconds)
