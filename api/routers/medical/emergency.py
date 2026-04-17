"""medical/emergency + aed — 응급실 현황·AED 위치 엔드포인트."""
import logging
import math
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_ER  = 300    # 5분
TTL_AED = 86400  # 24시간

DATA_GO_BASE = "http://apis.data.go.kr"

REGION_CODE = {
    "서울": "110000", "부산": "260000", "대구": "270000", "인천": "280000",
    "광주": "290000", "대전": "300000", "울산": "310000", "세종": "360000",
    "경기": "410000", "강원": "420000", "충북": "430000", "충남": "440000",
    "전북": "450000", "전남": "460000", "경북": "470000", "경남": "480000", "제주": "500000",
}


def _data_go_get(path: str, params: dict) -> dict:
    import requests
    key = os.getenv("DATA_GO_KR_API_KEY", "")
    params.update({"serviceKey": key, "_type": "json"})
    resp = requests.get(f"{DATA_GO_BASE}{path}", params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _wait_status(total: int, available: int) -> str:
    if total == 0:
        return "정보없음"
    ratio = available / total
    if ratio > 0.5:
        return "여유"
    elif ratio >= 0.2:
        return "보통"
    return "혼잡"


@router.get("/emergency")
def emergency_status(
    region: str = Query(..., description="시도 (서울·경기 등, 필수)"),
):
    """응급실 실시간 현황 (병상 가용·대기 상태)."""
    if region not in REGION_CODE:
        raise HTTPException(status_code=422, detail=f"지원 지역: {list(REGION_CODE.keys())}")

    cache_key = f"medical:emergency:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        raw = _data_go_get(
            "/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire",
            {"STAGE1": REGION_CODE[region], "pageNo": 1, "numOfRows": 50},
        )
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = []
        for i in items_raw:
            total = int(i.get("hvec") or 0)
            avail = int(i.get("hvs01") or 0)
            items.append({
                "name": i.get("dutyName"),
                "address": i.get("dutyAddr"),
                "phone": i.get("dutyTel3") or i.get("dutyTel1"),
                "er_beds_total": total,
                "er_beds_available": avail,
                "wait_status": _wait_status(total, avail),
                "is_open": i.get("dutyEryn") == "1",
                "lat": i.get("wgs84Lat"),
                "lon": i.get("wgs84Lon"),
            })

        resp = ok(items, meta={"region": region, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("emergency_status error: %s", e)
        raise HTTPException(status_code=504 if "timeout" in str(e).lower() else 502, detail=str(e))

    cache.set(cache_key, resp, TTL_ER)
    return resp


@router.get("/aed")
def aed_nearby(
    lat: float = Query(..., description="위도 (예: 37.5665)"),
    lon: float = Query(..., description="경도 (예: 126.9780)"),
    radius: float = Query(0.5, description="반경 km (기본 0.5)"),
):
    """근처 AED(자동심장충격기) 위치."""
    cache_key = f"medical:aed:{round(lat,3)}:{round(lon,3)}:{radius}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        raw = _data_go_get(
            "/B552657/AEDInfoInqireService/getAEDLcinfoInqire",
            {"LAT": lat, "LOT": lon, "pageNo": 1, "numOfRows": 100},
        )
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        radius_m = radius * 1000
        items = []
        for i in items_raw:
            ilat = float(i.get("lat") or 0)
            ilon = float(i.get("lon") or 0)
            if not ilat or not ilon:
                continue
            dist = _haversine_m(lat, lon, ilat, ilon)
            if dist <= radius_m:
                items.append({
                    "name": i.get("buildAddress"),
                    "address": i.get("buildAddress"),
                    "location_detail": i.get("buildPlace"),
                    "lat": ilat,
                    "lon": ilon,
                    "distance_m": round(dist),
                    "available_hours": i.get("aedUseYmd") or "24시간",
                    "manager_phone": i.get("mgrTel"),
                })

        items.sort(key=lambda x: x["distance_m"])
        resp = ok(items, meta={"lat": lat, "lon": lon, "radius_km": radius, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("aed_nearby error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_AED)
    return resp
