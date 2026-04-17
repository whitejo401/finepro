"""game/lol — LoL 소환사 전적·계산기·메타 엔드포인트."""
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_SUMMONER = 300   # 5분
TTL_MATCH    = 300
TTL_META     = 1800  # 30분

RIOT_KEY = os.getenv("RIOT_API_KEY", "")
RIOT_HEADERS = {"X-Riot-Token": RIOT_KEY}

KR_BASE    = "https://kr.api.riotgames.com"
ASIA_BASE  = "https://asia.api.riotgames.com"

# 정적 메타 (패치 주기 2주마다 수동 갱신 필요)
META_TIER_TABLE = {
    "S+": ["아리", "진", "카이사", "이즈리얼", "바이"],
    "S":  ["야스오", "카타리나", "갈리오", "루시안", "빅토르"],
    "A":  ["빅토르", "조이", "라이즈", "시비르", "케이틀린"],
    "B":  ["코르키", "르블랑", "트리스타나", "쓰레쉬"],
}

# 간단 챔피언 스탯 (DPS 계산용, 실제 Data Dragon 연동 필요)
CHAMPION_STATS = {
    "jinx":    {"base_ad": 57, "ad_growth": 3.4, "base_as": 0.625, "as_growth": 1.0, "range": 525},
    "caitlyn": {"base_ad": 62, "ad_growth": 3.8, "base_as": 0.568, "as_growth": 3.5, "range": 650},
    "kaisa":   {"base_ad": 59, "ad_growth": 3.0, "base_as": 0.644, "as_growth": 4.0, "range": 525},
    "ashe":    {"base_ad": 61, "ad_growth": 3.5, "base_as": 0.658, "as_growth": 3.5, "range": 600},
    "ezreal":  {"base_ad": 60, "ad_growth": 3.0, "base_as": 0.625, "as_growth": 3.5, "range": 550},
}

ITEM_STATS = {
    "infinity_edge":   {"ad": 70, "crit": 20},
    "kraken_slayer":   {"ad": 65, "as": 25},
    "galeforce":       {"ad": 55, "crit": 20},
    "phantom_dancer":  {"crit": 20, "as": 25},
    "bloodthirster":   {"ad": 55, "crit": 20},
    "rageblade":       {"ad": 30, "ap": 30, "as": 40},
}


def _riot_get(url: str) -> dict | None:
    if not RIOT_KEY:
        return None
    try:
        r = requests.get(url, headers=RIOT_HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return {}
        logger.debug("Riot API %s → %s", url, r.status_code)
        return None
    except Exception as e:
        logger.debug("Riot API 오류: %s", e)
        return None


@router.get("/summoner/{name}")
def lol_summoner(name: str = Path(description="소환사 이름")):
    """LoL 소환사 정보 (티어·LP·승률·주요 챔피언)."""
    cache_key = f"game:lol:summoner:{name}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not RIOT_KEY:
        raise HTTPException(status_code=503, detail="RIOT_API_KEY 미설정")

    # 1) 소환사 기본 정보
    summoner = _riot_get(f"{KR_BASE}/lol/summoner/v4/summoners/by-name/{requests.utils.quote(name)}")
    if summoner is None:
        raise HTTPException(status_code=503, detail="Riot API 호출 실패")
    if not summoner:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다")

    summoner_id = summoner.get("id")
    puuid       = summoner.get("puuid")

    # 2) 랭크 정보 + 챔피언 숙련도 병렬
    def get_league():
        return _riot_get(f"{KR_BASE}/lol/league/v4/entries/by-summoner/{summoner_id}")

    def get_mastery():
        return _riot_get(f"{KR_BASE}/lol/champion-mastery/v4/champion-masteries/by-summoner/{summoner_id}/top?count=3")

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_league  = ex.submit(get_league)
        f_mastery = ex.submit(get_mastery)
        league_data  = f_league.result() or []
        mastery_data = f_mastery.result() or []

    # 솔로랭크 우선
    rank_info = next((x for x in league_data if x.get("queueType") == "RANKED_SOLO_5x5"), None)
    tier = lp = win_rate = None
    if rank_info:
        wins   = rank_info.get("wins", 0)
        losses = rank_info.get("losses", 0)
        total  = wins + losses
        tier     = f"{rank_info.get('tier', '')} {rank_info.get('rank', '')}"
        lp       = rank_info.get("leaguePoints", 0)
        win_rate = round(wins / total * 100, 1) if total else None

    most_champions = [
        {"champion_id": m.get("championId"), "mastery": m.get("championPoints", 0)}
        for m in (mastery_data if isinstance(mastery_data, list) else [])
    ]

    resp = ok({
        "name":            summoner.get("name"),
        "level":           summoner.get("summonerLevel"),
        "tier":            tier,
        "lp":              lp,
        "win_rate":        win_rate,
        "most_champions":  most_champions,
    })
    cache.set(cache_key, resp, TTL_SUMMONER)
    return resp


@router.get("/match/{name}")
def lol_match(
    name: str = Path(description="소환사 이름"),
    count: int = Query(20, ge=1, le=50, description="최근 매치 수"),
):
    """LoL 최근 매치 기록."""
    cache_key = f"game:lol:match:{name}:{count}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not RIOT_KEY:
        raise HTTPException(status_code=503, detail="RIOT_API_KEY 미설정")

    summoner = _riot_get(f"{KR_BASE}/lol/summoner/v4/summoners/by-name/{requests.utils.quote(name)}")
    if not summoner:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다")

    puuid = summoner.get("puuid")
    match_list = _riot_get(f"{ASIA_BASE}/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}")
    if not match_list:
        return ok([], meta={"name": name, "count": 0})

    def fetch_match(match_id: str):
        return _riot_get(f"{ASIA_BASE}/lol/match/v5/matches/{match_id}")

    matches = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch_match, mid): mid for mid in match_list[:count]}
        for f in as_completed(futures):
            data = f.result()
            if not data:
                continue
            info = data.get("info", {})
            participant = next(
                (p for p in info.get("participants", []) if p.get("puuid") == puuid), None
            )
            if not participant:
                continue
            duration = info.get("gameDuration", 0)
            matches.append({
                "champion":      participant.get("championName"),
                "role":          participant.get("teamPosition"),
                "win":           participant.get("win"),
                "kills":         participant.get("kills"),
                "deaths":        participant.get("deaths"),
                "assists":       participant.get("assists"),
                "cs":            participant.get("totalMinionsKilled", 0) + participant.get("neutralMinionsKilled", 0),
                "damage":        participant.get("totalDamageDealtToChampions"),
                "duration_min":  round(duration / 60, 1),
            })

    matches.sort(key=lambda x: x.get("duration_min") or 0, reverse=True)
    resp = ok(matches, meta={"name": name, "count": len(matches)})
    cache.set(cache_key, resp, TTL_MATCH)
    return resp


