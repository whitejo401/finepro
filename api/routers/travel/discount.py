"""travel/discount — 정부 여행 할인 이벤트·숙박대전 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간

TOUR_BASE = "http://apis.data.go.kr/B551011/KorService1"

# 정부 주관 정기 여행 할인 이벤트 (반정적 데이터 — 연 2회 갱신)
GOVERNMENT_EVENTS = [
    {
        "title": "대한민국 숙박대전",
        "organizer": "한국관광공사",
        "discount": "최대 50% 할인 쿠폰",
        "months": [4, 10],       # 4월·10월 운영
        "duration_days": 30,
        "target": "전국 참여 숙박업소",
        "url": "https://korean.visitkorea.or.kr",
        "description": "전국 호텔·펜션·리조트 대상 최대 50% 할인 쿠폰 제공",
    },
    {
        "title": "여행가는달",
        "organizer": "문화체육관광부·한국관광공사",
        "discount": "숙박·교통·관광지 할인",
        "months": [4, 10],
        "duration_days": 31,
        "target": "참여 관광사업체 전체",
        "url": "https://korean.visitkorea.or.kr",
        "description": "국내여행 활성화를 위한 교통·숙박·관광 통합 할인 캠페인",
    },
    {
        "title": "코리아둘레길 캠페인",
        "organizer": "한국관광공사",
        "discount": "참여 숙소 특별 할인",
        "months": [5, 9],
        "duration_days": 60,
        "target": "코리아둘레길 인근 숙박업소",
        "url": "https://korean.visitkorea.or.kr",
        "description": "코리아둘레길(동해안·남해안·서해안·DMZ) 인근 숙박 할인",
    },
]


def _is_active(event: dict, today: datetime) -> bool:
    return today.month in event["months"]


def _next_event_date(event: dict, today: datetime) -> str | None:
    for m in sorted(event["months"]):
        if m > today.month:
            return f"{today.year}-{m:02d}-01"
    next_month = min(event["months"])
    return f"{today.year + 1}-{next_month:02d}-01"


def _fetch_tour_discount_stays() -> list[dict]:
    """TourAPI — 숙박대전·여행가는달 키워드 숙박시설 검색."""
    import requests
    key = os.getenv("TOUR_API_KEY", "")
    if not key:
        return []
    try:
        results = []
        for keyword in ["숙박대전", "여행가는달"]:
            resp = requests.get(
                f"{TOUR_BASE}/searchKeyword1",
                params={
                    "serviceKey": key, "MobileOS": "ETC", "MobileApp": "InfoAPI",
                    "_type": "json", "keyword": keyword,
                    "contentTypeId": 32, "numOfRows": 30, "pageNo": 1,
                },
                timeout=15,
            )
            resp.raise_for_status()
            raw = resp.json()
            items_raw = (
                raw.get("response", {}).get("body", {})
                   .get("items", {}) or {}
            ).get("item", [])
            if isinstance(items_raw, dict):
                items_raw = [items_raw]
            for i in items_raw:
                results.append({
                    "name": i.get("title"),
                    "region": (i.get("addr1") or "").split()[0] if i.get("addr1") else None,
                    "type": "숙박",
                    "discount_pct": None,
                    "booking_url": None,
                    "thumbnail": i.get("firstimage"),
                    "source": f"TourAPI:{keyword}",
                })
        return results
    except Exception as e:
        logger.warning("TourAPI 할인 숙소 조회 실패: %s", e)
        return []


@router.get("/events")
def discount_events():
    """현재 진행 중인 정부 주관 여행 할인 이벤트 목록."""
    cached = cache.get("travel:discount:events")
    if cached:
        return cached

    today = datetime.now()
    active = []
    upcoming = []

    for ev in GOVERNMENT_EVENTS:
        if _is_active(ev, today):
            active.append({**ev, "status": "진행중"})
        else:
            next_date = _next_event_date(ev, today)
            upcoming.append({**ev, "status": "예정", "next_start": next_date})

    resp = ok(
        {"active": active, "upcoming": upcoming},
        meta={"active_count": len(active), "upcoming_count": len(upcoming)},
    )
    cache.set("travel:discount:events", resp, TTL)
    return resp


@router.get("/festival")
def discount_festival():
    """숙박대전·여행가는달 참여 숙소 목록."""
    cached = cache.get("travel:discount:festival")
    if cached:
        return cached

    today = datetime.now()
    active_events = [ev["title"] for ev in GOVERNMENT_EVENTS if _is_active(ev, today)]

    if not active_events:
        next_dates = [_next_event_date(ev, today) for ev in GOVERNMENT_EVENTS]
        resp = ok([], meta={
            "count": 0,
            "note": "현재 진행 중인 할인 행사 없음",
            "next_events": [
                {"title": ev["title"], "next_start": _next_event_date(ev, today)}
                for ev in GOVERNMENT_EVENTS
            ],
        })
        cache.set("travel:discount:festival", resp, TTL)
        return resp

    stays = _fetch_tour_discount_stays()
    resp = ok(stays, meta={
        "count": len(stays),
        "active_events": active_events,
        "note": "TourAPI 키워드 검색 기반 (실제 참여 확인은 각 이벤트 공홈 필요)",
    })
    cache.set("travel:discount:festival", resp, TTL)
    return resp
