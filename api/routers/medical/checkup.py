"""medical/checkup — 건강검진 기관 목록 엔드포인트."""
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 86400  # 24시간

DATA_GO_BASE = "http://apis.data.go.kr"

REGION_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28",
    "광주": "29", "대전": "30", "울산": "31", "세종": "36",
    "경기": "41", "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}

CHECKUP_TYPE_CODE = {
    "일반": "01", "암검진": "02", "구강": "03",
}


def _data_go_get(path: str, params: dict) -> dict:
    import requests
    key = os.getenv("DATA_GO_KR_API_KEY", "")
    params.update({"serviceKey": key, "_type": "json"})
    resp = requests.get(f"{DATA_GO_BASE}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@router.get("")
def checkup_list(
    region: str = Query(..., description="시도 (서울·부산 등, 필수)"),
    type_: str = Query("일반", alias="type", description="일반·암검진·구강"),
):
    """건강검진 지정 기관 목록."""
    if region not in REGION_CODE:
        raise HTTPException(status_code=422, detail=f"지원 지역: {list(REGION_CODE.keys())}")

    cache_key = f"medical:checkup:{region}:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        type_cd = CHECKUP_TYPE_CODE.get(type_, "01")
        raw = _data_go_get(
            "/B551182/healthScreeningList/getHealthScreeningList",
            {
                "sidoCd": REGION_CODE[region],
                "checkupType": type_cd,
                "numOfRows": 100,
                "pageNo": 1,
            },
        )
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = [
            {
                "name": i.get("yadmNm"),
                "type": i.get("clCdNm"),
                "address": i.get("addr"),
                "phone": i.get("telno"),
                "checkup_types": [t.strip() for t in (i.get("checkupTypeNm") or type_).split(",")],
                "reservation_url": i.get("url"),
                "lat": i.get("YPos"),
                "lon": i.get("XPos"),
            }
            for i in items_raw if isinstance(i, dict)
        ]
        resp = ok(items, meta={"region": region, "type": type_, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("checkup_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
