"""news/geek — GeekNews IT 기술 뉴스 (RSS, 키 불필요)."""
from fastapi import APIRouter, HTTPException, Query
from typing import Literal

from api.core.cache import cache
from api.core.response import ok
from collectors.news.geek import CATEGORY_KEYWORDS

router = APIRouter()

TTL_FEED     = 60 * 10   # 10분 (실시간에 가까운 업데이트)
TTL_TRENDING = 60 * 60   # 1시간
TTL_CATEGORY = 60 * 10   # 10분

GeekCategory = Literal["AI/ML", "오픈소스", "보안", "스타트업", "클라우드", "모바일/앱", "웹/프론트", "데이터", "기타"]


@router.get("/latest")
def geek_latest(
    limit: int = Query(30, description="가져올 기사 수", ge=1, le=100),
):
    """GeekNews 최신 IT 기술 뉴스.

    - 공식 API 없음, RSS 피드 파싱 (https://news.hada.io/rss/news)
    - 카테고리 자동 분류 포함 (AI/ML·보안·오픈소스 등)
    - 키 불필요
    """
    key = f"news:geek:latest:{limit}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.news.geek import fetch_feed
        articles = fetch_feed(limit=limit)
        resp = ok(articles, meta={"source": "GeekNews RSS", "count": len(articles)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_FEED)
    return resp


@router.get("/trending")
def geek_trending(
    days:  int = Query(7,  description="최근 며칠 기사 분석", ge=1, le=30),
    top_n: int = Query(20, description="상위 N개 키워드",    ge=5, le=50),
):
    """GeekNews 트렌드 키워드.

    최근 N일 기사 제목에서 빈도 높은 키워드를 추출해 기술 트렌드를 파악한다.
    """
    key = f"news:geek:trending:{days}:{top_n}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.news.geek import get_trending_keywords
        keywords = get_trending_keywords(days=days, top_n=top_n)
        resp = ok(keywords, meta={"days": days, "count": len(keywords)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_TRENDING)
    return resp


@router.get("/category/{category}")
def geek_by_category(
    category: GeekCategory,
    limit: int = Query(20, description="최대 결과 수", ge=1, le=100),
):
    """카테고리별 GeekNews 기사.

    카테고리: AI/ML · 오픈소스 · 보안 · 스타트업 · 클라우드 · 모바일/앱 · 웹/프론트 · 데이터 · 기타
    """
    key = f"news:geek:category:{category}:{limit}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.news.geek import get_by_category
        articles = get_by_category(category=category, limit=limit)
        resp = ok(articles, meta={"category": category, "count": len(articles)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_CATEGORY)
    return resp


@router.get("/categories")
def geek_categories():
    """GeekNews 자동 분류 카테고리 목록 및 키워드."""
    return ok([
        {"category": cat, "keywords": kws[:5]}
        for cat, kws in CATEGORY_KEYWORDS.items()
    ])
