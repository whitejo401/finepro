"""seasonal/now — 현재 계절 기준 오픈 시설 통합 엔드포인트."""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 1800  # 30분


def _get_season(month: int) -> str:
    if month in [6, 7, 8]:  return "summer"
    if month in [12, 1, 2]: return "winter"
    if month in [3, 4, 5]:  return "spring"
    return "autumn"


def _safe_call(fn, *args, **kwargs) -> list:
    try:
        result = fn(*args, **kwargs)
        return result.get("data") or [] if isinstance(result, dict) else []
    except Exception as e:
        logger.warning("seasonal.now 내부 호출 실패: %s", e)
        return []


@router.get("/now")
def seasonal_now():
    """현재 계절 기준 오픈 중인 시설 전체 목록."""
    cached = cache.get("seasonal:now")
    if cached:
        return cached

    today = datetime.now()
    season = _get_season(today.month)
    today_str = today.strftime("%Y-%m-%d")
    soon_cutoff = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    open_facilities: dict = {}
    opening_soon: list = []
    off_season = season in ["spring", "autumn"]

    if season == "summer" or off_season:
        # 여름 시설 캐시 직접 조회
        for key_suffix, label in [
            ("water:전체:전체", "water"),
            ("beach:전체", "beach"),
            ("valley:전체", "valley"),
        ]:
            cached_data = cache.get(f"seasonal:{key_suffix}")
            items = (cached_data.get("data") or []) if cached_data else []
            open_items = [i for i in items if i.get("is_open")]
            soon_items = [
                {**i, "days_left": (datetime.strptime(i["open_date"], "%Y-%m-%d") - today).days}
                for i in items
                if not i.get("is_open") and i.get("open_date") and today_str <= i["open_date"] <= soon_cutoff
            ] if not open_items else []
            open_facilities[label] = open_items
            opening_soon.extend(soon_items)

    if season == "winter" or off_season:
        for key_suffix, label in [
            ("ski:전체", "ski"),
            ("ice:전체:전체", "ice"),
        ]:
            cached_data = cache.get(f"seasonal:{key_suffix}")
            items = (cached_data.get("data") or []) if cached_data else []
            open_items = [i for i in items if i.get("is_open")]
            open_facilities[label] = open_items

    meta: dict = {
        "season": season,
        "date": today_str,
        "off_season": off_season,
    }
    if off_season:
        meta["note"] = "봄·가을: 개장 예정(D-7 이내) 시설 포함. 캐시 선호출 권장: /seasonal/water, /seasonal/ski"

    resp = ok(
        {"open_facilities": open_facilities, "opening_soon": opening_soon},
        meta=meta,
    )
    cache.set("seasonal:now", resp, TTL)
    return resp
