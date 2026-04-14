"""benefits/central — 중앙정부 혜택 엔드포인트."""
from fastapi import APIRouter, HTTPException, Query
from typing import Literal

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL = 3600 * 6  # 6시간

LIFE_STAGES = Literal[
    "영유아", "아동", "청소년", "청년", "중장년", "노인", "장애인", "임산부", "다문화"
]

CATEGORIES = Literal[
    "생활안정", "주거자립", "보건의료", "교육", "고용취업",
    "행정사법", "임신출산", "보육", "아동청소년", "노인", "장애인", "기타"
]


@router.get("/welfare")
def welfare_list(
    category: CATEGORIES | None = Query(None, description="서비스 분야"),
    life_stage: LIFE_STAGES | None = Query(None, description="생애주기"),
    keyword: str | None = Query(None, description="서비스명 검색어"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """복지로 복지서비스 목록."""
    key = f"benefits:central:welfare:{category}:{life_stage}:{keyword}:{page}:{page_size}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.benefits.central import get_welfare_services
        items = get_welfare_services(
            category=category,
            life_stage=life_stage,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        resp = ok(items, meta={"count": len(items), "page": page, "page_size": page_size})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL)
    return resp


@router.get("/welfare/{service_id}")
def welfare_detail(service_id: str):
    """복지서비스 상세 정보."""
    key = f"benefits:central:welfare:detail:{service_id}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.benefits.central import get_welfare_detail
        item = get_welfare_detail(service_id)
        if not item:
            raise HTTPException(status_code=404, detail="서비스 정보 없음")
        resp = ok(item)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL)
    return resp


@router.get("/gov24")
def gov24_list(
    life_stage: LIFE_STAGES | None = Query(None, description="생애주기"),
    keyword: str | None = Query(None, description="서비스명 검색어"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """정부24 생애주기별 서비스 목록."""
    key = f"benefits:central:gov24:{life_stage}:{keyword}:{page}:{page_size}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.benefits.central import get_gov24_services
        items = get_gov24_services(
            life_stage=life_stage,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        resp = ok(items, meta={"count": len(items), "page": page})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL)
    return resp
