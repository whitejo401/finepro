"""transit/train — 코레일 열차 요금·시간표 엔드포인트 (공공데이터포털)."""
import logging
import os
from datetime import datetime

import requests
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 21600  # 6시간

DATA_KEY = os.getenv("DATA_GO_KR_API_KEY", "")

# 코레일 정적 요금 테이블 (주요 구간, KTX 일반실 기준 — API 미설정 시 폴백)
STATIC_FARES = {
    ("서울", "부산"):   [
        {"type": "KTX",    "grade": "일반실", "price": 59800, "duration_min": 162},
        {"type": "KTX",    "grade": "특실",   "price": 83800, "duration_min": 162},
        {"type": "무궁화",  "grade": "일반실", "price": 28600, "duration_min": 290},
    ],
    ("서울", "대구"):   [
        {"type": "KTX",    "grade": "일반실", "price": 42600, "duration_min": 107},
        {"type": "무궁화",  "grade": "일반실", "price": 20200, "duration_min": 205},
    ],
    ("서울", "광주"):   [
        {"type": "KTX",    "grade": "일반실", "price": 46800, "duration_min": 88},
        {"type": "무궁화",  "grade": "일반실", "price": 22300, "duration_min": 242},
    ],
    ("서울", "대전"):   [
        {"type": "KTX",    "grade": "일반실", "price": 23700, "duration_min": 49},
        {"type": "ITX새마을", "grade": "일반실", "price": 16000, "duration_min": 90},
        {"type": "무궁화",  "grade": "일반실", "price": 11200, "duration_min": 128},
    ],
    ("서울", "강릉"):   [
        {"type": "KTX-이음", "grade": "일반실", "price": 27600, "duration_min": 116},
    ],
    ("서울", "전주"):   [
        {"type": "KTX",    "grade": "일반실", "price": 38000, "duration_min": 107},
        {"type": "무궁화",  "grade": "일반실", "price": 18200, "duration_min": 185},
    ],
    ("서울", "여수"):   [
        {"type": "KTX",    "grade": "일반실", "price": 52800, "duration_min": 177},
    ],
    ("부산", "서울"):   [
        {"type": "KTX",    "grade": "일반실", "price": 59800, "duration_min": 162},
        {"type": "KTX",    "grade": "특실",   "price": 83800, "duration_min": 162},
        {"type": "무궁화",  "grade": "일반실", "price": 28600, "duration_min": 290},
    ],
}

KORAIL_TRAIN_URL = (
    "http://apis.data.go.kr/1613000/TrainInfoService/getStrtpntAlocFndTrainInfo"
)


def _fetch_korail(from_station: str, to_station: str, date: str) -> list[dict] | None:
    if not DATA_KEY:
        return None
    params = {
        "serviceKey": DATA_KEY,
        "pageNo": "1",
        "numOfRows": "20",
        "depPlaceId": from_station,
        "arrPlaceId": to_station,
        "depPlandTime": date,
        "_type": "json",
    }
    try:
        r = requests.get(KORAIL_TRAIN_URL, params=params, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        items = (
            data.get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", [])
        )
        if isinstance(items, dict):
            items = [items]
        fares = []
        for item in items:
            fares.append({
                "type":         item.get("trainGradeName", ""),
                "grade":        "일반실",
                "price":        item.get("adultCharge", 0),
                "duration_min": None,
                "depart":       item.get("depPlandTime", ""),
                "arrive":       item.get("arrPlandTime", ""),
            })
        return fares if fares else None
    except Exception as e:
        logger.debug("코레일 API 오류: %s", e)
        return None


@router.get("")
def train_fare(
    from_: str = Query(..., alias="from", description="출발역명 (예: 서울, 부산)"),
    to: str = Query(..., description="도착역명"),
    date: str = Query(None, description="날짜 YYYYMMDD (기본: 오늘)"),
):
    """코레일 열차 요금 조회."""
    if not date:
        date = datetime.now().strftime("%Y%m%d")

    cache_key = f"transit:train:{from_}:{to}:{date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 공공API 시도
    fares = _fetch_korail(from_, to, date)

    # API 미설정·실패 시 정적 테이블 폴백
    if not fares:
        key = (from_, to)
        rev = (to, from_)
        if key in STATIC_FARES:
            fares = STATIC_FARES[key]
        elif rev in STATIC_FARES:
            fares = STATIC_FARES[rev]
        else:
            raise HTTPException(
                status_code=422,
                detail=f"지원 구간 목록: {[f'{a}→{b}' for a, b in STATIC_FARES.keys()]}",
            )

    resp = ok({"from": from_, "to": to, "date": date, "fares": fares})
    cache.set(cache_key, resp, TTL)
    return resp
