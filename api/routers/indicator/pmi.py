"""indicator/pmi — PMI / 경기선행지수 엔드포인트."""
import os
import logging

import requests
from fastapi import APIRouter, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.indicator.pmi")

TTL = 60 * 60 * 6  # 6시간

FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# FRED PMI 대리변수: ISM_MAN_PMI → NAPM (ISM 제조업 PMI 히스토리)
_FRED_PMI_CANDIDATES = ["NAPM"]  # ISM 제조업 PMI


def _fred_series(series_id: str, limit: int = 6) -> list[dict]:
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


def _get_fred_pmi() -> dict | None:
    """FRED PMI 후보 시리즈 순서대로 시도."""
    for sid in _FRED_PMI_CANDIDATES:
        obs = _fred_series(sid, limit=3)
        valid = [o for o in obs if o.get("value") not in (".", None, "")]
        if valid:
            try:
                val = float(valid[0]["value"])
                return {
                    "source": f"FRED:{sid}",
                    "latest": val,
                    "date": valid[0]["date"],
                    "signal": "expanding" if val >= 50 else "contracting",
                }
            except Exception:
                continue
    return None


def _get_oecd_cli(country_code: str) -> dict | None:
    """OECD CLI 최신값 수집 (기존 macro 수집기 재활용 — 경량 버전)."""
    # OECD SDMX v2: 단일 국가 최근 3개월
    country_map = {"KR": "KOR", "US": "USA", "JP": "JPN", "DE": "DEU"}
    oecd_code = country_map.get(country_code, country_code)

    base_url = (
        "https://sdmx.oecd.org/public/rest/v2/data/dataflow/"
        "OECD.SDD.STES/DSD_STES@DF_CLI/4.0/*"
    )
    qs = "lastNObservations=6&format=csvfilewithlabels&dimensionAtObservation=TIME_PERIOD"
    url = f"{base_url}?{qs}"

    try:
        resp = requests.get(url, timeout=60, headers={"Accept-Encoding": "gzip"})
        resp.raise_for_status()
        from io import StringIO
        import pandas as pd

        text = resp.text.lstrip("\ufeff")
        df = pd.read_csv(StringIO(text))

        # 필터링
        area_col = next((c for c in df.columns if "AREA" in c.upper()), None)
        if area_col is None:
            return None
        if "MEASURE" in df.columns:
            df = df[df["MEASURE"] == "LI"]
        if "ADJUSTMENT" in df.columns:
            df = df[df["ADJUSTMENT"] == "AA"]
        if "TRANSFORMATION" in df.columns:
            df = df[df["TRANSFORMATION"] == "IX"]

        sub = df[df[area_col] == oecd_code][["TIME_PERIOD", "OBS_VALUE"]].copy()
        if sub.empty:
            return None
        sub = sub.sort_values("TIME_PERIOD")
        latest = sub.iloc[-1]
        val = float(latest["OBS_VALUE"])
        return {
            "source": "OECD_CLI",
            "latest": round(val, 3),
            "date": str(latest["TIME_PERIOD"])[:7],
            "signal": "expanding" if val >= 100 else "contracting",
        }
    except Exception as e:
        log.warning("OECD CLI fetch 실패 (%s): %s", country_code, e)
        return None


@router.get("/pmi")
def pmi(country: str = Query("KR", description="국가 코드 (KR, US)")):
    """PMI / 경기선행지수.

    - US 제조업 PMI: FRED NAPM (ISM 제조업)
    - OECD CLI: 한국·미국 복합선행지수 (100 기준 expanding/contracting)
    """
    country = country.upper()
    key = f"indicator:pmi:{country}"
    cached = cache.get(key)
    if cached:
        return cached

    cli = _get_oecd_cli(country)

    if country == "US":
        mfg_pmi = _get_fred_pmi()
    else:
        mfg_pmi = None  # KR ISM 없음 — OECD CLI로 대체

    resp = ok({
        "country": country,
        "manufacturing_pmi": mfg_pmi,
        "oecd_cli": cli,
    })
    cache.set(key, resp, TTL)
    return resp
