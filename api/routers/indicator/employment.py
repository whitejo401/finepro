"""indicator/employment — 고용 지표 엔드포인트."""
import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.indicator.employment")

TTL = 60 * 60 * 6  # 6시간

ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")


def _ecos_fetch(stat_code: str, limit_months: int = 24) -> list[dict]:
    """ECOS 월간 시리즈 수집."""
    if not ECOS_API_KEY:
        return []
    now = datetime.now()
    end_str = now.strftime("%Y%m")
    start_str = (now - timedelta(days=limit_months * 31)).strftime("%Y%m")
    url = (
        f"http://ecos.bok.or.kr/api/StatisticSearch/{ECOS_API_KEY}"
        f"/json/kr/1/100/{stat_code}/M/{start_str}/{end_str}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json().get("StatisticSearch", {}).get("row", [])
    except Exception as e:
        log.warning("ECOS fetch 실패 (%s): %s", stat_code, e)
        return []


def _fred_series(series_id: str, limit: int = 24) -> list[dict]:
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


def _parse_ecos_latest(rows: list[dict]) -> dict | None:
    """ECOS rows에서 최신값 추출."""
    parsed = []
    for r in rows:
        try:
            parsed.append({"date": r.get("TIME"), "value": float(r.get("DATA_VALUE", 0))})
        except Exception:
            continue
    if not parsed:
        return None
    parsed = sorted(parsed, key=lambda x: x["date"])
    latest = parsed[-1]
    return {"latest": latest["value"], "date": latest["date"]}


def _parse_fred_latest(obs: list[dict]) -> dict | None:
    """FRED observations에서 최신 유효값 추출."""
    for o in obs:  # desc 정렬
        val = o.get("value")
        if val in (".", None, ""):
            continue
        try:
            return {"latest": round(float(val), 3), "date": o["date"]}
        except Exception:
            continue
    return None


def _fred_mom_change(series_id: str) -> dict | None:
    """FRED 시리즈 최근 2개월 전월 증감 계산."""
    obs = _fred_series(series_id, limit=3)
    valid = [o for o in obs if o.get("value") not in (".", None, "")]
    if len(valid) < 2:
        return _parse_fred_latest(obs)
    try:
        cur = float(valid[0]["value"])
        prev = float(valid[1]["value"])
        mom = round(cur - prev, 1)
        return {"latest": cur, "mom_change": mom, "date": valid[0]["date"]}
    except Exception:
        return None


@router.get("/employment")
def employment(country: str = Query("KR", description="국가 코드 (KR, US)")):
    """고용 지표.

    - KR: 한국은행 ECOS 901Y027 (실업률), 901Y026 (고용률)
    - US: FRED UNRATE (실업률), PAYEMS (비농업고용 전월 증감)
    """
    country = country.upper()
    key = f"indicator:employment:{country}"
    cached = cache.get(key)
    if cached:
        return cached

    if country == "KR":
        unemployment_rows = _ecos_fetch("901Y027")
        employment_rows = _ecos_fetch("901Y026")
        resp = ok({
            "country": "KR",
            "unemployment": _parse_ecos_latest(unemployment_rows),
            "employment_rate": _parse_ecos_latest(employment_rows),
            "nonfarm_payrolls": None,
        })
    elif country == "US":
        resp = ok({
            "country": "US",
            "unemployment": _parse_fred_latest(_fred_series("UNRATE", limit=3)),
            "employment_rate": None,
            "nonfarm_payrolls": _fred_mom_change("PAYEMS"),
        })
    else:
        resp = ok({
            "country": country,
            "unemployment": None,
            "employment_rate": None,
            "nonfarm_payrolls": None,
        })

    cache.set(key, resp, TTL)
    return resp
