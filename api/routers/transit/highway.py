"""transit/highway — 고속도로 통행료 엔드포인트 (한국도로공사 API)."""
import logging
import os

import requests
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 86400  # 24시간

EX_KEY  = os.getenv("EX_API_KEY", "")
EX_BASE = "https://data.ex.co.kr/openapi/toll/search"

# 차종 코드 설명
VEHICLE_TYPE_DESC = {
    1: "승용차·소형승합차",
    2: "중형승합차",
    3: "대형승합차·2축화물",
    4: "특수대형차·3축화물",
    5: "4축 이상 화물",
}

# 정적 통행료 폴백 (서울↔부산 기준, 승용차)
STATIC_TOLL = {
    ("서울", "부산"):    {"toll_fee": 21700, "distance_km": 428},
    ("서울", "대구"):    {"toll_fee": 14400, "distance_km": 293},
    ("서울", "광주"):    {"toll_fee": 17700, "distance_km": 339},
    ("서울", "대전"):    {"toll_fee":  8000, "distance_km": 160},
    ("서울", "강릉"):    {"toll_fee": 10800, "distance_km": 212},
    ("서울", "전주"):    {"toll_fee": 13300, "distance_km": 248},
    ("서울", "울산"):    {"toll_fee": 19600, "distance_km": 395},
    ("서울", "청주"):    {"toll_fee":  5800, "distance_km": 131},
    ("서울", "창원"):    {"toll_fee": 18800, "distance_km": 377},
    ("서울", "여수"):    {"toll_fee": 19500, "distance_km": 374},
}


def _fetch_toll(from_: str, to: str, vehicle_type: int) -> dict | None:
    if not EX_KEY:
        return None
    params = {
        "key":         EX_KEY,
        "type":        "json",
        "startName":   from_,
        "endName":     to,
        "vehicleType": vehicle_type,
    }
    try:
        r = requests.get(EX_BASE, params=params, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        result = data.get("data", {})
        if not result:
            return None
        return {
            "toll_fee":    result.get("toll", 0),
            "distance_km": round(result.get("distance", 0) / 1000, 1),
        }
    except Exception as e:
        logger.debug("도로공사 API 오류: %s", e)
        return None


@router.get("")
def highway_toll(
    from_: str = Query(..., alias="from", description="출발 IC/지역명 (예: 서울)"),
    to: str = Query(..., description="도착 IC/지역명"),
    vehicle_type: int = Query(1, ge=1, le=5, description="차종 (1=승용차, 2=중형승합, 3=대형, 4=특수대형, 5=4축화물)"),
):
    """고속도로 통행료 조회."""
    cache_key = f"transit:highway:{from_}:{to}:{vehicle_type}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result = _fetch_toll(from_, to, vehicle_type)

    if not result:
        key = (from_, to)
        rev = (to, from_)
        if key in STATIC_TOLL:
            result = STATIC_TOLL[key]
        elif rev in STATIC_TOLL:
            result = STATIC_TOLL[rev]
        else:
            raise HTTPException(
                status_code=422,
                detail=f"지원 구간: {[f'{a}→{b}' for a, b in STATIC_TOLL.keys()]}",
            )
        # 차종별 요금 보정 (승용차 대비 배율)
        multipliers = {1: 1.0, 2: 1.4, 3: 2.0, 4: 2.7, 5: 3.0}
        result = {
            **result,
            "toll_fee": int(result["toll_fee"] * multipliers.get(vehicle_type, 1.0)),
        }

    resp = ok({
        "from":          from_,
        "to":            to,
        "vehicle_type":  vehicle_type,
        "vehicle_desc":  VEHICLE_TYPE_DESC.get(vehicle_type),
        "toll_fee":      result.get("toll_fee"),
        "distance_km":   result.get("distance_km"),
    })
    cache.set(cache_key, resp, TTL)
    return resp
