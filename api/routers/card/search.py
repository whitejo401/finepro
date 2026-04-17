"""card/search — finlife 카드 목록·상세 엔드포인트."""
import logging
import os

import requests
from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_LIST   = 10800  # 3시간
TTL_DETAIL = 21600  # 6시간

FINLIFE_KEY  = os.getenv("FINLIFE_API_KEY", "")
FINLIFE_BASE = "https://finlife.fss.or.kr/finlifeapi"

CARD_CATEGORIES = [
    "주유", "대형마트", "편의점", "카페", "음식점",
    "온라인쇼핑", "통신", "의료", "교통", "항공마일리지",
    "해외결제", "구독서비스", "백화점", "영화",
]

# 정적 카드 데이터 (finlife API 미설정 시 폴백)
STATIC_CARDS = [
    {
        "id": "card_001",
        "name": "신한 Deep Dream 카드",
        "company": "신한카드",
        "card_type": "신용",
        "annual_fee": 10000,
        "benefits": [
            {"category": "주유", "discount_rate": 7, "monthly_limit": 6000, "condition": "전월실적 30만원 이상"},
            {"category": "카페", "discount_rate": 5, "monthly_limit": 3000, "condition": "전월실적 30만원 이상"},
            {"category": "음식점", "discount_rate": 5, "monthly_limit": 3000},
        ],
        "min_spending": 300000,
        "apply_url": "https://www.shinhancard.com",
    },
    {
        "id": "card_002",
        "name": "KB국민 탄탄대로 카드",
        "company": "KB국민카드",
        "card_type": "신용",
        "annual_fee": 0,
        "benefits": [
            {"category": "대형마트", "discount_rate": 5, "monthly_limit": 5000, "condition": "전월실적 30만원 이상"},
            {"category": "편의점",  "discount_rate": 5, "monthly_limit": 2000},
            {"category": "교통",    "discount_rate": 10, "monthly_limit": 3000},
        ],
        "min_spending": 300000,
        "apply_url": "https://www.kbcard.com",
    },
    {
        "id": "card_003",
        "name": "삼성 iD ON 카드",
        "company": "삼성카드",
        "card_type": "신용",
        "annual_fee": 15000,
        "benefits": [
            {"category": "온라인쇼핑", "discount_rate": 10, "monthly_limit": 10000, "condition": "전월실적 50만원 이상"},
            {"category": "카페",      "discount_rate": 10, "monthly_limit": 5000},
            {"category": "구독서비스", "discount_rate": 10, "monthly_limit": 5000},
        ],
        "min_spending": 500000,
        "apply_url": "https://www.samsungcard.com",
    },
    {
        "id": "card_004",
        "name": "현대 ZEM 카드",
        "company": "현대카드",
        "card_type": "신용",
        "annual_fee": 0,
        "benefits": [
            {"category": "주유",    "discount_rate": 5, "monthly_limit": 5000, "condition": "전월실적 20만원 이상"},
            {"category": "의료",    "discount_rate": 5, "monthly_limit": 3000},
            {"category": "영화",    "discount_rate": 50, "monthly_limit": 5000, "note": "월 2회"},
        ],
        "min_spending": 200000,
        "apply_url": "https://www.hyundaicard.com",
    },
    {
        "id": "card_005",
        "name": "우리 카드의 정석 POINT",
        "company": "우리카드",
        "card_type": "신용",
        "annual_fee": 5000,
        "benefits": [
            {"category": "편의점",   "discount_rate": 10, "monthly_limit": 3000},
            {"category": "카페",     "discount_rate": 10, "monthly_limit": 3000},
            {"category": "통신",     "discount_rate": 5,  "monthly_limit": 4000},
        ],
        "min_spending": 200000,
        "apply_url": "https://www.wooricard.com",
    },
    {
        "id": "card_006",
        "name": "하나 1Q 카드",
        "company": "하나카드",
        "card_type": "신용",
        "annual_fee": 8000,
        "benefits": [
            {"category": "해외결제",   "discount_rate": 3, "monthly_limit": 10000},
            {"category": "항공마일리지", "discount_rate": 5, "monthly_limit": 5000, "note": "1달러당 1마일"},
            {"category": "음식점",    "discount_rate": 5, "monthly_limit": 5000},
        ],
        "min_spending": 500000,
        "apply_url": "https://www.hanacard.co.kr",
    },
    {
        "id": "card_007",
        "name": "롯데 LOCA 365 카드",
        "company": "롯데카드",
        "card_type": "신용",
        "annual_fee": 12000,
        "benefits": [
            {"category": "백화점",    "discount_rate": 5, "monthly_limit": 10000},
            {"category": "대형마트",  "discount_rate": 5, "monthly_limit": 5000},
            {"category": "온라인쇼핑","discount_rate": 5, "monthly_limit": 5000},
        ],
        "min_spending": 300000,
        "apply_url": "https://www.lottecard.co.kr",
    },
    {
        "id": "card_008",
        "name": "NH 농협 올바른 체크카드",
        "company": "NH농협카드",
        "card_type": "체크",
        "annual_fee": 0,
        "benefits": [
            {"category": "대형마트",  "discount_rate": 5, "monthly_limit": 3000},
            {"category": "교통",     "discount_rate": 10, "monthly_limit": 2000},
            {"category": "편의점",   "discount_rate": 5,  "monthly_limit": 2000},
        ],
        "min_spending": 0,
        "apply_url": "https://card.nonghyup.com",
    },
    {
        "id": "card_009",
        "name": "신한 Deep Oil 카드",
        "company": "신한카드",
        "card_type": "신용",
        "annual_fee": 5000,
        "benefits": [
            {"category": "주유", "discount_rate": 10, "monthly_limit": 12000, "condition": "전월실적 40만원 이상"},
            {"category": "교통", "discount_rate": 5,  "monthly_limit": 3000},
        ],
        "min_spending": 400000,
        "apply_url": "https://www.shinhancard.com",
    },
    {
        "id": "card_010",
        "name": "KB국민 MY WE:SH 카드",
        "company": "KB국민카드",
        "card_type": "신용",
        "annual_fee": 15000,
        "benefits": [
            {"category": "카페",      "discount_rate": 10, "monthly_limit": 5000},
            {"category": "음식점",    "discount_rate": 10, "monthly_limit": 10000},
            {"category": "구독서비스", "discount_rate": 10, "monthly_limit": 5000},
        ],
        "min_spending": 300000,
        "apply_url": "https://www.kbcard.com",
    },
]


