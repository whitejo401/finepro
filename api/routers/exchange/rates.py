"""exchange/rates — 환율 엔드포인트."""
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok
from collectors.exchange.rates import MAJOR_CURRENCIES

router = APIRouter()

TTL_LATEST  = 60 * 10   # 10분 (ECB는 영업일 1회 갱신)
TTL_HISTORY = 60 * 60   # 1시간
TTL_KRW     = 60 * 10   # 10분


@router.get("/latest")
def latest_rates(
    base: str = Query("USD", description="기준 통화 (USD, EUR, GBP 등)"),
):
    """최신 환율 (ECB 기준, frankfurter.app — 키 불필요).

    - 영업일 기준 최신값 반환
    - KRW는 ECB 미지원 → /krw 엔드포인트 사용
    """
    base = base.upper()
    key = f"exchange:rates:latest:{base}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.exchange.rates import get_latest_rates
        data = get_latest_rates(base=base)
        if not data:
            raise HTTPException(status_code=502, detail="환율 데이터 수집 실패")
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_LATEST)
    return resp


@router.get("/history")
def rate_history(
    base: str   = Query("USD", description="기준 통화"),
    target: str = Query("KRW", description="대상 통화"),
    start: str  = Query(None,  description="시작일 YYYY-MM-DD (기본: 90일 전)"),
    end: str    = Query(None,  description="종료일 YYYY-MM-DD (기본: 오늘)"),
):
    """기간별 환율 이력.

    - USD/EUR 등 ECB 지원 통화: frankfurter.app
    - KRW 관련: ECOS(한국은행) + frankfurter 교차 계산
    """
    base = base.upper()
    target = target.upper()
    key = f"exchange:rates:history:{base}:{target}:{start}:{end}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.exchange.rates import get_rate_history
        data = get_rate_history(base=base, target=target, start=start, end=end)
        if not data:
            raise HTTPException(status_code=502, detail="이력 데이터 수집 실패")
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_HISTORY)
    return resp


@router.get("/convert")
def convert(
    amount: float = Query(...,   description="변환할 금액"),
    base: str     = Query("USD", description="기준 통화"),
    target: str   = Query("KRW", description="대상 통화"),
):
    """환전 계산.

    예) amount=100, base=USD, target=KRW → 100달러를 원화로
    """
    base = base.upper()
    target = target.upper()

    if base == target:
        return ok({"base": base, "target": target, "amount": amount, "converted": amount, "rate": 1.0})

    # KRW 기준이면 /krw 로직 활용
    if target == "KRW":
        from collectors.exchange.rates import get_krw_rates
        krw_data = get_krw_rates(currencies=[base])
        rate_base_per_krw = krw_data.get("rates", {}).get(base)
        if not rate_base_per_krw:
            raise HTTPException(status_code=502, detail="환율 조회 실패")
        rate_krw_per_base = 1 / rate_base_per_krw
        return ok({
            "base": base, "target": target,
            "amount": amount,
            "converted": round(amount * rate_krw_per_base, 2),
            "rate": round(rate_krw_per_base, 4),
            "date": krw_data.get("date"),
        })

    if base == "KRW":
        from collectors.exchange.rates import get_krw_rates
        krw_data = get_krw_rates(currencies=[target])
        rate = krw_data.get("rates", {}).get(target)
        if not rate:
            raise HTTPException(status_code=502, detail="환율 조회 실패")
        return ok({
            "base": base, "target": target,
            "amount": amount,
            "converted": round(amount * rate, 4),
            "rate": rate,
            "date": krw_data.get("date"),
        })

    # 일반 통화 간
    try:
        from collectors.exchange.rates import get_latest_rates
        data = get_latest_rates(base=base)
        rate = data.get("rates", {}).get(target)
        if not rate:
            raise HTTPException(status_code=404, detail=f"'{target}' 환율 없음")
        return ok({
            "base": base, "target": target,
            "amount": amount,
            "converted": round(amount * rate, 4),
            "rate": rate,
            "date": data.get("date"),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/krw")
def krw_rates(
    currencies: str = Query(
        ",".join(c for c in MAJOR_CURRENCIES if c != "KRW"),
        description="조회할 통화 목록 (쉼표 구분, 예: USD,EUR,JPY)",
    ),
):
    """원화(KRW) 기준 주요 통화 환율.

    ECOS(한국은행) 원/달러 기준 + frankfurter 교차 계산.
    """
    cur_list = [c.strip().upper() for c in currencies.split(",") if c.strip()]
    key = f"exchange:rates:krw:{','.join(sorted(cur_list))}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from collectors.exchange.rates import get_krw_rates
        data = get_krw_rates(currencies=cur_list)
        if not data:
            raise HTTPException(status_code=502, detail="원화 환율 수집 실패")
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_KRW)
    return resp
