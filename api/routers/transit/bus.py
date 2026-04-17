"""transit/bus — 고속버스 요금·시간표 엔드포인트 (공공데이터포털)."""
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

BUS_SCHEDULE_URL = (
    "http://apis.data.go.kr/1613000/ExpBusInfoService/getExpBusList"
)

# 정적 요금 폴백 테이블 (우등/일반)
STATIC_BUS_FARES = {
    ("서울", "부산"):   {"우등": 31400, "일반": 23300, "duration_min": 280, "depart": "서울고속버스터미널", "arrive": "부산종합버스터미널"},
    ("서울", "광주"):   {"우등": 20700, "일반": 15400, "duration_min": 195, "depart": "서울고속버스터미널", "arrive": "광주종합버스터미널"},
    ("서울", "대구"):   {"우등": 22700, "일반": 16800, "duration_min": 185, "depart": "서울고속버스터미널", "arrive": "대구북부정류장"},
    ("서울", "강릉"):   {"우등": 20700, "일반": 15400, "duration_min": 140, "depart": "동서울터미널",       "arrive": "강릉고속버스터미널"},
    ("서울", "전주"):   {"우등": 15400, "일반": 11400, "duration_min": 145, "depart": "서울고속버스터미널", "arrive": "전주고속버스터미널"},
    ("서울", "대전"):   {"우등": 11400, "일반":  8400, "duration_min": 100, "depart": "서울고속버스터미널", "arrive": "대전복합터미널"},
    ("서울", "여수"):   {"우등": 27100, "일반": 20200, "duration_min": 250, "depart": "서울고속버스터미널", "arrive": "여수공용버스터미널"},
    ("서울", "울산"):   {"우등": 27600, "일반": 20400, "duration_min": 255, "depart": "서울고속버스터미널", "arrive": "울산고속버스터미널"},
    ("서울", "창원"):   {"우등": 25300, "일반": 18800, "duration_min": 230, "depart": "서울고속버스터미널", "arrive": "창원종합버스터미널"},
    ("서울", "청주"):   {"우등":  9700, "일반":  7200, "duration_min":  75, "depart": "서울고속버스터미널", "arrive": "청주고속버스터미널"},
}


def _normalize_key(from_: str, to: str):
    """출발·도착 방향에 무관하게 키 반환."""
    key = (from_, to)
    rev = (to, from_)
    if key in STATIC_BUS_FARES:
        return key, False
    if rev in STATIC_BUS_FARES:
        return rev, True
    return None, False


def _fetch_bus(from_: str, to: str, date: str) -> list[dict] | None:
    if not DATA_KEY:
        return None
    params = {
        "serviceKey": DATA_KEY,
        "pageNo": "1",
        "numOfRows": "10",
        "depTerminalId": from_,
        "arrTerminalId": to,
        "depPlandTime": date,
        "busGradeId": "1",  # 1=고속
        "_type": "json",
    }
    try:
        r = requests.get(BUS_SCHEDULE_URL, params=params, timeout=8)
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
                "grade":        item.get("gradeNm", ""),
                "price":        item.get("charge", 0),
                "duration_min": None,
                "depart_time":  item.get("depPlandTime", ""),
                "arrive_time":  item.get("arrPlandTime", ""),
            })
        return fares if fares else None
    except Exception as e:
        logger.debug("고속버스 API 오류: %s", e)
        return None


@router.get("")
def bus_fare(
    from_: str = Query(..., alias="from", description="출발지명 (예: 서울, 부산)"),
    to: str = Query(..., description="도착지명"),
    date: str = Query(None, description="날짜 YYYYMMDD (기본: 오늘)"),
):
    """고속버스 요금 조회."""
    if not date:
        date = datetime.now().strftime("%Y%m%d")

    cache_key = f"transit:bus:{from_}:{to}:{date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    fares = _fetch_bus(from_, to, date)

    if not fares:
        key, reversed_ = _normalize_key(from_, to)
        if key is None:
            raise HTTPException(
                status_code=422,
                detail=f"지원 구간: {[f'{a}→{b}' for a, b in STATIC_BUS_FARES.keys()]}",
            )
        info = STATIC_BUS_FARES[key]
        depart_terminal = info["arrive"] if reversed_ else info["depart"]
        arrive_terminal = info["depart"] if reversed_ else info["arrive"]
        fares = [
            {"grade": "우등", "price": info["우등"], "duration_min": info["duration_min"]},
            {"grade": "일반", "price": info["일반"], "duration_min": info["duration_min"]},
        ]
        terminals = {"departure": depart_terminal, "arrival": arrive_terminal}
    else:
        terminals = {"departure": f"{from_} 터미널", "arrival": f"{to} 터미널"}

    resp = ok({"from": from_, "to": to, "date": date, "fares": fares, "terminals": terminals})
    cache.set(cache_key, resp, TTL)
    return resp
