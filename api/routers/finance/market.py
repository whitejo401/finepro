"""finance/market — 시장 스냅샷 엔드포인트."""
import glob
import os
from fastapi import APIRouter, HTTPException
import pandas as pd

from api.core.cache import cache
from api.core.response import ok, error
from config import PROCESSED_DIR

router = APIRouter()

TTL_MARKET = 300  # 5분


def _load_latest_master() -> pd.DataFrame:
    """최신 master parquet 로드."""
    files = sorted(glob.glob(str(PROCESSED_DIR / "master_*.parquet")))
    if not files:
        raise FileNotFoundError("master parquet 없음")
    return pd.read_parquet(files[-1])


@router.get("/snapshot")
def market_snapshot():
    """글로벌 시장 최신 스냅샷 (주요 지수·환율·원자재·VIX)."""
    cached = cache.get("finance:market:snapshot")
    if cached:
        return cached

    try:
        master = _load_latest_master()
        cols = [c for c in master.columns if c.startswith(("us_", "fx_", "cmd_", "alt_vix"))]
        last = master[cols].dropna(how="all").iloc[-1]
        data = {col: (None if pd.isna(v) else round(float(v), 4)) for col, v in last.items()}
        resp = ok(data, meta={"date": str(last.name.date() if hasattr(last.name, "date") else last.name)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set("finance:market:snapshot", resp, TTL_MARKET)
    return resp


@router.get("/history/{symbol}")
def market_history(symbol: str, days: int = 90):
    """특정 심볼의 최근 N일 시계열."""
    key = f"finance:market:history:{symbol}:{days}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        master = _load_latest_master()
        if symbol not in master.columns:
            raise HTTPException(status_code=404, detail=f"심볼 '{symbol}' 없음")
        series = master[symbol].dropna().tail(days)
        data = {str(k.date() if hasattr(k, "date") else k): round(float(v), 4)
                for k, v in series.items()}
        resp = ok(data, meta={"symbol": symbol, "days": len(data)})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_MARKET)
    return resp
