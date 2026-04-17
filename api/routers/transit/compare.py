"""transit/compare — 교통수단 통합 비교·ODsay 경로 요금 엔드포인트."""
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_COMPARE = 21600  # 6시간
TTL_ROUTE   = 600    # 10분

ODSAY_KEY  = os.getenv("ODSAY_API_KEY", "")
ODSAY_BASE = "https://api.odsay.com/v1/api"

# 자가용 기본 설정
DEFAULT_FUEL_EFFICIENCY = 12  # km/L
DEFAULT_FUEL_PRICE      = 1650  # 원/L (price 그룹 캐시에서 갱신 가능)

# 주요 구간 거리 (km) — compare용 자가용 유류비 계산
ROUTE_DISTANCE = {
    ("서울", "부산"):  428,
    ("서울", "대구"):  293,
    ("서울", "광주"):  339,
    ("서울", "대전"):  160,
    ("서울", "강릉"):  212,
    ("서울", "전주"):  248,
    ("서울", "울산"):  395,
    ("서울", "청주"):  131,
    ("서울", "창원"):  377,
    ("서울", "여수"):  374,
}

# CO₂ 배출 계수 (g/km per person)
CO2_PER_KM = {"KTX": 41, "고속버스": 58, "자가용": 167}


def _get_distance(from_: str, to: str) -> int | None:
    key = (from_, to)
    rev = (to, from_)
    return ROUTE_DISTANCE.get(key) or ROUTE_DISTANCE.get(rev)


def _get_fuel_price() -> int:
    """price 그룹 캐시에서 휘발유 가격 조회 (없으면 기본값)."""
    cached = cache.get("transit:fuel_price")
    if cached:
        return cached
    # price 그룹 캐시 키 시도
    fuel_cache = cache.get("price:fuel:recent")
    if fuel_cache and isinstance(fuel_cache, dict):
        data = fuel_cache.get("data", {})
        gasoline = data.get("gasoline_avg") or data.get("gasoline")
        if gasoline:
            price = int(gasoline)
            cache.set("transit:fuel_price", price, 3600)
            return price
    return DEFAULT_FUEL_PRICE


def _fetch_odsay_route(from_xy: str, to_xy: str) -> list[dict]:
    if not ODSAY_KEY:
        return []
    try:
        fx, fy = from_xy.split(",")
        tx, ty = to_xy.split(",")
        params = {
            "apiKey":  ODSAY_KEY,
            "SX": fx.strip(), "SY": fy.strip(),
            "EX": tx.strip(), "EY": ty.strip(),
            "SearchType": "0",
            "SearchPathType": "0",
        }
        r = requests.get(f"{ODSAY_BASE}/searchPubTransPathT", params=params, timeout=8)
        if r.status_code != 200:
            return []
        data = r.json()
        paths = data.get("result", {}).get("path", [])
        routes = []
        for path in paths[:3]:
            info = path.get("info", {})
            routes.append({
                "total_fare":     info.get("payment", 0),
                "duration_min":   info.get("totalTime", 0),
                "transfer_count": info.get("busTransitCount", 0) + info.get("subwayTransitCount", 0),
                "walk_min":       info.get("totalWalk", 0) // 60,
                "distance_m":     info.get("totalDistance", 0),
            })
        return routes
    except Exception as e:
        logger.debug("ODsay API 오류: %s", e)
        return []


@router.get("/route/fare")
def route_fare(
    from_: str = Query(..., alias="from", description="출발지 위경도 (경도,위도) 또는 지역명"),
    to: str = Query(..., description="도착지 위경도 (경도,위도) 또는 지역명"),
):
    """ODsay 대중교통 경로·요금 (최적 3경로)."""
    cache_key = f"transit:route:{from_}:{to}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not ODSAY_KEY:
        raise HTTPException(status_code=503, detail="ODSAY_API_KEY 미설정")

    routes = _fetch_odsay_route(from_, to)
    resp = ok(routes, meta={"from": from_, "to": to, "count": len(routes)})
    cache.set(cache_key, resp, TTL_ROUTE)
    return resp


@router.get("/compare")
def transit_compare(
    from_: str = Query(..., alias="from", description="출발지 (예: 서울)"),
    to: str = Query(..., description="도착지 (예: 부산)"),
):
    """교통수단 요금 통합 비교 (KTX·버스·자가용)."""
    cache_key = f"transit:compare:{from_}:{to}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    date = datetime.now().strftime("%Y%m%d")

    # 내부 캐시 or 직접 임포트하지 않고 정적 데이터로 직접 처리
    from .train import STATIC_FARES
    from .bus import STATIC_BUS_FARES
    from .highway import STATIC_TOLL

    comparison = []

    # KTX
    train_key = (from_, to) if (from_, to) in STATIC_FARES else ((to, from_) if (to, from_) in STATIC_FARES else None)
    if train_key:
        for fare in STATIC_FARES[train_key]:
            dist = _get_distance(from_, to)
            co2 = int(dist * CO2_PER_KM["KTX"]) if dist else None
            comparison.append({
                "mode":         fare["type"],
                "grade":        fare.get("grade"),
                "price":        fare["price"],
                "duration_min": fare.get("duration_min"),
                "co2_g":        co2,
                "toll":         None,
            })

    # 고속버스
    bus_key = (from_, to) if (from_, to) in STATIC_BUS_FARES else ((to, from_) if (to, from_) in STATIC_BUS_FARES else None)
    if bus_key:
        info = STATIC_BUS_FARES[bus_key]
        dist = _get_distance(from_, to)
        co2 = int(dist * CO2_PER_KM["고속버스"]) if dist else None
        for grade in ["우등", "일반"]:
            comparison.append({
                "mode":         f"고속버스({grade})",
                "grade":        grade,
                "price":        info[grade],
                "duration_min": info["duration_min"],
                "co2_g":        co2,
                "toll":         None,
            })

    # 자가용
    dist = _get_distance(from_, to)
    toll_key = (from_, to) if (from_, to) in STATIC_TOLL else ((to, from_) if (to, from_) in STATIC_TOLL else None)
    toll = STATIC_TOLL[toll_key]["toll_fee"] if toll_key else 0
    if dist:
        fuel_price = _get_fuel_price()
        fuel_cost  = int(dist / DEFAULT_FUEL_EFFICIENCY * fuel_price)
        co2 = int(dist * CO2_PER_KM["자가용"])
        avg_speed  = 100  # km/h 고속도로 평균
        duration   = int(dist / avg_speed * 60)
        comparison.append({
            "mode":         "자가용",
            "grade":        None,
            "price":        fuel_cost + toll,
            "duration_min": duration,
            "co2_g":        co2,
            "toll":         toll,
            "fuel_cost":    fuel_cost,
            "fuel_price":   fuel_price,
            "distance_km":  dist,
        })

    if not comparison:
        raise HTTPException(
            status_code=422,
            detail=f"지원 구간이 없습니다. 지원 구간: {[f'{a}→{b}' for a, b in STATIC_TOLL.keys()]}",
        )

    # 요금순 정렬
    comparison.sort(key=lambda x: x.get("price") or 0)

    resp = ok({"from": from_, "to": to, "comparison": comparison})
    cache.set(cache_key, resp, TTL_COMPARE)
    return resp
