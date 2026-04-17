"""saving/pension — ISA·연금저축·IRP 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 10800  # 3시간

FINLIFE_BASE = "https://finlife.fss.or.kr/finlifeapi"

ISA_INFO = {
    "중개형": {
        "tax_benefit": "이자·배당 200만원까지 비과세, 초과분 9.9% 분리과세",
        "annual_limit": 2000,
        "eligible": "19세 이상 거주자 (직전년도 금융소득 2천만원 이하)",
        "min_period": 3,
    },
    "신탁형": {
        "tax_benefit": "이자·배당 200만원까지 비과세, 초과분 9.9% 분리과세",
        "annual_limit": 2000,
        "eligible": "19세 이상 거주자",
        "min_period": 3,
    },
    "서민형": {
        "tax_benefit": "이자·배당 400만원까지 비과세, 초과분 9.9% 분리과세",
        "annual_limit": 2000,
        "eligible": "총급여 5천만원 이하 또는 종합소득 3800만원 이하",
        "min_period": 3,
    },
}

PENSION_TAX = {
    "연금저축펀드": "납입액 연 600만원 세액공제 (16.5% 또는 13.2%)",
    "연금저축보험": "납입액 연 600만원 세액공제 (16.5% 또는 13.2%)",
    "IRP": "연금저축 합산 연 900만원 세액공제",
}


def _finlife_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("FINLIFE_API_KEY", "")
    params.update({"auth": key, "topFinGrpNo": "060000", "pageNo": 1})
    resp = requests.get(f"{FINLIFE_BASE}/{endpoint}.json", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@router.get("/isa")
def isa_info(
    type_: str = Query("중개형", alias="type", description="중개형·신탁형·서민형"),
):
    """ISA 계좌 유형별 세제혜택 + 상품 안내."""
    if type_ not in ISA_INFO:
        raise HTTPException(status_code=422, detail=f"지원 유형: {list(ISA_INFO.keys())}")

    cache_key = f"saving:isa:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    info = ISA_INFO[type_]
    resp = ok({
        "type": type_,
        **info,
        "note": "ISA 만기 후 연금계좌로 이전 시 추가 세액공제 혜택",
        "open_guide": "증권사·은행 앱에서 개설 가능 (비대면 포함)",
    })
    cache.set(cache_key, resp, TTL)
    return resp


@router.get("/pension")
def pension_list(
    type_: str = Query("연금저축펀드", alias="type", description="연금저축펀드·연금저축보험·IRP"),
):
    """연금저축·IRP 상품 목록 + 세제혜택."""
    if type_ not in PENSION_TAX:
        raise HTTPException(status_code=422, detail=f"지원 유형: {list(PENSION_TAX.keys())}")

    cache_key = f"saving:pension:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    products: list[dict] = []
    if os.getenv("FINLIFE_API_KEY"):
        try:
            ep = "annuitySavingProductsSearch" if "연금저축" in type_ else "iraProductsSearch"
            raw = _finlife_get(ep, {})
            base_list = (raw.get("result") or {}).get("baseList") or []
            opt_list  = (raw.get("result") or {}).get("optionList") or []
            base_map = {b["fin_prdt_cd"]: b for b in base_list}

            for opt in opt_list:
                base = base_map.get(opt.get("fin_prdt_cd"), {})
                products.append({
                    "company": base.get("kor_co_nm"),
                    "product": base.get("fin_prdt_nm"),
                    "yield_1y": opt.get("intr_rate"),
                    "fee_pct": opt.get("fee_rate"),
                    "join_way": base.get("join_way"),
                    "tax_benefit": PENSION_TAX[type_],
                })
        except Exception as e:
            logger.warning("pension 조회 실패: %s", e)

    resp = ok(products, meta={
        "type": type_,
        "tax_benefit": PENSION_TAX[type_],
        "count": len(products),
    })
    cache.set(cache_key, resp, TTL)
    return resp
