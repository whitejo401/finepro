"""indicator/calendar — 주요 경제지표 발표 일정 엔드포인트."""
import os
import logging
from datetime import datetime, timezone

import requests
from fastapi import APIRouter

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.indicator.calendar")

TTL = 60 * 60  # 1시간

FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# FRED release ID 매핑
_FRED_RELEASES = {
    10:  {"indicator": "CPI",        "country": "US", "importance": "high"},
    50:  {"indicator": "Employment",  "country": "US", "importance": "high"},
    53:  {"indicator": "GDP",         "country": "US", "importance": "high"},
    14:  {"indicator": "PPI",         "country": "US", "importance": "medium"},
    54:  {"indicator": "PCE",         "country": "US", "importance": "high"},
    113: {"indicator": "FOMC",        "country": "US", "importance": "high"},
    20:  {"indicator": "ISM_MFG_PMI", "country": "US", "importance": "medium"},
}

# 고정 KR 발표 일정 (매달 업데이트 필요한 구조 — 공휴일 제외 영업일 기준 근사치)
_KR_STATIC_SCHEDULE = [
    {"indicator": "CPI",         "country": "KR", "importance": "high",   "note": "매달 초 발표 (통계청)"},
    {"indicator": "GDP",         "country": "KR", "importance": "high",   "note": "분기말 +25일 전후 (한국은행)"},
    {"indicator": "Employment",  "country": "KR", "importance": "high",   "note": "매달 중순 발표 (통계청)"},
    {"indicator": "Trade",       "country": "KR", "importance": "medium", "note": "매달 1일 전후 발표 (관세청)"},
    {"indicator": "M2",          "country": "KR", "importance": "medium", "note": "매달 말 발표 (한국은행)"},
]


def _fetch_fred_release_dates(release_id: int, from_date: str, to_date: str) -> list[dict]:
    """FRED release dates API 호출."""
    if not FRED_API_KEY:
        return []
    url = "https://api.stlouisfed.org/fred/release/dates"
    params = {
        "release_id": release_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "realtime_start": from_date,
        "realtime_end": to_date,
        "include_release_dates_with_no_data": "false",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        dates = resp.json().get("release_dates", [])
        return [d["date"] for d in dates if isinstance(d, dict) and "date" in d]
    except Exception as e:
        log.warning("FRED release dates 실패 (release_id=%d): %s", release_id, e)
        return []


@router.get("/calendar")
def calendar():
    """주요 경제지표 발표 일정 — 이번 달 + 다음 달.

    - US: FRED release dates API (CPI/GDP/Employment/PPI/PCE/FOMC/ISM)
    - KR: 정적 발표 일정 (매달 갱신 구조)
    """
    key = "indicator:calendar"
    cached = cache.get(key)
    if cached:
        return cached

    now = datetime.now(timezone.utc)
    # 이번 달 1일 ~ 다음 달 말일
    from_date = now.replace(day=1).strftime("%Y-%m-%d")
    if now.month == 12:
        to_date = f"{now.year + 1}-01-31"
    else:
        import calendar as cal
        next_month = now.month + 1
        last_day = cal.monthrange(now.year, next_month)[1]
        to_date = f"{now.year}-{next_month:02d}-{last_day:02d}"

    events: list[dict] = []

    # US — FRED release dates
    for release_id, meta in _FRED_RELEASES.items():
        dates = _fetch_fred_release_dates(release_id, from_date, to_date)
        for date_str in dates:
            events.append({
                "date": date_str,
                "country": meta["country"],
                "indicator": meta["indicator"],
                "period": None,
                "importance": meta["importance"],
                "source": f"FRED:release/{release_id}",
            })

    # KR — 정적 일정 (발표 날짜 미확정 → date=None)
    for item in _KR_STATIC_SCHEDULE:
        events.append({
            "date": None,
            "country": item["country"],
            "indicator": item["indicator"],
            "period": f"{now.year}-{now.month:02d}",
            "importance": item["importance"],
            "note": item.get("note"),
            "source": "static",
        })

    # 날짜 기준 정렬 (None은 뒤로)
    events.sort(key=lambda e: (e["date"] is None, e["date"] or ""))

    resp = ok({
        "from": from_date,
        "to": to_date,
        "total": len(events),
        "events": events,
    })
    cache.set(key, resp, TTL)
    return resp
