"""
processors/cleaner.py

원시 DataFrame의 타입 정규화, 이상값 제거 등 데이터 정제 기능.
DatetimeIndex 강제 변환 → 숫자형 캐스팅 → 중복/미래 날짜 제거 →
Rolling Z-Score 기반 이상값 NaN 처리 순으로 동작한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import date

from collectors.base import get_logger

logger = get_logger(__name__)


def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    타입 정규화.

    - 인덱스를 pd.DatetimeIndex로 강제 변환 (변환 실패 행 제거)
    - 숫자형 컬럼을 float64로 변환 (변환 불가 → NaN)
    - 중복 인덱스 제거 (마지막 값 유지)
    - 미래 날짜(today 초과) 행 제거
    """
    if df.empty:
        return df.copy()

    result = df.copy()

    # 인덱스 → DatetimeIndex
    if not isinstance(result.index, pd.DatetimeIndex):
        original_len = len(result)
        result.index = pd.to_datetime(result.index, errors="coerce")
        result = result[result.index.notna()]
        dropped = original_len - len(result)
        if dropped:
            logger.warning("normalize_types: 인덱스 변환 실패로 %d행 제거", dropped)

    # 숫자형 캐스팅
    for col in result.columns:
        if not pd.api.types.is_numeric_dtype(result[col]):
            result[col] = pd.to_numeric(result[col], errors="coerce")
        result[col] = result[col].astype("float64")

    # 중복 인덱스 제거 (마지막 값 유지)
    dup_count = result.index.duplicated(keep="last").sum()
    if dup_count:
        logger.warning("normalize_types: 중복 인덱스 %d건 제거 (마지막 값 유지)", dup_count)
        result = result[~result.index.duplicated(keep="last")]

    # 미래 날짜 제거
    today = pd.Timestamp(date.today())
    future_mask = result.index > today
    future_count = future_mask.sum()
    if future_count:
        logger.warning("normalize_types: 미래 날짜 %d행 제거", future_count)
        result = result[~future_mask]

    return result


def remove_outliers(df: pd.DataFrame, threshold: float = 5.0) -> pd.DataFrame:
    """
    Rolling Z-Score 기준 이상값 NaN 처리.

    - window=252, min_periods=30
    - |z| > threshold 인 값을 NaN으로 대체
    - 컬럼별 개별 적용
    """
    if df.empty:
        return df.copy()

    result = df.copy()
    window = 252
    min_periods = 30
    outlier_total = 0

    for col in result.columns:
        series = result[col]
        if series.isna().all():
            continue

        roll_mean = series.rolling(window=window, min_periods=min_periods).mean()
        roll_std = series.rolling(window=window, min_periods=min_periods).std()

        # std=0이면 z-score 계산 불가 → 해당 위치는 NaN 처리하지 않음
        with np.errstate(divide="ignore", invalid="ignore"):
            z = np.where(roll_std == 0, 0.0, (series - roll_mean) / roll_std)

        outlier_mask = np.abs(z) > threshold
        outlier_count = int(outlier_mask.sum())
        if outlier_count:
            result.loc[result.index[outlier_mask], col] = np.nan
            outlier_total += outlier_count

    if outlier_total:
        logger.info("remove_outliers: threshold=%.1f, 총 %d개 이상값 NaN 처리", threshold, outlier_total)

    return result


def clean(df: pd.DataFrame, outlier_threshold: float = 5.0) -> pd.DataFrame:
    """
    메인 정제 함수.

    normalize_types → remove_outliers 순서로 실행.
    """
    if df.empty:
        return df.copy()

    logger.info("clean: 시작 (%d행 × %d컬럼)", len(df), len(df.columns))
    df = normalize_types(df)
    df = remove_outliers(df, threshold=outlier_threshold)
    logger.info("clean: 완료 (%d행 × %d컬럼)", len(df), len(df.columns))
    return df


def process(df: pd.DataFrame, **options) -> pd.DataFrame:
    """표준 프로세서 인터페이스. options: outlier_threshold(float)=5.0"""
    outlier_threshold = float(options.get("outlier_threshold", 5.0))
    return clean(df, outlier_threshold=outlier_threshold)
