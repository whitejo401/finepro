"""
collectors/global_/trends.py
─────────────────────────────────────────────────────────────────────────────
Google Trends 기반 시장 감성 수집기 (pytrends).

키 불필요, 히스토리 수집 가능 (구글 서버 rate limit 주의 — 과호출 시 429).

수집 키워드 그룹:
  FEAR   : "stock market crash", "recession", "market crash", "sell stocks"
  GREED  : "buy stocks", "bull market", "stock rally", "all time high"
  KOSPI  : "코스피", "한국주식", "코스닥"
  CRYPTO : "bitcoin buy", "bitcoin crash"

출력 컬럼:
  trends_fear_us       : 미국 공포 검색량 지수 (0~100, 주간 → 일간 ffill)
  trends_greed_us      : 미국 탐욕 검색량 지수 (0~100)
  trends_fear_greed_us : (탐욕 - 공포) 순합산 (-100~100, 양수=탐욕)
  trends_kospi_kr      : 코스피 검색 관심도 (한국, 0~100)
  trends_crypto_btc    : BTC 관련 검색 지수 (글로벌)
"""
from __future__ import annotations

import time
from datetime import timedelta

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache

log = get_logger("collectors.trends")

# 키워드 그룹 정의 (pytrends는 한 번에 최대 5개)
_GROUPS: dict[str, dict] = {
    "fear_us": {
        "keywords": ["stock market crash", "recession", "market crash"],
        "geo": "US",
    },
    "greed_us": {
        "keywords": ["buy stocks", "bull market", "stock rally"],
        "geo": "US",
    },
    "kospi_kr": {
        "keywords": ["코스피", "한국주식", "코스닥"],
        "geo": "KR",
    },
    "crypto_btc": {
        "keywords": ["bitcoin buy", "bitcoin crash"],
        "geo": "",  # 글로벌
    },
}


def _fetch_group(
    keywords: list[str],
    timeframe: str,
    geo: str,
    retries: int = 3,
) -> pd.DataFrame:
    """단일 키워드 그룹 pytrends 수집."""
    from pytrends.request import TrendReq

    pt = TrendReq(hl="en-US", tz=0, timeout=(15, 30))

    for attempt in range(retries):
        try:
            pt.build_payload(keywords, timeframe=timeframe, geo=geo)
            df = pt.interest_over_time()
            if "isPartial" in df.columns:
                df = df[~df["isPartial"]][keywords]
            else:
                df = df[keywords]
            return df
        except Exception as e:
            wait = 30 * (attempt + 1)
            log.warning(
                "pytrends 수집 실패 (attempt %d/%d, geo=%r): %s — %ds 대기",
                attempt + 1, retries, geo, e, wait,
            )
            time.sleep(wait)

    return pd.DataFrame()


def _to_timeframe(start: str, end: str) -> str:
    """날짜 문자열 → pytrends timeframe 문자열."""
    # pytrends: 'YYYY-MM-DD YYYY-MM-DD' 형식
    return f"{start} {end}"


def _weekly_to_daily(df: pd.DataFrame) -> pd.DataFrame:
    """주간 데이터를 일간으로 forward-fill 확장."""
    if df.empty:
        return df
    # 마지막 날짜까지 일간 인덱스 생성 후 ffill
    daily_idx = pd.date_range(df.index.min(), df.index.max() + timedelta(days=6), freq="D")
    return df.reindex(daily_idx).ffill()


def get_trends_sentiment(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Google Trends 기반 시장 감성 수집.

    pytrends는 날짜 범위에 따라 일간/주간을 자동 선택:
      - 90일 이하 → 일간
      - 90일 초과 → 주간 (일간으로 ffill 변환)

    rate limit 주의: 그룹 사이 2초 대기.

    Returns:
        DatetimeIndex DataFrame (일별):
          trends_fear_us, trends_greed_us, trends_fear_greed_us,
          trends_kospi_kr, trends_crypto_btc
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")

    # 기간 90일 이하 → 일간, 초과 → 주간 구간 분할 없이 전체 수집 (주간 → ffill)
    cache_key = f"trends_{start[:7]}_{end[:7]}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    timeframe = _to_timeframe(start, end)
    frames: list[pd.DataFrame] = []

    for group_name, cfg in _GROUPS.items():
        log.info("pytrends 수집: %s (geo=%r)", group_name, cfg["geo"])
        df_raw = _fetch_group(cfg["keywords"], timeframe, cfg["geo"])
        if df_raw.empty:
            log.warning("pytrends %s: 데이터 없음", group_name)
            time.sleep(2)
            continue

        # 주간이면 일간으로 변환
        df_daily = _weekly_to_daily(df_raw)
        df_daily.index.name = "date"

        # 그룹별 평균 → 단일 컬럼
        col = f"trends_{group_name}"
        series = df_daily.mean(axis=1).rename(col).round(2)
        frames.append(series.to_frame())
        log.info("pytrends %s: %d행", group_name, len(series))
        time.sleep(2)  # rate limit 회피

    if not frames:
        log.warning("get_trends_sentiment: 수집된 데이터 없음")
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")

    # 공포-탐욕 순합산 컬럼
    if "trends_fear_us" in result.columns and "trends_greed_us" in result.columns:
        result["trends_fear_greed_us"] = (
            result["trends_greed_us"] - result["trends_fear_us"]
        ).round(2)

    # 날짜 범위 필터링
    result = result.sort_index()
    result = result.loc[start:end]

    log.info("get_trends_sentiment: %d행 × %d컬럼", *result.shape)

    if use_cache:
        save_cache(cache_key, result)

    return result
