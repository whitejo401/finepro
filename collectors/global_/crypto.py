"""
암호화폐 데이터 수집기 (CoinGecko Demo API).

수집 항목:
  - BTC/ETH 일별 종가 (USD)
  - 전체 암호화폐 시가총액
  - BTC 도미넌스 (%)

컬럼명 규칙: crypto_ 접두사
  crypto_btc_close, crypto_eth_close,
  crypto_total_mcap, crypto_btc_dominance

COINGECKO_API_KEY 없으면 빈 DataFrame 반환.
"""
from __future__ import annotations

import time

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache
from config import COINGECKO_API_KEY

log = get_logger("global.crypto")

# 수집 대상 코인: (컬럼 접미사, CoinGecko coin id)
_COINS = [
    ("btc", "bitcoin"),
    ("eth", "ethereum"),
]


def _get_cg_client():
    from pycoingecko import CoinGeckoAPI
    # Demo 키는 demo_api_key 파라미터로 전달해야 api.coingecko.com 엔드포인트 사용
    return CoinGeckoAPI(demo_api_key=COINGECKO_API_KEY)


def _fetch_coin_prices(
    cg,
    coin_id: str,
    start: str,
    end: str,
) -> pd.Series:
    """
    CoinGecko market_chart/range API로 일별 종가 조회.

    Returns:
        DatetimeIndex(UTC→date) Series, 이름 = crypto_{coin_id}_close
    """
    import datetime as dt

    start_ts = int(pd.Timestamp(start).timestamp())
    end_ts = int(pd.Timestamp(end).timestamp())

    try:
        data = cg.get_coin_market_chart_range_by_id(
            id=coin_id,
            vs_currency="usd",
            from_timestamp=start_ts,
            to_timestamp=end_ts,
        )
    except Exception as e:
        log.warning("CoinGecko price fetch 실패 (%s): %s", coin_id, e)
        return pd.Series(dtype=float)

    prices = data.get("prices", [])
    if not prices:
        log.warning("CoinGecko: %s 가격 데이터 없음", coin_id)
        return pd.Series(dtype=float)

    s = pd.Series(
        {pd.Timestamp(ts, unit="ms").tz_localize(None).normalize(): price for ts, price in prices},
        dtype=float,
    )
    s.index = pd.DatetimeIndex(s.index)
    # coin_id 앞 3글자 대신 호출부에서 suffix를 넘겨받도록 name은 호출 시 지정
    s.name = f"crypto_{coin_id}_close"
    return s


def _fetch_global_metrics(cg, start: str, end: str) -> pd.DataFrame:
    """
    BTC 도미넌스 및 전체 시총을 market_chart 방식으로 조회.

    CoinGecko Demo API는 global history 엔드포인트를 지원하지 않으므로
    bitcoin dominance는 별도 global_data 스냅샷(오늘 값)으로 대체하고,
    전체 시총은 'total_market_cap' 카테고리 코인으로 근사한다.

    실용적 대안: BTC 시총 / (BTC + ETH 시총) 비율을 도미넌스 근사값으로 사용.
    실제 도미넌스는 오늘 스냅샷만 수집하여 마지막 날짜에 기록.

    Returns:
        DataFrame with columns: crypto_total_mcap, crypto_btc_dominance
    """
    start_ts = int(pd.Timestamp(start).timestamp())
    end_ts = int(pd.Timestamp(end).timestamp())

    frames = {}

    # BTC 시총 이력
    try:
        btc_data = cg.get_coin_market_chart_range_by_id(
            id="bitcoin", vs_currency="usd",
            from_timestamp=start_ts, to_timestamp=end_ts,
        )
        btc_mcap = {
            pd.Timestamp(ts, unit="ms").tz_localize(None).normalize(): v
            for ts, v in btc_data.get("market_caps", [])
        }
        frames["btc_mcap"] = pd.Series(btc_mcap, dtype=float)
        time.sleep(1.2)  # Demo API rate limit
    except Exception as e:
        log.warning("CoinGecko BTC 시총 조회 실패: %s", e)
        return pd.DataFrame()

    # ETH 시총 이력
    try:
        eth_data = cg.get_coin_market_chart_range_by_id(
            id="ethereum", vs_currency="usd",
            from_timestamp=start_ts, to_timestamp=end_ts,
        )
        eth_mcap = {
            pd.Timestamp(ts, unit="ms").tz_localize(None).normalize(): v
            for ts, v in eth_data.get("market_caps", [])
        }
        frames["eth_mcap"] = pd.Series(eth_mcap, dtype=float)
    except Exception as e:
        log.warning("CoinGecko ETH 시총 조회 실패: %s", e)
        frames["eth_mcap"] = pd.Series(dtype=float)

    btc_s = frames["btc_mcap"]
    eth_s = frames.get("eth_mcap", pd.Series(dtype=float))

    df = pd.DataFrame(index=btc_s.index)
    df.index = pd.DatetimeIndex(df.index)

    # 전체 시총: BTC + ETH (근사, Demo API 제한)
    combined = btc_s.add(eth_s.reindex(btc_s.index), fill_value=0)
    df["crypto_total_mcap"] = combined

    # BTC 도미넌스 근사 (BTC / (BTC+ETH))
    df["crypto_btc_dominance"] = (btc_s / combined.replace(0, float("nan"))) * 100

    df.index.name = "date"
    return df


