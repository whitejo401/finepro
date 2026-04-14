"""benefits/education — 교육 혜택 엔드포인트."""
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL = 3600 * 6  # 6시간


@router.get("/voucher")
def lifelong_edu_voucher(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """평생교육바우처 지원 프로그램 목록."""
    key = f"benefits:education:voucher:{page}:{page_size}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.benefits.education import get_lifelong_edu_voucher
        items = get_lifelong_edu_voucher(page=page, page_size=page_size)
        resp = ok(items, meta={"count": len(items), "page": page})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL)
    return resp


@router.get("/scholarship")
def scholarship(
    university_name: str | None = Query(None, description="대학명"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """국가장학금 정보 조회."""
    key = f"benefits:education:scholarship:{university_name}:{page}:{page_size}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.benefits.education import get_scholarship_info
        items = get_scholarship_info(
            university_name=university_name,
            page=page,
            page_size=page_size,
        )
        resp = ok(items, meta={"count": len(items), "page": page})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL)
    return resp


@router.get("/training")
def vocational_training(
    region: str | None = Query(None, description="지역 (서울, 경기 등)"),
    keyword: str | None = Query(None, description="훈련과정명 검색어"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """국민내일배움카드 직업훈련 과정 조회."""
    key = f"benefits:education:training:{region}:{keyword}:{page}:{page_size}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.benefits.education import get_vocational_training
        items = get_vocational_training(
            region=region,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        resp = ok(items, meta={"count": len(items), "page": page})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL)
    return resp
