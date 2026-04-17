"""game/maple — 메이플스토리 캐릭터 조회·데미지·스타포스 계산기."""
import logging
import os
import random

import requests
from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_CHAR = 600  # 10분

NEXON_KEY  = os.getenv("NEXON_API_KEY", "")
NEXON_BASE = "https://open.api.nexon.com"
NEXON_HEADERS = {"x-nxopen-api-key": NEXON_KEY}

# 스타포스 확률 테이블 (성공/실패/파괴) — KMS 기준
# index = 현재 별 수
STARFORCE_TABLE = [
    (0.95, 0.05, 0.00),   # 0→1
    (0.90, 0.10, 0.00),   # 1→2
    (0.85, 0.15, 0.00),   # 2→3
    (0.85, 0.15, 0.00),   # 3→4
    (0.80, 0.20, 0.00),   # 4→5
    (0.75, 0.25, 0.00),   # 5→6
    (0.70, 0.30, 0.00),   # 6→7
    (0.65, 0.35, 0.00),   # 7→8
    (0.60, 0.40, 0.00),   # 8→9
    (0.55, 0.45, 0.00),   # 9→10
    (0.50, 0.50, 0.00),   # 10→11
    (0.45, 0.55, 0.00),   # 11→12
    (0.40, 0.594, 0.006), # 12→13
    (0.35, 0.637, 0.013), # 13→14
    (0.30, 0.686, 0.014), # 14→15
    (0.30, 0.679, 0.021), # 15→16
    (0.30, 0.679, 0.021), # 16→17
    (0.30, 0.679, 0.021), # 17→18
    (0.30, 0.672, 0.028), # 18→19
    (0.30, 0.672, 0.028), # 19→20
    (0.30, 0.63,  0.07),  # 20→21
    (0.30, 0.63,  0.07),  # 21→22
    (0.03, 0.776, 0.194), # 22→23
    (0.02, 0.686, 0.294), # 23→24
    (0.01, 0.594, 0.396), # 24→25
]

# 아이템 레벨별 스타포스 비용 (간략화, 실제는 복잡한 공식)
def _starforce_cost(item_level: int, star: int) -> int:
    base = 1000 + (item_level ** 3) * (star + 1) // 25
    return max(base, 1000)


def _nexon_get(path: str) -> dict | None:
    if not NEXON_KEY:
        return None
    try:
        r = requests.get(f"{NEXON_BASE}{path}", headers=NEXON_HEADERS, timeout=6)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return {}
        logger.debug("넥슨 API %s → %s", path, r.status_code)
        return None
    except Exception as e:
        logger.debug("넥슨 API 오류: %s", e)
        return None


def _get_ocid(name: str) -> str | None:
    data = _nexon_get(f"/maplestory/v1/id?character_name={requests.utils.quote(name)}")
    if not data:
        return None
    return data.get("ocid")


@router.get("/character/{name}")
def maple_character(name: str = Path(description="캐릭터명")):
    """메이플스토리 캐릭터 기본정보·스탯."""
    cache_key = f"game:maple:char:{name}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    if not NEXON_KEY:
        raise HTTPException(status_code=503, detail="NEXON_API_KEY 미설정")

    ocid = _get_ocid(name)
    if not ocid:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다")

    basic = _nexon_get(f"/maplestory/v1/character/basic?ocid={ocid}")
    stat  = _nexon_get(f"/maplestory/v1/character/stat?ocid={ocid}")
    if not basic:
        raise HTTPException(status_code=503, detail="넥슨 API 호출 실패")

    # 스탯 파싱
    stat_map = {}
    if stat and isinstance(stat.get("final_stat"), list):
        for s in stat["final_stat"]:
            stat_map[s.get("stat_name")] = s.get("stat_value")

    resp = ok({
        "name":   basic.get("character_name"),
        "class":  basic.get("character_class"),
        "level":  basic.get("character_level"),
        "world":  basic.get("world_name"),
        "guild":  basic.get("character_guild_name"),
        "stats": {
            "str":              stat_map.get("STR"),
            "dex":              stat_map.get("DEX"),
            "int":              stat_map.get("INT"),
            "luk":              stat_map.get("LUK"),
            "damage_pct":       stat_map.get("데미지"),
            "boss_damage_pct":  stat_map.get("보스 몬스터 데미지"),
            "crit_rate":        stat_map.get("크리티컬 확률"),
            "final_dmg_pct":    stat_map.get("최종 데미지"),
        },
    })
    cache.set(cache_key, resp, TTL_CHAR)
    return resp


