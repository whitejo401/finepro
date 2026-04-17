"""culture/festival — TourAPI 전국 축제·행사 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간

TOUR_BASE = "http://apis.data.go.kr/B551011/KorService1"

REGION_AREA = {
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
    "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
    "충북": 33, "충남": 34, "경북": 35, "경남": 36, "전북": 37,
    "전남": 38, "제주": 39,
}

THEME_KEYWORDS = {
    "음식": ["음식", "푸드", "맛", "먹거리"],
    "음악": ["음악", "뮤직", "재즈", "록"],
    "전통": ["전통", "민속", "한복", "풍물"],
    "빛": ["빛", "야경", "조명", "루미"],
    "꽃": ["꽃", "벚꽃", "장미", "국화", "매화"],
}


def _tour_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("TOUR_API_KEY", "")
    params.update({
        "serviceKey": key,
        "MobileOS": "ETC",
        "MobileApp": "InfoAPI",
        "_type": "json",
    })
    resp = requests.get(f"{TOUR_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _fmt_date(d: str | None) -> str | None:
    if not d or len(d) < 8:
        return d
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _parse_item(item: dict) -> dict:
    return {
        "id": f"tour_{item.get('contentid')}",
        "title": item.get("title"),
        "type": "축제/행사",
        "region": (item.get("addr1") or "").split()[0] if item.get("addr1") else None,
        "venue": item.get("addr1"),
        "start_date": _fmt_date(item.get("eventstartdate")),
        "end_date": _fmt_date(item.get("eventenddate")),
        "thumbnail": item.get("firstimage") or item.get("firstimage2"),
        "lat": item.get("mapy"),
        "lon": item.get("mapx"),
        "source": "TourAPI",
    }


@router.get("")
def festival_list(
    region: str = Query("전체", description="지역 (서울·부산 등 또는 전체)"),
    month: str | None = Query(None, description="YYYYMM — 생략 시 당월"),
    theme: str | None = Query(None, description="음식·음악·전통·빛·꽃"),
):
    """전국 축제·행사 목록 (테마·지역 필터)."""
    if not month:
        month = datetime.now().strftime("%Y%m")
    stdate = month + "01"
    etdate = month + "31"

    cache_key = f"culture:festival:{region}:{month}:{theme}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        params: dict = {
            "eventStartDate": stdate,
            "eventEndDate": etdate,
            "numOfRows": 100,
            "pageNo": 1,
            "arrange": "A",  # 제목순
        }
        if region != "전체" and region in REGION_AREA:
            params["areaCode"] = REGION_AREA[region]

        raw = _tour_get("searchFestival1", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [_parse_item(i) for i in items_raw]

        # 테마 필터
        if theme and theme in THEME_KEYWORDS:
            kws = THEME_KEYWORDS[theme]
            items = [i for i in items if any(kw in (i["title"] or "") for kw in kws)]

        resp = ok(items, meta={
            "region": region, "month": month, "theme": theme, "count": len(items),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("festival_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
