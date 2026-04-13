"""
collectors/global_/sentiment_alt.py
─────────────────────────────────────
Reddit 대체 감성 수집기.

데이터 소스 (모두 무료, API 키 불필요):
  1. Alternative.me Fear & Greed Index
       - BTC 시장 심리를 Volatility·Momentum·Social·Dominance·Trends로 합산
       - 0(극도공포) ~ 100(극도탐욕), 2018-02-01 ~ 현재 (일별)
  2. Binance Futures Funding Rate
       - BTC/ETH 무기한 선물 펀딩비율 (8시간 주기)
       - 양수 → 롱 우세(강세 레버리지), 음수 → 숏 우세(약세 레버리지)

출력 컬럼 (master 병합용):
  sent_fear_greed           : Alternative.me F&G (0~100)
  sent_fear_greed_class     : 분류 문자열 (Extreme Fear ~ Extreme Greed)
  deriv_btc_funding_rate    : BTC 일평균 펀딩비율 (%)
  deriv_eth_funding_rate    : ETH 일평균 펀딩비율 (%)
  deriv_btc_funding_cum7d   : BTC 7일 누적 펀딩비율 (레버리지 방향 누적)
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests

from collectors.base import get_logger, load_cache, save_cache

log = get_logger("collectors.sentiment_alt")

_FNG_URL      = "https://api.alternative.me/fng/"
_BINANCE_BASE = "https://fapi.binance.com/fapi/v1/fundingRate"


# ──────────────────────────────────────────────────────────────────────────────
# Alternative.me Fear & Greed Index
# ──────────────────────────────────────────────────────────────────────────────

def get_fear_greed_index(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Alternative.me 공포탐욕지수 수집.

    limit=0 → 전체 히스토리 (2018-02-01~), 일별.
    키 불필요.

    Returns:
        DatetimeIndex DataFrame:
          sent_fear_greed (float 0~100), sent_fear_greed_class (str)
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"fng_{start[:7]}_{end[:7]}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch Alternative.me F&G: %s ~ %s", start, end)
    try:
        resp = requests.get(
            _FNG_URL,
            params={"limit": 0, "format": "json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        log.warning("Alternative.me F&G 수집 실패: %s", e)
        return pd.DataFrame()

    rows = []
    for item in data:
        try:
            ts  = pd.Timestamp(int(item["timestamp"]), unit="s").normalize()
            val = float(item["value"])
            cls = item.get("value_classification", "")
            rows.append({"date": ts, "sent_fear_greed": val, "sent_fear_greed_class": cls})
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("date")
    df.index.name = "date"
    df.sort_index(inplace=True)
    df = df.loc[start:end]

    log.info("Alternative.me F&G: %d행 (%s ~ %s)", len(df), start, end)
    if use_cache:
        save_cache(cache_key, df)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Binance Futures Funding Rate
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_binance_funding(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    """Binance 펀딩비율 페이지 수집 (limit=1000, 반복)."""
    rows: list[dict] = []
    cur_start = start_ms
    while True:
        try:
            resp = requests.get(
                _BINANCE_BASE,
                params={
                    "symbol":    symbol,
                    "startTime": cur_start,
                    "endTime":   end_ms,
                    "limit":     1000,
                },
                timeout=20,
            )
            resp.raise_for_status()
            batch = resp.json()
        except Exception as e:
            log.warning("Binance funding [%s]: %s", symbol, e)
            break

        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        cur_start = int(batch[-1]["fundingTime"]) + 1

    return rows


def get_binance_funding_rate(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Binance 무기한 선물 BTC/ETH 펀딩비율 수집.

    8시간 주기 → 일별 평균·누적으로 집계.
    키 불필요.

    Returns:
        DatetimeIndex DataFrame:
          deriv_btc_funding_rate    : BTC 일평균 펀딩비율 (%)
          deriv_eth_funding_rate    : ETH 일평균 펀딩비율 (%)
          deriv_btc_funding_cum7d   : BTC 7일 누적 펀딩비율
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"binance_funding_{start[:7]}_{end[:7]}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    start_ms = int(pd.Timestamp(start).timestamp() * 1000)
    end_ms   = int(pd.Timestamp(end).timestamp() * 1000)

    frames: list[pd.DataFrame] = []
    for symbol, col_name in [("BTCUSDT", "deriv_btc_funding_rate"),
                              ("ETHUSDT", "deriv_eth_funding_rate")]:
        log.info("fetch Binance funding: %s (%s ~ %s)", symbol, start, end)
        rows = _fetch_binance_funding(symbol, start_ms, end_ms)
        if not rows:
            continue

        sub = pd.DataFrame(rows)
        sub["date"] = pd.to_datetime(sub["fundingTime"], unit="ms").dt.normalize()
        sub["rate"] = sub["fundingRate"].astype(float) * 100  # % 환산
        daily = sub.groupby("date")["rate"].mean().rename(col_name)
        daily.index.name = "date"
        frames.append(daily.to_frame())
        log.info("Binance funding %s: %d행", symbol, len(daily))

    if not frames:
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")

    # BTC 7일 누적 펀딩비율
    if "deriv_btc_funding_rate" in result.columns:
        result["deriv_btc_funding_cum7d"] = (
            result["deriv_btc_funding_rate"]
            .rolling(7, min_periods=1)
            .sum()
            .round(6)
        )

    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 통합 수집 함수
# ──────────────────────────────────────────────────────────────────────────────

def get_sentiment_alt_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Alternative.me F&G + Binance Funding Rate 통합 수집.

    Returns:
        DatetimeIndex DataFrame (일별):
          sent_fear_greed, sent_fear_greed_class,
          deriv_btc_funding_rate, deriv_eth_funding_rate,
          deriv_btc_funding_cum7d
    """
    frames: list[pd.DataFrame] = []

    df_fng = get_fear_greed_index(start, end, use_cache=use_cache)
    if not df_fng.empty:
        frames.append(df_fng)

    df_fund = get_binance_funding_rate(start, end, use_cache=use_cache)
    if not df_fund.empty:
        frames.append(df_fund)

    if not frames:
        log.warning("get_sentiment_alt_dataset: 수집된 데이터 없음")
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")
    result.sort_index(inplace=True)

    log.info("sentiment_alt: %d행 × %d컬럼", *result.shape)
    return result
