"""invest/fund — 펀드 목록 엔드포인트.

TODO: KOFIA 펀드 공시 REST API (dis.kofia.or.kr) 연동.
      현재는 공식 API 접근 방법 불명확으로 정적 샘플 데이터 반환.
      실제 연동 시 아래 참고:
        URL: http://dis.kofia.or.kr/serviceq/fund/mupd/listFundByCondition.do
        Method: POST, Content-Type: application/x-www-form-urlencoded
        params: stndDd={YYYYMMDD}&fundGbCd={1=국내주식형, 2=해외주식형, ...}
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger(__name__)

TTL_FUND = 60 * 60  # 1시간

# 펀드 유형 코드 매핑 (KOFIA 기준, TODO 연동 시 사용)
FUND_TYPE_CODE = {
    "국내주식형": "1",
    "해외주식형": "2",
    "채권형":     "3",
    "혼합형":     "4",
    "MMF":       "5",
}

_SAMPLE_FUNDS = [
    {
        "fund_code": "KR5223941789",
        "name": "미래에셋TIGER200인덱스증권상장지수투자신탁(주식)",
        "type": "국내주식형",
        "aum": 12345678000000,
        "yield_1m": 1.23,
        "yield_3m": 3.45,
        "yield_6m": 5.67,
        "yield_1y": 12.34,
        "risk_grade": 2,
    },
    {
        "fund_code": "KR5223941001",
        "name": "삼성KODEX200증권상장지수투자신탁(주식)",
        "type": "국내주식형",
        "aum": 9876543000000,
        "yield_1m": 1.10,
        "yield_3m": 3.20,
        "yield_6m": 5.10,
        "yield_1y": 11.50,
        "risk_grade": 2,
    },
    {
        "fund_code": "KR5223942001",
        "name": "KB미국S&P500인덱스증권자투자신탁(주식)(H)",
        "type": "해외주식형",
        "aum": 5432100000000,
        "yield_1m": 2.10,
        "yield_3m": 6.30,
        "yield_6m": 11.20,
        "yield_1y": 22.80,
        "risk_grade": 3,
    },
    {
        "fund_code": "KR5223943001",
        "name": "한국투자국채증권투자신탁1호(채권)(C-e)",
        "type": "채권형",
        "aum": 3210000000000,
        "yield_1m": 0.32,
        "yield_3m": 0.95,
        "yield_6m": 1.88,
        "yield_1y": 3.76,
        "risk_grade": 1,
    },
    {
        "fund_code": "KR5223944001",
        "name": "신한혼합자산배분증권자투자신탁(혼합-재간접)(C-e)",
        "type": "혼합형",
        "aum": 1500000000000,
        "yield_1m": 0.80,
        "yield_3m": 2.40,
        "yield_6m": 4.50,
        "yield_1y": 8.90,
        "risk_grade": 2,
    },
]

SORT_FIELDS = {"yield_1m", "yield_3m", "yield_6m", "yield_1y", "aum"}


@router.get("")
def fund_list(
    type: str  = Query(None, description="펀드 유형: 국내주식형|해외주식형|채권형|혼합형|MMF"),
    sort: str  = Query("yield_1y", description="정렬 기준: yield_1m|yield_3m|yield_6m|yield_1y|aum"),
):
    """펀드 목록.

    NOTE: KOFIA 공식 API 미연동 상태로 샘플 데이터 반환.
          실제 연동은 TODO 주석 참고.
    """
    sort = sort if sort in SORT_FIELDS else "yield_1y"
    key = f"invest:fund:list:{type}:{sort}"
    cached = cache.get(key)
    if cached:
        return cached

    funds = _SAMPLE_FUNDS
    if type:
        funds = [f for f in funds if f["type"] == type]

    funds_sorted = sorted(funds, key=lambda x: x.get(sort, 0) or 0, reverse=True)

    resp = ok({
        "source":  "sample",  # TODO: "kofia" 로 변경 시 실제 연동 완료
        "note":    "KOFIA 펀드 공시 API 미연동 — 샘플 데이터",
        "as_of":   datetime.now().strftime("%Y-%m-%d"),
        "count":   len(funds_sorted),
        "items":   funds_sorted,
    })
    cache.set(key, resp, TTL_FUND)
    return resp
