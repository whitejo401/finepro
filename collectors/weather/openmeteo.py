"""Open-Meteo 날씨 수집기 — API 키 불필요, 완전 무료."""
import logging
from datetime import date, timedelta

import requests

from collectors.weather.cities import WMO_CODE

log = logging.getLogger(__name__)

_BASE      = "https://api.open-meteo.com/v1"
_BASE_AQI  = "https://air-quality-api.open-meteo.com/v1"

# 현재 날씨 요청 변수
_CURRENT_VARS = [
    "temperature_2m", "relative_humidity_2m", "apparent_temperature",
    "weather_code", "wind_speed_10m", "wind_direction_10m",
    "precipitation", "surface_pressure", "visibility",
    "uv_index", "is_day",
]

# 일별 예보 변수
_DAILY_VARS = [
    "weather_code", "temperature_2m_max", "temperature_2m_min",
    "apparent_temperature_max", "apparent_temperature_min",
    "sunrise", "sunset", "precipitation_sum", "wind_speed_10m_max",
    "uv_index_max", "precipitation_probability_max",
]

# 시간별 예보 변수 (24h)
_HOURLY_VARS = [
    "temperature_2m", "relative_humidity_2m", "apparent_temperature",
    "weather_code", "precipitation_probability", "wind_speed_10m",
]


def get_current(lat: float, lon: float, timezone: str = "auto") -> dict:
    """현재 날씨 조회.

    Args:
        lat: 위도
        lon: 경도
        timezone: 타임존 (기본 auto)

    Returns:
        현재 날씨 dict
    """
    params = {
        "latitude":  lat,
        "longitude": lon,
        "current":   ",".join(_CURRENT_VARS),
        "timezone":  timezone,
    }
    try:
        resp = requests.get(f"{_BASE}/forecast", params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        current = raw.get("current", {})
        code = current.get("weather_code")
        current["weather_description"] = WMO_CODE.get(code, "알 수 없음")
        return {
            "timezone":   raw.get("timezone"),
            "latitude":   lat,
            "longitude":  lon,
            "current":    current,
        }
    except Exception as e:
        log.error("Open-Meteo 현재 날씨 수집 실패 (%.4f, %.4f): %s", lat, lon, e)
        return {}


def get_forecast(lat: float, lon: float, days: int = 7, timezone: str = "auto") -> dict:
    """일별 예보 조회.

    Args:
        lat: 위도
        lon: 경도
        days: 예보 일수 (1~16)
        timezone: 타임존

    Returns:
        일별 예보 dict
    """
    days = max(1, min(days, 16))
    params = {
        "latitude":       lat,
        "longitude":      lon,
        "daily":          ",".join(_DAILY_VARS),
        "forecast_days":  days,
        "timezone":       timezone,
    }
    try:
        resp = requests.get(f"{_BASE}/forecast", params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        daily = raw.get("daily", {})

        # 날짜별로 재구성
        dates = daily.get("time", [])
        records = []
        for i, d in enumerate(dates):
            rec = {"date": d}
            for key in _DAILY_VARS:
                values = daily.get(key, [])
                rec[key] = values[i] if i < len(values) else None
            code = rec.get("weather_code")
            rec["weather_description"] = WMO_CODE.get(code, "알 수 없음")
            records.append(rec)

        return {
            "timezone":  raw.get("timezone"),
            "latitude":  lat,
            "longitude": lon,
            "days":      len(records),
            "forecast":  records,
        }
    except Exception as e:
        log.error("Open-Meteo 예보 수집 실패 (%.4f, %.4f): %s", lat, lon, e)
        return {}


def get_hourly(lat: float, lon: float, timezone: str = "auto") -> dict:
    """오늘 + 내일 시간별 예보.

    Returns:
        시간별 예보 리스트
    """
    params = {
        "latitude":      lat,
        "longitude":     lon,
        "hourly":        ",".join(_HOURLY_VARS),
        "forecast_days": 2,
        "timezone":      timezone,
    }
    try:
        resp = requests.get(f"{_BASE}/forecast", params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        hourly = raw.get("hourly", {})

        times = hourly.get("time", [])
        records = []
        for i, t in enumerate(times):
            rec = {"time": t}
            for key in _HOURLY_VARS:
                values = hourly.get(key, [])
                rec[key] = values[i] if i < len(values) else None
            code = rec.get("weather_code")
            rec["weather_description"] = WMO_CODE.get(code, "알 수 없음")
            records.append(rec)

        return {
            "timezone": raw.get("timezone"),
            "latitude": lat,
            "longitude": lon,
            "hourly":   records,
        }
    except Exception as e:
        log.error("Open-Meteo 시간별 예보 수집 실패: %s", e)
        return {}


def get_aqi(lat: float, lon: float, timezone: str = "auto") -> dict:
    """대기질(미세먼지·오존·UV) 조회.

    Returns:
        현재 대기질 dict (pm10, pm2_5, european_aqi 등)
    """
    params = {
        "latitude":  lat,
        "longitude": lon,
        "current":   "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone,european_aqi,us_aqi",
        "timezone":  timezone,
    }
    try:
        resp = requests.get(f"{_BASE_AQI}/air-quality", params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        current = raw.get("current", {})

        # 미세먼지 등급 (한국 기준)
        pm10 = current.get("pm10")
        pm25 = current.get("pm2_5")
        current["pm10_grade"]  = _pm10_grade(pm10)
        current["pm25_grade"]  = _pm25_grade(pm25)

        return {
            "timezone":  raw.get("timezone"),
            "latitude":  lat,
            "longitude": lon,
            "aqi":       current,
        }
    except Exception as e:
        log.error("Open-Meteo 대기질 수집 실패: %s", e)
        return {}


def _pm10_grade(val: float | None) -> str:
    if val is None:
        return "알 수 없음"
    if val <= 30:   return "좋음"
    if val <= 80:   return "보통"
    if val <= 150:  return "나쁨"
    return "매우나쁨"


def _pm25_grade(val: float | None) -> str:
    if val is None:
        return "알 수 없음"
    if val <= 15:   return "좋음"
    if val <= 35:   return "보통"
    if val <= 75:   return "나쁨"
    return "매우나쁨"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== 서울 현재 날씨 ===")
    import json
    print(json.dumps(get_current(37.5665, 126.9780, timezone="Asia/Seoul"), ensure_ascii=False, indent=2))
    print("\n=== 서울 대기질 ===")
    print(json.dumps(get_aqi(37.5665, 126.9780, timezone="Asia/Seoul"), ensure_ascii=False, indent=2))
