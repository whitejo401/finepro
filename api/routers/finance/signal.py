"""finance/signal — KOSPI 예측 신호 엔드포인트."""
from fastapi import APIRouter, HTTPException
import pandas as pd

from api.core.cache import cache
from api.core.master import get_master
from api.core.response import ok

router = APIRouter()

TTL_SIGNAL = 3600  # 1시간


def _load_latest_master() -> pd.DataFrame:
    df = get_master()
    if df.empty:
        raise FileNotFoundError("master parquet 없음")
    return df


@router.get("/kospi")
def kospi_signal():
    """KOSPI 방향 예측 신호 (다수결 + 로지스틱 확률)."""
    cached = cache.get("finance:signal:kospi")
    if cached:
        return cached

    try:
        import numpy as np
        from analysis.prediction import build_today_prediction
        master = _load_latest_master()
        raw = build_today_prediction(master)

        # JSON 직렬화 가능한 형태로 변환
        def _to_json(v):
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating,)):
                return None if np.isnan(v) else float(v)
            if isinstance(v, pd.DataFrame):
                return v[["feature", "spearman_rho"]].head(5).values.tolist()
            if isinstance(v, dict):
                return {k2: _to_json(v2) for k2, v2 in v.items()}
            return v

        result = {k: _to_json(v) for k, v in raw.items()}
        resp = ok(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set("finance:signal:kospi", resp, TTL_SIGNAL)
    return resp
