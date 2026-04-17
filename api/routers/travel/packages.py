"""travel/packages — 지역별 여행 패키지·코스 추천 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 10800  # 3시간

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
    params.update({
        "serviceKey": key, "MobileOS": "ETC",
        "MobileApp": "InfoAPI", "_type": "json",
    })
    resp = requests.get(f"{TOUR_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@router.get("")
def packages_list(
    region: str = Query("전체", description="지역 (서울·강원 등 또는 전체)"),
):
    """지역별 여행 패키지·코스 목록 (TourAPI 여행코스 contentTypeId=25)."""
    cache_key = f"travel:packages:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        params: dict = {
            "contentTypeId": 25,   # 여행코스
            "numOfRows": 50,
            "pageNo": 1,
            "arrange": "C",        # 수정일 내림차순
        }
        if region != "전체" and region in REGION_AREA:
            params["areaCode"] = REGION_AREA[region]

        raw = _tour_get("areaBasedList1", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [
            {
                "id": f"pkg_{i.get('contentid')}",
                "title": i.get("title"),
                "region": (i.get("addr1") or "").split()[0] if i.get("addr1") else region,
                "address": i.get("addr1"),
                "thumbnail": i.get("firstimage") or i.get("firstimage2"),
                "source": "TourAPI",
            }
            for i in items_raw
        ]
        resp = ok(items, meta={"region": region, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("packages_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
