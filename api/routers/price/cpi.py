"""price/cpi — ECOS CPI 시계열 엔드포인트 (indicator 캐시 재활용)."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 21600  # 6시간

ECOS_BASE = "https://ecos.bok.or.kr/api"


def _ecos_get(stat_code: str, cycle: str, start: str, end: str, item_code: str = "") -> list:
    import requests
    key = os.getenv("ECOS_API_KEY", "")
    if not key:
        return []
    url = f"{ECOS_BASE}/StatisticSearch/{key}/json/kr/1/100/{stat_code}/{cycle}/{start}/{end}"
    if item_code:
        url += f"/{item_code}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    raw = resp.json()
    return (raw.get("StatisticSearch") or {}).get("row") or []


@router.get("")
def cpi_trend():
    """소비자물가지수(CPI) 최근 12개월 추이 + 전월비·전년비."""
    cached = cache.get("price:cpi")
    if cached:
        return cached

    # indicator 그룹 캐시 우선 조회
    ind_cached = cache.get("indicator:inflation:KR")
    if ind_cached:
        resp = ind_cached
        cache.set("price:cpi", resp, TTL)
        return resp

    if not os.getenv("ECOS_API_KEY"):
        raise HTTPException(status_code=503, detail="ECOS_API_KEY 미설정")

    try:
        today = datetime.now()
        start = f"{today.year - 1}{today.month:02d}"
        end = f"{today.year}{today.month:02d}"

        rows = _ecos_get("901Y009", "M", start, end, "0")  # CPI 전국 종합
        history = [
            {
                "date": r.get("TIME"),
                "cpi": float(r.get("DATA_VALUE") or 0),
            }
            for r in rows
        ]
        # 전월비·전년비
        for i, row in enumerate(history):
            row["mom"] = round(row["cpi"] - history[i-1]["cpi"], 2) if i > 0 else None
            row["yoy"] = round(row["cpi"] - history[i-12]["cpi"], 2) if i >= 12 else None

        latest = history[-1] if history else {}
        resp = ok(history, meta={
            "latest_date": latest.get("date"),
            "latest_cpi": latest.get("cpi"),
            "mom": latest.get("mom"),
            "yoy": latest.get("yoy"),
            "count": len(history),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("cpi_trend error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set("price:cpi", resp, TTL)
    return resp
