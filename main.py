"""
Financial Data Pipeline - Entry Point
Usage: python main.py [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--no-cache]
"""
import argparse
from datetime import date

from collectors.base import get_logger
from config import DEFAULT_START

log = get_logger("main")


def parse_args():
    parser = argparse.ArgumentParser(description="Financial data pipeline")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=str(date.today()))
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--mode",
        choices=["daily", "weekly", "monthly", "all",
                 "d1", "d2", "d3", "w2", "w3", "w4", "m1", "m3"],
        default="all",
        help="생성할 리포트 종류",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    use_cache = not args.no_cache
    start, end = args.start, args.end

    log.info("Pipeline start: %s ~ %s, cache=%s", start, end, use_cache)

    import pandas as pd
    frames: list[pd.DataFrame] = []

    # ── 1. 글로벌 시장 (yfinance) ────────────────────────────────────────────
    try:
        from collectors.global_.market import get_prices
        tickers = ["us_sp500", "us_nasdaq", "kr_kospi", "cmd_wti", "cmd_gold",
                   "fx_krw_usd", "alt_vix", "rate_us10y"]
        df_market = get_prices(tickers, start=start, end=end, use_cache=use_cache)
        if not df_market.empty:
            frames.append(df_market)
            log.info("market: %d rows x %d cols", *df_market.shape)
    except Exception as e:
        log.warning("market collector failed: %s", e)

    # ── 2. 국내 주식 (pykrx) ────────────────────────────────────────────────
    try:
        from collectors.kr.stock import get_index_ohlcv
        df_kospi = get_index_ohlcv("1001", start=start, end=end, use_cache=use_cache)
        if not df_kospi.empty:
            frames.append(df_kospi)
            log.info("kr stock (KOSPI index): %d rows x %d cols", *df_kospi.shape)
    except Exception as e:
        log.warning("kr stock collector failed: %s", e)

    # ── 3. 미국 거시 (FRED + EIA) ────────────────────────────────────────────
    try:
        from collectors.global_.macro import get_macro_dataset
        df_macro = get_macro_dataset(start=start, end=end, use_cache=use_cache)
        if not df_macro.empty:
            frames.append(df_macro)
            log.info("macro: %d rows x %d cols", *df_macro.shape)
    except Exception as e:
        log.warning("macro collector failed: %s", e)

    # ── 4. 국내 재무 (DART) ─────────────────────────────────────────────────
    try:
        from collectors.kr.financials import get_key_ratios
        # 삼성전자 샘플
        df_dart = get_key_ratios("005930", start=start, end=end, use_cache=use_cache)
        if not df_dart.empty:
            frames.append(df_dart)
            log.info("dart (005930): %d rows x %d cols", *df_dart.shape)
    except Exception as e:
        log.warning("dart collector failed: %s", e)

    # ── 5. 암호화폐 (CoinGecko) ──────────────────────────────────────────────
    try:
        from collectors.global_.crypto import get_crypto_dataset
        df_crypto = get_crypto_dataset(start=start, end=end, use_cache=use_cache)
        if not df_crypto.empty:
            frames.append(df_crypto)
            log.info("crypto: %d rows x %d cols", *df_crypto.shape)
    except Exception as e:
        log.warning("crypto collector failed: %s", e)

    # ── 6. 뉴스 감성 (NewsAPI) ───────────────────────────────────────────────
    try:
        from collectors.global_.alt import get_news_sentiment
        df_news = get_news_sentiment(start=start, end=end, use_cache=use_cache)
        if not df_news.empty:
            frames.append(df_news)
            log.info("news sentiment: %d rows x %d cols", *df_news.shape)
    except Exception as e:
        log.warning("news sentiment collector failed: %s", e)

    if not frames:
        log.error("No data collected — check API keys and network.")
        return

    # ── 7. 병합 ─────────────────────────────────────────────────────────────
    try:
        from processors.merger import merge_dataframes
        master = merge_dataframes(frames)
        log.info("master: %d rows x %d cols", *master.shape)
    except Exception as e:
        log.error("merge failed: %s", e)
        return

    # ── 8. 리포트 생성 ───────────────────────────────────────────────────────
    mode = args.mode
    generated: list[str] = []

    _REPORT_MAP = {
        "d1": ("build_daily_report",   "일간 시황"),
        "d2": ("build_d2_report",      "연준·감성"),
        "d3": ("build_d3_report",      "암호화폐"),
        "w2": ("build_weekly_report",  "주간 국면"),
        "w3": ("build_w3_report",      "크립토 상관"),
        "w4": ("build_w4_report",      "KOSPI 3각"),
        "m1": ("build_report",         "월간 종합"),
        "m3": ("build_m3_report",      "경기 사이클"),
    }

    # mode 별 실행 대상 결정
    if mode == "all":
        targets = list(_REPORT_MAP.keys())
    elif mode == "daily":
        targets = ["d1", "d2", "d3"]
    elif mode == "weekly":
        targets = ["w2", "w3", "w4"]
    elif mode == "monthly":
        targets = ["m1", "m3"]
    else:
        targets = [mode]

    import visualization.report as _rpt
    for key in targets:
        func_name, label = _REPORT_MAP[key]
        try:
            func = getattr(_rpt, func_name)
            path = func(master)
            log.info("%s 리포트: %s", label, path)
            generated.append(path)
        except Exception as e:
            log.error("%s report failed: %s", label, e)

    for p in generated:
        print(f"Report: {p}")


if __name__ == "__main__":
    main()
