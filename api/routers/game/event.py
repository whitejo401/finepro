"""game/event — 게임 이벤트·점검 엔드포인트 (RSS 파싱)."""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_EVENT = 1800  # 30분
TTL_MAINT = 600   # 10분

GAME_RSS = {
    "maple":    "https://maplestory.nexon.com/news/notice/rss",
    "fc":       "https://fconline.nexon.com/news/notice/rss",
    "lol":      "https://www.leagueoflegends.com/ko-kr/news/rss.xml",
    "valorant": "https://playvalorant.com/ko-kr/news/rss.xml",
    "pubg":     "https://www.pubg.com/ko/news/rss",
    "dnf":      "https://df.nexon.com/news/notice/rss",
}

MAINTENANCE_KEYWORDS = ["점검", "서버 점검", "maintenance", "서버점검", "업데이트 점검"]
EVENT_KEYWORDS       = ["이벤트", "event", "혜택", "선물", "보상", "기간", "진행"]

# 날짜 범위 패턴 (예: 4월 17일 ~ 4월 30일)
DATE_RANGE_PATTERN = re.compile(
    r'(\d{1,2})월\s*(\d{1,2})일\s*[~\-~]\s*(\d{1,2})월\s*(\d{1,2})일'
)


def _fetch_rss(url: str) -> list[dict]:
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.text)
        channel = root.find("channel")
        if not channel:
            return []
        items = []
        for item in channel.findall("item"):
            items.append({
                "title":   (item.findtext("title") or "").strip(),
                "link":    (item.findtext("link") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
                "desc":    (item.findtext("description") or "").strip()[:300],
            })
        return items[:30]
    except Exception as e:
        logger.debug("RSS %s 오류: %s", url, e)
        return []


def _parse_event_dates(text: str) -> tuple[str | None, str | None]:
    m = DATE_RANGE_PATTERN.search(text)
    year = datetime.now().year
    if m:
        try:
            start = datetime(year, int(m.group(1)), int(m.group(2)))
            end   = datetime(year, int(m.group(3)), int(m.group(4)))
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        except Exception:
            pass
    return None, None


def _is_event(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(k in text for k in EVENT_KEYWORDS)


def _is_maintenance(title: str, desc: str) -> bool:
    text = title + " " + desc
    return any(k in text for k in MAINTENANCE_KEYWORDS)


def _collect_events(game: str | None = None) -> list[dict]:
    target = {game: GAME_RSS[game]} if game and game in GAME_RSS else GAME_RSS
    events = []
    for g, url in target.items():
        for item in _fetch_rss(url):
            title = item.get("title", "")
            desc  = item.get("desc", "")
            if not _is_event(title, desc):
                continue
            start, end = _parse_event_dates(title + " " + desc)
            rewards = None
            if any(k in desc for k in ["경험치", "메소", "포인트", "코인", "아이템"]):
                rewards = desc[:100]
            events.append({
                "title":           title,
                "game":            g,
                "start":           start,
                "end":             end,
                "rewards_summary": rewards,
                "url":             item.get("link"),
                "pub_date":        item.get("pubDate"),
            })
    return events


def _collect_maintenance(game: str | None = None) -> list[dict]:
    target = {game: GAME_RSS[game]} if game and game in GAME_RSS else GAME_RSS
    maintenances = []
    for g, url in target.items():
        for item in _fetch_rss(url):
            title = item.get("title", "")
            desc  = item.get("desc", "")
            if not _is_maintenance(title, desc):
                continue
            start, end = _parse_event_dates(title + " " + desc)
            now = datetime.now().strftime("%Y-%m-%d")
            is_ongoing = (start or "") <= now <= (end or "9999")
            maintenances.append({
                "game":               g,
                "title":              title,
                "start":              start,
                "end":                end,
                "is_ongoing":         is_ongoing,
                "estimated_restore":  end,
                "url":                item.get("link"),
            })
    return maintenances


@router.get("")
def game_events(
    game: str = Query(None, description=f"게임 필터: {', '.join(GAME_RSS.keys())} (생략 시 전체)"),
):
    """게임 이벤트 목록."""
    cache_key = f"game:event:{game or 'all'}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    events = _collect_events(game)
    events.sort(key=lambda x: x.get("start") or "9999")
    resp = ok(events, meta={"game": game, "count": len(events)})
    cache.set(cache_key, resp, TTL_EVENT)
    return resp


@router.get("/all")
def game_events_all():
    """전 게임 이벤트 통합 캘린더 (시작일순)."""
    cached = cache.get("game:event:calendar")
    if cached:
        return cached

    events = _collect_events()
    events.sort(key=lambda x: x.get("start") or "9999")
    resp = ok(events, meta={"total": len(events), "games": list(GAME_RSS.keys())})
    cache.set("game:event:calendar", resp, TTL_EVENT)
    return resp


@router.get("/ending")
def game_events_ending(
    days: int = Query(3, ge=1, le=30, description="종료 임박 기준 (일)"),
):
    """종료 임박 이벤트 (days일 내 종료)."""
    cached = cache.get(f"game:event:ending:{days}")
    if cached:
        return cached

    events = _collect_events()
    today  = datetime.now()
    cutoff = (today + timedelta(days=days)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    ending = []
    for e in events:
        end = e.get("end")
        if end and today_str <= end <= cutoff:
            remaining = (datetime.strptime(end, "%Y-%m-%d") - today).days
            ending.append({**e, "remaining_days": remaining})

    ending.sort(key=lambda x: x.get("end") or "9999")
    resp = ok(ending, meta={"days": days, "count": len(ending)})
    cache.set(f"game:event:ending:{days}", resp, TTL_EVENT)
    return resp


@router.get("/maintenance")
def game_maintenance():
    """게임 점검 일정 (전 게임)."""
    cached = cache.get("game:maintenance")
    if cached:
        return cached

    maintenances = _collect_maintenance()
    # 진행 중인 점검을 앞으로
    maintenances.sort(key=lambda x: (not x.get("is_ongoing"), x.get("start") or "9999"))
    resp = ok(maintenances, meta={"count": len(maintenances)})
    cache.set("game:maintenance", resp, TTL_MAINT)
    return resp
