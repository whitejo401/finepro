"""outdoor/recommend — 날씨 기반 캠핑·휴양림 추천 엔드포인트."""
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간

# 추천 적합 조건
RAIN_PROB_MAX = 30    # 강수확률 30% 이하
TEMP_MIN = 10         # 최저기온 10°C 이상
TEMP_MAX = 30         # 최고기온 30°C 이하

GOOD_REGIONS = ["강원", "경기", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]


def _get_weather_for_region(region: str, date: str) -> dict | None:
    """weather 라우터 캐시를 직접 조회 (내부 재활용)."""
    from api.routers.weather.forecast import CITY_COORDS
    city_map = {
        "서울": "seoul", "부산": "busan", "대구": "daegu", "인천": "incheon",
        "광주": "gwangju", "대전": "daejeon", "울산": "ulsan",
        "강원": "chuncheon", "경기": "suwon", "충북": "cheongju",
        "충남": "cheonan", "전북": "jeonju", "전남": "yeosu",
        "경북": "andong", "경남": "changwon", "제주": "jeju",
    }
    city = city_map.get(region)
    if not city:
        return None

    cache_key = f"weather:daily:{city}:7"
    cached = cache.get(cache_key)
    if not cached:
        return None

    for day in cached.get("data", []):
        if day.get("date") == date:
            return day
    return None


def _fetch_camping_sample(region: str) -> list[dict]:
    """캠핑장 캐시 조회 (없으면 간략 응답)."""
    cache_key = f"outdoor:camping:{region}:전체:None:None"
    cached = cache.get(cache_key)
    if cached:
        return cached.get("data", [])[:3]
    return []


@router.get("/recommend")
def outdoor_recommend(
    date: str = Query(..., description="추천 날짜 YYYY-MM-DD"),
    region: str | None = Query(None, description="특정 지역 (생략 시 전국)"),
    type_: str = Query("전체", alias="type", description="camping·forest·전체"),
):
    """날씨 기반 캠핑·휴양림 추천."""
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail="date는 YYYY-MM-DD 형식")

    cache_key = f"outdoor:recommend:{date}:{region}:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    target_regions = [region] if region else GOOD_REGIONS
    recommended: list[dict] = []
    weather_ok_regions: list[str] = []
    weather_missing = False

    for reg in target_regions:
        wx = _get_weather_for_region(reg, date)
        if wx is None:
            weather_missing = True
            # 날씨 없으면 전 지역 후보로 포함
            weather_ok_regions.append(reg)
            continue

        rain = wx.get("rain_prob") or wx.get("precipitation_prob") or 0
        t_max = wx.get("temp_max") or wx.get("max_temp") or 20
        t_min = wx.get("temp_min") or wx.get("min_temp") or 10

        if rain <= RAIN_PROB_MAX and TEMP_MIN <= t_min and t_max <= TEMP_MAX:
            weather_ok_regions.append(reg)
            camps = _fetch_camping_sample(reg)
            for c in camps:
                recommended.append({
                    "type": "camping",
                    "name": c.get("name"),
                    "region": reg,
                    "address": c.get("address"),
                    "reservation_url": c.get("reservation_url"),
                    "weather": f"강수{rain}% / {t_min}~{t_max}°C",
                })

    summary = (
        f"날씨 적합 지역: {', '.join(weather_ok_regions)}" if weather_ok_regions
        else "해당 날짜 추천 지역 없음"
    )

    meta: dict = {
        "date": date,
        "weather_summary": summary,
        "count": len(recommended),
    }
    if weather_missing:
        meta["note"] = "날씨 캐시 없음 — /api/v1/weather/forecast/daily 先 호출 권장"

    resp = ok(recommended, meta=meta)
    cache.set(cache_key, resp, TTL)
    return resp
