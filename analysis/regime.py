"""
매크로 경기 국면 분류 모듈.

Merrill Lynch Investment Clock 기반으로 PMI와 CPI의 방향성을 조합하여
reflation / overheat / stagflation / deflation 4개 국면을 분류한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from collectors.base import get_logger

log = get_logger("analysis.regime")


# ---------------------------------------------------------------------------
# 국면 정의 및 추천 자산
# ---------------------------------------------------------------------------

# reflation:    PMI↑ + CPI↓  → 성장 회복, 인플레 없음 → 주식 유리
# overheat:     PMI↑ + CPI↑  → 과열 → 원자재 유리
# stagflation:  PMI↓ + CPI↑  → 스태그플레이션 → 현금/채권 유리
# deflation:    PMI↓ + CPI↓  → 디플레이션 → 채권 유리

REGIME_ASSETS: dict[str, list[str]] = {
    "reflation":   ["주식", "리츠"],
    "overheat":    ["원자재", "에너지주"],
    "stagflation": ["현금", "단기채권"],
    "deflation":   ["장기채권", "금"],
}

_REGIMES = list(REGIME_ASSETS.keys())


# ---------------------------------------------------------------------------
# 국면 분류
# ---------------------------------------------------------------------------

def classify_regime(
    pmi_series: pd.Series,
    cpi_series: pd.Series,
    window: int = 6,
) -> pd.Series:
    """
    PMI와 CPI의 window개월 변화율로 국면 분류.

    변화율 > 0 이면 '상승', <= 0 이면 '하락'으로 판단.
    np.select로 4개 국면 분기.

    Returns:
        pd.Series, values in ['reflation','overheat','stagflation','deflation'].
        데이터 부족(window 미만) 구간은 NaN.
    """
    if pmi_series.empty or cpi_series.empty:
        return pd.Series(dtype=object)

    pmi_aligned, cpi_aligned = pmi_series.align(cpi_series, join="inner")
    if pmi_aligned.empty:
        return pd.Series(dtype=object)

    pmi_chg = pmi_aligned.diff(window)
    cpi_chg = cpi_aligned.diff(window)

    pmi_up = pmi_chg > 0
    cpi_up = cpi_chg > 0

    conditions = [
        pmi_up & ~cpi_up,   # reflation
        pmi_up & cpi_up,    # overheat
        ~pmi_up & cpi_up,   # stagflation
        ~pmi_up & ~cpi_up,  # deflation
    ]

    result_arr = np.select(conditions, _REGIMES, default=None)

    # diff()로 생긴 NaN 구간은 NaN 유지
    valid_mask = pmi_chg.notna() & cpi_chg.notna()
    result = pd.Series(result_arr, index=pmi_aligned.index, dtype=object)
    result[~valid_mask] = np.nan
    result.name = "regime"
    return result


# ---------------------------------------------------------------------------
# 국면별 자산 성과
# ---------------------------------------------------------------------------

def regime_asset_performance(
    regime_series: pd.Series,
    asset_returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    국면별 자산 평균 수익률 집계.

    Returns:
        DataFrame (index=regime, columns=asset, values=mean_return).
        빈 입력이면 빈 DataFrame 반환.
    """
    if regime_series.empty or asset_returns.empty:
        return pd.DataFrame()

    combined = asset_returns.copy()
    combined["regime"] = regime_series
    combined = combined.dropna(subset=["regime"])

    if combined.empty:
        return pd.DataFrame()

    result = combined.groupby("regime")[asset_returns.columns.tolist()].mean()
    # 정의된 국면 순서 유지 (존재하는 것만)
    ordered = [r for r in _REGIMES if r in result.index]
    result = result.reindex(ordered)
    return result


# ---------------------------------------------------------------------------
# 현재 국면
# ---------------------------------------------------------------------------

def current_regime(
    pmi_series: pd.Series,
    cpi_series: pd.Series,
    window: int = 6,
) -> str:
    """
    최근 국면 반환.

    classify_regime의 마지막 유효값(NaN 제외).
    유효값이 없으면 빈 문자열 반환.
    """
    series = classify_regime(pmi_series, cpi_series, window)
    valid = series.dropna()
    if valid.empty:
        log.warning("유효한 국면 데이터가 없습니다.")
        return ""
    return str(valid.iloc[-1])


# ---------------------------------------------------------------------------
# 종합 요약
# ---------------------------------------------------------------------------

def regime_transition_matrix(
    regime_series: pd.Series,
) -> pd.DataFrame:
    """
    국면 간 천이 확률 행렬.

    연속된 두 기간의 국면 쌍을 집계하여
    'from 국면 → to 국면' 확률을 계산한다.

    Args:
        regime_series: classify_regime() 결과 Series

    Returns:
        DataFrame (index=from_regime, columns=to_regime, values=확률 0~1).
        행 합계 = 1.0. 데이터 부족 시 빈 DataFrame 반환.
    """
    s = regime_series.dropna()
    if len(s) < 2:
        log.warning("regime_transition_matrix: 데이터 부족 (n=%d)", len(s))
        return pd.DataFrame()

    from_vals = s.iloc[:-1].values
    to_vals   = s.iloc[1:].values

    matrix = pd.crosstab(
        pd.Series(from_vals, name="from"),
        pd.Series(to_vals,   name="to"),
        normalize="index",
    )

    # 정의된 4개 국면 순서로 정렬 (없는 국면은 0 채움)
    present = [r for r in _REGIMES if r in matrix.index or r in matrix.columns]
    matrix = matrix.reindex(index=present, columns=present, fill_value=0.0)
    return matrix.round(3)


def regime_summary(
    master: pd.DataFrame,
    pmi_col: str = "macro_pmi_us",
    cpi_col: str = "macro_cpi",
) -> dict:
    """
    master DataFrame에서 국면 분류 + 자산 성과 요약.

    master에 pmi_col 또는 cpi_col이 없으면 경고 후 빈 dict 반환.

    Returns:
        {
            'current': str,               # 현재 국면
            'series': pd.Series,          # 전체 국면 시리즈
            'performance': pd.DataFrame,  # 국면별 자산 성과
        }
    """
    if master.empty:
        log.warning("master DataFrame이 비어 있습니다.")
        return {}

    missing = [c for c in [pmi_col, cpi_col] if c not in master.columns]
    if missing:
        log.warning("master에 필요한 컬럼이 없습니다: %s", missing)
        return {}

    regime_s = classify_regime(master[pmi_col], master[cpi_col])

    # 자산 수익률 컬럼: pmi_col, cpi_col 이외의 숫자형 컬럼
    exclude = {pmi_col, cpi_col}
    asset_cols = [
        c for c in master.select_dtypes(include=[np.number]).columns
        if c not in exclude
    ]

    if asset_cols:
        perf = regime_asset_performance(regime_s, master[asset_cols])
    else:
        log.info("자산 수익률 컬럼이 없어 성과 집계를 건너뜁니다.")
        perf = pd.DataFrame()

    curr = current_regime(master[pmi_col], master[cpi_col])

    log.info("현재 국면: %s", curr if curr else "알 수 없음")

    return {
        "current": curr,
        "series": regime_s,
        "performance": perf,
    }
