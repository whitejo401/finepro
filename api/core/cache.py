"""메모리 TTL 캐시 (외부 의존성 없음)."""
import time
from typing import Any


class TTLCache:
    """간단한 인메모리 TTL 캐시."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


# 싱글턴
cache = TTLCache()
