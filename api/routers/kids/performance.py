"""kids/performance — KOPIS 아동 공연 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간

KOPIS_BASE = "http://www.kopis.or.kr/openApi/restful"
GENRE_CHILD = "AAAB"  # 아동 장르코드

REGION_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28",
    "광주": "29", "대전": "30", "울산": "31", "세종": "36",
    "경기": "41", "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}


def _kopis_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("KOPIS_API_KEY", "")
    params["service"] = key
    resp = requests.get(f"{KOPIS_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    import xml.etree.ElementTree as ET
    return ET.fromstring(resp.text)


def _parse_db(el) -> dict:
    """KOPIS <db> 엘리먼트 → dict."""
    def t(tag): return (el.findtext(tag) or "").strip()
    return {
        "id": t("mt20id"),
        "title": t("prfnm"),
        "venue": t("fcltynm"),
        "start_date": t("prfpdfrom"),
        "end_date": t("prfpdto"),
        "poster_url": t("poster"),
        "genre": t("genrenm"),
        "state": t("prfstate"),
        "area": t("area"),
        "admission": "무료",
        "source": "KOPIS",
    }


@router.get("")
def kids_performance(
    region: str = Query("전체", description="지역 (서울·부산 등 또는 전체)"),
    age: str = Query("전체", description="영유아·초등·중고등·전체"),
    month: str | None = Query(None, description="YYYYMM — 생략 시 당월"),
):
    """어린이 무료 공연 목록 (아동극·음악회 등)."""
    if not month:
        month = datetime.now().strftime("%Y%m")
    stdate = month + "01"
    etdate = month + "31"

    cache_key = f"kids:performance:{region}:{age}:{month}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        api_key = os.getenv("KOPIS_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=503, detail="KOPIS_API_KEY 미설정")

        params = {
            "stdate": stdate,
            "eddate": etdate,
            "shcate": GENRE_CHILD,
            "rows": 100,
            "cpage": 1,
            "prfprice": "무료",
        }
        if region != "전체" and region in REGION_CODE:
            params["signgucode"] = REGION_CODE[region]

        root = _kopis_get("pblprfr", params)
        items = [_parse_db(db) for db in root.findall("db")]

        resp = ok(items, meta={
            "region": region, "age": age, "month": month,
            "count": len(items), "source": "KOPIS",
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("kids_performance error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
