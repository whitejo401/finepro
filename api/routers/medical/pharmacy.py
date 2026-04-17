"""medical/pharmacy — 근처 약국 엔드포인트."""
import logging
import math
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 600  # 10분

DATA_GO_BASE = "http://apis.data.go.kr"


def _data_go_get(path: str, params: dict) -> dict:
    import requests
    key = os.getenv("DATA_GO_KR_API_KEY", "")
    params.update({"serviceKey": key, "_type": "json"})
    resp = requests.get(f"{DATA_GO_BASE}{path}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


@router.get("")
def pharmacy_nearby(
    lat: float = Query(..., description="위도 (필수)"),
    lon: float = Query(..., description="경도 (필수)"),
    radius: float = Query(1.0, description="반경 km (기본 1.0)"),
    open_now: bool | None = Query(None, description="현재 운영 중인 곳만"),
):
    """위경도 기반 근처 약국 목록 (거리순)."""
    cache_key = f"medical:pharmacy:{round(lat,3)}:{round(lon,3)}:{radius}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        raw = _data_go_get(
            "/B552657/ErmctInsttInfoInqireService/getParmacyLcinfoInqire",
            {"LAT": lat, "LOT": lon, "pageNo": 1, "numOfRows": 100},
        )
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        radius_m = radius * 1000
        from datetime import datetime
        now = datetime.now()
        now_hhmm = now.hour * 100 + now.minute
        weekday = now.weekday()  # 0=월

        items = []
        for i in items_raw:
            ilat = float(i.get("wgs84Lat") or 0)
            ilon = float(i.get("wgs84Lon") or 0)
            if not ilat or not ilon:
                continue
            dist = _haversine_m(lat, lon, ilat, ilon)
            if dist > radius_m:
                continue

            # 운영시간 파싱 (dutyTime1s~dutyTime7s/e: 1=월)
            day_key = str(weekday + 1)
            open_t = i.get(f"dutyTime{day_key}s")
            close_t = i.get(f"dutyTime{day_key}c")
            is_open = False
            if open_t and close_t:
                try:
                    is_open = int(open_t) <= now_hhmm <= int(close_t)
                except Exception:
                    pass

            items.append({
                "name": i.get("dutyName"),
                "address": i.get("dutyAddr"),
                "phone": i.get("dutyTel1"),
                "distance_m": round(dist),
                "hours": f"{open_t or '?'}~{close_t or '?'}",
                "open_now": is_open,
                "lat": ilat,
                "lon": ilon,
            })

        if open_now is not None:
            items = [x for x in items if x["open_now"] == open_now]

        items.sort(key=lambda x: x["distance_m"])
        resp = ok(items, meta={"lat": lat, "lon": lon, "radius_km": radius, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("pharmacy_nearby error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
