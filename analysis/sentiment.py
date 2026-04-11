"""
analysis/sentiment.py

뉴스 감성 점수 후처리 및 복합 감성 지수 계산.

입력: master DataFrame의 sent_news_global, sent_news_fed 컬럼 (-1~1)
출력: 이동평균, 복합 감성 점수, 신호 레이블
"""
from __future__ import annotations

import pandas as pd

from collectors.base import get_logger

log = get_logger("analysis.sentiment")

_SENT_COLS = ["sent_news_global", "sent_news_fed"]
_WEIGHTS = {"sent_news_global": 0.6, "sent_news_fed": 0.4}


def calc_sentiment_ma(
    master: pd.DataFrame,
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """
    감성 점수 이동평균 계산.

    Args:
        master : master DataFrame
        windows: 이동평균 창 리스트 (기본 [7, 30])
    Returns:
        DataFrame (columns: sent_{col}_ma{w})
    """
    windows = windows or [7, 30]
    available = [c for c in _SENT_COLS if c in master.columns]
    if not available:
        log.warning("calc_sentiment_ma: 감성 컬럼 없음")
        return pd.DataFrame()

    result = pd.DataFrame(index=master.index)
    for col in available:
        s = master[col]
        for w in windows:
            result[f"{col}_ma{w}"] = s.rolling(w, min_periods=1).mean()

    return result


def composite_sentiment_score(
    master: pd.DataFrame,
    use_ma: int | None = 7,
) -> pd.Series:
    """
    복합 감성 점수 계산 (글로벌 60% + 연준 40%).

    Args:
        master: master DataFrame
        use_ma: 이동평균 창 (None이면 원본 사용)
    Returns:
        pd.Series (index=날짜, values -1~1), name='sent_composite'
    """
    available = {col: w for col, w in _WEIGHTS.items() if col in master.columns}
    if not available:
        log.warning("composite_sentiment_score: 감성 컬럼 없음")
        return pd.Series(dtype=float)

    total_weight = sum(available.values())
    composite = pd.Series(0.0, index=master.index)

    for col, weight in available.items():
        s = master[col]
        if use_ma:
            s = s.rolling(use_ma, min_periods=1).mean()
        composite += s * (weight / total_weight)

    composite.name = "sent_composite"
    return composite


def sentiment_label(score: float) -> str:
    """감성 점수 → 레이블 변환."""
    if score >= 0.3:
        return "긍정"
    elif score >= 0.1:
        return "약한 긍정"
    elif score >= -0.1:
        return "중립"
    elif score >= -0.3:
        return "약한 부정"
    else:
        return "부정"
