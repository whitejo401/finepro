"""game/fc — FC온라인 매치·선수 순위 엔드포인트 (넥슨 API)."""
import logging
import os

import requests
from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_USER  = 300   # 5분
TTL_RANK  = 1800  # 30분

NEXON_KEY  = os.getenv("NEXON_API_KEY", "")
NEXON_BASE = "https://open.api.nexon.com"
NEXON_HEADERS = {"x-nxopen-api-key": NEXON_KEY}


def _nexon_get(path: str) -> dict | None:
    if not NEXON_KEY:
        return None
    try:
        r = requests.get(f"{NEXON_BASE}{path}", headers=NEXON_HEADERS, timeout=6)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return {}
        logger.debug("넥슨 FC API %s → %s", path, r.status_code)
        return None
    except Exception as e:
        logger.debug("넥슨 FC API 오류: %s", e)
        return None


@router.get("/user/{name}")
def fc_user(name: str = Path(description="FC온라인 닉네임")):
    """FC온라인 유저 정보·매치 기록."""
    cache_key = f"game:fc:user:{name}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not NEXON_KEY:
        raise HTTPException(status_code=503, detail="NEXON_API_KEY 미설정")

    user = _nexon_get(f"/fconline/v1/id?nickname={requests.utils.quote(name)}")
    if user is None:
        raise HTTPException(status_code=503, detail="넥슨 API 호출 실패")
    if not user:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다")

    ouid = user.get("ouid")
    basic = _nexon_get(f"/fconline/v1/user/basic?ouid={ouid}")
    match = _nexon_get(f"/fconline/v1/user/match?ouid={ouid}&matchtype=50&offset=0&limit=5")

    resp = ok({
        "nickname": basic.get("nickname") if basic else name,
        "level":    basic.get("level") if basic else None,
        "recent_matches": match if isinstance(match, list) else [],
    }, meta={"ouid": ouid})
    cache.set(cache_key, resp, TTL_USER)
    return resp


@router.get("/top_players")
def fc_top_players(
    matchtype: int = Query(50, description="매치 타입 (50=공식경기)"),
):
    """FC온라인 상위 랭커 목록."""
    cache_key = f"game:fc:top:{matchtype}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not NEXON_KEY:
        raise HTTPException(status_code=503, detail="NEXON_API_KEY 미설정")

    data = _nexon_get(f"/fconline/v1/ranking/top?matchtype={matchtype}")
    if data is None:
        raise HTTPException(status_code=503, detail="넥슨 API 호출 실패")

    resp = ok(data if isinstance(data, list) else [], meta={"matchtype": matchtype})
    cache.set(cache_key, resp, TTL_RANK)
    return resp
