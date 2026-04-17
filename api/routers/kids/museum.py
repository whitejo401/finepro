"""kids/museum — 박물관·미술관 어린이 체험교육 프로그램 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 10800  # 3시간

CULTURE_BASE = "http://www.culture.go.kr/openapi/rest"
EMUSEUM_BASE  = "https://www.emuseum.go.kr/openapi"


def _culture_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("CULTURE_API_KEY", "")
    params.update({"serviceKey": key, "type": "json"})
    resp = requests.get(f"{CULTURE_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _emuseum_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("EMUSEUM_API_KEY", "")
    params.update({"apiKey": key, "returnType": "json"})
    resp = requests.get(f"{EMUSEUM_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _parse_culture_item(item: dict) -> dict:
    return {
        "title": item.get("title"),
        "organizer": item.get("host"),
        "venue": item.get("place"),
        "region": item.get("area"),
        "start_date": item.get("startDate"),
        "end_date": item.get("endDate"),
        "admission": item.get("useFee") or "무료",
        "capacity": item.get("quota"),
        "reservation_required": bool(item.get("bookingUrl")),
        "registration_url": item.get("bookingUrl") or item.get("url"),
        "image_url": item.get("thumbnail"),
        "source": "문화공공데이터",
    }


def _parse_emuseum_item(item: dict) -> dict:
    return {
        "title": item.get("progTitle") or item.get("title"),
        "organizer": item.get("museum") or "국립박물관",
        "venue": item.get("place"),
        "region": None,
        "start_date": item.get("startDt"),
        "end_date": item.get("endDt"),
        "admission": "무료",
        "capacity": item.get("quota"),
        "reservation_required": True,
        "registration_url": item.get("homepage"),
        "image_url": item.get("thumbUrl"),
        "source": "e뮤지엄",
    }


@router.get("")
def kids_museum(
    region: str = Query("전체", description="지역 (서울 등 또는 전체)"),
    age: str = Query("전체", description="영유아·초등·중고등·전체"),
    month: str | None = Query(None, description="YYYYMM — 생략 시 당월"),
):
    """박물관·미술관 어린이 체험교육 프로그램 통합 목록."""
    if not month:
        month = datetime.now().strftime("%Y%m")
    stdate = month + "01"
    etdate = month + "31"

    cache_key = f"kids:museum:{region}:{age}:{month}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    items: list[dict] = []
    partial = False

    # 1) 문화공공데이터광장
    culture_key = os.getenv("CULTURE_API_KEY", "")
    if culture_key:
        try:
            params: dict = {
                "from": stdate,
                "to": etdate,
                "keyword": "어린이",
                "rows": 100,
                "start": 1,
            }
            if region != "전체":
                params["sido"] = region
            raw = _culture_get("publicperformancefestivals", params)
            for item in (raw.get("response") or {}).get("body", {}).get("items", {}).get("item", []):
                if isinstance(item, dict):
                    items.append(_parse_culture_item(item))
        except Exception as e:
            logger.warning("문화공공데이터 실패: %s", e)
            partial = True
    else:
        partial = True

    # 2) e뮤지엄
    emuseum_key = os.getenv("EMUSEUM_API_KEY", "")
    if emuseum_key:
        try:
            raw = _emuseum_get("/education/list", {
                "startDt": stdate,
                "endDt": etdate,
                "target": "어린이",
                "pageUnit": 50,
                "pageIndex": 1,
            })
            for item in (raw.get("list") or []):
                items.append(_parse_emuseum_item(item))
        except Exception as e:
            logger.warning("e뮤지엄 실패: %s", e)
            partial = True
    else:
        partial = True

    meta = {
        "region": region, "age": age, "month": month,
        "count": len(items),
    }
    if partial:
        meta["partial"] = True
        meta["note"] = "일부 소스 누락 — API 키 확인 필요"
    if not items:
        meta["tip"] = "검색 조건을 넓혀보세요"

    resp = ok(items, meta=meta)
    cache.set(cache_key, resp, TTL)
    return resp
