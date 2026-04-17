"""medical/drug — 식약처 의약품 허가정보 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 86400  # 24시간

DATA_GO_BASE = "http://apis.data.go.kr"


def _mfds_get(path: str, params: dict) -> dict:
    import requests
    key = os.getenv("DATA_GO_KR_API_KEY", "")
    params.update({"serviceKey": key, "type": "json"})
    resp = requests.get(f"{DATA_GO_BASE}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _clean_html(text: str | None) -> str:
    """간단한 HTML 태그 제거."""
    if not text:
        return ""
    import re
    return re.sub(r"<[^>]+>", " ", text).strip()[:500]


@router.get("")
def drug_info(
    name: str = Query(..., description="의약품명 (예: 타이레놀, 아스피린)"),
):
    """의약품 허가정보·성분·효능·주의사항 (식약처)."""
    cache_key = f"medical:drug:{name}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        raw = _mfds_get(
            "/1471057/MdcinGrnIdntfcInfoService01/getMdcinGrnIdntfcInfoList01",
            {"item_name": name, "numOfRows": 5, "pageNo": 1},
        )
        items_raw = (
            raw.get("body") or raw.get("response", {}).get("body") or {}
        ).get("items") or []
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        if not items_raw:
            # 폴백: 의약품 낱알식별 API
            raw2 = _mfds_get(
                "/1471057/DrugPrdtPrmsnInfoService06/getDrugPrdtPrmsnDtlInq06",
                {"item_name": name, "numOfRows": 5, "pageNo": 1},
            )
            items_raw = (
                (raw2.get("body") or raw2.get("response", {}).get("body") or {})
                .get("items") or []
            )
            if isinstance(items_raw, dict):
                items_raw = [items_raw]

        if not items_raw:
            return ok([], meta={"name": name, "count": 0, "message": "검색 결과 없음"})

        results = []
        for i in items_raw if isinstance(items_raw, list) else [items_raw]:
            results.append({
                "name": i.get("itemName") or i.get("ITEM_NAME"),
                "english_name": i.get("enName") or i.get("ENTP_NAME"),
                "ingredient": _clean_html(i.get("ingr") or i.get("INGR_NAME")),
                "category": i.get("classNm") or i.get("CLASS_NM"),
                "company": i.get("entpNm") or i.get("ENTP_NM"),
                "efficacy": _clean_html(i.get("efcyQesitm") or i.get("EE_DOC_DATA")),
                "dosage": _clean_html(i.get("useMethodQesitm") or i.get("UD_DOC_DATA")),
                "caution": _clean_html(i.get("atpnWarnQesitm") or i.get("NB_DOC_DATA")),
                "approved_date": i.get("permitDate") or i.get("PERMIT_DATE"),
                "image_url": i.get("itemImage") or i.get("ITEM_IMAGE"),
            })

        resp = ok(results, meta={"name": name, "count": len(results)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("drug_info error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
