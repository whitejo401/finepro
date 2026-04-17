"""game/coupon — 게임 쿠폰 코드 수집·조회 엔드포인트 (RSS 파싱)."""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_COUPON = 600  # 10분

GAME_RSS = {
    "maple":     "https://maplestory.nexon.com/news/notice/rss",
    "fc":        "https://fconline.nexon.com/news/notice/rss",
    "lol":       "https://www.leagueoflegends.com/ko-kr/news/rss.xml",
    "valorant":  "https://playvalorant.com/ko-kr/news/rss.xml",
    "pubg":      "https://www.pubg.com/ko/news/rss",
    "dnf":       "https://df.nexon.com/news/notice/rss",
    "cookierun": "https://www.cookierun.com/ko/rss",
    "ovensmash": "https://www.ovensmash.com/ko/rss",
    "bdo":       "https://www.blackdesertonline.com/news/rss",
}

# 쿠폰 코드 패턴 (영문+숫자 조합, 6~20자)
COUPON_PATTERN = re.compile(r'\b[A-Z0-9]{6,20}\b')

SUPPORTED_GAMES = list(GAME_RSS.keys())

# 필터링할 일반 단어
SKIP_WORDS = {"THE", "AND", "FOR", "NEW", "FREE", "EVENT", "CODE", "NEXON", "NEWS", "HTTP", "HTTPS"}


def _fetch_rss_items(url: str) -> list[dict]:
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
                "desc":    (item.findtext("description") or "").strip(),
            })
        return items[:30]
    except Exception as e:
        logger.debug("RSS %s 오류: %s", url, e)
        return []


def _extract_coupons(game: str, items: list[dict]) -> list[dict]:
    """RSS 항목에서 쿠폰 코드 추출."""
    coupons = []
    for item in items:
        title = item.get("title", "")
        desc  = item.get("desc", "")
        text  = title + " " + desc

        if not any(k in text for k in ["쿠폰", "coupon", "코드", "code", "Coupon"]):
            continue

        codes = COUPON_PATTERN.findall(text.upper())
        codes = [c for c in codes if c not in SKIP_WORDS]

        pub_date = item.get("pubDate", "")
        try:
            issued = datetime.strptime(pub_date[:16], "%a, %d %b %Y")
        except Exception:
            issued = datetime.now()
        expiry = issued + timedelta(days=30)

        for code in set(codes):
            coupons.append({
                "code":             code,
                "game":             game,
                "source":           item.get("link"),
                "title":            title[:100],
                "issued_date":      issued.strftime("%Y-%m-%d"),
                "estimated_expiry": expiry.strftime("%Y-%m-%d"),
                "rewards":          None,
            })

    return coupons


@router.get("")
def coupon_by_game(
    game: str = Query(..., description=f"게임명: {', '.join(SUPPORTED_GAMES)}"),
):
    """특정 게임 쿠폰 코드 조회."""
    if game not in GAME_RSS:
        raise HTTPException(status_code=422, detail=f"지원 게임: {SUPPORTED_GAMES}")

    cache_key = f"game:coupon:{game}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    items   = _fetch_rss_items(GAME_RSS[game])
    coupons = _extract_coupons(game, items)

    resp = ok(coupons, meta={"game": game, "count": len(coupons)})
    cache.set(cache_key, resp, TTL_COUPON)
    return resp


@router.get("/all")
def coupon_all():
    """전 게임 쿠폰 통합 조회 (만료 임박순)."""
    cached = cache.get("game:coupon:all")
    if cached:
        return cached

    all_coupons = []
    for game, rss_url in GAME_RSS.items():
        sub_cached = cache.get(f"game:coupon:{game}")
        if sub_cached:
            items_data = sub_cached.get("data", [])
        else:
            items = _fetch_rss_items(rss_url)
            items_data = _extract_coupons(game, items)

        all_coupons.extend(items_data)

    today = datetime.now().strftime("%Y-%m-%d")
    all_coupons = [c for c in all_coupons if (c.get("estimated_expiry") or "9999") >= today]
    all_coupons.sort(key=lambda x: x.get("estimated_expiry") or "9999")

    resp = ok(all_coupons, meta={"total": len(all_coupons), "games": list(GAME_RSS.keys())})
    cache.set("game:coupon:all", resp, TTL_COUPON)
    return resp
