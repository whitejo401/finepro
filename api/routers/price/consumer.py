"""price/consumer — 생필품·외식 가격 (한국소비자원 참가격) 엔드포인트."""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 10800  # 3시간

DATA_GO_BASE = "http://apis.data.go.kr"

CATEGORY_ENDPOINT = {
    "가공식품": "/1471057/ConsumerPrice/getConsumerPriceList",
    "외식":     "/1471057/ConsumerPrice/getEatOutPriceList",
    "생활용품": "/1471057/ConsumerPrice/getLivingGoodsPriceList",
}


def _data_go_get(path: str, params: dict) -> dict:
    import requests
    key = os.getenv("DATA_GO_KR_API_KEY", "")
    params.update({"serviceKey": key, "type": "json", "numOfRows": 100, "pageNo": 1})
    resp = requests.get(f"{DATA_GO_BASE}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@router.get("")
def consumer_price(
    category: str = Query("가공식품", description="가공식품·외식·생활용품"),
):
    """생필품·외식 가격 비교 (전주 대비 등락)."""
    if category not in CATEGORY_ENDPOINT:
        raise HTTPException(status_code=422, detail=f"지원 카테고리: {list(CATEGORY_ENDPOINT.keys())}")

    cache_key = f"price:consumer:{category}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        raw = _data_go_get(CATEGORY_ENDPOINT[category], {})
        body = (raw.get("response") or {}).get("body") or {}
        items_raw = (body.get("items") or {}).get("item") or []
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [
            {
                "name": i.get("productNm") or i.get("itemNm"),
                "brand": i.get("brandNm"),
                "unit": i.get("unit"),
                "price": i.get("price"),
                "prev_price": i.get("prevPrice"),
                "change_pct": i.get("fluctuationRate"),
                "survey_date": i.get("surveyDate"),
            }
            for i in items_raw if isinstance(i, dict)
        ]
        resp = ok(items, meta={"category": category, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("consumer_price error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
