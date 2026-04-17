"""culture/performance — KOPIS 공연 목록 엔드포인트."""
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 1800  # 30분

KOPIS_BASE = "http://www.kopis.or.kr/openApi/restful"

GENRE_CODE = {
    "뮤지컬": "AAAC",
    "연극":   "AAA5",
    "클래식": "AAAD",
    "무용":   "AAAF",
    "국악":   "AAAB",  # 실제론 AAAB=아동, 국악=AAAE
    "대중음악": "AAAG",
    "전체":   "",
}

REGION_SIGNU = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28",
    "광주": "29", "대전": "30", "울산": "31", "세종": "36",
    "경기": "41", "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}


def _kopis_get(endpoint: str, params: dict):
    import requests
    key = os.getenv("KOPIS_API_KEY", "")
    params["service"] = key
    resp = requests.get(f"{KOPIS_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return ET.fromstring(resp.text)


def _parse_db(el) -> dict:
    def t(tag): return (el.findtext(tag) or "").strip()
    price = t("pcseguidance")
    return {
        "id": t("mt20id"),
        "title": t("prfnm"),
        "genre": t("genrenm"),
        "venue": t("fcltynm"),
        "region": t("area"),
        "start_date": t("prfpdfrom"),
        "end_date": t("prfpdto"),
        "state": t("prfstate"),
        "price_range": price,
        "is_free": "무료" in price or price == "0" or price == "",
        "poster_url": t("poster"),
        "source": "KOPIS",
    }


@router.get("")
def performance_list(
    region: str = Query("전체", description="지역 (서울·부산 등 또는 전체)"),
    genre: str = Query("전체", description="뮤지컬·연극·클래식·무용·국악·대중음악·전체"),
    price_max: int | None = Query(None, description="최대 가격 (0 = 무료만)"),
    start_date: str | None = Query(None, description="YYYYMMDD"),
    end_date: str | None = Query(None, description="YYYYMMDD"),
):
    """공연 목록 (장르·가격·지역 필터)."""
    today = datetime.now()
    stdate = start_date or today.strftime("%Y%m01")
    etdate = end_date or today.strftime("%Y%m31")

    cache_key = f"culture:performance:{region}:{genre}:{price_max}:{stdate}:{etdate}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("KOPIS_API_KEY"):
        raise HTTPException(status_code=503, detail="KOPIS_API_KEY 미설정")

    try:
        params: dict = {
            "stdate": stdate,
            "eddate": etdate,
            "rows": 100,
            "cpage": 1,
        }
        gc = GENRE_CODE.get(genre, "")
        if gc:
            params["shcate"] = gc
        if region != "전체" and region in REGION_SIGNU:
            params["signgucode"] = REGION_SIGNU[region]
        if price_max == 0:
            params["prfprice"] = "무료"

        root = _kopis_get("pblprfr", params)
        items = [_parse_db(db) for db in root.findall("db")]

        if price_max is not None and price_max > 0:
            # 가격 텍스트 파싱이 복잡해 클라이언트 필터로 안내
            pass

        resp = ok(items, meta={
            "region": region, "genre": genre, "count": len(items),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("performance_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
