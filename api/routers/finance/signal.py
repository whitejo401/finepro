"""finance/signal — KOSPI 예측 신호 엔드포인트."""
import glob
from fastapi import APIRouter, HTTPException
import pandas as pd

from api.core.cache import cache
from api.core.response import ok
from config import PROCESSED_DIR

router = APIRouter()

TTL_SIGNAL = 3600  # 1시간


def _load_latest_master() -> pd.DataFrame:
    files = sorted(glob.glob(str(PROCESSED_DIR / "master_*.parquet")))
    if not files:
        raise FileNotFoundError("master parquet 없음")
    return pd.read_parquet(files[-1])


@router.get("/kospi")
def kospi_signal():
    """KOSPI 방향 예측 신호 (다수결 + 로지스틱 확률)."""
    cached = cache.get("finance:signal:kospi")
    if cached:
        return cached

    try:
        from analysis.prediction import build_today_prediction
        master = _load_latest_master()
        result = build_today_prediction(master)
        resp = ok(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set("finance:signal:kospi", resp, TTL_SIGNAL)
    return resp
