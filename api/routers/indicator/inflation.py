"""indicator/inflation — 물가 지표 엔드포인트."""
import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.indicator.inflation")

TTL = 60 * 60 * 6  # 6시간

ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")


def _ecos_fetch(stat_code: str, start: str, end: str) -> list[dict]:
    """ECOS StatisticSearch API 호출, 실패 시 빈 리스트."""
    if not ECOS_API_KEY:
        return []
    url = (
        f"http://ecos.bok.or.kr/api/StatisticSearch/{ECOS_API_KEY}"
        f"/json/kr/1/1000/{stat_code}/M/{start}/{end}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("StatisticSearch", {}).get("row", [])
        return rows
    except Exception as e:
        log.warning("ECOS fetch 실패 (%s): %s", stat_code, e)
        return []


def _fred_series(series_id: str, limit: int = 24) -> list[dict]:
    """FRED API 단일 시리즈 최근 limit개, 실패 시 빈 리스트."""
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
        obs = resp.json().get("observations", [])
        return obs
    except Exception as e:
        log.warning("FRED fetch 실패 (%s): %s", series_id, e)
        return []


def _pct_change(values: list[float]) -> float | None:
    """마지막 2개 값으로 전월비(%) 계산."""
    if len(values) < 2 or values[-2] == 0:
        return None
    return round((values[-1] / values[-2] - 1) * 100, 3)


def _yoy_pct(values: list[float]) -> float | None:
    """마지막 값과 12개월 전 값으로 전년비(%) 계산."""
    if len(values) < 13 or values[-13] == 0:
        return None
    return round((values[-1] / values[-13] - 1) * 100, 3)


def _build_kr_cpi() -> dict | None:
    """ECOS CPI 수집 → {latest, mom_pct, yoy_pct, date}."""
    end_str = datetime.now().strftime("%Y%m")
    start_str = (datetime.now() - timedelta(days=400)).strftime("%Y%m")

    # 901Y009: CPI 전월비, 901Y010: CPI 전년비 (직접 수치 사용)
    rows_mom = _ecos_fetch("901Y009", start_str, end_str)
    rows_yoy = _ecos_fetch("901Y010", start_str, end_str)

    if not rows_mom and not rows_yoy:
        return None

    def _parse_rows(rows):
        result = []
        for r in rows:
            try:
                result.append({"date": r.get("TIME"), "value": float(r.get("DATA_VALUE", 0))})
            except Exception:
                continue
        return sorted(result, key=lambda x: x["date"])

    mom_data = _parse_rows(rows_mom)
    yoy_data = _parse_rows(rows_yoy)

    latest_date = mom_data[-1]["date"] if mom_data else (yoy_data[-1]["date"] if yoy_data else None)
    mom_pct = mom_data[-1]["value"] if mom_data else None
    yoy_pct = yoy_data[-1]["value"] if yoy_data else None

    return {
        "latest": None,
        "mom_pct": mom_pct,
        "yoy_pct": yoy_pct,
        "date": latest_date,
    }


def _build_us_cpi() -> dict | None:
    """FRED CPIAUCSL → {latest, mom_pct, yoy_pct, date}."""
    obs = _fred_series("CPIAUCSL", limit=24)
    if not obs:
        return None
    valid = [o for o in reversed(obs) if o.get("value") not in (".", None, "")]
    if not valid:
        return None
    values = []
    for o in valid:
        try:
            values.append(float(o["value"]))
        except Exception:
            pass
    latest = values[-1] if values else None
    return {
        "latest": latest,
        "mom_pct": _pct_change(values),
        "yoy_pct": _yoy_pct(values),
        "date": valid[-1]["date"] if valid else None,
    }


def _build_us_ppi() -> dict | None:
    """FRED PPIFIS → {latest, mom_pct, yoy_pct, date}."""
    obs = _fred_series("PPIFIS", limit=24)
    if not obs:
        return None
    valid = [o for o in reversed(obs) if o.get("value") not in (".", None, "")]
    if not valid:
        return None
    values = [float(o["value"]) for o in valid if o.get("value") not in (".", None, "")]
    return {
        "latest": values[-1] if values else None,
        "mom_pct": _pct_change(values),
        "yoy_pct": _yoy_pct(values),
        "date": valid[-1]["date"] if valid else None,
    }


def _build_us_pce() -> dict | None:
    """FRED PCEPI → {latest, mom_pct, yoy_pct, date}."""
    obs = _fred_series("PCEPI", limit=24)
    if not obs:
        return None
    valid = [o for o in reversed(obs) if o.get("value") not in (".", None, "")]
    if not valid:
        return None
    values = [float(o["value"]) for o in valid if o.get("value") not in (".", None, "")]
    return {
        "latest": values[-1] if values else None,
        "mom_pct": _pct_change(values),
        "yoy_pct": _yoy_pct(values),
        "date": valid[-1]["date"] if valid else None,
    }


@router.get("/inflation")
def inflation(country: str = Query("KR", description="국가 코드 (KR, US)")):
    """CPI/PPI/PCE 물가 지표.

    - KR: 한국은행 ECOS API (CPI 전월비·전년비)
    - US: FRED CPIAUCSL, PPIFIS, PCEPI
    """
    country = country.upper()
    key = f"indicator:inflation:{country}"
    cached = cache.get(key)
    if cached:
        return cached

    if country == "KR":
        cpi = _build_kr_cpi()
        resp = ok({
            "country": "KR",
            "cpi": cpi,
            "ppi": None,
            "pce": None,
        })
    elif country == "US":
        resp = ok({
            "country": "US",
            "cpi": _build_us_cpi(),
            "ppi": _build_us_ppi(),
            "pce": _build_us_pce(),
        })
    else:
        resp = ok({"country": country, "cpi": None, "ppi": None, "pce": None})

    cache.set(key, resp, TTL)
    return resp
