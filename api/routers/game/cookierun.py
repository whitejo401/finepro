"""game/cookierun — 쿠키런·오븐스매시·Devsisters 뉴스 엔드포인트 (비공식 API + RSS)."""
import logging
import xml.etree.ElementTree as ET

import requests
from fastapi import APIRouter, HTTPException, Path

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_COOKIE  = 21600  # 6시간
TTL_NEWS    = 1800   # 30분

CRLKD_BASE        = "https://api.crlkd.me"
DEVSISTERS_RSS    = "https://www.devsisters.com/ko/news/rss"
COOKIERUN_RSS     = "https://www.cookierun.com/ko/rss"
OVENSMASH_RSS     = "https://www.ovensmash.com/ko/rss"


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
                "title": (item.findtext("title") or "").strip(),
                "url":   (item.findtext("link") or "").strip(),
                "date":  (item.findtext("pubDate") or "").strip(),
                "desc":  (item.findtext("description") or "").strip()[:200],
            })
        return items[:20]
    except Exception as e:
        logger.debug("RSS %s 오류: %s", url, e)
        return []


def _classify_news_type(title: str, desc: str) -> str:
    text = (title + " " + desc).lower()
    if any(k in text for k in ["쿠폰", "coupon", "코드"]):
        return "쿠폰"
    if any(k in text for k in ["점검", "maintenance", "서버"]):
        return "점검"
    if any(k in text for k in ["이벤트", "event", "혜택", "선물"]):
        return "이벤트"
    return "업데이트"


@router.get("/cookie/{name}")
def cookierun_cookie(name: str = Path(description="쿠키 이름 (영문)")):
    """쿠키런 쿠키 정보 (비공식 API)."""
    cache_key = f"game:cookierun:cookie:{name}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        r = requests.get(f"{CRLKD_BASE}/cookies/{name}", timeout=6)
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="쿠키를 찾을 수 없습니다")
        if r.status_code != 200:
            raise HTTPException(status_code=503, detail="커뮤니티 API 일시 불가")
        data = r.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.debug("crlkd API 오류: %s", e)
        raise HTTPException(status_code=503, detail="커뮤니티 API 일시 불가")

    resp = ok({
        "name":                   data.get("name"),
        "rarity":                 data.get("rarity"),
        "type":                   data.get("type"),
        "skill":                  data.get("skill"),
        "topping_recommendation": data.get("topping_recommendation"),
        "position":               data.get("position"),
        "story":                  data.get("story"),
    })
    cache.set(cache_key, resp, TTL_COOKIE)
    return resp


@router.get("/ovensmash/{name}")
def ovensmash_character(name: str = Path(description="캐릭터 이름")):
    """오븐스매시 캐릭터 정보 (커뮤니티 데이터)."""
    cache_key = f"game:ovensmash:char:{name}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 공식 API 없음 — RSS에서 관련 뉴스 반환
    items = _fetch_rss(OVENSMASH_RSS)
    matched = [i for i in items if name.lower() in i.get("title", "").lower()]

    resp = ok(
        matched if matched else items[:5],
        meta={"name": name, "note": "오븐스매시 공식 API 미제공 — 관련 뉴스 반환"},
    )
    cache.set(cache_key, resp, TTL_COOKIE)
    return resp


@router.get("/devsisters/news")
def devsisters_news():
    """Devsisters 공식 뉴스 (쿠키런·오븐스매시 통합)."""
    cached = cache.get("game:devsisters:news")
    if cached:
        return cached

    items = _fetch_rss(DEVSISTERS_RSS)
    if not items:
        items = _fetch_rss(COOKIERUN_RSS)

    news = []
    for item in items:
        title = item.get("title", "")
        desc  = item.get("desc", "")
        game  = "오븐스매시" if "오븐스매시" in title or "ovensmash" in title.lower() else "쿠키런"
        news.append({
            "game":  game,
            "title": title,
            "date":  item.get("date"),
            "type":  _classify_news_type(title, desc),
            "url":   item.get("url"),
        })

    resp = ok(news, meta={"count": len(news), "partial": len(news) == 0})
    cache.set("game:devsisters:news", resp, TTL_NEWS)
    return resp
