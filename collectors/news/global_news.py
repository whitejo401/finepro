"""글로벌 뉴스 수집기 — NewsAPI (헤드라인 목록 제공)."""
import os
import logging
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

_NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
_BASE = "https://newsapi.org/v2"

# 지원 국가 코드 (top-headlines)
COUNTRY_CODES = {
    "kr": "한국", "us": "미국", "jp": "일본",
    "cn": "중국", "gb": "영국", "de": "독일",
    "fr": "프랑스", "au": "호주", "in": "인도",
}

# 지원 카테고리
CATEGORIES = [
    "business", "entertainment", "general",
    "health", "science", "sports", "technology",
]


def get_top_headlines(
    country: str = "kr",
    category: str | None = None,
    keyword: str | None = None,
    page_size: int = 20,
) -> list[dict]:
    """국가별 주요 뉴스 헤드라인.

    Args:
        country: 국가 코드 (기본: kr)
        category: 카테고리 (business|technology|sports 등)
        keyword: 검색어 (선택)
        page_size: 결과 수 (최대 100)

    Returns:
        기사 리스트 [{title, description, url, source, publishedAt}, ...]
    """
    if not _NEWS_API_KEY:
        log.warning("NEWS_API_KEY 미설정")
        return []

    params = {
        "apiKey":   _NEWS_API_KEY,
        "country":  country,
        "pageSize": min(page_size, 100),
    }
    if category:
        params["category"] = category
    if keyword:
        params["q"] = keyword

    try:
        resp = requests.get(f"{_BASE}/top-headlines", params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        return [_clean_article(a) for a in articles]
    except Exception as e:
        log.error("NewsAPI 헤드라인 수집 실패 (country=%s): %s", country, e)
        return []


def search_news(
    query: str,
    language: str = "ko",
    from_date: str | None = None,
    page_size: int = 20,
    sort_by: str = "publishedAt",
) -> list[dict]:
    """키워드 뉴스 검색 (everything 엔드포인트).

    Args:
        query: 검색어
        language: 언어 코드 (ko|en|ja 등)
        from_date: 시작일 YYYY-MM-DD (무료 플랜 최근 30일 제한)
        page_size: 결과 수
        sort_by: publishedAt|relevancy|popularity

    Returns:
        기사 리스트
    """
    if not _NEWS_API_KEY:
        log.warning("NEWS_API_KEY 미설정")
        return []

    if not from_date:
        from_date = (date.today() - timedelta(days=7)).isoformat()

    params = {
        "apiKey":    _NEWS_API_KEY,
        "q":         query,
        "language":  language,
        "from":      from_date,
        "pageSize":  min(page_size, 100),
        "sortBy":    sort_by,
    }

    try:
        resp = requests.get(f"{_BASE}/everything", params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        return [_clean_article(a) for a in articles]
    except Exception as e:
        log.error("NewsAPI 검색 실패 (query=%r): %s", query, e)
        return []


def _clean_article(a: dict) -> dict:
    """기사 dict에서 필요 필드만 추출."""
    return {
        "title":       a.get("title", ""),
        "description": a.get("description", ""),
        "url":         a.get("url", ""),
        "source":      a.get("source", {}).get("name", ""),
        "published_at": a.get("publishedAt", ""),
        "image_url":   a.get("urlToImage", ""),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    articles = get_top_headlines(country="kr", category="technology", page_size=5)
    for a in articles:
        print(a["title"])
