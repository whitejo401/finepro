"""
processors/normalizer.py

정제된 DataFrame의 결측값 보간 및 정규화 기능.
- forward_fill: 발표 주기 데이터(CPI, PMI 등)의 영업일 보간 (max_gap 제한)
- zscore_normalize: Rolling Z-Score 정규화
- align_to_daily: 서로 다른 주기 시리즈를 영업일 인덱스로 통일
- normalize: method 인자로 위 기능을 조합하는 메인 함수
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from collectors.base import get_logger

logger = get_logger(__name__)


def forward_fill(df: pd.DataFrame, max_gap: int = 5) -> pd.DataFrame:
    """
    Forward Fill (max_gap 제한).

    max_gap일을 초과하는 연속 NaN 구간은 채우지 않는다.
    발표 주기 데이터(CPI, PMI 등)처럼 의도적 공백이 있는 시리즈에 사용.

    Args:
        df: DatetimeIndex를 가진 DataFrame
        max_gap: 연속 NaN 허용 최대 일수. 초과 구간은 NaN 유지.
    """
    if df.empty:
        return df.copy()

    result = df.copy()

    for col in result.columns:
        series = result[col]
        if series.isna().all():
            continue

        # pandas limit 파라미터: 연속 NaN 최대 채움 수
        result[col] = series.ffill(limit=max_gap)

    logger.debug("forward_fill: max_gap=%d, %d컬럼 처리", max_gap, len(result.columns))
    return result


def zscore_normalize(df: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """
    Rolling Z-Score 정규화.

    - min_periods=60
    - 표준편차 0인 위치는 NaN (상수 구간 보호)

    Args:
        df: DatetimeIndex를 가진 DataFrame
        window: 롤링 윈도우 크기 (기본 252 영업일 = 약 1년)
    """
    if df.empty:
        return df.copy()

    min_periods = 60
    result = pd.DataFrame(index=df.index, columns=df.columns, dtype="float64")

    for col in df.columns:
        series = df[col]
        if series.isna().all():
            result[col] = np.nan
            continue

        roll_mean = series.rolling(window=window, min_periods=min_periods).mean()
        roll_std = series.rolling(window=window, min_periods=min_periods).std()

        # std=0인 위치는 NaN (상수 컬럼/구간 방지)
        z = (series - roll_mean) / roll_std.replace(0, np.nan)
        result[col] = z

    logger.debug("zscore_normalize: window=%d, min_periods=%d, %d컬럼 처리", window, min_periods, len(df.columns))
    return result


def align_to_daily(series_dict: dict[str, pd.Series], start: str, end: str) -> pd.DataFrame:
    """
    서로 다른 주기 시리즈를 영업일(B) 인덱스로 통일.

    각 시리즈는 영업일 인덱스에 reindex 후 ffill 적용.

    Args:
        series_dict: {컬럼명: pd.Series} 딕셔너리 (각 시리즈는 DatetimeIndex)
        start: 시작일 문자열 (예: "2015-01-01")
        end: 종료일 문자열 (예: "2024-12-31")

    Returns:
        영업일 DatetimeIndex를 가진 통합 DataFrame
    """
    if not series_dict:
        logger.warning("align_to_daily: 빈 series_dict 입력")
        return pd.DataFrame()

    bday_index = pd.bdate_range(start=start, end=end)
    frames: dict[str, pd.Series] = {}

    for name, series in series_dict.items():
        if not isinstance(series.index, pd.DatetimeIndex):
            series = series.copy()
            series.index = pd.to_datetime(series.index, errors="coerce")
            series = series[series.index.notna()]

        # 중복 인덱스 제거 (마지막 값 유지)
        series = series[~series.index.duplicated(keep="last")]

        aligned = series.reindex(bday_index).ffill()
        frames[name] = aligned

    result = pd.DataFrame(frames, index=bday_index)
    logger.info(
        "align_to_daily: %s ~ %s, %d영업일, %d시리즈 통합",
        start, end, len(bday_index), len(series_dict),
    )
    return result


def normalize(df: pd.DataFrame, method: str = "zscore", **kwargs) -> pd.DataFrame:
    """
    메인 정규화 함수.

    Args:
        df: DatetimeIndex를 가진 DataFrame
        method:
            'zscore' — Rolling Z-Score 정규화만 수행
            'ffill'  — Forward Fill만 수행
            'both'   — ffill → zscore 순서로 수행
        **kwargs:
            max_gap (int): forward_fill 파라미터 (기본 5)
            window  (int): zscore_normalize 파라미터 (기본 252)
    """
    if df.empty:
        return df.copy()

    max_gap = int(kwargs.get("max_gap", 5))
    window = int(kwargs.get("window", 252))

    valid_methods = {"zscore", "ffill", "both"}
    if method not in valid_methods:
        raise ValueError(f"normalize: method는 {valid_methods} 중 하나여야 합니다. 입력값: {method!r}")

    logger.info("normalize: method=%s, %d행 × %d컬럼", method, len(df), len(df.columns))

    if method == "ffill":
        return forward_fill(df, max_gap=max_gap)

    if method == "zscore":
        return zscore_normalize(df, window=window)

    # both: ffill → zscore
    df = forward_fill(df, max_gap=max_gap)
    df = zscore_normalize(df, window=window)
    return df


def process(df: pd.DataFrame, **options) -> pd.DataFrame:
    """표준 프로세서 인터페이스. options: method(str)='zscore', max_gap(int)=5, window(int)=252"""
    method = str(options.get("method", "zscore"))
    return normalize(df, method=method, **options)
