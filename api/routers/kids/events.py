"""kids/events — 어린이 행사 통합 목록·축제 엔드포인트."""
import logging
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간

TOUR_BASE = "http://apis.data.go.kr/B551011/KorService1"

REGION_AREA = {
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
    "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
    "충북": 33, "충남": 34, "경북": 35, "경남": 36, "전북": 37,
    "전남": 38, "제주": 39,
}


def _tour_get(endpoint: str, params: dict) -> dict:
    import requests
    key = os.getenv("TOUR_API_KEY", "")
    params.update({
        "serviceKey": key,
        "MobileOS": "ETC",
        "MobileApp": "InfoAPI",
        "_type": "json",
    })
    resp = requests.get(f"{TOUR_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _parse_tour_item(item: dict) -> dict:
    return {
        "title": item.get("title"),
        "type": "축제/행사",
        "organizer": None,
        "region": item.get("addr1", "").split()[0] if item.get("addr1") else None,
        "venue": item.get("addr1"),
        "age_group": "전체",
        "admission": "무료",
        "start_date": _fmt_date(item.get("eventstartdate")),
        "end_date": _fmt_date(item.get("eventenddate")),
        "registration_url": item.get("firstimage") and None,
        "image_url": item.get("firstimage"),
        "source": "TourAPI",
    }


def _fmt_date(d: str | None) -> str | None:
    if not d or len(d) < 8:
        return d
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _fetch_tour_kids(region: str, month: str) -> list[dict]:
    """TourAPI — 어린이 체험·축제 (contentTypeId=15 행사/축제)."""
    if not os.getenv("TOUR_API_KEY"):
        return []
    try:
        stdate = month + "01"
        etdate = month + "31"
        params: dict = {
            "eventStartDate": stdate,
            "eventEndDate": etdate,
            "keyword": "어린이",
            "numOfRows": 100,
            "pageNo": 1,
            "contentTypeId": 15,
        }
        if region != "전체" and region in REGION_AREA:
            params["areaCode"] = REGION_AREA[region]
        raw = _tour_get("searchFestival1", params)
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        return [_parse_tour_item(i) for i in items_raw]
    except Exception as e:
        logger.warning("TourAPI 어린이 행사 실패: %s", e)
        return []


def _fetch_kopis_kids(region: str, month: str) -> list[dict]:
    """KOPIS — 아동 무료 공연."""
    if not os.getenv("KOPIS_API_KEY"):
        return []
    try:
        import requests, xml.etree.ElementTree as ET
        key = os.getenv("KOPIS_API_KEY", "")
        stdate = month + "01"
        etdate = month + "31"
        params: dict = {
            "service": key,
            "stdate": stdate,
            "eddate": etdate,
            "shcate": "AAAB",
            "rows": 50,
            "cpage": 1,
            "prfprice": "무료",
        }
        resp = requests.get("http://www.kopis.or.kr/openApi/restful/pblprfr",
                            params=params, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = []
        for db in root.findall("db"):
            def t(tag): return (db.findtext(tag) or "").strip()
            items.append({
                "title": t("prfnm"),
                "type": "공연",
                "organizer": None,
                "region": t("area"),
                "venue": t("fcltynm"),
                "age_group": "초등",
                "admission": "무료",
                "start_date": t("prfpdfrom"),
                "end_date": t("prfpdto"),
                "image_url": t("poster"),
                "source": "KOPIS",
            })
        return items
    except Exception as e:
        logger.warning("KOPIS 어린이 공연 실패: %s", e)
        return []


@router.get("")
def kids_events(
    region: str = Query("전체", description="지역 (서울·부산 등 또는 전체)"),
    age: str = Query("전체", description="영유아·초등·중고등·전체"),
    month: str | None = Query(None, description="YYYYMM — 생략 시 당월"),
):
    """어린이·학생 무료 체험 행사 통합 목록 (TourAPI + KOPIS 병렬)."""
    if not month:
        month = datetime.now().strftime("%Y%m")

    cache_key = f"kids:events:{region}:{age}:{month}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 병렬 수집
    all_items: list[dict] = []
    partial = False
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(_fetch_tour_kids, region, month): "TourAPI",
            ex.submit(_fetch_kopis_kids, region, month): "KOPIS",
        }
        for f in as_completed(futures):
            result = f.result()
            if result:
                all_items.extend(result)
            elif not os.getenv("TOUR_API_KEY") or not os.getenv("KOPIS_API_KEY"):
                partial = True

    # 날짜순 정렬
    all_items.sort(key=lambda x: x.get("start_date") or "")

    meta: dict = {"region": region, "age": age, "month": month, "count": len(all_items)}
    if partial:
        meta["partial"] = True
        meta["note"] = "일부 소스 누락 — API 키 확인 필요"
    if not all_items:
        meta["tip"] = "검색 조건을 넓혀보세요"

    resp = ok(all_items, meta=meta)
    cache.set(cache_key, resp, TTL)
    return resp


@router.get("/festival")
def kids_festival(
    region: str = Query("전체", description="지역 (서울·부산 등 또는 전체)"),
    month: str | None = Query(None, description="YYYYMM — 생략 시 당월"),
):
    """전국 어린이 축제·체험 행사 (TourAPI)."""
    if not month:
        month = datetime.now().strftime("%Y%m")

    cache_key = f"kids:festival:{region}:{month}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not os.getenv("TOUR_API_KEY"):
        raise HTTPException(status_code=503, detail="TOUR_API_KEY 미설정")

    try:
        items = _fetch_tour_kids(region, month)
        resp = ok(items, meta={
            "region": region, "month": month, "count": len(items),
            "tip": "검색 조건을 넓혀보세요" if not items else None,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("kids_festival error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL)
    return resp
