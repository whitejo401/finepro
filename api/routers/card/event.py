"""card/event — 카드사 이벤트 RSS 파싱 엔드포인트."""
import logging
import re
from datetime import datetime, timedelta

import feedparser
from fastapi import APIRouter

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 1800  # 30분

# 카드사별 공지/이벤트 RSS
COMPANY_RSS = {
    "삼성카드": "https://www.samsungcard.com/home/rss/event.xml",
    "신한카드": "https://www.shinhancard.com/pconts/rss/event.xml",
    "KB국민카드": "https://card.kbcard.com/rss/event.xml",
    "현대카드": "https://www.hyundaicard.com/rss/event.xml",
    "롯데카드": "https://www.lottecard.co.kr/app/LPCDBRCA_V100.lc",
    "우리카드": "https://www.wooricard.com/rss/event.xml",
    "하나카드": "https://www.hanacard.co.kr/rss/event.xml",
}

DATE_PATTERN = re.compile(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})')


def _parse_date(text: str) -> str | None:
    m = DATE_PATTERN.search(text or "")
    if m:
        try:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        except Exception:
            pass
    return None


def _fetch_company_events(company: str, rss_url: str) -> list[dict]:
    try:
        feed = feedparser.parse(rss_url)
        events = []
        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            desc  = (entry.get("summary") or entry.get("description") or "").strip()
            link  = entry.get("link", "")
            pub   = entry.get("published", "")

            # 날짜 파싱: 설명에서 기간 추출 시도
            text = title + " " + desc
            dates = DATE_PATTERN.findall(text)
            if len(dates) >= 2:
                try:
                    start = f"{dates[0][0]}-{int(dates[0][1]):02d}-{int(dates[0][2]):02d}"
                    end   = f"{dates[1][0]}-{int(dates[1][1]):02d}-{int(dates[1][2]):02d}"
                except Exception:
                    start = end = None
            else:
                start = _parse_date(pub)
                end   = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d") if start else None

            events.append({
                "company":     company,
                "title":       title[:120],
                "description": desc[:200],
                "start":       start,
                "end":         end,
                "url":         link,
            })
        return events
    except Exception as e:
        logger.debug("%s RSS 파싱 실패: %s", company, e)
        return []


@router.get("/event")
def card_events():
    """카드사 이벤트 통합 (전 카드사 RSS)."""
    cached = cache.get("card:events")
    if cached:
        return cached

    all_events = []
    failed = []
    for company, rss_url in COMPANY_RSS.items():
        events = _fetch_company_events(company, rss_url)
        if events:
            all_events.extend(events)
        else:
            failed.append(company)

    today = datetime.now().strftime("%Y-%m-%d")
    # 진행 중 이벤트 우선, 이후 시작일순
    all_events.sort(key=lambda e: (
        not ((e.get("start") or "0000") <= today <= (e.get("end") or "9999")),
        e.get("start") or "9999",
    ))

    resp = ok(all_events, meta={
        "total":  len(all_events),
        "failed": failed,
        "partial": len(failed) > 0,
    })
    cache.set("card:events", resp, TTL)
    return resp
