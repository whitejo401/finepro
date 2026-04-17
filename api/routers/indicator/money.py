"""indicator/money — 통화량 / 신용 지표 엔드포인트."""
import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.indicator.money")

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


def _parse_fred_latest_with_yoy(obs: list[dict]) -> dict | None:
    """FRED 최신값 + 전년비 계산."""
    valid = [o for o in obs if o.get("value") not in (".", None, "")]
    if not valid:
        return None
    try:
        cur = float(valid[0]["value"])
        yoy = None
        if len(valid) >= 13:
            prev = float(valid[12]["value"])
            if prev != 0:
                yoy = round((cur / prev - 1) * 100, 3)
        return {"latest": cur, "yoy_pct": yoy, "date": valid[0]["date"]}
    except Exception:
        return None


@router.get("/money")
def money(country: str = Query("KR", description="국가 코드 (KR, US)")):
    """통화량 / 신용 지표.

    - KR: 한국은행 ECOS 101Y004 (M2 전년비), 121Y006 (대출 증감)
    - US: FRED M2SL (M2 통화량)
    """
    country = country.upper()
    key = f"indicator:money:{country}"
    cached = cache.get(key)
    if cached:
        return cached

    if country == "KR":
        m2_rows = _ecos_fetch("101Y004")   # M2 전년비
        loan_rows = _ecos_fetch("121Y006")  # 대출 증감
        resp = ok({
            "country": "KR",
            "m2": _parse_ecos_latest(m2_rows),
            "loan_growth": _parse_ecos_latest(loan_rows),
        })
    elif country == "US":
        m2_obs = _fred_series("M2SL", limit=24)
        resp = ok({
            "country": "US",
            "m2": _parse_fred_latest_with_yoy(m2_obs),
            "loan_growth": None,
        })
    else:
        resp = ok({"country": country, "m2": None, "loan_growth": None})

    cache.set(key, resp, TTL)
    return resp
