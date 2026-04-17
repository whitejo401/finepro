"""saving/recommend — 상품 추천·예금자보호 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_REC  = 3600   # 1시간
TTL_PROT = 86400  # 24시간

# 금융기관 유형별 예금자보호 여부 (예금보험공사 기준)
PROTECTION_DB = {
    "은행":        {"protected": True,  "limit": 50_000_000, "note": "1인당 5천만원"},
    "저축은행":    {"protected": True,  "limit": 50_000_000, "note": "1인당 5천만원"},
    "증권사":      {"protected": True,  "limit": 50_000_000, "note": "투자자예탁금·예수금만 보호"},
    "보험사":      {"protected": True,  "limit": 50_000_000, "note": "해약환급금·만기보험금 보호"},
    "상호금융":    {"protected": False, "limit": 0,          "note": "농협·신협·수협 자체 예금자보호 (예보 미적용)"},
    "새마을금고":  {"protected": False, "limit": 0,          "note": "새마을금고중앙회 자체 보호 (예보 미적용)"},
    "우체국":      {"protected": False, "limit": 0,          "note": "정부가 전액 지급 보증 (사실상 무한 보호)"},
    "CMA":         {"protected": False, "limit": 0,          "note": "MMF형 CMA는 비보호, RP형·종금형은 보호"},
}

RISK_LOGIC = {
    "낮음": [
        {"type": "예금", "detail": "은행 정기예금 (12개월)", "rationale": "원금 보장 + 예금자보호"},
        {"type": "ETF", "detail": "채권 ETF (국내채권)", "rationale": "낮은 변동성 + 이자소득"},
    ],
    "보통": [
        {"type": "적금", "detail": "은행·저축은행 자유적립식 적금", "rationale": "유연한 납입 + 복리"},
        {"type": "ETF", "detail": "배당 ETF (고배당주)", "rationale": "배당소득 + 자본이익"},
        {"type": "ISA", "detail": "중개형 ISA 계좌", "rationale": "비과세 혜택 + 다양한 편입 자산"},
    ],
    "높음": [
        {"type": "ETF",   "detail": "성장주 ETF (해외주식·나스닥)", "rationale": "장기 성장 기대"},
        {"type": "연금",  "detail": "연금저축펀드 (주식형)", "rationale": "세액공제 + 복리 효과"},
        {"type": "리츠",  "detail": "리츠 ETF", "rationale": "부동산 간접투자 + 배당"},
    ],
}


@router.get("/recommend")
def saving_recommend(
    amount: int = Query(..., description="가입금액 (만원)"),
    term: int = Query(..., description="목표 기간 (개월)"),
    risk: str = Query("보통", description="낮음·보통·높음"),
):
    """금액·기간·위험성향 기반 금융상품 추천."""
    if risk not in RISK_LOGIC:
        raise HTTPException(status_code=422, detail=f"risk: {list(RISK_LOGIC.keys())}")

    cache_key = f"saving:recommend:{amount}:{term}:{risk}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    recommendations = []
    for item in RISK_LOGIC[risk]:
        rec = {**item, "amount_wan": amount, "term_months": term}
        # 예상 수익 (간단 추정)
        if item["type"] == "예금" and term >= 12:
            rec["expected_yield_pct"] = 3.5
        elif item["type"] == "적금":
            rec["expected_yield_pct"] = 4.0
        elif item["type"] == "ETF":
            rec["expected_yield_pct"] = None  # 시장 변동
        else:
            rec["expected_yield_pct"] = None
        recommendations.append(rec)

    resp = ok(recommendations, meta={
        "amount": amount, "term": term, "risk": risk, "count": len(recommendations),
        "disclaimer": "본 추천은 참고용이며 투자 결정 전 전문가 상담 권장",
    })
    cache.set(cache_key, resp, TTL_REC)
    return resp


@router.get("/protection")
def deposit_protection(
    bank: str = Query(..., description="금융기관명 또는 유형 (은행·저축은행·새마을금고 등)"),
):
    """금융기관 예금자보호 여부 조회."""
    cache_key = f"saving:protection:{bank}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 기관명에서 유형 매칭
    matched = None
    for key in PROTECTION_DB:
        if key in bank:
            matched = key
            break

    if not matched:
        # 기본: 은행으로 처리
        matched = "은행"

    info = PROTECTION_DB[matched]
    resp = ok({
        "bank": bank,
        "institution_type": matched,
        **info,
    })
    cache.set(cache_key, resp, TTL_PROT)
    return resp
