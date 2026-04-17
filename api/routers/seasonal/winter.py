"""seasonal/winter — 스키장·빙상장 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_SKI = 3600   # 1시간
TTL_ICE = 10800  # 3시간

TOUR_BASE = "http://apis.data.go.kr/B551011/KorService1"

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


@router.get("/ski")
def ski_list(
    region: str = Query("전체", description="강원·경기·충북 등 또는 전체"),
):
    """스키장·눈썰매장 개장 여부 및 현황."""
    cache_key = f"seasonal:ski:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        today_month = datetime.now().month
        is_ski_season = today_month in [12, 1, 2, 3]

        params: dict = {"keyword": "스키장", "contentTypeId": 28, "numOfRows": 30, "pageNo": 1}
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
                "region": (i.get("addr1") or "").split()[0] if i.get("addr1") else None,
                "address": i.get("addr1"),
                "phone": i.get("tel"),
                "is_open": is_ski_season,
                "slopes": None,
                "snow_depth_cm": None,
                "thumbnail": i.get("firstimage"),
                "url": None,
                "source": "TourAPI",
            }
            for i in items_raw
        ]
        resp = ok(items, meta={
            "region": region, "count": len(items),
            "season_note": "12~3월 운영" if not is_ski_season else "현재 시즌 중",
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ski_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_SKI)
    return resp


@router.get("/ice")
def ice_list(
    region: str = Query("전체", description="지역 (서울·경기 등 또는 전체)"),
    type_: str = Query("전체", alias="type", description="실내·실외·전체"),
):
    """빙상장·아이스링크 운영 현황."""
    cache_key = f"seasonal:ice:{region}:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        today_month = datetime.now().month
        is_ice_season = today_month in [11, 12, 1, 2, 3]

        keyword = "빙상장" if type_ == "전체" else f"{type_}빙상장"
        params: dict = {"keyword": keyword, "contentTypeId": 28, "numOfRows": 30, "pageNo": 1}
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
                "type": type_ if type_ != "전체" else "빙상장",
                "region": (i.get("addr1") or "").split()[0] if i.get("addr1") else None,
                "address": i.get("addr1"),
                "phone": i.get("tel"),
                "hours": None,
                "admission": "확인 필요",
                "is_open": is_ice_season,
                "thumbnail": i.get("firstimage"),
                "source": "TourAPI",
            }
            for i in items_raw
        ]
        resp = ok(items, meta={"region": region, "type": type_, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ice_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_ICE)
    return resp