def get_crypto_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    암호화폐 데이터셋 수집 (BTC/ETH 종가, 시총, BTC 도미넌스).

    Args:
        start    : 수집 시작일 'YYYY-MM-DD'
        end      : 수집 종료일 'YYYY-MM-DD', 기본값 오늘
        use_cache: True면 캐시 우선 사용
    Returns:
        DatetimeIndex DataFrame, 컬럼:
          crypto_btc_close, crypto_eth_close,
          crypto_total_mcap, crypto_btc_dominance
        API 키 없거나 실패 시 빈 DataFrame
    """
    if not COINGECKO_API_KEY:
        log.warning("COINGECKO_API_KEY 없음 — 빈 DataFrame 반환")
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"crypto_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("캐시 히트: %s", cache_key)
            return cached

    # Demo API 제한: 최근 365일만 조회 가능
    cutoff = (pd.Timestamp.today() - pd.Timedelta(days=364)).strftime("%Y-%m-%d")
    effective_start = max(start, cutoff)
    if effective_start != start:
        log.info(
            "CoinGecko Demo 제한: start=%s → %s (최근 365일)",
            start, effective_start,
        )

    log.info("CoinGecko 수집 시작: %s ~ %s", effective_start, end)

    try:
        cg = _get_cg_client()
    except ImportError:
        log.warning("pycoingecko 패키지 없음 — pip install pycoingecko")
        return pd.DataFrame()

    frames: list[pd.Series] = []

    # 코인별 종가
    for suffix, coin_id in _COINS:
        s = _fetch_coin_prices(cg, coin_id, effective_start, end)
        if not s.empty:
            s.name = f"crypto_{suffix}_close"
            frames.append(s)
        time.sleep(1.2)  # Demo API rate limit (30 req/min)

    # 시총 + 도미넌스
    df_global = _fetch_global_metrics(cg, effective_start, end)

    if not frames and df_global.empty:
        log.warning("CoinGecko: 수집된 데이터 없음")
        return pd.DataFrame()

    # 병합
    if frames:
        df_prices = pd.concat(frames, axis=1)
        df_prices.index = pd.DatetimeIndex(df_prices.index)
        df_prices.index.name = "date"
    else:
        df_prices = pd.DataFrame()

    if not df_prices.empty and not df_global.empty:
        df = df_prices.join(df_global, how="outer")
    elif not df_prices.empty:
        df = df_prices
    else:
        df = df_global

    df.sort_index(inplace=True)
    df = df.loc[effective_start:end]

    if df.empty:
        log.warning("CoinGecko: %s ~ %s 범위 데이터 없음", start, end)
        return pd.DataFrame()

    log.info("CoinGecko 수집 완료: %d행 × %d컬럼", len(df), len(df.columns))

    if use_cache:
        save_cache(cache_key, df)

    return df
