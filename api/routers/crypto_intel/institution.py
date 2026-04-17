"""crypto_intel/institution — 기관 보유량·ETF 자금흐름 엔드포인트."""
import logging
from fastapi import APIRouter, HTTPException, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_TREASURY = 21600   # 6시간
TTL_ETF = 600          # 10분
TTL_ETF_HIST = 3600    # 1시간

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
SOSOVALUE_BASE = "https://sosovalue.com/api"


def _cg_get(path: str, params: dict | None = None) -> dict | list:
    import os, requests
    headers = {}
    api_key = os.getenv("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    resp = requests.get(f"{COINGECKO_BASE}{path}", params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _fetch_treasury_coingecko() -> list[dict]:
    """CoinGecko public_companies API — 상장사 BTC/ETH 보유량."""
    btc = _cg_get("/companies/public_treasury/bitcoin")
    eth = _cg_get("/companies/public_treasury/ethereum")

    rows = []
    for item in (btc.get("companies") or []):
        rows.append({
            "asset": "BTC",
            "company": item.get("name"),
            "symbol": item.get("symbol"),
            "country": item.get("country"),
            "holdings": item.get("total_holdings"),
            "entry_value_usd": item.get("total_entry_value_usd"),
            "current_value_usd": item.get("total_current_value_usd"),
            "pct_of_supply": item.get("percentage_of_total_supply"),
        })
    for item in (eth.get("companies") or []):
        rows.append({
            "asset": "ETH",
            "company": item.get("name"),
            "symbol": item.get("symbol"),
            "country": item.get("country"),
            "holdings": item.get("total_holdings"),
            "entry_value_usd": item.get("total_entry_value_usd"),
            "current_value_usd": item.get("total_current_value_usd"),
            "pct_of_supply": item.get("percentage_of_total_supply"),
        })
    return sorted(rows, key=lambda x: x.get("current_value_usd") or 0, reverse=True)


def _fetch_etf_flow_sosovalue() -> list[dict]:
    """SoSoValue BTC 현물 ETF 일간 자금흐름."""
    import requests
    try:
        # SoSoValue 공개 엔드포인트 (인증 불필요)
        resp = requests.get(
            "https://sosovalue.com/api/etf/us-btc-spot",
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
        # 응답 구조: {"code":0, "data": {"list": [...]}}
        items = (raw.get("data") or {}).get("list") or []
        return [
            {
                "ticker": item.get("ticker"),
                "name": item.get("name"),
                "issuer": item.get("issuer"),
                "aum_usd": item.get("aum"),
                "net_flow_usd": item.get("netInflow"),
                "btc_holdings": item.get("btcHolding"),
                "date": item.get("date"),
            }
            for item in items
        ]
    except Exception as e:
        logger.warning("SoSoValue ETF flow 실패: %s", e)
        return []


def _fetch_etf_flow_coinglass() -> list[dict]:
    """CoinGlass BTC ETF 자금흐름 (무료 티어 폴백)."""
    import requests
    try:
        resp = requests.get(
            "https://open-api.coinglass.com/public/v2/indicator/bitcoin_etf_flow",
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
        items = raw.get("data") or []
        return [
            {
                "ticker": item.get("ticker"),
                "name": item.get("name"),
                "net_flow_usd": item.get("netFlow"),
                "aum_usd": item.get("aum"),
                "date": item.get("date"),
            }
            for item in items
        ]
    except Exception as e:
        logger.warning("CoinGlass ETF flow 실패: %s", e)
        return []


@router.get("/treasury")
def institution_treasury(
    asset: str = Query("all", description="all | BTC | ETH"),
    limit: int = Query(50, ge=1, le=200),
):
    """상장사·기관 BTC·ETH 보유량 순위."""
    cache_key = f"crypto_intel:institution:treasury:{asset}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        rows = _fetch_treasury_coingecko()
        if asset.upper() != "ALL":
            rows = [r for r in rows if r["asset"] == asset.upper()]
        rows = rows[:limit]
        meta = {
            "asset": asset,
            "count": len(rows),
            "total_btc": sum(r["holdings"] for r in rows if r["asset"] == "BTC" and r["holdings"]),
            "total_eth": sum(r["holdings"] for r in rows if r["asset"] == "ETH" and r["holdings"]),
        }
        resp = ok(rows, meta=meta)
    except Exception as e:
        logger.error("institution_treasury error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_TREASURY)
    return resp


@router.get("/etf/flow")
def etf_flow():
    """미국 BTC 현물 ETF 일간 자금유입출 (AUM·넷플로우)."""
    cached = cache.get("crypto_intel:etf:flow")
    if cached:
        return cached

    try:
        data = _fetch_etf_flow_sosovalue()
        if not data:
            data = _fetch_etf_flow_coinglass()
        if not data:
            raise HTTPException(status_code=503, detail="ETF 데이터 소스 모두 실패")

        total_aum = sum(d.get("aum_usd") or 0 for d in data)
        total_flow = sum(d.get("net_flow_usd") or 0 for d in data)
        resp = ok(data, meta={
            "total_aum_usd": total_aum,
            "total_net_flow_usd": total_flow,
            "count": len(data),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("etf_flow error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set("crypto_intel:etf:flow", resp, TTL_ETF)
    return resp


@router.get("/etf/holdings")
def etf_holdings():
    """ETF별 BTC 보유량·AUM·운용사 비교."""
    cached = cache.get("crypto_intel:etf:holdings")
    if cached:
        return cached

    try:
        data = _fetch_etf_flow_sosovalue()
        if not data:
            data = _fetch_etf_flow_coinglass()
        if not data:
            raise HTTPException(status_code=503, detail="ETF 데이터 소스 모두 실패")

        # BTC 보유량 기준 정렬
        data = sorted(data, key=lambda x: x.get("btc_holdings") or x.get("aum_usd") or 0, reverse=True)
        resp = ok(data, meta={"count": len(data)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("etf_holdings error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set("crypto_intel:etf:holdings", resp, TTL_ETF)
    return resp


@router.get("/etf/history")
def etf_history(days: int = Query(90, ge=7, le=365)):
    """BTC ETF 자금흐름 누적 시계열."""
    cache_key = f"crypto_intel:etf:history:{days}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        import requests
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        resp_raw = requests.get(
            "https://sosovalue.com/api/etf/us-btc-spot/history",
            params={"days": days},
            timeout=15,
        )
        resp_raw.raise_for_status()
        raw = resp_raw.json()
        items = (raw.get("data") or {}).get("list") or []

        # 일별 집계: 날짜별 전체 넷플로우 합산
        from collections import defaultdict
        daily: dict[str, float] = defaultdict(float)
        for item in items:
            d = item.get("date", "")[:10]
            daily[d] += item.get("netInflow") or 0

        history = [{"date": d, "net_flow_usd": v} for d, v in sorted(daily.items())]
        # 누적
        cumulative = 0.0
        for row in history:
            cumulative += row["net_flow_usd"]
            row["cumulative_flow_usd"] = round(cumulative, 2)

        resp = ok(history, meta={"days": days, "count": len(history)})
    except Exception as e:
        logger.error("etf_history error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_ETF_HIST)
    return resp
