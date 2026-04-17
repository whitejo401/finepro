"""crypto_intel/sector — 코인 섹터·분류 엔드포인트."""
import logging
from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_SECTOR = 21600   # 6시간
TTL_MARKET = 600     # 10분
TTL_PROFILE = 3600   # 1시간

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


def _cg_get(path: str, params: dict | None = None) -> dict | list:
    import os, requests
    headers = {}
    api_key = os.getenv("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    resp = requests.get(f"{COINGECKO_BASE}{path}", params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


@router.get("/list")
def sector_list():
    """전체 코인 섹터·카테고리 목록 (id, name, market_cap, change_24h)."""
    cached = cache.get("crypto_intel:sector:list")
    if cached:
        return cached

    try:
        raw = _cg_get("/coins/categories")
        data = [
            {
                "id": item["id"],
                "name": item["name"],
                "market_cap": item.get("market_cap"),
                "market_cap_change_24h": item.get("market_cap_change_24h"),
                "volume_24h": item.get("volume_24h"),
                "top_3_coins": item.get("top_3_coins", []),
            }
            for item in raw
        ]
        resp = ok(data, meta={"count": len(data)})
    except Exception as e:
        logger.error("sector_list error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set("crypto_intel:sector:list", resp, TTL_SECTOR)
    return resp


@router.get("/{sector_id}")
def sector_coins(
    sector_id: str = Path(description="CoinGecko 카테고리 ID (예: decentralized-finance-defi)"),
    limit: int = Query(50, ge=1, le=250),
    order: str = Query("market_cap_desc", description="market_cap_desc | volume_desc | gecko_desc"),
):
    """섹터별 코인 목록 — 시총·24h 등락률·도미넌스 비중."""
    cache_key = f"crypto_intel:sector:{sector_id}:{limit}:{order}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        raw = _cg_get("/coins/markets", params={
            "vs_currency": "usd",
            "category": sector_id,
            "order": order,
            "per_page": limit,
            "page": 1,
            "sparkline": False,
            "price_change_percentage": "24h,7d,30d",
        })
        # 섹터 전체 시총 합산 (도미넌스 계산용)
        total_mcap = sum(c.get("market_cap") or 0 for c in raw)
        data = [
            {
                "rank": c.get("market_cap_rank"),
                "id": c["id"],
                "symbol": c["symbol"].upper(),
                "name": c["name"],
                "price_usd": c.get("current_price"),
                "market_cap": c.get("market_cap"),
                "dominance_pct": round(c["market_cap"] / total_mcap * 100, 2) if total_mcap and c.get("market_cap") else None,
                "volume_24h": c.get("total_volume"),
                "change_24h": c.get("price_change_percentage_24h_in_currency"),
                "change_7d": c.get("price_change_percentage_7d_in_currency"),
                "change_30d": c.get("price_change_percentage_30d_in_currency"),
                "image": c.get("image"),
            }
            for c in raw
        ]
        resp = ok(data, meta={"sector_id": sector_id, "count": len(data), "total_market_cap": total_mcap})
    except Exception as e:
        logger.error("sector_coins error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_MARKET)
    return resp


@router.get("/heatmap/performance")
def sector_heatmap(
    period: str = Query("24h", description="24h | 7d | 30d"),
):
    """섹터 성과 히트맵 — 기간별 등락률 순위."""
    cache_key = f"crypto_intel:sector:heatmap:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        raw = _cg_get("/coins/categories")
        field_map = {"24h": "market_cap_change_24h", "7d": "market_cap_change_24h", "30d": "market_cap_change_24h"}
        # CoinGecko 무료 티어는 24h만 제공 — 요청 기간 명시
        data = sorted(
            [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "change_pct": item.get("market_cap_change_24h"),
                    "market_cap": item.get("market_cap"),
                    "top_3_coins": item.get("top_3_coins", []),
                }
                for item in raw
                if item.get("market_cap_change_24h") is not None
            ],
            key=lambda x: x["change_pct"],
            reverse=True,
        )
        resp = ok(data, meta={"period": period, "note": "무료 티어 — 24h 기준", "count": len(data)})
    except Exception as e:
        logger.error("sector_heatmap error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_MARKET)
    return resp


@router.get("/coin/{coin_id}/profile")
def coin_profile(
    coin_id: str = Path(description="CoinGecko 코인 ID (예: bitcoin, ethereum)"),
):
    """코인 프로필 — 섹터·태그·체인·런치일·설명·백서링크."""
    cache_key = f"crypto_intel:coin:{coin_id}:profile"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        raw = _cg_get(f"/coins/{coin_id}", params={
            "localization": False,
            "tickers": False,
            "market_data": False,
            "community_data": False,
            "developer_data": False,
            "sparkline": False,
        })
        links = raw.get("links", {})
        data = {
            "id": raw["id"],
            "symbol": raw["symbol"].upper(),
            "name": raw["name"],
            "categories": raw.get("categories", []),
            "description": (raw.get("description") or {}).get("en", "")[:500],
            "genesis_date": raw.get("genesis_date"),
            "hashing_algorithm": raw.get("hashing_algorithm"),
            "asset_platform_id": raw.get("asset_platform_id"),
            "whitepaper": links.get("whitepaper") or None,
            "homepage": (links.get("homepage") or [""])[0] or None,
            "github": (links.get("repos_url") or {}).get("github", []),
            "twitter": links.get("twitter_screen_name"),
            "coingecko_score": raw.get("coingecko_score"),
            "image": (raw.get("image") or {}).get("small"),
        }
        resp = ok(data)
    except Exception as e:
        logger.error("coin_profile error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_PROFILE)
    return resp