@router.get("/calc/dps")
def lol_calc_dps(
    champion: str = Query(..., description="챔피언 영문 소문자 (예: jinx, caitlyn)"),
    build: str = Query("", description="아이템 쉼표 구분 (예: infinity_edge,kraken_slayer)"),
    level: int = Query(18, ge=1, le=18, description="챔피언 레벨"),
):
    """LoL DPS 계산기 (정적 스탯 기반)."""
    champ_lower = champion.lower()
    if champ_lower not in CHAMPION_STATS:
        raise HTTPException(status_code=422, detail=f"지원 챔피언: {list(CHAMPION_STATS.keys())}")

    base = CHAMPION_STATS[champ_lower]
    # 레벨 보정
    ad = base["base_ad"] + base["ad_growth"] * (level - 1)
    base_as = base["base_as"]
    as_bonus = base["as_growth"] / 100 * (level - 1)

    total_ad   = ad
    total_ap   = 0
    total_crit = 0
    total_as_pct = as_bonus

    items = [i.strip() for i in build.split(",") if i.strip()] if build else []
    for item in items:
        stats = ITEM_STATS.get(item.lower(), {})
        total_ad      += stats.get("ad", 0)
        total_ap      += stats.get("ap", 0)
        total_crit    += stats.get("crit", 0)
        total_as_pct  += stats.get("as", 0) / 100

    attack_speed = base_as * (1 + total_as_pct)
    # 크리티컬: 최대 100%, 크리 보정 계수 0.75
    crit_factor = 1 + min(total_crit / 100, 1.0) * 0.75
    dps = total_ad * attack_speed * crit_factor

    resp = ok({
        "champion":    champion,
        "level":       level,
        "build":       items,
        "ad":          round(total_ad, 1),
        "ap":          round(total_ap, 1),
        "attack_speed": round(attack_speed, 3),
        "crit_pct":    total_crit,
        "dps":         round(dps, 1),
        "burst_dmg":   round(total_ad * crit_factor * 3, 1),
        "effective_hp": None,
        "note":        "정적 스탯 기반 추정치. Data Dragon 연동 시 정밀도 향상 가능",
    })
    return resp


@router.get("/meta/tier")
def lol_meta_tier():
    """LoL 챔피언 메타 티어표 (정적, 패치 주기마다 수동 갱신)."""
    cached = cache.get("game:lol:meta:tier")
    if cached:
        return cached

    tiers = []
    for tier, champions in META_TIER_TABLE.items():
        for champ in champions:
            tiers.append({"champion": champ, "tier": tier})

    resp = ok(tiers, meta={
        "count": len(tiers),
        "note": "패치 2주 주기로 수동 갱신 필요. 자동 수집 미지원.",
    })
    cache.set("game:lol:meta:tier", resp, TTL_META)
    return resp
