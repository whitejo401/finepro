"""indicator/growth — GDP 성장률 엔드포인트."""
import os
import logging

import requests
from fastapi import APIRouter, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.indicator.growth")

TTL = 60 * 60 * 12  # 12시간

ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")


def _ecos_fetch_quarterly(stat_code: str, limit_quarters: int = 12) -> list[dict]:
    """ECOS 분기 시리즈 수집."""
    if not ECOS_API_KEY:
        return []
    from datetime import datetime, timedelta
    end_str = datetime.now().strftime("%Y%q").replace("%q", f"Q{((datetime.now().month - 1) // 3) + 1}")
    # ECOS 분기 형식: YYYYQN (예: 2023Q4)
    now = datetime.now()
    end_str = f"{now.year}Q{((now.month - 1) // 3) + 1}"
    start_year = now.year - (limit_quarters // 4) - 2
    start_str = f"{start_year}Q1"

    url = (
        f"http://ecos.bok.or.kr/api/StatisticSearch/{ECOS_API_KEY}"
        f"/json/kr/1/100/{stat_code}/Q/{start_str}/{end_str}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        rows = resp.json().get("StatisticSearch", {}).get("row", [])
        return rows
    except Exception as e:
        log.warning("ECOS fetch 실패 (%s): %s", stat_code, e)
        return []


def _fred_series(series_id: str, limit: int = 12) -> list[dict]:
    """FRED API 단일 시리즈 최근 limit개."""
    if not FRED_API_KEY:
        return []
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("observations", [])
    except Exception as e:
        log.warning("FRED fetch 실패 (%s): %s", series_id, e)
        return []


def _parse_ecos_quarterly(rows: list[dict]) -> list[dict]:
    """ECOS 분기 rows → [{date, growth_pct}] 최근 8개."""
    result = []
    for r in rows:
        try:
            time_val = r.get("TIME", "")  # 예: 2023Q4
            value = float(r.get("DATA_VALUE", 0))
            # 분기 → 날짜 변환 (분기 마지막 월)
            year = int(time_val[:4])
            quarter = int(time_val[-1])
            month = quarter * 3
            date_str = f"{year}-{month:02d}-01"
            result.append({"date": date_str, "growth_pct": value})
        except Exception:
            continue
    result = sorted(result, key=lambda x: x["date"])
    return result[-8:]


def _parse_fred_quarterly(obs: list[dict]) -> list[dict]:
    """FRED 분기 observations → [{date, growth_pct}] 최근 8개."""
    result = []
    for o in reversed(obs):
        val = o.get("value")
        if val in (".", None, ""):
            continue
        try:
            result.append({"date": o["date"], "growth_pct": round(float(val), 3)})
        except Exception:
            continue
    result = sorted(result, key=lambda x: x["date"])
    return result[-8:]


@router.get("/gdp")
def gdp(country: str = Query("KR", description="국가 코드 (KR, US)")):
    """GDP 성장률 — 최근 8분기.

    - KR: 한국은행 ECOS 200Y001 (실질GDP 성장률, 분기)
    - US: FRED A191RL1Q225SBEA (실질GDP 성장률, 분기)
    """
    country = country.upper()
    key = f"indicator:gdp:{country}"
    cached = cache.get(key)
    if cached:
        return cached

    if country == "KR":
        rows = _ecos_fetch_quarterly("200Y001")
        series = _parse_ecos_quarterly(rows)
        latest = series[-1] if series else None
    elif country == "US":
        obs = _fred_series("A191RL1Q225SBEA", limit=12)
        series = _parse_fred_quarterly(obs)
        latest = series[-1] if series else None
    else:
        series = []
        latest = None

    resp = ok({
        "country": country,
        "unit": "% QoQ",
        "latest": latest,
        "series": series,
    })
    cache.set(key, resp, TTL)
    return resp
