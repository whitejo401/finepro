"""game/pubg — PUBG 플레이어 전적 엔드포인트."""
import logging
import os

import requests
from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_PLAYER = 300  # 5분

PUBG_KEY  = os.getenv("PUBG_API_KEY", "")
PUBG_BASE = "https://api.pubg.com/shards/kakao"
PUBG_HEADERS = {
    "Authorization": f"Bearer {PUBG_KEY}",
    "Accept": "application/vnd.api+json",
}


def _pubg_get(path: str) -> dict | None:
    if not PUBG_KEY:
        return None
    try:
        r = requests.get(f"{PUBG_BASE}{path}", headers=PUBG_HEADERS, timeout=6)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return {}
        logger.debug("PUBG API %s → %s", path, r.status_code)
        return None
    except Exception as e:
        logger.debug("PUBG API 오류: %s", e)
        return None


@router.get("/player/{name}")
def pubg_player(
    name: str = Path(description="PUBG 플레이어 이름"),
    season: str = Query("current", description="시즌 ID 또는 'current'"),
):
    """PUBG 플레이어 전적 (솔로·듀오·스쿼드)."""
    cache_key = f"game:pubg:player:{name}:{season}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not PUBG_KEY:
        raise HTTPException(status_code=503, detail="PUBG_API_KEY 미설정")

    # 플레이어 조회
    player_data = _pubg_get(f"/players?filter[playerNames]={name}")
    if player_data is None:
        raise HTTPException(status_code=503, detail="PUBG API 호출 실패")
    if not player_data or not player_data.get("data"):
        raise HTTPException(status_code=404, detail="플레이어를 찾을 수 없습니다")

    player = player_data["data"][0]
    player_id = player["id"]

    # 현재 시즌 조회
    if season == "current":
        seasons_data = _pubg_get("/seasons")
        if seasons_data and seasons_data.get("data"):
            current = next(
                (s for s in seasons_data["data"] if s.get("attributes", {}).get("isCurrentSeason")),
                None,
            )
            season_id = current["id"] if current else "division.bro.official.pc-2018-01"
        else:
            season_id = "division.bro.official.pc-2018-01"
    else:
        season_id = season

    # 시즌 스탯
    stats_data = _pubg_get(f"/players/{player_id}/seasons/{season_id}")
    if not stats_data or not stats_data.get("data"):
        raise HTTPException(status_code=503, detail="시즌 스탯 조회 실패")

    attr = stats_data["data"].get("attributes", {}).get("gameModeStats", {})

    def extract_mode(mode_key: str) -> dict:
        m = attr.get(mode_key, {})
        rounds = m.get("roundsPlayed", 0)
        wins   = m.get("wins", 0)
        return {
            "rounds":       rounds,
            "wins":         wins,
            "win_rate":     round(wins / rounds * 100, 1) if rounds else 0,
            "top10_rate":   round(m.get("top10s", 0) / rounds * 100, 1) if rounds else 0,
            "avg_rank":     round(m.get("rankPointsTitle", 0), 1),
            "kills":        m.get("kills", 0),
            "kda":          round((m.get("kills", 0) + m.get("assists", 0)) / max(m.get("losses", 1), 1), 2),
            "avg_dmg":      round(m.get("damageDealt", 0) / rounds, 1) if rounds else 0,
            "headshot_rate": round(m.get("headshotKills", 0) / max(m.get("kills", 1), 1) * 100, 1),
        }

    resp = ok({
        "name":     name,
        "season":   season_id,
        "solo":     extract_mode("solo"),
        "duo":      extract_mode("duo"),
        "squad":    extract_mode("squad"),
        "solo_fpp": extract_mode("solo-fpp"),
        "squad_fpp": extract_mode("squad-fpp"),
    })
    cache.set(cache_key, resp, TTL_PLAYER)
    return resp
