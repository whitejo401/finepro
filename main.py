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
                 "d1", "d2", "d3", "d4", "d5", "d6",
                 "w2", "w3", "w4", "w5", "w6",
                 "m1", "m3", "m5", "m6"],
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
        tickers = ["us_sp500", "us_nasdaq", "cmd_wti", "cmd_gold",
                   "fx_krw_usd", "alt_vix", "rate_us10y",
                   "us_sect_tech", "us_sect_energy", "us_sect_fin",
                   "us_sect_health", "us_sect_indus"]
        # kr_kospi는 2단계에서 OHLCV 전체 수집하므로 여기서 제외
        df_market = get_prices(tickers, start=start, end=end, use_cache=use_cache)
        if not df_market.empty:
            frames.append(df_market)
            log.info("market: %d rows x %d cols", *df_market.shape)
    except Exception as e:
        log.warning("market collector failed: %s", e)

    # ── 2. 국내 주식 (yfinance KOSPI OHLCV + pykrx fallback) ─────────────────
    try:
        from collectors.global_.market import get_price
        df_kospi_ohlcv = get_price("kr_kospi", start=start, end=end, use_cache=use_cache)
        if not df_kospi_ohlcv.empty:
            frames.append(df_kospi_ohlcv)
            log.info("kr kospi ohlcv (yf): %d rows x %d cols", *df_kospi_ohlcv.shape)
    except Exception as e:
        log.warning("kr kospi ohlcv collector failed: %s", e)

    # ── 2-b. 국내 수급 (pykrx 외인·기관 순매수) ─────────────────────────────
    try:
        from collectors.kr.stock import get_market_net_buying
        df_net = get_market_net_buying("KOSPI", start=start, end=end, use_cache=use_cache)
        if not df_net.empty:
            frames.append(df_net)
            log.info("kr market net buying: %d rows x %d cols", *df_net.shape)
    except Exception as e:
        log.warning("kr market net buying collector failed: %s", e)

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

    # ── 7. 고래 온체인 (Whale Alert + Glassnode) ────────────────────────────
    try:
        from collectors.global_.whale import get_whale_dataset
        df_whale = get_whale_dataset(start=start, end=end, use_cache=use_cache)
        if not df_whale.empty:
            frames.append(df_whale)
            log.info("whale data: %d rows x %d cols", *df_whale.shape)
    except Exception as e:
        log.warning("whale collector failed: %s", e)

    # ── 8. 비트코인 ETF (yfinance) ─────────────────────────────────────────
    try:
        from collectors.global_.institutions import get_bitcoin_etf_data
        df_etf = get_bitcoin_etf_data(start=start, end=end, use_cache=use_cache)
        if not df_etf.empty:
            frames.append(df_etf)
            log.info("btc etf: %d rows x %d cols", *df_etf.shape)
    except Exception as e:
        log.warning("btc etf collector failed: %s", e)

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
        "d4": ("build_d4_report",      "KOSPI 예측"),
        "d5": ("build_d5_report",      "미국→KOSPI 선행"),
        "d6": ("build_d6_report",      "고래·기관 스냅샷"),
        "w2": ("build_weekly_report",  "주간 국면"),
        "w3": ("build_w3_report",      "크립토 상관"),
        "w4": ("build_w4_report",      "KOSPI 3각"),
        "w5": ("build_w5_report",      "예측 적중률"),
        "w6": ("build_w6_report",      "기관 포트폴리오"),
        "m1": ("build_report",         "월간 종합"),
        "m3": ("build_m3_report",      "경기 사이클"),
        "m5": ("build_m5_report",      "국면별 자산 성과"),
        "m6": ("build_m6_report",      "공포-탐욕 지수"),
    }

    # mode 별 실행 대상 결정
    if mode == "all":
        targets = list(_REPORT_MAP.keys())
    elif mode == "daily":
        targets = ["d1", "d2", "d3", "d4", "d5", "d6"]
    elif mode == "weekly":
        targets = ["w2", "w3", "w4", "w5", "w6"]
    elif mode == "monthly":
        targets = ["m1", "m3", "m5", "m6"]
    else:
        targets = [mode]

    # 기관 데이터 (d6, w6에서 사용 — 한 번만 수집)
    btc_companies_df = None
    sec_13f_df = None
    if any(t in targets for t in ["d6", "w6"]):
        try:
            from collectors.global_.institutions import get_public_company_holdings, get_sec_13f_crypto
            btc_companies_df = get_public_company_holdings("bitcoin", use_cache=use_cache)
            sec_13f_df = get_sec_13f_crypto(use_cache=use_cache)
        except Exception as e:
            log.warning("institution data failed: %s", e)

    import visualization.report as _rpt
    for key in targets:
        func_name, label = _REPORT_MAP[key]
        try:
            func = getattr(_rpt, func_name)
            # d6, w6은 추가 인자 전달
            if key == "d6":
                path = func(master, btc_companies_df=btc_companies_df)
            elif key == "w6":
                path = func(master, btc_companies_df=btc_companies_df, sec_13f_df=sec_13f_df)
            else:
                path = func(master)
            log.info("%s 리포트: %s", label, path)
            generated.append(path)
        except Exception as e:
            log.error("%s report failed: %s", label, e)

    for p in generated:
        print(f"Report: {p}")


if __name__ == "__main__":
    main()
