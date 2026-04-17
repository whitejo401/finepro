"""card/recommend — 지출 패턴 기반 카드 추천 엔드포인트."""
import logging
from itertools import combinations

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간


def _get_cards():
    from .search import _get_cards as _gc
    return _gc()


def _parse_spend(spend: str) -> dict[str, int]:
    """'주유:30,카페:10,마트:20' → {'주유': 300000, '카페': 100000, ...}"""
    result = {}
    try:
        for part in spend.split(","):
            part = part.strip()
            if not part:
                continue
            cat, amount = part.split(":")
            result[cat.strip()] = int(amount.strip()) * 10000
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="spend 형식 오류. 예: spend=주유:30,카페:10,마트:20 (단위: 만원/월)",
        )
    return result


def _calc_monthly_saving(card: dict, spend_map: dict[str, int]) -> int:
    """카드 1장의 월 절감액 계산."""
    total = 0
    total_spend = sum(spend_map.values())

    # 전월실적 조건 체크
    min_spending = card.get("min_spending", 0)
    if total_spend < min_spending:
        return 0

    for benefit in card.get("benefits", []):
        cat   = benefit.get("category", "")
        rate  = benefit.get("discount_rate", 0) / 100
        limit = benefit.get("monthly_limit", 9_999_999)
        spend = spend_map.get(cat, 0)
        total += min(spend * rate, limit)

    return int(total)


def _card_score(card: dict, spend_map: dict[str, int]) -> dict:
    monthly_saving = _calc_monthly_saving(card, spend_map)
    annual_saving  = monthly_saving * 12
    annual_fee     = card.get("annual_fee", 0)
    net_benefit    = annual_saving - annual_fee

    return {
        "card":           card["name"],
        "card_id":        card["id"],
        "company":        card["company"],
        "monthly_saving": monthly_saving,
        "annual_saving":  annual_saving,
        "annual_fee":     annual_fee,
        "net_benefit":    net_benefit,
    }


def _combo_saving(c1: dict, c2: dict, spend_map: dict[str, int]) -> int:
    """2카드 조합의 월 절감액 (카테고리 중복 시 높은 쪽 우선)."""
    total = 0
    total_spend = sum(spend_map.values())
    min1 = c1.get("min_spending", 0)
    min2 = c2.get("min_spending", 0)

    for cat, spend in spend_map.items():
        rates = []
        limits = []

        if total_spend >= min1:
            b1 = next((b for b in c1.get("benefits", []) if b.get("category") == cat), None)
            if b1:
                rates.append(b1.get("discount_rate", 0) / 100)
                limits.append(b1.get("monthly_limit", 9_999_999))

        if total_spend >= min2:
            b2 = next((b for b in c2.get("benefits", []) if b.get("category") == cat), None)
            if b2:
                rates.append(b2.get("discount_rate", 0) / 100)
                limits.append(b2.get("monthly_limit", 9_999_999))

        if rates:
            best_idx = rates.index(max(rates))
            total += min(spend * rates[best_idx], limits[best_idx])

    return int(total)


@router.get("/recommend")
def card_recommend(
    spend: str = Query(..., description="지출 패턴 (예: 주유:30,카페:10,마트:20, 단위: 만원/월)"),
):
    """지출 패턴 기반 최적 카드 추천 (단일 + 2카드 조합)."""
    cache_key = f"card:recommend:{spend}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    spend_map = _parse_spend(spend)
    if not spend_map:
        raise HTTPException(status_code=422, detail="지출 패턴이 비어 있습니다")

    monthly_total = sum(spend_map.values())
    cards = _get_cards()

    # 단일 카드 점수 계산
    scores = [_card_score(c, spend_map) for c in cards]
    scores.sort(key=lambda x: x["net_benefit"], reverse=True)
    best_single = scores[0] if scores else None
    top5 = scores[:5]

    # 2카드 조합 최적화 (상위 8개 카드 중에서 탐색)
    top8 = [c for c in cards if any(s["card_id"] == c["id"] for s in scores[:8])]
    best_combo = None
    best_combo_net = -999_999_999

    for c1, c2 in combinations(top8, 2):
        monthly = _combo_saving(c1, c2, spend_map)
        annual  = monthly * 12
        fee     = c1.get("annual_fee", 0) + c2.get("annual_fee", 0)
        net     = annual - fee
        if net > best_combo_net:
            best_combo_net = net
            best_combo = {
                "cards":          [c1["name"], c2["name"]],
                "card_ids":       [c1["id"], c2["id"]],
                "companies":      [c1["company"], c2["company"]],
                "monthly_saving": monthly,
                "annual_saving":  annual,
                "annual_fee":     fee,
                "net_benefit":    net,
            }

    resp = ok({
        "spend_input":          spend,
        "monthly_spend_total":  monthly_total,
        "spend_breakdown":      {k: v for k, v in spend_map.items()},
        "best_single":          best_single,
        "best_combo":           best_combo,
        "top5_single":          top5,
        "disclaimer":           "추정 혜택은 전월실적 충족 및 월 한도 내 사용을 가정한 참고치입니다",
    })
    cache.set(cache_key, resp, TTL)
    return resp
