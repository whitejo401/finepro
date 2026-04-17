"""indicator/trade — 무역 지표 엔드포인트."""
import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.indicator.trade")

TTL = 60 * 60 * 6  # 6시간

DATA_GO_KR_API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

_CUSTOMS_URL = "https://unipass.customs.go.kr/openapi/rest/trtStatsTotAmt"


def _fetch_customs(year: int, month: int) -> dict | None:
    """관세청 무역통계 API 호출."""
    if not DATA_GO_KR_API_KEY:
        return None
    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "year": str(year),
        "month": f"{month:02d}",
        "type": "JSON",
    }
    try:
        resp = requests.get(_CUSTOMS_URL, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        # 응답 구조: {"trtStatsTotAmt": {"item": [...]}} 또는 직접 리스트
        items = (
            body.get("trtStatsTotAmt", {}).get("item", [])
            or body.get("items", {}).get("item", [])
            or []
        )
        if not items:
            return None
        item = items[0] if isinstance(items, list) else items
        return {
            "year": year,
            "month": month,
            "export_amt": _safe_float(item.get("expAmt")),
            "import_amt": _safe_float(item.get("impAmt")),
            "balance": _safe_float(item.get("blnc")),
        }
    except Exception as e:
        log.warning("관세청 API 실패 (%d-%02d): %s", year, month, e)
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", ""))
    except Exception:
        return None


def _yoy_change(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur / prev - 1) * 100, 2)


def _fred_trade_balance() -> dict | None:
    """FRED BOPGSTB (미국 무역수지) 폴백."""
    if not FRED_API_KEY:
        return None
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "BOPGSTB",
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 14,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        valid = [o for o in obs if o.get("value") not in (".", None, "")]
        if not valid:
            return None
        cur = float(valid[0]["value"])
        prev_yoy = float(valid[12]["value"]) if len(valid) > 12 else None
        return {
            "source": "FRED:BOPGSTB",
            "date": valid[0]["date"],
            "balance": cur,
            "yoy_change_pct": _yoy_change(cur, prev_yoy),
            "export_amt": None,
            "import_amt": None,
        }
    except Exception as e:
        log.warning("FRED BOPGSTB 실패: %s", e)
        return None


@router.get("/trade")
def trade(country: str = Query("KR", description="국가 코드 (KR, US)")):
    """무역 지표.

    - KR: 관세청 무역통계 API (수출·수입·무역수지)
    - US: 관세청 실패 시 FRED BOPGSTB 폴백
    """
    country = country.upper()
    key = f"indicator:trade:{country}"
    cached = cache.get(key)
    if cached:
        return cached

    if country == "KR":
        now = datetime.now()
        # 이번 달 데이터 미발표 가능성 → 전월 기준
        target = now - timedelta(days=35)
        cur = _fetch_customs(target.year, target.month)
        prev_year = _fetch_customs(target.year - 1, target.month)

        if cur:
            data = {
                "country": "KR",
                "source": "customs.go.kr",
                "date": f"{target.year}-{target.month:02d}",
                "export_amt": cur["export_amt"],
                "import_amt": cur["import_amt"],
                "balance": cur["balance"],
                "export_yoy_pct": _yoy_change(cur["export_amt"], prev_year["export_amt"] if prev_year else None),
                "import_yoy_pct": _yoy_change(cur["import_amt"], prev_year["import_amt"] if prev_year else None),
            }
        else:
            # 폴백: FRED 미국 무역수지
            fallback = _fred_trade_balance()
            data = {
                "country": "KR",
                "source": "fallback:FRED:BOPGSTB",
                "data": fallback,
            }
    elif country == "US":
        fallback = _fred_trade_balance()
        data = {
            "country": "US",
            "source": "FRED:BOPGSTB",
            **(fallback or {}),
        }
    else:
        data = {"country": country, "balance": None}

    resp = ok(data)
    cache.set(key, resp, TTL)
    return resp
