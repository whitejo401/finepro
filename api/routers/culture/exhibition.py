"""culture/exhibition — 전시·박물관·미술관 행사 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 10800  # 3시간

CULTURE_BASE = "https://www.culture.go.kr/openapi/rest"


def _culture_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("CULTURE_API_KEY", "")
    params.update({"serviceKey": key, "type": "json"})
    resp = requests.get(f"{CULTURE_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _parse_item(item: dict) -> dict:
    return {
        "title": item.get("title") or item.get("exhNm"),
        "type": item.get("subCategory") or "전시",
        "organizer": item.get("host") or item.get("organizer"),
        "venue": item.get("place") or item.get("exhPlace"),
        "region": item.get("area") or item.get("sido"),
        "start_date": item.get("startDate") or item.get("exhPeriodStart"),
        "end_date": item.get("endDate") or item.get("exhPeriodEnd"),
        "admission": item.get("useFee") or "확인 필요",
        "url": item.get("url") or item.get("homepage"),
        "thumbnail": item.get("thumbnail") or item.get("imgUrl"),
        "source": "문화공공데이터",
    }


@router.get("")
def exhibition_list(
    region: str = Query("전체", description="지역 (서울·부산 등 또는 전체)"),
    type_: str = Query("전체", alias="type", description="박물관·미술관·전시·전체"),
    month: str | None = Query(None, description="YYYYMM — 생략 시 당월"),
):
    """전시·박물관·미술관 행사 목록."""
    if not month:
        month = datetime.now().strftime("%Y%m")
    stdate = month + "01"
    etdate = month + "31"

    cache_key = f"culture:exhibition:{region}:{type_}:{month}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("CULTURE_API_KEY"):
        raise HTTPException(status_code=503, detail="CULTURE_API_KEY 미설정")

    try:
        params: dict = {
            "from": stdate,
            "to": etdate,
            "rows": 100,
            "start": 1,
        }
        if region != "전체":
            params["sido"] = region
        if type_ not in ("전체", None):
            params["subCategory"] = type_

        raw = _culture_get("publicperformancefestivals", params)
        body = (raw.get("response") or {}).get("body") or {}
        items_raw = (body.get("items") or {}).get("item") or []
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [_parse_item(i) for i in items_raw if isinstance(i, dict)]

        resp = ok(items, meta={
            "region": region, "type": type_, "month": month, "count": len(items),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("exhibition_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
