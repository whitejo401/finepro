"""culture/trending — 행사 통합 목록 + 트렌딩 Top10 엔드포인트."""
import logging
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL = 3600  # 1시간

TOUR_BASE = "http://apis.data.go.kr/B551011/KorService1"
KOPIS_BASE = "http://www.kopis.or.kr/openApi/restful"

# 트렌딩 스코어 가중치
MAJOR_REGIONS = {"서울", "부산", "대구", "인천", "광주", "대전"}

REGION_AREA = {
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
    "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
    "충북": 33, "충남": 34, "경북": 35, "경남": 36, "전북": 37,
    "전남": 38, "제주": 39,
}


def _fmt_date(d: str | None) -> str | None:
    if not d or len(d) < 8:
        return d
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _fetch_tour(region: str, month: str) -> list[dict]:
    import requests
    key = os.getenv("TOUR_API_KEY", "")
    if not key:
        return []
    try:
        params: dict = {
            "serviceKey": key, "MobileOS": "ETC", "MobileApp": "InfoAPI",
            "_type": "json", "numOfRows": 100, "pageNo": 1,
            "eventStartDate": month + "01", "eventEndDate": month + "31",
        }
        if region != "전체" and region in REGION_AREA:
            params["areaCode"] = REGION_AREA[region]
        resp = requests.get(f"{TOUR_BASE}/searchFestival1", params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
        items_raw = (
            raw.get("response", {}).get("body", {})
               .get("items", {}) or {}
        ).get("item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        return [
            {
                "id": f"tour_{i.get('contentid')}",
                "title": i.get("title"),
                "type": "축제/행사",
                "region": (i.get("addr1") or "").split()[0] if i.get("addr1") else None,
                "venue": i.get("addr1"),
                "start_date": _fmt_date(i.get("eventstartdate")),
                "end_date": _fmt_date(i.get("eventenddate")),
                "thumbnail": i.get("firstimage"),
                "source": "TourAPI",
            }
            for i in items_raw
        ]
    except Exception as e:
        logger.warning("TourAPI 실패: %s", e)
        return []


def _fetch_kopis(region: str, month: str) -> list[dict]:
    import requests, xml.etree.ElementTree as ET
    key = os.getenv("KOPIS_API_KEY", "")
    if not key:
        return []
    try:
        params: dict = {
            "service": key, "stdate": month + "01", "eddate": month + "31",
            "rows": 100, "cpage": 1,
        }
        resp = requests.get(f"{KOPIS_BASE}/pblprfr", params=params, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = []
        for db in root.findall("db"):
            def t(tag): return (db.findtext(tag) or "").strip()
            items.append({
                "id": f"kopis_{t('mt20id')}",
                "title": t("prfnm"),
                "type": "공연",
                "region": t("area"),
                "venue": t("fcltynm"),
                "start_date": t("prfpdfrom"),
                "end_date": t("prfpdto"),
                "thumbnail": t("poster"),
                "source": "KOPIS",
            })
        return items
    except Exception as e:
        logger.warning("KOPIS 실패: %s", e)
        return []


def _score(item: dict, today: datetime) -> float:
    """트렌딩 스코어: 진행중 여부 + 대도시 + 주말 근접."""
    score = 0.0
    try:
        s = datetime.strptime(item["start_date"], "%Y-%m-%d") if item.get("start_date") else None
        e = datetime.strptime(item["end_date"], "%Y-%m-%d") if item.get("end_date") else None
        if s and e:
            if s <= today <= e:
                score += 50  # 진행 중
            elif s > today and (s - today).days <= 7:
                score += 30  # 7일 내 시작
    except Exception:
        pass

    region = item.get("region") or ""
    if any(r in region for r in MAJOR_REGIONS):
        score += 20

    # 주말(금~일) 근접
    if today.weekday() >= 4:
        score += 10

    return score


@router.get("")
def culture_events(
    region: str = Query("전체", description="지역 (서울·부산 등 또는 전체)"),
    month: str | None = Query(None, description="YYYYMM — 생략 시 당월"),
    keyword: str | None = Query(None, description="검색어"),
):
    """문화행사·축제 통합 목록 (TourAPI + KOPIS 병렬)."""
    if not month:
        month = datetime.now().strftime("%Y%m")

    cache_key = f"culture:events:{region}:{month}:{keyword}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    all_items: list[dict] = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [
            ex.submit(_fetch_tour, region, month),
            ex.submit(_fetch_kopis, region, month),
        ]
        for f in as_completed(futures):
            all_items.extend(f.result())

    if keyword:
        all_items = [i for i in all_items if keyword in (i.get("title") or "")]

    all_items.sort(key=lambda x: x.get("start_date") or "")

    partial = not os.getenv("TOUR_API_KEY") or not os.getenv("KOPIS_API_KEY")
    meta: dict = {"region": region, "month": month, "count": len(all_items)}
    if partial:
        meta["partial"] = True

    resp = ok(all_items, meta=meta)
    cache.set(cache_key, resp, TTL)
    return resp


@router.get("/trending")
def culture_trending(limit: int = Query(10, ge=1, le=20)):
    """이번 주 인기 행사 Top N (진행중·대도시·주말 가중치 스코어링)."""
    cache_key = f"culture:trending:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    today = datetime.now()
    month = today.strftime("%Y%m")

    all_items: list[dict] = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [
            ex.submit(_fetch_tour, "전체", month),
            ex.submit(_fetch_kopis, "전체", month),
        ]
        for f in as_completed(futures):
            all_items.extend(f.result())

    scored = sorted(all_items, key=lambda x: _score(x, today), reverse=True)[:limit]
    for i, item in enumerate(scored, 1):
        item["rank"] = i
        item["score"] = round(_score(item, today), 1)

    resp = ok(scored, meta={"count": len(scored), "base_date": today.strftime("%Y-%m-%d")})
    cache.set(cache_key, resp, TTL)
    return resp
