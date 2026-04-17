"""outdoor/camping — 고캠핑 캠핑장 목록·상세 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 21600  # 6시간

GOCAMPING_BASE = "http://apis.data.go.kr/B551011/GoCamping"

FACILITIES_MAP = {
    "sbrsCook": "취사", "sbrsFirepits": "화로대", "sbrsElec": "전기",
    "sbrsToilt": "화장실", "sbrsSh": "샤워실", "sbrsStore": "매점",
    "sbrsWifi": "Wi-Fi", "sbrsPool": "수영장", "sbrsWaterSlide": "워터슬라이드",
    "sbrsPlayEqui": "놀이터", "sbrsStair": "산책로",
}


def _gocamping_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("TOUR_API_KEY", "")
    params.update({
        "serviceKey": key,
        "MobileOS": "ETC",
        "MobileApp": "InfoAPI",
        "_type": "json",
    })
    resp = requests.get(f"{GOCAMPING_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _parse_camp(item: dict) -> dict:
    facilities = [label for key, label in FACILITIES_MAP.items() if item.get(key) == "Y"]
    return {
        "id": str(item.get("contentId") or item.get("facltNm", "")),
        "name": item.get("facltNm"),
        "type": item.get("induty"),
        "region": item.get("doNm"),
        "city": item.get("sigunguNm"),
        "address": item.get("addr1"),
        "phone": item.get("tel"),
        "facilities": facilities,
        "pet_allowed": item.get("animalCmgCl") == "가능",
        "reservation_url": item.get("resveUrl") or item.get("homepage"),
        "thumbnail": item.get("firstImageUrl"),
        "lat": item.get("mapY"),
        "lon": item.get("mapX"),
        "intro": (item.get("lineIntro") or "")[:200],
        "source": "고캠핑",
    }


@router.get("")
def camping_list(
    region: str = Query("전체", description="시도 (강원·경기 등 또는 전체)"),
    type_: str = Query("전체", alias="type", description="일반야영장·글램핑·카라반·자동차야영장·전체"),
    pet: bool | None = Query(None, description="반려동물 동반 가능"),
    electric: bool | None = Query(None, description="전기 사용 가능"),
):
    """전국 캠핑장 목록 (타입·지역·시설 필터)."""
    cache_key = f"outdoor:camping:{region}:{type_}:{pet}:{electric}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        params: dict = {"numOfRows": 500, "pageNo": 1}
        if region != "전체":
            params["doNm"] = region
        if type_ != "전체":
            params["induty"] = type_

        raw = _gocamping_get("basedList", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [_parse_camp(i) for i in items_raw]

        if pet is not None:
            items = [i for i in items if i["pet_allowed"] == pet]
        if electric is True:
            items = [i for i in items if "전기" in i["facilities"]]

        resp = ok(items, meta={"region": region, "type": type_, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("camping_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp


@router.get("/{camp_id}")
def camping_detail(camp_id: str = Path(description="캠핑장 contentId")):
    """캠핑장 상세 (기본정보 + 이미지)."""
    cache_key = f"outdoor:camping:detail:{camp_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        # 기본 정보
        raw = _gocamping_get("basedList", {"contentId": camp_id, "numOfRows": 1, "pageNo": 1})
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not items_raw:
            raise HTTPException(status_code=404, detail="캠핑장 없음")

        detail = _parse_camp(items_raw[0])

        # 이미지
        try:
            img_raw = _gocamping_get("imageList", {"contentId": camp_id, "numOfRows": 10, "pageNo": 1})
            imgs = (
                img_raw.get("response", {}).get("body", {})
                       .get("items", {}) or {}
            ).get("item", [])
            if isinstance(imgs, dict):
                imgs = [imgs]
            detail["images"] = [i.get("imageUrl") for i in imgs if i.get("imageUrl")]
        except Exception:
            detail["images"] = []

        resp = ok(detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("camping_detail error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
