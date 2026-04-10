"""
Global market data collector using yfinance.
Covers: equity indices, commodities, FX, VIX, bonds.
"""
import pandas as pd
import yfinance as yf

from collectors.base import get_logger, load_cache, save_cache

log = get_logger("global.market")

# Ticker reference
TICKERS = {
    # Equity indices
    "us_sp500":   "^GSPC",
    "us_nasdaq":  "^IXIC",
    "us_dow":     "^DJI",
    "us_russell": "^RUT",
    "eu_stoxx":   "^STOXX50E",
    "jp_nikkei":  "^N225",
    "cn_sse":     "000001.SS",
    "kr_kospi":   "^KS11",
    "kr_kosdaq":  "^KQ11",
    # Commodities
    "cmd_wti":    "CL=F",
    "cmd_brent":  "BZ=F",
    "cmd_gold":   "GC=F",
    "cmd_copper": "HG=F",
    "cmd_natgas": "NG=F",
    # FX (USD base)
    "fx_krw_usd": "KRW=X",
    "fx_dxy":     "DX=F",
    "fx_eur_usd": "EURUSD=X",
    "fx_jpy_usd": "JPY=X",
    "fx_cny_usd": "CNY=X",
    # Volatility & bonds
    "alt_vix":    "^VIX",
    "rate_us10y": "^TNX",
    "rate_us2y":  "^IRX",
}


def get_price(
    ticker_key: str,
    start: str,
    end: str = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Single ticker OHLCV.

    Args:
        ticker_key: key from TICKERS dict (e.g. 'us_sp500') or raw yfinance symbol
        start: 'YYYY-MM-DD'
        end:   'YYYY-MM-DD', defaults to today
    Returns:
        DataFrame with DatetimeIndex, columns: open, high, low, close, volume
        Column names prefixed with ticker_key.
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    symbol = TICKERS.get(ticker_key, ticker_key)
    cache_key = f"yf_{symbol}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch yfinance: %s (%s ~ %s)", symbol, start, end)
    raw = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)

    if raw.empty:
        log.warning("empty result for %s", symbol)
        return pd.DataFrame()

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = [f"{ticker_key}_open", f"{ticker_key}_high",
                  f"{ticker_key}_low",  f"{ticker_key}_close",
                  f"{ticker_key}_volume"]
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    save_cache(cache_key, df)
    return df


def get_prices(
    ticker_keys: list[str],
    start: str,
    end: str = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Multiple tickers merged into one DataFrame (close prices only).
    Column names: {ticker_key}_close
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    symbols = {k: TICKERS.get(k, k) for k in ticker_keys}
    cache_key = f"yf_multi_{'_'.join(sorted(ticker_keys))}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch yfinance multi: %d tickers", len(symbols))
    raw = yf.download(
        list(symbols.values()), start=start, end=end,
        progress=False, auto_adjust=True
    )

    if raw.empty:
        log.warning("empty result for multi-ticker download")
        return pd.DataFrame()

    close = raw["Close"].copy()
    # Rename columns: symbol -> ticker_key
    inv = {v: k for k, v in symbols.items()}
    close.columns = [f"{inv.get(c, c)}_close" for c in close.columns]
    close.index = pd.to_datetime(close.index)
    close.index.name = "date"

    save_cache(cache_key, close)
    return close
