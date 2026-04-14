"""공통 응답 포맷."""
from typing import Any
from datetime import datetime, timezone


def ok(data: Any, meta: dict | None = None) -> dict:
    """성공 응답."""
    resp = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    if meta:
        resp["meta"] = meta
    return resp


def error(message: str, code: int = 400) -> dict:
    """에러 응답."""
    return {
        "status": "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": {"message": message, "code": code},
    }
