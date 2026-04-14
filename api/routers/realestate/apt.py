"""realestate/apt — 아파트 실거래가 엔드포인트."""
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL_APT = 86400  # 24시간


@router.get("/trade")
def apt_trade(
    region: str = Query("11110", description="법정동 코드 앞 5자리 (기본: 서울 종로구)"),
    year_month: str = Query(None, description="조회 연월 YYYYMM (기본: 최근)"),
):
    """아파트 실거래가 조회."""
    key = f"realestate:apt:trade:{region}:{year_month}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.kr.macro import get_apt_trade
        df = get_apt_trade(region_code=region, year_month=year_month)
        records = df.to_dict(orient="records") if df is not None and not df.empty else []
        resp = ok(records, meta={"region": region, "year_month": year_month, "count": len(records)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_APT)
    return resp
