"""seasonal/water — 물놀이터·해수욕장·계곡 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_WATER = 3600   # 1시간
TTL_BEACH = 10800  # 3시간

TOUR_BASE = "http://apis.data.go.kr/B551011/KorService1"
DATA_GO_BASE = "http://apis.data.go.kr"

REGION_AREA = {
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
    "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
    "충북": 33, "충남": 34, "경북": 35, "경남": 36, "전북": 37,
    "전남": 38, "제주": 39,
}


def _tour_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("TOUR_API_KEY", "")
    params.update({"serviceKey": key, "MobileOS": "ETC", "MobileApp": "InfoAPI", "_type": "json"})
    resp = requests.get(f"{TOUR_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _data_go_get(path: str, params: dict) -> dict:
    import requests
    key = os.getenv("DATA_GO_KR_API_KEY", "")
    params.update({"serviceKey": key, "_type": "json"})
    resp = requests.get(f"{DATA_GO_BASE}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _is_open(open_date: str | None, close_date: str | None) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    if not open_date:
        return False
    return (open_date <= today) and (not close_date or today <= close_date)


@router.get("/water")
def water_list(
    region: str = Query("전체", description="시도 (서울·강원 등 또는 전체)"),
    type_: str = Query("전체", alias="type", description="물놀이터·공공수영장·워터파크·전체"),
):
    """지역별 공공 물놀이장·수영장 개장 현황."""
    cache_key = f"seasonal:water:{region}:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        keyword = type_ if type_ != "전체" else "물놀이"
        params: dict = {"keyword": keyword, "contentTypeId": 12, "numOfRows": 50, "pageNo": 1}
        if region != "전체" and region in REGION_AREA:
            params["areaCode"] = REGION_AREA[region]

        raw = _tour_get("searchKeyword1", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [
            {
                "name": i.get("title"),
                "type": type_ if type_ != "전체" else "물놀이시설",
                "region": (i.get("addr1") or "").split()[0] if i.get("addr1") else None,
                "address": i.get("addr1"),
                "phone": i.get("tel"),
                "admission": "확인 필요",
                "is_open": None,  # TourAPI 개장일 정보 없음
                "thumbnail": i.get("firstimage"),
                "source": "TourAPI",
            }
            for i in items_raw
        ]
        resp = ok(items, meta={"region": region, "type": type_, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("water_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_WATER)
    return resp


@router.get("/beach")
def beach_list(
    region: str = Query("전체", description="강원·경남·전남·제주·충남·전체"),
):
    """해수욕장 개장 현황 (TourAPI)."""
    cache_key = f"seasonal:beach:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        params: dict = {"keyword": "해수욕장", "contentTypeId": 12, "numOfRows": 50, "pageNo": 1}
        if region != "전체" and region in REGION_AREA:
            params["areaCode"] = REGION_AREA[region]

        raw = _tour_get("searchKeyword1", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        today_month = datetime.now().month
        items = [
            {
                "name": i.get("title"),
                "region": (i.get("addr1") or "").split()[0] if i.get("addr1") else None,
                "address": i.get("addr1"),
                "phone": i.get("tel"),
                "is_open": today_month in [7, 8],  # 7~8월 개장 시즌
                "water_temp": None,
                "wave_height": None,
                "safety_grade": None,
                "thumbnail": i.get("firstimage"),
                "source": "TourAPI",
            }
            for i in items_raw
        ]
        resp = ok(items, meta={"region": region, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("beach_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_BEACH)
    return resp


@router.get("/valley")
def valley_list(
    region: str = Query("전체", description="지역 (경기·강원 등 또는 전체)"),
):
    """전국 주요 계곡 현황 (TourAPI)."""
    cache_key = f"seasonal:valley:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        params: dict = {"keyword": "계곡", "contentTypeId": 12, "numOfRows": 50, "pageNo": 1}
        if region != "전체" and region in REGION_AREA:
            params["areaCode"] = REGION_AREA[region]

        raw = _tour_get("searchKeyword1", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        today_month = datetime.now().month
        items = [
            {
                "name": i.get("title"),
                "region": (i.get("addr1") or "").split()[0] if i.get("addr1") else None,
                "address": i.get("addr1"),
                "phone": i.get("tel"),
                "is_open": today_month in [6, 7, 8, 9],
                "safety_grade": None,
                "congestion": None,
                "thumbnail": i.get("firstimage"),
                "source": "TourAPI",
            }
            for i in items_raw
        ]
        resp = ok(items, meta={"region": region, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("valley_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_BEACH)
    return resp
