"""
Korean stock market collector using pykrx.
Covers: OHLCV, PER/PBR/DIV, investor trading (foreign/institution), short selling.
"""
import pandas as pd
from pykrx import stock as krx

from collectors.base import get_logger, load_cache, save_cache

log = get_logger("kr.stock")

MARKETS = ("KOSPI", "KOSDAQ")


def _fmt(date_str: str) -> str:
    """'YYYY-MM-DD' -> 'YYYYMMDD' for pykrx."""
    return date_str.replace("-", "")


def get_ohlcv(
    ticker: str,
    start: str,
    end: str = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Single stock OHLCV.

    Args:
        ticker: 6-digit stock code (e.g. '005930')
        start:  'YYYY-MM-DD'
        end:    'YYYY-MM-DD', defaults to today
    Returns:
        DataFrame with DatetimeIndex, columns: kr_{ticker}_open/high/low/close/volume
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"krx_ohlcv_{ticker}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch pykrx ohlcv: %s (%s ~ %s)", ticker, start, end)
    try:
        raw = krx.get_market_ohlcv(_fmt(start), _fmt(end), ticker)
    except Exception as e:
        log.warning("pykrx ohlcv API error for %s: %s", ticker, e)
        return pd.DataFrame()

    if raw.empty:
        log.warning("empty result for %s", ticker)
        return pd.DataFrame()

    df = raw[["시가", "고가", "저가", "종가", "거래량"]].copy()
    df.columns = [
        f"kr_{ticker}_open", f"kr_{ticker}_high",
        f"kr_{ticker}_low",  f"kr_{ticker}_close",
        f"kr_{ticker}_volume",
    ]
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    save_cache(cache_key, df)
    return df


def get_fundamental(
    ticker: str,
    start: str,
    end: str = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    PER, PBR, DIV (배당수익률) for a single stock.
    Returns:
        DataFrame with columns: kr_fin_{ticker}_per, _pbr, _div
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"krx_fundamental_{ticker}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch pykrx fundamental: %s", ticker)
    try:
        raw = krx.get_market_fundamental(_fmt(start), _fmt(end), ticker)
    except Exception as e:
        log.warning("pykrx fundamental API error for %s: %s", ticker, e)
        return pd.DataFrame()

    if raw.empty:
        log.warning("empty fundamental for %s", ticker)
        return pd.DataFrame()

    df = raw[["PER", "PBR", "DIV"]].copy()
    df.columns = [f"kr_fin_{ticker}_per", f"kr_fin_{ticker}_pbr", f"kr_fin_{ticker}_div"]
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    save_cache(cache_key, df)
    return df


def get_investor_trading(
    ticker: str,
    start: str,
    end: str = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Foreign & institutional net buying volume.
    Returns:
        DataFrame with columns: kr_{ticker}_foreign_net, kr_{ticker}_inst_net
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"krx_investor_{ticker}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch pykrx investor: %s", ticker)
    try:
        raw = krx.get_market_trading_volume_by_investor(_fmt(start), _fmt(end), ticker)
    except Exception as e:
        log.warning("pykrx investor API error for %s: %s", ticker, e)
        return pd.DataFrame()

    if raw.empty:
        log.warning("empty investor data for %s", ticker)
        return pd.DataFrame()

    cols_needed = []
    for col in raw.columns:
        if "외국인" in str(col):
            cols_needed.append(col)
        elif "기관합계" in str(col) or "기관" in str(col):
            cols_needed.append(col)

    if len(cols_needed) < 2:
        log.warning("unexpected columns for investor data: %s", raw.columns.tolist())
        return pd.DataFrame()

    df = raw[cols_needed[:2]].copy()
    df.columns = [f"kr_{ticker}_foreign_net", f"kr_{ticker}_inst_net"]
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    save_cache(cache_key, df)
    return df


def get_market_net_buying(
    market: str = "KOSPI",
    start: str = None,
    end: str = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    KOSPI/KOSDAQ 시장 전체 투자자별 순매수금액.

    pykrx get_market_net_purchases_of_equities_by_investor 사용.

    Args:
        market: 'KOSPI' | 'KOSDAQ'
        start:  'YYYY-MM-DD'
        end:    'YYYY-MM-DD', defaults to today

    Returns:
        DataFrame with columns:
          kr_{market.lower()}_foreign_net : 외국인 순매수금액 (원)
          kr_{market.lower()}_inst_net    : 기관 순매수금액 (원)
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    mkt = market.lower()
    cache_key = f"krx_mktnet_{mkt}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch pykrx market net buying: %s (%s ~ %s)", market, start, end)

    # pykrx 1.2.7+: KRX_ID/KRX_PW 환경변수로 로그인 후 수급 데이터 수집 가능.
    # get_market_trading_value_by_date → 날짜별 × 투자자별(기관합계/외국인합계/개인) 순매수금액.
    try:
        raw = krx.get_market_trading_value_by_date(_fmt(start), _fmt(end), market)
    except Exception as e:
        log.warning(
            "pykrx market net buying 수집 실패 (%s): %s — KRX_ID/KRX_PW 환경변수 확인 필요",
            market, e,
        )
        return pd.DataFrame()

    if raw.empty:
        log.warning("empty market net buying for %s", market)
        return pd.DataFrame()

    # 컬럼: 기관합계 / 외국인합계 / 개인 / 기타법인 / 전체
    foreign_col = next((c for c in raw.columns if "외국인" in str(c)), None)
    inst_col    = next((c for c in raw.columns if "기관합계" in str(c)), None)

    if not foreign_col or not inst_col:
        log.warning("unexpected columns for market net buying %s: %s", market, raw.columns.tolist())
        return pd.DataFrame()

    df = raw[[foreign_col, inst_col]].copy()
    df.columns = [f"kr_{mkt}_foreign_net", f"kr_{mkt}_inst_net"]
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    save_cache(cache_key, df)
    return df


def get_index_ohlcv(
    index_ticker: str,
    start: str,
    end: str = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Index OHLCV. Common index_tickers: '1001'=KOSPI, '2001'=KOSDAQ.
    Returns:
        DataFrame with columns: kr_idx_{index_ticker}_open/high/low/close/volume
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"krx_idx_{index_ticker}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch pykrx index: %s", index_ticker)
    try:
        raw = krx.get_index_ohlcv(_fmt(start), _fmt(end), index_ticker)
    except Exception as e:
        log.warning("pykrx index API error for %s: %s", index_ticker, e)
        return pd.DataFrame()

    if raw.empty:
        log.warning("empty index data for %s", index_ticker)
        return pd.DataFrame()

    df = raw[["시가", "고가", "저가", "종가", "거래량"]].copy()
    prefix = f"kr_idx_{index_ticker}"
    df.columns = [f"{prefix}_open", f"{prefix}_high", f"{prefix}_low",
                  f"{prefix}_close", f"{prefix}_volume"]
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    save_cache(cache_key, df)
    return df
