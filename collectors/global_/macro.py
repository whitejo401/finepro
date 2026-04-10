"""
US/Global macroeconomic data collector using FRED (Federal Reserve Economic Data).
Fetches interest rates, inflation, growth, employment, and liquidity indicators
via fredapi. Each series is cached independently; get_macro_dataset merges them
into a single outer-joined DataFrame without forward-filling.
"""
from __future__ import annotations

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache
from config import FRED_API_KEY

log = get_logger("global.macro")

# FRED series reference
FRED_SERIES: dict[str, str] = {
    # 물가
    "macro_cpi":          "CPIAUCSL",      # 미국 CPI (월간)
    "macro_pce":          "PCEPI",         # PCE 물가지수 (월간)
    # 성장
    "macro_pmi_us":       "MANEMP",        # 제조업 고용 (PMI 대리변수)
    "macro_gdp_us":       "GDP",           # 미국 GDP (분기)
    "macro_unemployment": "UNRATE",        # 실업률 (월간)
    # 금리/신용
    "rate_fed":           "FEDFUNDS",      # 연방기금금리 (월간)
    "rate_us10y":         "DGS10",         # 10년 국채 (일간)
    "rate_us2y":          "DGS2",          # 2년 국채 (일간)
    "rate_spread_10_2":   "T10Y2Y",        # 장단기 스프레드 (일간)
    "rate_hy_spread":     "BAMLH0A0HYM2",  # 하이일드 스프레드 (일간)
    # 통화/유동성
    "macro_m2_us":        "M2SL",          # M2 통화량 (월간)
    # 주택/실물
    "macro_housing":      "HOUST",         # 주택착공건수 (월간)
}


def _get_fred_client():
    """fredapi Fred 인스턴스 반환. API 키 없으면 None 반환."""
    if not FRED_API_KEY:
        log.warning("FRED_API_KEY is not set — skipping FRED fetch")
        return None
    try:
        from fredapi import Fred
        return Fred(api_key=FRED_API_KEY)
    except ImportError:
        log.warning("fredapi is not installed — run: pip install fredapi")
        return None


def get_fred_series(
    series_key: str,
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    단일 FRED 시리즈 수집.

    Args:
        series_key: FRED_SERIES의 키 (예: 'macro_cpi') 또는 FRED 시리즈 ID 직접 입력
        start: 시작일 'YYYY-MM-DD'
        end:   종료일 'YYYY-MM-DD', 기본값은 오늘
        use_cache: 캐시 사용 여부

    Returns:
        DatetimeIndex, 컬럼명 = series_key 인 DataFrame.
        API 키 없거나 오류 발생 시 빈 DataFrame 반환.
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    fred_id = FRED_SERIES.get(series_key, series_key)
    cache_key = f"fred_{fred_id}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    fred = _get_fred_client()
    if fred is None:
        return pd.DataFrame()

    log.info("fetch FRED: %s (series_key=%s, %s ~ %s)", fred_id, series_key, start, end)
    try:
        raw: pd.Series = fred.get_series(fred_id, observation_start=start, observation_end=end)
    except Exception as e:
        log.warning("FRED fetch error for %s (%s): %s", series_key, fred_id, e)
        return pd.DataFrame()

    if raw.empty:
        log.warning("empty result for %s (%s)", series_key, fred_id)
        return pd.DataFrame()

    df = raw.to_frame(name=series_key)
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    if use_cache:
        save_cache(cache_key, df)

    return df


def get_macro_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
    series_keys: list[str] | None = None,
) -> pd.DataFrame:
    """
    여러 FRED 시리즈를 수집해 하나의 DataFrame으로 병합.

    Args:
        start:       시작일 'YYYY-MM-DD'
        end:         종료일 'YYYY-MM-DD', 기본값은 오늘
        use_cache:   캐시 사용 여부
        series_keys: 수집할 시리즈 키 목록. None이면 FRED_SERIES 전체

    Returns:
        outer join 병합된 DataFrame (Forward Fill 없음 — 상위 processor 책임).
        수집된 시리즈가 없으면 빈 DataFrame 반환.
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    keys = series_keys if series_keys is not None else list(FRED_SERIES.keys())

    sorted_keys = "_".join(sorted(keys))
    cache_key = f"fred_macro_{sorted_keys}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    frames: list[pd.DataFrame] = []
    for key in keys:
        try:
            df = get_fred_series(key, start=start, end=end, use_cache=use_cache)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            log.warning("unexpected error collecting %s: %s", key, e)

    if not frames:
        log.warning("no FRED series collected for keys=%s", keys)
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")

    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)

    log.info(
        "macro dataset ready: %d series, %d rows (%s ~ %s)",
        len(result.columns),
        len(result),
        result.index.min().date() if not result.empty else "N/A",
        result.index.max().date() if not result.empty else "N/A",
    )
    return result
