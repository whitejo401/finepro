"""card/compare — 카드 비교 테이블·연회비 ROI 엔드포인트."""
import logging

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 21600  # 6시간

CARD_CATEGORIES = [
    "주유", "대형마트", "편의점", "카페", "음식점",
    "온라인쇼핑", "통신", "의료", "교통", "항공마일리지",
    "해외결제", "구독서비스", "백화점", "영화",
]

# 카테고리별 평균 월 지출 추정 (원) — ROI 계산용
AVG_MONTHLY_SPEND = {
    "주유":       200000,
    "대형마트":    150000,
    "편의점":      50000,
    "카페":        60000,
    "음식점":     200000,
    "온라인쇼핑":  200000,
    "통신":        80000,
    "의료":        50000,
    "교통":        80000,
    "항공마일리지": 100000,
    "해외결제":    100000,
    "구독서비스":   30000,
    "백화점":      100000,
    "영화":        20000,
}


def _get_cards():
    from .search import _get_cards as _gc
    return _gc()


@router.get("/compare")
def card_compare(
    ids: str = Query(..., description="카드 ID 쉼표 구분 (최대 4개, 예: card_001,card_002)"),
):
    """카드 혜택 비교 테이블 (카테고리 기준)."""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if len(id_list) > 4:
        raise HTTPException(status_code=422, detail="최대 4개 카드 비교 가능")

    cache_key = f"card:compare:{','.join(sorted(id_list))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    cards = _get_cards()
    card_map = {c["id"]: c for c in cards}

    selected = []
    for cid in id_list:
        if cid not in card_map:
            raise HTTPException(status_code=404, detail=f"카드 ID {cid} 없음")
        selected.append(card_map[cid])

    # 카테고리별 비교 테이블
    card_names = [c["name"] for c in selected]
    comparison = []
    for cat in CARD_CATEGORIES:
        row = {"category": cat}
        has_benefit = False
        for c in selected:
            benefit = next((b for b in c.get("benefits", []) if b.get("category") == cat), None)
            row[c["name"]] = benefit.get("discount_rate") if benefit else None
            if benefit:
                has_benefit = True
        if has_benefit:
            comparison.append(row)

    resp = ok({
        "cards":        card_names,
        "comparison":   comparison,
        "annual_fee":   {c["name"]: c.get("annual_fee", 0) for c in selected},
        "min_spending": {c["name"]: c.get("min_spending", 0) for c in selected},
        "card_type":    {c["name"]: c.get("card_type", "신용") for c in selected},
    })
    cache.set(cache_key, resp, TTL)
    return resp


@router.get("/annual_fee")
def card_annual_fee_roi(
    benefit: str = Query(None, description="특정 혜택 카테고리 필터 (선택)"),
):
    """카드 연회비 ROI 분석 (연간 혜택 추정액 / 연회비)."""
    cache_key = f"card:annual_fee_roi:{benefit or 'all'}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    cards = _get_cards()
    if benefit:
        cards = [c for c in cards if any(b.get("category") == benefit for b in c.get("benefits", []))]

    result = []
    for card in cards:
        annual_fee = card.get("annual_fee", 0)
        benefits = card.get("benefits", [])

        # 연간 혜택 추정: Σ(카테고리 월평균지출 × 할인율 × min(12, monthly_limit/지출))
        estimated_monthly = 0
        for b in benefits:
            cat       = b.get("category", "")
            rate      = b.get("discount_rate", 0) / 100
            limit     = b.get("monthly_limit", 9999999)
            avg_spend = AVG_MONTHLY_SPEND.get(cat, 50000)
            monthly_benefit = min(avg_spend * rate, limit)
            estimated_monthly += monthly_benefit

        estimated_annual = int(estimated_monthly * 12)
        net_benefit = estimated_annual - annual_fee
        roi = round(estimated_annual / annual_fee * 100, 1) if annual_fee > 0 else None

        result.append({
            "id":                card["id"],
            "name":              card["name"],
            "company":           card["company"],
            "annual_fee":        annual_fee,
            "estimated_benefit": estimated_annual,
            "net_benefit":       net_benefit,
            "roi":               roi,
            "roi_label":         "연회비 무료" if annual_fee == 0 else f"ROI {roi}%" if roi else None,
        })

    result.sort(key=lambda x: x.get("net_benefit") or 0, reverse=True)
    resp = ok(result, meta={
        "count": len(result),
        "note": "평균 지출 패턴 기반 추정치. 실제 혜택은 전월실적·월 한도에 따라 다를 수 있음",
    })
    cache.set(cache_key, resp, TTL)
    return resp
