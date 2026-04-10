"""
analysis/correlation.py

시계열 데이터 간 상관관계를 계산하는 모듈.

주요 함수:
  - rolling_spearman   : 두 시리즈의 Rolling Spearman 상관계수
  - correlation_matrix : DataFrame 컬럼 간 상관계수 행렬
  - top_correlations   : 특정 컬럼과 가장 상관관계 높은 n개 컬럼 반환
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from collectors.base import get_logger

log = get_logger("analysis.correlation")


def rolling_spearman(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int = 60,
) -> pd.Series:
    """
    두 시리즈의 Rolling Spearman 상관계수.

    scipy.stats.spearmanr을 window 단위로 rolling 적용한다.
    min_periods = window // 2

    Args:
        series_a: 첫 번째 시계열
        series_b: 두 번째 시계열
        window  : 롤링 윈도우 크기 (기본 60)

    Returns:
        Rolling Spearman 상관계수 pd.Series (index는 series_a와 동일)
    """
    if series_a.empty or series_b.empty:
        log.warning("rolling_spearman: 빈 시리즈 입력 — 빈 결과 반환")
        return pd.Series(dtype=float)

    min_periods = window // 2

    # 인덱스 정렬 후 공통 구간만 사용
    aligned_a, aligned_b = series_a.align(series_b, join="inner")

    if aligned_a.empty:
        log.warning("rolling_spearman: 공통 인덱스 없음 — 빈 결과 반환")
        return pd.Series(dtype=float)

    result = pd.Series(np.nan, index=aligned_a.index, dtype=float)

    values_a = aligned_a.values
    values_b = aligned_b.values
    n = len(values_a)

    for i in range(n):
        start = max(0, i - window + 1)
        window_a = values_a[start : i + 1]
        window_b = values_b[start : i + 1]

        # NaN 제거
        mask = ~(np.isnan(window_a) | np.isnan(window_b))
        valid_a = window_a[mask]
        valid_b = window_b[mask]

        if len(valid_a) < min_periods:
            continue

        corr, _ = stats.spearmanr(valid_a, valid_b)
        result.iloc[i] = corr

    log.debug(
        "rolling_spearman: window=%d, n=%d, non-NaN=%d",
        window,
        n,
        result.notna().sum(),
    )
    return result


def correlation_matrix(
    df: pd.DataFrame,
    method: str = "spearman",
    min_periods: int = 30,
) -> pd.DataFrame:
    """
    DataFrame 컬럼 간 상관계수 행렬.

    충분한 데이터(min_periods)가 없는 쌍은 NaN으로 처리한다.

    Args:
        df         : 입력 DataFrame
        method     : 상관계수 방식 ('spearman' | 'pearson')
        min_periods: 유효 상관계수 계산에 필요한 최소 데이터 수

    Returns:
        상관계수 행렬 DataFrame (컬럼 × 컬럼)
    """
    if df.empty:
        log.warning("correlation_matrix: 빈 DataFrame 입력 — 빈 결과 반환")
        return pd.DataFrame()

    if method not in ("spearman", "pearson"):
        raise ValueError(f"method는 'spearman' 또는 'pearson'이어야 합니다. 입력값: {method!r}")

    cols = df.columns.tolist()
    n = len(cols)
    matrix = pd.DataFrame(np.nan, index=cols, columns=cols, dtype=float)

    for i in range(n):
        matrix.iloc[i, i] = 1.0  # 자기 자신과의 상관계수
        for j in range(i + 1, n):
            col_a = df.iloc[:, i]
            col_b = df.iloc[:, j]

            # 두 컬럼 모두 유효한 행만 선택
            valid_mask = col_a.notna() & col_b.notna()
            valid_count = valid_mask.sum()

            if valid_count < min_periods:
                log.debug(
                    "correlation_matrix: (%s, %s) 유효 데이터 %d < min_periods %d — NaN",
                    cols[i],
                    cols[j],
                    valid_count,
                    min_periods,
                )
                continue

            a_valid = col_a[valid_mask].values
            b_valid = col_b[valid_mask].values

            if method == "spearman":
                corr, _ = stats.spearmanr(a_valid, b_valid)
            else:
                corr = np.corrcoef(a_valid, b_valid)[0, 1]

            matrix.iloc[i, j] = corr
            matrix.iloc[j, i] = corr  # 대칭

    log.info(
        "correlation_matrix: shape=%s, method=%s, non-NaN pairs=%d",
        matrix.shape,
        method,
        int(matrix.notna().sum().sum() - n),  # 대각선 제외
    )
    return matrix


def top_correlations(
    df: pd.DataFrame,
    target_col: str,
    n: int = 10,
    method: str = "spearman",
) -> pd.DataFrame:
    """
    target_col과 가장 상관관계 높은 n개 컬럼 반환.

    Args:
        df        : 입력 DataFrame
        target_col: 기준 컬럼명
        n         : 반환할 상위 컬럼 수 (기본 10)
        method    : 상관계수 방식 ('spearman' | 'pearson')

    Returns:
        DataFrame with columns [column, correlation, abs_corr]
        정렬: abs_corr 내림차순
    """
    empty_result = pd.DataFrame(columns=["column", "correlation", "abs_corr"])

    if df.empty:
        log.warning("top_correlations: 빈 DataFrame 입력 — 빈 결과 반환")
        return empty_result

    if target_col not in df.columns:
        log.warning("top_correlations: target_col=%r 이 DataFrame에 없음", target_col)
        return empty_result

    corr_matrix = correlation_matrix(df, method=method)

    if corr_matrix.empty or target_col not in corr_matrix.index:
        return empty_result

    target_corrs = corr_matrix[target_col].drop(index=target_col, errors="ignore")
    target_corrs = target_corrs.dropna()

    if target_corrs.empty:
        log.warning("top_correlations: %r 와 유효한 상관관계 없음", target_col)
        return empty_result

    result = pd.DataFrame({
        "column": target_corrs.index,
        "correlation": target_corrs.values,
        "abs_corr": target_corrs.abs().values,
    })

    result = result.sort_values("abs_corr", ascending=False).head(n).reset_index(drop=True)

    log.info(
        "top_correlations: target=%r, method=%s, 반환 %d개",
        target_col,
        method,
        len(result),
    )
    return result
