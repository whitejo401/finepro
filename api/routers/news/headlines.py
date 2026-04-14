"""news/headlines — 글로벌 뉴스 헤드라인 (NewsAPI)."""
from fastapi import APIRouter, HTTPException, Query
from typing import Literal

from api.core.cache import cache
from api.core.response import ok
from collectors.news.global_news import COUNTRY_CODES, CATEGORIES

router = APIRouter()

TTL_HEADLINES = 60 * 15   # 15분
TTL_SEARCH    = 60 * 30   # 30분

CountryCode = Literal["kr", "us", "jp", "cn", "gb", "de", "fr", "au", "in"]
Category    = Literal["business", "entertainment", "general", "health", "science", "sports", "technology"]


@router.get("/top")
def top_headlines(
    country:  CountryCode = Query("kr",  description="국가 코드"),
    category: Category | None = Query(None, description="카테고리"),
    keyword:  str | None = Query(None,  description="검색어"),
    page_size: int       = Query(20,    description="결과 수", ge=1, le=100),
):
    """국가별 주요 뉴스 헤드라인.

    - 무료 플랜: 최근 30일, 100건/요청
    - 지원 국가: kr·us·jp·cn·gb·de·fr·au·in
    - 지원 카테고리: business·technology·sports·health·science·entertainment·general
    """
    key = f"news:headlines:top:{country}:{category}:{keyword}:{page_size}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.news.global_news import get_top_headlines
        articles = get_top_headlines(
            country=country, category=category,
            keyword=keyword, page_size=page_size,
        )
        resp = ok(articles, meta={"country": country, "category": category, "count": len(articles)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_HEADLINES)
    return resp


@router.get("/search")
def search_news(
    query:     str        = Query(...,           description="검색어"),
    language:  str        = Query("ko",          description="언어 코드 (ko|en|ja)"),
    from_date: str | None = Query(None,          description="시작일 YYYY-MM-DD (최근 30일 이내)"),
    page_size: int        = Query(20,            description="결과 수", ge=1, le=100),
    sort_by:   str        = Query("publishedAt", description="정렬 (publishedAt|relevancy|popularity)"),
):
    """키워드 뉴스 검색."""
    key = f"news:headlines:search:{query}:{language}:{from_date}:{page_size}:{sort_by}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.news.global_news import search_news as _search
        articles = _search(
            query=query, language=language,
            from_date=from_date, page_size=page_size, sort_by=sort_by,
        )
        resp = ok(articles, meta={"query": query, "count": len(articles)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_SEARCH)
    return resp


@router.get("/countries")
def countries():
    """지원 국가 목록."""
    return ok([{"code": k, "name_ko": v} for k, v in COUNTRY_CODES.items()])


@router.get("/categories")
def categories():
    """지원 카테고리 목록."""
    return ok(CATEGORIES)
