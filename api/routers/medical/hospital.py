"""medical/hospital — 병원 목록 엔드포인트 (HIRA)."""
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간

HIRA_BASE = "http://apis.data.go.kr/B551182/MdctnPerfmncInfoService01"

REGION_CODE = {
    "서울": "110000", "부산": "260000", "대구": "270000", "인천": "280000",
    "광주": "290000", "대전": "300000", "울산": "310000", "세종": "360000",
    "경기": "410000", "강원": "420000", "충북": "430000", "충남": "440000",
    "전북": "450000", "전남": "460000", "경북": "470000", "경남": "480000", "제주": "500000",
}

DEPT_CODE = {
    "내과": "01", "외과": "02", "정형외과": "03", "신경과": "04",
    "정신건강의학과": "05", "피부과": "06", "비뇨기과": "07", "산부인과": "08",
    "소아과": "10", "안과": "11", "이비인후과": "12", "영상의학과": "13",
    "마취통증의학과": "14", "응급의학과": "41",
}


def _hira_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("DATA_GO_KR_API_KEY", "")
    params.update({"serviceKey": key, "_type": "json"})
    resp = requests.get(f"{HIRA_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@router.get("")
def hospital_list(
    region: str = Query(..., description="시도 (서울·부산 등, 필수)"),
    dept: str | None = Query(None, description="진료과목 (소아과·정형외과 등)"),
    type_: str | None = Query(None, alias="type", description="병원·의원·종합병원"),
):
    """지역별 병원 목록 (진료과목·유형 필터)."""
    if region not in REGION_CODE:
        raise HTTPException(status_code=422, detail=f"지원 지역: {list(REGION_CODE.keys())}")

    cache_key = f"medical:hospital:{region}:{dept}:{type_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise HTTPException(status_code=503, detail="DATA_GO_KR_API_KEY 미설정")

    try:
        params: dict = {
            "sidoCd": REGION_CODE[region],
            "numOfRows": 100,
            "pageNo": 1,
        }
        if dept and dept in DEPT_CODE:
            params["dgsbjtCd"] = DEPT_CODE[dept]

        raw = _hira_get("getMdctnPerfmncInfo01", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        items = []
        for i in items_raw:
            clsf = i.get("clCdNm") or ""
            if type_ and type_ not in clsf:
                continue
            items.append({
                "name": i.get("yadmNm"),
                "type": clsf,
                "address": i.get("addr"),
                "phone": i.get("telno"),
                "depts": [d.strip() for d in (i.get("dgsbjtCdNm") or "").split(",") if d.strip()],
                "lat": i.get("YPos"),
                "lon": i.get("XPos"),
                "source": "HIRA",
            })

        resp = ok(items, meta={"region": region, "dept": dept, "type": type_, "count": len(items)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("hospital_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
