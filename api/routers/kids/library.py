"""kids/library — 도서관 정보나루 어린이 프로그램 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 10800  # 3시간

LIBRARY_BASE = "https://data4library.kr/api"

REGION_MAP = {
    "서울": "11", "부산": "21", "대구": "22", "인천": "23",
    "광주": "24", "대전": "25", "울산": "26", "세종": "29",
    "경기": "31", "강원": "32", "충북": "33", "충남": "34",
    "전북": "35", "전남": "36", "경북": "37", "경남": "38", "제주": "39",
}

AGE_KEYWORD = {
    "영유아": ["영유아", "유아", "아기"],
    "초등": ["초등", "어린이"],
    "중고등": ["청소년", "중학생", "고등학생"],
    "전체": [],
}


def _lib_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("LIBRARY_API_KEY", "")
    params.update({"authKey": key, "format": "json"})
    resp = requests.get(f"{LIBRARY_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _match_age(title: str, target: str) -> bool:
    if target == "전체":
        return True
    keywords = AGE_KEYWORD.get(target, [])
    return any(kw in title for kw in keywords)


@router.get("")
def kids_library(
    region: str = Query("전체", description="지역 (서울 등 또는 전체)"),
    age: str = Query("전체", description="영유아·초등·중고등·전체"),
    month: str | None = Query(None, description="YYYYMM — 생략 시 당월"),
):
    """도서관 어린이·청소년 독서·만들기 프로그램 목록."""
    if not month:
        month = datetime.now().strftime("%Y%m")

    cache_key = f"kids:library:{region}:{age}:{month}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    api_key = os.getenv("LIBRARY_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="LIBRARY_API_KEY 미설정")

    try:
        params: dict = {
            "month": month,
            "pageNo": 1,
            "pageSize": 100,
        }
        if region != "전체" and region in REGION_MAP:
            params["sido"] = REGION_MAP[region]

        raw = _lib_get("libSrchByEvent", params)
        events = (raw.get("response") or {}).get("result") or []
        if isinstance(events, dict):
            events = [events]

        items = []
        for e in events:
            title = e.get("eventNm") or ""
            if not _match_age(title, age):
                continue
            # 어린이·청소년 대상이 아닌 항목 제외
            target = e.get("eventTarget") or ""
            if age != "전체" and target and not _match_age(target, age):
                continue
            items.append({
                "library_name": e.get("libNm"),
                "program_title": title,
                "target": target,
                "start_date": e.get("startDate"),
                "end_date": e.get("endDate"),
                "region": e.get("sido"),
                "registration_url": e.get("homepage"),
                "admission": "무료",
                "source": "도서관정보나루",
            })

        resp = ok(items, meta={
            "region": region, "age": age, "month": month, "count": len(items),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("kids_library error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
