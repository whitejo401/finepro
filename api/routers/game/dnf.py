"""game/dnf — 던전앤파이터 캐릭터·모험단 엔드포인트 (Neople API)."""
import logging
import os

import requests
from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_CHAR = 600  # 10분

NEOPLE_KEY  = os.getenv("NEOPLE_API_KEY", "")
NEOPLE_BASE = "https://api.neople.co.kr/df"

SERVER_NAMES = {
    "cain": "카인", "diregie": "디레지에", "siroco": "시로코",
    "prey": "프레이", "casillas": "카시야스", "hilder": "힐더",
    "anton": "안톤", "bakal": "바칼",
}


def _neople_get(path: str) -> dict | None:
    if not NEOPLE_KEY:
        return None
    sep = "&" if "?" in path else "?"
    try:
        r = requests.get(f"{NEOPLE_BASE}{path}{sep}apikey={NEOPLE_KEY}", timeout=6)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return {}
        logger.debug("Neople API %s → %s", path, r.status_code)
        return None
    except Exception as e:
        logger.debug("Neople API 오류: %s", e)
        return None


@router.get("/character/{server}/{name}")
def dnf_character(
    server: str = Path(description=f"서버명 ({', '.join(SERVER_NAMES.keys())})"),
    name: str = Path(description="캐릭터명"),
):
    """DNF 캐릭터 검색."""
    if server not in SERVER_NAMES:
        raise HTTPException(status_code=422, detail=f"지원 서버: {list(SERVER_NAMES.keys())}")

    cache_key = f"game:dnf:char:{server}:{name}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not NEOPLE_KEY:
        raise HTTPException(status_code=503, detail="NEOPLE_API_KEY 미설정")

    data = _neople_get(f"/servers/{server}/characters?characterName={requests.utils.quote(name)}&wordType=match")
    if data is None:
        raise HTTPException(status_code=503, detail="Neople API 호출 실패")
    if not data or not data.get("rows"):
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다")

    rows = data["rows"][:5]
    results = []
    for row in rows:
        char_id = row.get("characterId")
        detail = _neople_get(f"/servers/{server}/characters/{char_id}")
        if detail:
            results.append({
                "character_id":   char_id,
                "name":           detail.get("characterName"),
                "job":            detail.get("jobName"),
                "job_grow":       detail.get("jobGrowName"),
                "level":          detail.get("level"),
                "fame":           detail.get("fame"),
                "adventure_name": detail.get("adventureName"),
                "guild":          detail.get("guildName"),
            })
        else:
            results.append(row)

    resp = ok(results, meta={"server": SERVER_NAMES.get(server, server), "count": len(results)})
    cache.set(cache_key, resp, TTL_CHAR)
    return resp


@router.get("/adventure/{server}/{name}")
def dnf_adventure(
    server: str = Path(description="서버명"),
    name: str = Path(description="모험단명"),
):
    """DNF 모험단 정보·소속 캐릭터."""
    if server not in SERVER_NAMES:
        raise HTTPException(status_code=422, detail=f"지원 서버: {list(SERVER_NAMES.keys())}")

    cache_key = f"game:dnf:adventure:{server}:{name}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not NEOPLE_KEY:
        raise HTTPException(status_code=503, detail="NEOPLE_API_KEY 미설정")

    data = _neople_get(f"/servers/{server}/modals/adventure?adventureName={requests.utils.quote(name)}")
    if data is None:
        raise HTTPException(status_code=503, detail="Neople API 호출 실패")
    if not data:
        raise HTTPException(status_code=404, detail="모험단을 찾을 수 없습니다")

    resp = ok(data, meta={"server": SERVER_NAMES.get(server, server)})
    cache.set(cache_key, resp, TTL_CHAR)
    return resp
