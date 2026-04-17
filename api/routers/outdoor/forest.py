"""outdoor/forest + healing — 자연휴양림·치유의숲 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_FOREST  = 21600   # 6시간
TTL_HEALING = 43200   # 12시간

DATA_GO_BASE = "http://apis.data.go.kr"


def _data_go_get(path: str, params: dict) -> dict:
    import requests
    key = os.getenv("DATA_GO_KR_API_KEY", "")
    params.update({"serviceKey": key, "_type": "json"})
    resp = requests.get(f"{DATA_GO_BASE}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _parse_forest(item: dict) -> dict:
    return {
        "name": item.get("forestName") or item.get("huyangNm"),
        "region": item.get("siDo") or item.get("sido"),
        "address": item.get("address") or item.get("addr"),
        "phone": item.get("phoneNumber") or item.get("tel"),
        "facilities": [f.strip() for f in (item.get("facilities") or "").split(",") if f.strip()],
        "reservation_url": item.get("reservationUrl") or "https://huyang.go.kr",
        "homepage": item.get("homepage"),
        "fee": item.get("usageFee"),
        "source": "국립자연휴양림",
    }


def _parse_healing(item: dict) -> dict:
    return {
        "name": item.get("name") or item.get("forestNm"),
        "type": item.get("type") or "치유의숲",
        "region": item.get("sido"),
        "address": item.get("addr"),
        "phone": item.get("tel"),
        "program": item.get("program"),
        "reservation_url": item.get("homepage") or "https://healing.forest.go.kr",
        "source": "산림청",
    }


@router.get("/forest")
def forest_list(
    region: str = Query("전체", description="시도 (강원·경기 등 또는 전체)"),
):
    """전국 국립자연휴양림 목록."""
    cache_key = f"outdoor:forest:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        params: dict = {"numOfRows": 200, "pageNo": 1}
        if region != "전체":
            params["siDo"] = region

        raw = _data_go_get(
            "/1400119/forestRecreationService/forestRecreationList",
            params,
        )
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [_parse_forest(i) for i in items_raw]
        resp = ok(items, meta={"region": region, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("forest_list error: %s", e)
        # 키 없거나 API 변경 시 빈 응답 반환
        resp = ok([], meta={"region": region, "count": 0, "note": str(e)})

    cache.set(cache_key, resp, TTL_FOREST)
    return resp


@router.get("/healing")
def healing_list(
    region: str = Query("전체", description="시도 (충북·전남 등 또는 전체)"),
):
    """전국 치유의숲·산림욕장 목록."""
    cache_key = f"outdoor:healing:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        params: dict = {"numOfRows": 200, "pageNo": 1}
        if region != "전체":
            params["sido"] = region

        raw = _data_go_get(
            "/1400119/forestHealingService/forestHealingList",
            params,
        )
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [_parse_healing(i) for i in items_raw]
        resp = ok(items, meta={"region": region, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("healing_list error: %s", e)
        resp = ok([], meta={"region": region, "count": 0, "note": str(e)})

    cache.set(cache_key, resp, TTL_HEALING)
    return resp
