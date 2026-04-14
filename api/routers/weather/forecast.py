"""weather/forecast — 날씨 엔드포인트 (Open-Meteo, 키 불필요)."""
from fastapi import APIRouter, HTTPException, Query
from typing import Annotated

from api.core.cache import cache
from api.core.response import ok
from collectors.weather.cities import CITIES

router = APIRouter()

TTL_CURRENT  = 60 * 10   # 10분
TTL_FORECAST = 60 * 30   # 30분
TTL_AQI      = 60 * 10   # 10분


def _resolve_location(
    city: str | None,
    lat: float | None,
    lon: float | None,
) -> tuple[float, float, str]:
    """도시명 또는 좌표로 위치 결정. (lat, lon, timezone) 반환."""
    if city:
        city_key = city.lower().replace(" ", "")
        info = CITIES.get(city_key)
        if not info:
            raise HTTPException(
                status_code=404,
                detail=f"'{city}' 도시 없음. 지원 도시: {', '.join(CITIES.keys())}",
            )
        return info["lat"], info["lon"], info["timezone"]

    if lat is not None and lon is not None:
        return lat, lon, "auto"

    raise HTTPException(status_code=422, detail="city 또는 lat+lon 중 하나를 입력하세요.")


@router.get("/current")
def current_weather(
    city: str   | None = Query(None,  description="도시 (예: seoul, tokyo, newyork)"),
    lat:  float | None = Query(None,  description="위도 (city 미입력 시 필수)"),
    lon:  float | None = Query(None,  description="경도 (city 미입력 시 필수)"),
):
    """현재 날씨 — 기온·체감온도·습도·풍속·날씨코드·UV지수."""
    resolved_lat, resolved_lon, tz = _resolve_location(city, lat, lon)
    key = f"weather:current:{resolved_lat:.4f}:{resolved_lon:.4f}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.weather.openmeteo import get_current
        data = get_current(resolved_lat, resolved_lon, timezone=tz)
        if not data:
            raise HTTPException(status_code=502, detail="날씨 데이터 수집 실패")
        if city:
            data["city"] = city.lower()
            data["city_ko"] = CITIES[city.lower().replace(" ", "")].get("name_ko", "")
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_CURRENT)
    return resp


@router.get("/daily")
def daily_forecast(
    city: str   | None = Query(None, description="도시 (예: seoul, busan, tokyo)"),
    lat:  float | None = Query(None, description="위도"),
    lon:  float | None = Query(None, description="경도"),
    days: int          = Query(7,    description="예보 일수 (1~16)", ge=1, le=16),
):
    """일별 날씨 예보 — 최고·최저 기온, 강수량, 일출·일몰, UV."""
    resolved_lat, resolved_lon, tz = _resolve_location(city, lat, lon)
    key = f"weather:daily:{resolved_lat:.4f}:{resolved_lon:.4f}:{days}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.weather.openmeteo import get_forecast
        data = get_forecast(resolved_lat, resolved_lon, days=days, timezone=tz)
        if not data:
            raise HTTPException(status_code=502, detail="예보 데이터 수집 실패")
        if city:
            data["city"] = city.lower()
            data["city_ko"] = CITIES[city.lower().replace(" ", "")].get("name_ko", "")
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_FORECAST)
    return resp


@router.get("/hourly")
def hourly_forecast(
    city: str   | None = Query(None, description="도시"),
    lat:  float | None = Query(None, description="위도"),
    lon:  float | None = Query(None, description="경도"),
):
    """오늘+내일 시간별 날씨 예보 (48시간)."""
    resolved_lat, resolved_lon, tz = _resolve_location(city, lat, lon)
    key = f"weather:hourly:{resolved_lat:.4f}:{resolved_lon:.4f}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.weather.openmeteo import get_hourly
        data = get_hourly(resolved_lat, resolved_lon, timezone=tz)
        if not data:
            raise HTTPException(status_code=502, detail="시간별 예보 수집 실패")
        if city:
            data["city"] = city.lower()
            data["city_ko"] = CITIES[city.lower().replace(" ", "")].get("name_ko", "")
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_FORECAST)
    return resp


@router.get("/aqi")
def air_quality(
    city: str   | None = Query(None, description="도시"),
    lat:  float | None = Query(None, description="위도"),
    lon:  float | None = Query(None, description="경도"),
):
    """대기질 — PM10·PM2.5·오존·유럽AQI·미국AQI + 한국 기준 등급."""
    resolved_lat, resolved_lon, tz = _resolve_location(city, lat, lon)
    key = f"weather:aqi:{resolved_lat:.4f}:{resolved_lon:.4f}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.weather.openmeteo import get_aqi
        data = get_aqi(resolved_lat, resolved_lon, timezone=tz)
        if not data:
            raise HTTPException(status_code=502, detail="대기질 데이터 수집 실패")
        if city:
            data["city"] = city.lower()
            data["city_ko"] = CITIES[city.lower().replace(" ", "")].get("name_ko", "")
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_AQI)
    return resp


@router.get("/cities")
def cities_list():
    """지원 도시 목록."""
    return ok([
        {"key": k, "name_ko": v["name_ko"], "lat": v["lat"], "lon": v["lon"]}
        for k, v in CITIES.items()
    ])