@router.get("/calc/damage")
def maple_calc_damage(
    atk: float = Query(..., description="최종 공격력"),
    damage_pct: float = Query(0, description="데미지 % 합산"),
    boss_pct: float = Query(0, description="보스 데미지 %"),
    final_dmg_pct: float = Query(0, description="최종 데미지 %"),
    crit_rate: float = Query(0, ge=0, le=100, description="크리티컬 확률 %"),
    crit_dmg: float = Query(50, description="크리티컬 데미지 % (기본 50)"),
):
    """메이플스토리 데미지 계산기."""
    avg_dmg = atk * (1 + damage_pct / 100) * (1 + boss_pct / 100) * (1 + final_dmg_pct / 100)
    avg_crit = avg_dmg * (1 + (crit_rate / 100) * (crit_dmg / 100))

    resp = ok({
        "atk":           atk,
        "damage_pct":    damage_pct,
        "boss_pct":      boss_pct,
        "final_dmg_pct": final_dmg_pct,
        "crit_rate":     crit_rate,
        "crit_dmg":      crit_dmg,
        "avg_dmg":       round(avg_dmg, 1),
        "avg_crit":      round(avg_crit, 1),
        "min_dmg":       round(avg_dmg * 0.85, 1),
        "max_dmg":       round(avg_dmg * 1.15, 1),
    })
    return resp


@router.get("/calc/starforce")
def maple_calc_starforce(
    item_level: int = Query(200, description="장비 레벨"),
    current_star: int = Query(..., ge=0, le=24, description="현재 별 수"),
    target_star: int = Query(..., ge=1, le=25, description="목표 별 수"),
    event: bool = Query(False, description="30% 비용 할인 이벤트 여부"),
    simulations: int = Query(10000, ge=1000, le=50000, description="시뮬레이션 횟수"),
):
    """스타포스 기대 비용·파괴 횟수 몬테카를로 시뮬레이션."""
    if current_star >= target_star:
        raise HTTPException(status_code=422, detail="target_star는 current_star보다 커야 합니다")
    if target_star > len(STARFORCE_TABLE):
        raise HTTPException(status_code=422, detail=f"최대 목표 별 수: {len(STARFORCE_TABLE)}")

    costs = []
    destructions = []
    attempts_list = []

    for _ in range(simulations):
        total_cost   = 0
        destruction  = 0
        total_att    = 0
        star = current_star

        while star < target_star:
            prob = STARFORCE_TABLE[star]
            success_p, fail_p, dest_p = prob

            if event:
                cost = int(_starforce_cost(item_level, star) * 0.7)
            else:
                cost = _starforce_cost(item_level, star)

            total_cost += cost
            total_att  += 1

            r = random.random()
            if r < success_p:
                star += 1
            elif r < success_p + dest_p:
                destruction += 1
                star = max(star - 1, 12)  # 파괴 시 12성으로 복구 가정
            else:
                # 실패: 10~14성은 별 유지, 15성 이상은 -1
                if star >= 15:
                    star -= 1

        costs.append(total_cost)
        destructions.append(destruction)
        attempts_list.append(total_att)

    costs.sort()
    expected_cost = sum(costs) // simulations
    p50 = costs[int(simulations * 0.5)]
    p90 = costs[int(simulations * 0.9)]
    avg_dest = sum(destructions) / simulations
    avg_att  = sum(attempts_list) / simulations

    resp = ok({
        "item_level":        item_level,
        "current_star":      current_star,
        "target_star":       target_star,
        "event_discount":    event,
        "simulations":       simulations,
        "expected_cost":     expected_cost,
        "p50_cost":          p50,
        "p90_cost":          p90,
        "avg_destruction":   round(avg_dest, 2),
        "avg_attempts":      round(avg_att, 1),
    })
    return resp
