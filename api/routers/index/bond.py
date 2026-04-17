"""index/bond — 미국 국채금리 엔드포인트."""
import os
import logging

import yfinance as yf
from fastapi import APIRouter, HTTPException

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.index.bond")

TTL_BOND = 60 * 10  # 10분

# FRED 시리즈 코드
BOND_FRED = {"10Y": "DGS10", "2Y": "DGS2", "30Y": "DGS30"}

# yfinance 폴백 심볼 (^TNX=10Y, ^IRX≈3M, ^TYX=30Y)
BOND_YF_FALLBACK = {"10Y": "^TNX", "2Y": "^IRX", "30Y": "^TYX"}


def _fetch_fred() -> dict[str, float | None]:
    """fredapi로 국채금리 조회. 실패 시 None 반환."""
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        return {}
    try:
        from fredapi import Fred
        fred = Fred(api_key=api_key)
        result = {}
        for label, series_id in BOND_FRED.items():
            s = fred.get_series(series_id)
            s = s.dropna()
            result[label] = round(float(s.iloc[-1]), 3) if not s.empty else None
        return result
    except Exception as e:
        log.warning("FRED 조회 실패, yfinance 폴백: %s", e)
        return {}


def _fetch_yfinance() -> dict[str, float | None]:
    """yfinance 폴백으로 국채금리 조회."""
    result = {}
    for label, symbol in BOND_YF_FALLBACK.items():
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if hist.empty:
                result[label] = None
            else:
                result[label] = round(float(hist.iloc[-1]["Close"]), 3)
        except Exception:
            result[label] = None
    return result


@router.get("/bond")
def bond():
    """미국 국채금리 (10Y·2Y·30Y) 및 장단기 금리차.

    FRED API 키가 있으면 fredapi 우선 사용, 없으면 yfinance 폴백.
    """
    key = "index:bond"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        # FRED 우선 시도
        rates = _fetch_fred()
        source = "FRED"

        # FRED 실패 또는 키 없으면 yfinance 폴백
        if not rates or any(v is None for v in rates.values()):
            rates = _fetch_yfinance()
            source = "yfinance(폴백)"

        y10 = rates.get("10Y")
        y2  = rates.get("2Y")
        y30 = rates.get("30Y")

        if y10 is None or y2 is None:
            raise HTTPException(status_code=502, detail="국채금리 데이터 수집 실패")

        spread_10y2y = round(y10 - y2, 3)
        inverted     = spread_10y2y < 0

        data = {
            "rates": {
                "10Y": y10,
                "2Y":  y2,
                "30Y": y30,
            },
            "spread_10y2y": spread_10y2y,
            "inverted":     inverted,
            "source":       source,
        }
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_BOND)
    return resp
