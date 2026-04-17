"""price/fuel — 오피넷 유가 엔드포인트."""
import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_PRICE = 600    # 10분
TTL_TREND = 3600   # 1시간

OPINET_BASE = "http://www.opinet.co.kr/api"

REGION_CODE = {
    "서울": "01", "부산": "02", "대구": "03", "인천": "04",
    "광주": "05", "대전": "06", "울산": "07", "세종": "08",
    "경기": "09", "강원": "10", "충북": "11", "충남": "12",
    "전북": "13", "전남": "14", "경북": "15", "경남": "16", "제주": "17",
}

FUEL_CODE = {"휘발유": "B027", "경유": "D047", "LPG": "K015", "등유": "C004"}


def _opinet_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("OPINET_API_KEY", "")
    params.update({"code": key, "out": "json"})
    resp = requests.get(f"{OPINET_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@router.get("")
def fuel_price(
    region: str = Query("전국", description="시도 (서울·부산 등 또는 전국)"),
    type_: str = Query("휘발유", alias="type", description="휘발유·경유·LPG"),
):
    """지역별 주유소 평균 유가 + 최저가 Top5."""
    cache_key = f"price:fuel:{region}:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("OPINET_API_KEY"):
        raise HTTPException(status_code=503, detail="OPINET_API_KEY 미설정")

    fuel_cd = FUEL_CODE.get(type_)
    if not fuel_cd:
        raise HTTPException(status_code=422, detail=f"지원 유종: {list(FUEL_CODE.keys())}")

    try:
        # 전국 평균
        nat_raw = _opinet_get("avgRecentPrice.do", {"prodcd": fuel_cd, "cnt": 1})
        nat_items = nat_raw.get("RESULT", {}).get("OIL", [])
        national_avg = int(nat_items[0].get("PRICE", 0)) if nat_items else None

        # 지역 평균
        region_avg = None
        if region != "전국" and region in REGION_CODE:
            reg_raw = _opinet_get("avgRecentPrice.do", {
                "prodcd": fuel_cd, "sido": REGION_CODE[region], "cnt": 1,
            })
            reg_items = reg_raw.get("RESULT", {}).get("OIL", [])
            region_avg = int(reg_items[0].get("PRICE", 0)) if reg_items else None

        avg = region_avg or national_avg

        # 최저가 Top5
        low5 = []
        try:
            low_params: dict = {"prodcd": fuel_cd, "cnt": 5}
            if region != "전국" and region in REGION_CODE:
                low_params["sido"] = REGION_CODE[region]
            low_raw = _opinet_get("lowTop10.do", low_params)
            for s in (low_raw.get("RESULT", {}).get("OIL", []) or [])[:5]:
                low5.append({
                    "name": s.get("OS_NM"),
                    "price": s.get("PRICE"),
                    "address": s.get("NEW_ADR"),
                    "phone": s.get("TEL"),
                })
        except Exception as e:
            logger.warning("최저가 Top5 조회 실패: %s", e)

        data = {
            "region": region,
            "type": type_,
            "avg_price": avg,
            "national_avg": national_avg,
            "diff_from_national": (avg - national_avg) if (avg and national_avg) else None,
            "low_top5": low5,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("fuel_price error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_PRICE)
    return resp


@router.get("/trend")
def fuel_trend(
    days: int = Query(30, description="7·30·90"),
    type_: str = Query("휘발유", alias="type", description="휘발유·경유·LPG"),
):
    """전국 평균 유가 추이."""
    cache_key = f"price:fuel:trend:{days}:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("OPINET_API_KEY"):
        raise HTTPException(status_code=503, detail="OPINET_API_KEY 미설정")

    fuel_cd = FUEL_CODE.get(type_)
    if not fuel_cd:
        raise HTTPException(status_code=422, detail=f"지원 유종: {list(FUEL_CODE.keys())}")

    try:
        raw = _opinet_get("avgRecentPrice.do", {"prodcd": fuel_cd, "cnt": min(days, 90)})
        items = raw.get("RESULT", {}).get("OIL", [])
        history = [
            {"date": i.get("DATE"), "price": i.get("PRICE")}
            for i in reversed(items)
        ]
        resp = ok(history, meta={"type": type_, "days": days, "count": len(history)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("fuel_trend error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_TREND)
    return resp
