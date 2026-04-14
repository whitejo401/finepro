"""crypto/market — 암호화폐 시장 엔드포인트."""
import glob
from fastapi import APIRouter, HTTPException
import pandas as pd

from api.core.cache import cache
from api.core.response import ok
from config import PROCESSED_DIR

router = APIRouter()

TTL_CRYPTO = 60  # 1분


def _load_latest_master() -> pd.DataFrame:
    files = sorted(glob.glob(str(PROCESSED_DIR / "master_*.parquet")))
    if not files:
        raise FileNotFoundError("master parquet 없음")
    return pd.read_parquet(files[-1])


@router.get("/snapshot")
def crypto_snapshot():
    """BTC·ETH 최신 가격 + 도미넌스 + 공포탐욕 지수."""
    cached = cache.get("crypto:market:snapshot")
    if cached:
        return cached

    try:
        master = _load_latest_master()
        cols = [c for c in master.columns if c.startswith("crypto_")]
        last = master[cols].dropna(how="all").iloc[-1]
        data = {col: (None if pd.isna(v) else round(float(v), 4)) for col, v in last.items()}
        resp = ok(data, meta={"date": str(last.name.date() if hasattr(last.name, "date") else last.name)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set("crypto:market:snapshot", resp, TTL_CRYPTO)
    return resp
