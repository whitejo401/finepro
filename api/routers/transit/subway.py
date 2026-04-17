"""transit/subway — 지하철 요금 체계 엔드포인트 (정적 테이블)."""
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL = 86400  # 24시간

# 지역별 지하철 요금 체계 (2024년 기준)
SUBWAY_FARE = {
    "서울": {
        "base_fare": 1400,
        "card_fare": 1400,
        "cash_fare": 1500,
        "youth_fare": 720,
        "child_fare": 450,
        "distance_surcharge": [
            {"km_range": "0~10km",  "fare": 0,   "note": "기본요금 구간"},
            {"km_range": "10~50km", "fare": 100, "per_km": 5,  "note": "5km마다 100원 추가"},
            {"km_range": "50km+",   "fare": 100, "per_km": 8,  "note": "8km마다 100원 추가"},
        ],
        "transfer_discount": "환승 시 기본요금 미중복 적용 (추가 거리요금만 부과)",
        "free_transfer_window_min": 30,
        "operator": "서울교통공사·코레일",
    },
    "부산": {
        "base_fare": 1400,
        "card_fare": 1400,
        "cash_fare": 1500,
        "youth_fare": 720,
        "child_fare": 450,
        "distance_surcharge": [
            {"km_range": "0~10km",  "fare": 0},
            {"km_range": "10km+",   "fare": 100, "per_km": 5},
        ],
        "transfer_discount": "부산 도시철도 내 환승 30분 무료",
        "free_transfer_window_min": 30,
        "operator": "부산교통공사",
    },
    "대구": {
        "base_fare": 1400,
        "card_fare": 1400,
        "cash_fare": 1500,
        "youth_fare": 720,
        "child_fare": 450,
        "distance_surcharge": [
            {"km_range": "0~10km", "fare": 0},
            {"km_range": "10km+",  "fare": 100, "per_km": 5},
        ],
        "transfer_discount": "대구 도시철도 내 환승 30분 무료",
        "free_transfer_window_min": 30,
        "operator": "대구도시철도공사",
    },
    "광주": {
        "base_fare": 1250,
        "card_fare": 1250,
        "cash_fare": 1350,
        "youth_fare": 630,
        "child_fare": 390,
        "distance_surcharge": [],
        "transfer_discount": "광주 도시철도 내 환승 무료",
        "free_transfer_window_min": 30,
        "operator": "광주도시철도공사",
    },
    "대전": {
        "base_fare": 1250,
        "card_fare": 1250,
        "cash_fare": 1350,
        "youth_fare": 630,
        "child_fare": 390,
        "distance_surcharge": [],
        "transfer_discount": "대전 도시철도 내 환승 무료",
        "free_transfer_window_min": 30,
        "operator": "대전도시철도공사",
    },
    "인천": {
        "base_fare": 1400,
        "card_fare": 1400,
        "cash_fare": 1500,
        "youth_fare": 720,
        "child_fare": 450,
        "distance_surcharge": [
            {"km_range": "0~10km",  "fare": 0},
            {"km_range": "10~50km", "fare": 100, "per_km": 5},
            {"km_range": "50km+",   "fare": 100, "per_km": 8},
        ],
        "transfer_discount": "수도권 통합 환승 적용 (서울·경기·인천 공통)",
        "free_transfer_window_min": 30,
        "operator": "인천교통공사",
    },
}

SUPPORTED_REGIONS = list(SUBWAY_FARE.keys())


@router.get("")
def subway_fare(
    region: str = Query("서울", description=f"지역: {', '.join(SUPPORTED_REGIONS)}"),
):
    """지하철 요금 체계 조회 (거리비례제·환승 할인)."""
    if region not in SUBWAY_FARE:
        raise HTTPException(status_code=422, detail=f"지원 지역: {SUPPORTED_REGIONS}")

    cache_key = f"transit:subway:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    info = SUBWAY_FARE[region]
    resp = ok({
        "region":               region,
        "base_fare":            info["base_fare"],
        "card_fare":            info["card_fare"],
        "cash_fare":            info["cash_fare"],
        "youth_fare":           info["youth_fare"],
        "child_fare":           info["child_fare"],
        "distance_surcharge":   info["distance_surcharge"],
        "transfer_discount":    info["transfer_discount"],
        "free_transfer_window_min": info["free_transfer_window_min"],
        "operator":             info["operator"],
    })
    cache.set(cache_key, resp, TTL)
    return resp


@router.get("/calc")
def subway_fare_calc(
    region: str = Query("서울", description=f"지역: {', '.join(SUPPORTED_REGIONS)}"),
    distance_km: float = Query(..., ge=0, description="이동 거리 (km)"),
    passenger: str = Query("adult", description="adult·youth·child"),
):
    """지하철 요금 계산기 (거리 입력 → 실제 요금)."""
    if region not in SUBWAY_FARE:
        raise HTTPException(status_code=422, detail=f"지원 지역: {SUPPORTED_REGIONS}")

    info = SUBWAY_FARE[region]
    base = info["card_fare"]

    # 거리 추가요금 계산
    extra = 0
    surcharges = info.get("distance_surcharge", [])
    if len(surcharges) >= 2 and distance_km > 10:
        over10 = min(distance_km - 10, 40)  # 10~50km 구간
        extra += int(over10 / 5) * 100
    if len(surcharges) >= 3 and distance_km > 50:
        over50 = distance_km - 50
        extra += int(over50 / 8) * 100

    total = base + extra

    # 승객 유형 할인
    if passenger == "youth":
        total = info["youth_fare"] + int(extra * 0.8)
    elif passenger == "child":
        total = info["child_fare"] + int(extra * 0.5)

    resp = ok({
        "region":        region,
        "distance_km":   distance_km,
        "passenger":     passenger,
        "base_fare":     base,
        "extra_fare":    extra,
        "total_fare":    total,
    })
    return resp