def _fetch_finlife_cards() -> list[dict] | None:
    if not FINLIFE_KEY:
        return None
    try:
        params = {
            "auth": FINLIFE_KEY,
            "topFinGrpNo": "020000",
            "pageNo": "1",
        }
        r = requests.get(
            f"{FINLIFE_BASE}/creditCardSearch.json",
            params=params,
            timeout=8,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        items = data.get("result", {}).get("baseList", [])
        if not items:
            return None

        cards = []
        for item in items:
            cards.append({
                "id":          item.get("fin_prdt_cd"),
                "name":        item.get("fin_prdt_nm"),
                "company":     item.get("kor_co_nm"),
                "card_type":   "신용",
                "annual_fee":  int(item.get("anual_fee", 0) or 0),
                "benefits":    [],
                "min_spending": int(item.get("bnft_cnd", 0) or 0),
            })
        return cards
    except Exception as e:
        logger.debug("finlife 카드 API 오류: %s", e)
        return None


def _get_cards() -> list[dict]:
    cached = cache.get("card:all")
    if cached:
        return cached

    cards = _fetch_finlife_cards() or STATIC_CARDS
    cache.set("card:all", cards, TTL_LIST)
    return cards


def _summary(card: dict) -> dict:
    top = sorted(card.get("benefits", []), key=lambda b: b.get("discount_rate", 0), reverse=True)[:3]
    return {
        "id":           card["id"],
        "name":         card["name"],
        "company":      card["company"],
        "card_type":    card.get("card_type", "신용"),
        "annual_fee":   card.get("annual_fee", 0),
        "top_benefits": top,
        "min_spending": card.get("min_spending", 0),
    }


@router.get("/search")
def card_search(
    category: str = Query(None, description=f"혜택 카테고리: {', '.join(CARD_CATEGORIES)}"),
    company: str = Query(None, description="카드사명 (예: 신한카드)"),
    card_type: str = Query("신용", description="신용·체크"),
    annual_fee_max: int = Query(None, description="최대 연회비 (원)"),
    sort: str = Query("discount_rate", description="discount_rate·annual_fee"),
):
    """카드 목록 검색 (카테고리·카드사·연회비 필터)."""
    cache_key = f"card:search:{category}:{company}:{card_type}:{annual_fee_max}:{sort}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    cards = _get_cards()

    # 필터
    result = [c for c in cards if c.get("card_type", "신용") == card_type]
    if category:
        result = [c for c in result if any(b.get("category") == category for b in c.get("benefits", []))]
    if company:
        result = [c for c in result if company in c.get("company", "")]
    if annual_fee_max is not None:
        result = [c for c in result if c.get("annual_fee", 0) <= annual_fee_max]

    # 정렬
    if sort == "annual_fee":
        result.sort(key=lambda c: c.get("annual_fee", 0))
    else:  # discount_rate
        def max_rate(c):
            benefits = c.get("benefits", [])
            if category:
                filtered = [b for b in benefits if b.get("category") == category]
                return max((b.get("discount_rate", 0) for b in filtered), default=0)
            return max((b.get("discount_rate", 0) for b in benefits), default=0)
        result.sort(key=max_rate, reverse=True)

    items = [_summary(c) for c in result]
    resp = ok({"total": len(items), "items": items})
    cache.set(cache_key, resp, TTL_LIST)
    return resp


@router.get("/{card_id}")
def card_detail(card_id: str = Path(description="카드 ID")):
    """카드 상세 정보."""
    cache_key = f"card:detail:{card_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    cards = _get_cards()
    card = next((c for c in cards if c["id"] == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="카드를 찾을 수 없습니다")

    resp = ok({
        **card,
        "annual_fee_detail": {
            "domestic":      card.get("annual_fee", 0),
            "international": int(card.get("annual_fee", 0) * 1.3),
        },
    })
    cache.set(cache_key, resp, TTL_DETAIL)
    return resp
