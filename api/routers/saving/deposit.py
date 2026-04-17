"""saving/deposit — 금융감독원 finlife 예금·적금·특판 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_LIST    = 3600   # 1시간
TTL_SPECIAL = 1800   # 30분

FINLIFE_BASE = "https://finlife.fss.or.kr/finlifeapi"

# 기준금리 (한은) — 특판 임계값 계산용 (정적, 주기적 업데이트 필요)
BASE_RATE = 3.00
SPECIAL_THRESHOLD = BASE_RATE + 1.5


def _finlife_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("FINLIFE_API_KEY", "")
    params.update({"auth": key, "topFinGrpNo": "020000", "pageNo": 1})
    resp = requests.get(f"{FINLIFE_BASE}/{endpoint}.json", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _parse_option(opt: dict, base: dict) -> dict:
    return {
        "bank": base.get("kor_co_nm"),
        "product": base.get("fin_prdt_nm"),
        "rate_basic": float(opt.get("intr_rate") or 0),
        "rate_max": float(opt.get("intr_rate2") or 0),
        "term_months": opt.get("save_trm"),
        "join_way": base.get("join_way"),
        "conditions": base.get("spcl_cnd"),
        "min_amount": base.get("join_amt"),
        "join_member": base.get("join_member"),
        "protected": True,  # 은행 예금은 기본 보호
    }


def _fetch_products(endpoint: str, term: int | None, bank: str | None) -> list[dict]:
    try:
        params: dict = {}
        if bank and bank != "전체":
            params["kor_co_nm"] = bank
        raw = _finlife_get(endpoint, params)
        base_list = (raw.get("result") or {}).get("baseList") or []
        opt_list  = (raw.get("result") or {}).get("optionList") or []

        base_map = {b["fin_prdt_cd"]: b for b in base_list}
        results = []
        for opt in opt_list:
            if term and str(term) != str(opt.get("save_trm")):
                continue
            base = base_map.get(opt.get("fin_prdt_cd"), {})
            results.append(_parse_option(opt, base))

        return sorted(results, key=lambda x: x["rate_max"], reverse=True)
    except Exception as e:
        logger.warning("finlife %s 조회 실패: %s", endpoint, e)
        return []


@router.get("/deposit")
def deposit_list(
    bank: str = Query("전체", description="은행명 또는 전체"),
    term: int = Query(12, description="가입 기간 (개월): 3·6·12·24·36"),
):
    """은행별 정기예금 금리 비교 (최고금리 내림차순)."""
    cache_key = f"saving:deposit:{bank}:{term}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("FINLIFE_API_KEY"):
        raise HTTPException(status_code=503, detail="FINLIFE_API_KEY 미설정")

    items = _fetch_products("depositProductsSearch", term, bank)
    resp = ok(items, meta={"bank": bank, "term": term, "count": len(items)})
    cache.set(cache_key, resp, TTL_LIST)
    return resp


@router.get("/savings")
def savings_list(
    bank: str = Query("전체", description="은행명 또는 전체"),
    term: int = Query(12, description="가입 기간 (개월)"),
    type_: str = Query("전체", alias="type", description="정액적립식·자유적립식·전체"),
):
    """은행별 적금 금리 비교."""
    cache_key = f"saving:savings:{bank}:{term}:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("FINLIFE_API_KEY"):
        raise HTTPException(status_code=503, detail="FINLIFE_API_KEY 미설정")

    items = _fetch_products("savingProductsSearch", term, bank)
    if type_ != "전체":
        items = [i for i in items if type_ in (i.get("join_way") or "")]

    resp = ok(items, meta={"bank": bank, "term": term, "type": type_, "count": len(items)})
    cache.set(cache_key, resp, TTL_LIST)
    return resp


@router.get("/special")
def special_products():
    """현재 고금리 특판 예·적금 (기준금리+1.5% 이상)."""
    cached = cache.get("saving:special")
    if cached:
        return cached

    if not os.getenv("FINLIFE_API_KEY"):
        raise HTTPException(status_code=503, detail="FINLIFE_API_KEY 미설정")

    all_items: list[dict] = []
    for ep, ptype in [
        ("depositProductsSearch", "예금"),
        ("savingProductsSearch", "적금"),
    ]:
        items = _fetch_products(ep, None, None)
        for i in items:
            if (i.get("rate_max") or 0) >= SPECIAL_THRESHOLD:
                i["product_type"] = ptype
                all_items.append(i)

    all_items.sort(key=lambda x: x.get("rate_max") or 0, reverse=True)
    resp = ok(all_items, meta={
        "threshold": SPECIAL_THRESHOLD,
        "base_rate": BASE_RATE,
        "count": len(all_items),
    })
    cache.set("saving:special", resp, TTL_SPECIAL)
    return resp
