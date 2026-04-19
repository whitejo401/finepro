"""
analysis/fear_greed.py

공포-탐욕 지수 계산.

5개 지표를 Z-Score 정규화 후 방향성 보정, 가중 합산하여 0~100 지수 생성.

구성 지표:
  alt_vix_close      → 역방향 (VIX↑ = 공포↑ = 지수↓)
  rate_hy_spread     → 역방향 (스프레드↑ = 공포↑ = 지수↓)
  sent_news_global   → 정방향 (감성↑ = 탐욕↑ = 지수↑)
  crypto_btc_dominance → 중립/정방향 (BTC 독주 = 위험선호 낮음 → 역방향)
  rate_spread_10_2   → 역방향 (역전 = 경기침체 우려 = 공포)

해석:
  0~20  : 극공포
  20~40 : 공포
  40~60 : 중립
  60~80 : 탐욕
  80~100: 극탐욕
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from collectors.base import get_logger

log = get_logger("analysis.fear_greed")

# (컬럼명, 방향: +1=정방향, -1=역방향, 가중치)
# 가중치 합계 = 1.0 (가용 지표 수에 따라 정규화됨)
_COMPONENTS = [
    ("alt_vix_close",           -1, 0.22),
    ("rate_hy_spread",          -1, 0.18),
    ("sent_news_global",        +1, 0.20),
    ("crypto_btc_dominance",    -1, 0.13),
    ("rate_spread_10_2",        +1, 0.12),
    ("trends_fear_greed_us",    +1, 0.15),  # Google Trends (탐욕-공포 순합산)
]


def calc_fear_greed_index(
    master: pd.DataFrame,
    rolling_window: int = 252,
) -> pd.Series:
    """
    공포-탐욕 지수 계산 (0~100).

    각 지표를 rolling_window 기간 Z-Score로 정규화 → 방향 보정 → 가중 합산
    → sigmoid 변환으로 0~100 범위 조정.

    Args:
        master        : master DataFrame
        rolling_window: Z-Score 계산 롤링 창 (기본 252일 = 1년)
    Returns:
        pd.Series (index=날짜, values 0~100), name='fear_greed'
    """
    available = [(col, direction, weight)
                 for col, direction, weight in _COMPONENTS
                 if col in master.columns]

    if not available:
        log.warning("calc_fear_greed_index: 구성 지표 없음")
        return pd.Series(dtype=float)

    total_weight = sum(w for _, _, w in available)
    composite = pd.Series(0.0, index=master.index)

    for col, direction, weight in available:
        s = master[col].ffill()
        # Z-Score (롤링)
        roll_mean = s.rolling(rolling_window, min_periods=30).mean()
        roll_std  = s.rolling(rolling_window, min_periods=30).std()
        z = (s - roll_mean) / roll_std.replace(0, np.nan)
        z = z.fillna(0)
        composite += direction * z * (weight / total_weight)

    # sigmoid → 0~100
    fear_greed = 100 / (1 + np.exp(-composite))
    fear_greed.name = "fear_greed"
    return fear_greed.round(2)


def fear_greed_label(score: float) -> str:
    """공포-탐욕 지수 → 레이블."""
    if score < 20:
        return "극공포"
    elif score < 40:
        return "공포"
    elif score < 60:
        return "중립"
    elif score < 80:
        return "탐욕"
    else:
        return "극탐욕"


def fear_greed_summary(master: pd.DataFrame) -> dict:
    """
    현재 공포-탐욕 지수 + 구성 지표 기여도 요약.

    Returns:
        {
            'index'      : float,   # 0~100
            'label'      : str,
            'series'     : pd.Series,
            'components' : dict {col: z_score}
        }
    """
    series = calc_fear_greed_index(master)
    if series.empty:
        return {}

    valid = series.dropna()
    current = float(valid.iloc[-1]) if not valid.empty else 50.0

    # 구성 지표 현재 Z-Score
    components = {}
    for col, direction, _ in _COMPONENTS:
        if col not in master.columns:
            continue
        s = master[col].ffill().dropna()
        if s.empty or s.std() == 0:
            continue
        z = float((s.iloc[-1] - s.mean()) / s.std())
        components[col] = round(direction * z, 3)

    return {
        "index": round(current, 1),
        "label": fear_greed_label(current),
        "series": series,
        "components": components,
    }
