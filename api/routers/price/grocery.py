"""price/grocery — KAMIS 농축수산물 가격 엔드포인트."""
import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간

KAMIS_BASE = "http://www.kamis.or.kr/service/price/xml.do"

CATEGORY_CODE = {
    "채소": "100", "과일": "200", "수산": "300", "축산": "400", "곡물": "500",
}

REGION_CODE = {
    "전국": "1101", "서울": "1101", "부산": "2100", "대구": "2200",
    "인천": "2300", "광주": "2401", "대전": "2501", "울산": "2601",
}


def _kamis_get(params: dict) -> dict:
    import requests
    api_key = os.getenv("KAMIS_API_KEY", "")
    cert_key = os.getenv("KAMIS_CERT_KEY", "")
    params.update({
        "action": "periodProductList",
        "apikey": api_key,
        "cert_key": cert_key,
        "returntype": "json",
    })
    resp = requests.get(KAMIS_BASE, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@router.get("")
def grocery_price(
    category: str = Query("채소", description="채소·과일·수산·축산·곡물"),
    item: str | None = Query(None, description="품목명 (예: 배추, 사과)"),
    region: str = Query("전국", description="지역 (서울·부산 등 또는 전국)"),
):
    """농축수산물 가격 (전일 대비 등락)."""
    if category not in CATEGORY_CODE:
        raise HTTPException(status_code=422, detail=f"지원 카테고리: {list(CATEGORY_CODE.keys())}")

    cache_key = f"price:grocery:{category}:{item}:{region}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("KAMIS_API_KEY"):
        raise HTTPException(status_code=503, detail="KAMIS_API_KEY 미설정")

    try:
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        params: dict = {
            "p_startday": yesterday.strftime("%Y-%m-%d"),
            "p_endday": today.strftime("%Y-%m-%d"),
            "p_categorycode": CATEGORY_CODE[category],
            "p_regday": today.strftime("%Y-%m-%d"),
            "p_countrycode": REGION_CODE.get(region, "1101"),
        }
        if item:
            params["p_itemname"] = item

        raw = _kamis_get(params)
        items_raw = (raw.get("data") or {}).get("item") or []
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        result = []
        for i in items_raw:
            price_str = (i.get("price") or "0").replace(",", "")
            diff_str = (i.get("diff") or "0").replace(",", "").replace("+", "")
            try:
                price = int(float(price_str)) if price_str else None
                diff = int(float(diff_str)) if diff_str else 0
                change_pct = round(diff / (price - diff) * 100, 1) if price and price != diff else 0
            except Exception:
                price, diff, change_pct = None, 0, 0

            result.append({
                "name": i.get("item_name"),
                "kind": i.get("kind_name"),
                "unit": i.get("unit"),
                "price": price,
                "change": diff,
                "change_pct": change_pct,
                "rank": i.get("rank"),
            })

        resp = ok(result, meta={
            "category": category, "region": region,
            "date": today.strftime("%Y-%m-%d"), "count": len(result),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("grocery_price error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
