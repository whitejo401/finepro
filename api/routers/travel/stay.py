"""travel/stay — TourAPI 숙박시설 목록·상세 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_LIST   = 10800  # 3시간
TTL_DETAIL = 21600  # 6시간

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


def _parse_stay(item: dict) -> dict:
    return {
        "id": f"stay_{item.get('contentid')}",
        "content_id": item.get("contentid"),
        "name": item.get("title"),
        "type": item.get("cat3") or item.get("contenttypeid"),
        "address": item.get("addr1"),
        "phone": item.get("tel"),
        "thumbnail": item.get("firstimage") or item.get("firstimage2"),
        "lat": item.get("mapy"),
        "lon": item.get("mapx"),
        "source": "TourAPI",
    }


@router.get("")
def stay_list(
    region: str = Query(..., description="시도 (서울·제주 등, 필수)"),
    type_: str = Query("전체", alias="type", description="호텔·콘도·펜션·게스트하우스·모텔·한옥·전체"),
    pet: bool | None = Query(None, description="반려동물 동반 가능"),
):
    """지역별 숙박시설 목록."""
    cache_key = f"travel:stay:{region}:{type_}:{pet}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        keyword = type_ if type_ != "전체" else "숙박"
        params: dict = {
            "keyword": keyword,
            "contentTypeId": 32,
            "numOfRows": 100,
            "pageNo": 1,
        }
        if region in REGION_AREA:
            params["areaCode"] = REGION_AREA[region]

        raw = _tour_get("searchKeyword1", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [_parse_stay(i) for i in items_raw]
        resp = ok(items, meta={"region": region, "type": type_, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("stay_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_LIST)
    return resp


@router.get("/{stay_id}")
def stay_detail(stay_id: str = Path(description="숙박시설 contentId")):
    """숙박시설 상세 (이미지 + 근처 관광지 3개)."""
    cache_key = f"travel:stay:detail:{stay_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        # 기본 정보
        raw = _tour_get("detailCommon1", {
            "contentId": stay_id, "contentTypeId": 32,
            "defaultYN": "Y", "firstImageYN": "Y",
            "addrinfoYN": "Y", "mapinfoYN": "Y",
            "overviewYN": "Y",
        })
        item = ((raw.get("response", {}).get("body", {})
                    .get("items", {}) or {}).get("item") or [{}])
        detail_raw = item[0] if isinstance(item, list) else item
        detail = {
            "content_id": stay_id,
            "name": detail_raw.get("title"),
            "address": detail_raw.get("addr1"),
            "phone": detail_raw.get("tel"),
            "homepage": detail_raw.get("homepage"),
            "overview": (detail_raw.get("overview") or "")[:400],
            "thumbnail": detail_raw.get("firstimage"),
            "lat": detail_raw.get("mapy"),
            "lon": detail_raw.get("mapx"),
        }

        # 이미지
        try:
            img_raw = _tour_get("detailImage1", {
                "contentId": stay_id, "imageYN": "Y",
                "subImageYN": "Y", "numOfRows": 10, "pageNo": 1,
            })
            imgs = ((img_raw.get("response", {}).get("body", {})
                           .get("items", {}) or {}).get("item") or [])
            if isinstance(imgs, dict):
                imgs = [imgs]
            detail["images"] = [i.get("originimgurl") for i in imgs if i.get("originimgurl")]
        except Exception:
            detail["images"] = []

        # 근처 관광지 (반경 5km)
        detail["nearby"] = []
        if detail.get("lat") and detail.get("lon"):
            try:
                nb_raw = _tour_get("locationBasedList1", {
                    "mapX": detail["lon"], "mapY": detail["lat"],
                    "radius": 5000, "contentTypeId": 12,
                    "numOfRows": 3, "pageNo": 1,
                })
                nb_items = ((nb_raw.get("response", {}).get("body", {})
                                   .get("items", {}) or {}).get("item") or [])
                if isinstance(nb_items, dict):
                    nb_items = [nb_items]
                detail["nearby"] = [
                    {"name": n.get("title"), "address": n.get("addr1"), "thumbnail": n.get("firstimage")}
                    for n in nb_items[:3]
                ]
            except Exception:
                pass

        resp = ok(detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("stay_detail error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_DETAIL)
    return resp
