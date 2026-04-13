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
                 "w1", "w2", "w3", "w4", "w5", "w6",
                 "m1", "m2", "m3", "m4", "m5", "m6"],
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

    # ── 3. 미국 거시 (FRED) ──────────────────────────────────────────────────
    try:
        from collectors.global_.macro import get_macro_dataset
        df_macro = get_macro_dataset(start=start, end=end, use_cache=use_cache)
        if not df_macro.empty:
            frames.append(df_macro)
            log.info("macro: %d rows x %d cols", *df_macro.shape)
    except Exception as e:
        log.warning("macro collector failed: %s", e)

    # ── 3-b. EIA (원유재고·생산량·천연가스) ──────────────────────────────────
    try:
        from collectors.global_.macro import get_eia_dataset
        df_eia = get_eia_dataset(start=start, end=end, use_cache=use_cache)
        if not df_eia.empty:
            frames.append(df_eia)
            log.info("eia: %d rows x %d cols", *df_eia.shape)
    except Exception as e:
        log.warning("eia collector failed: %s", e)

    # ── 3-c. World Bank (주요국 GDP·CPI·경상수지) ────────────────────────────
    try:
        from collectors.global_.macro import get_worldbank_dataset
        df_wb = get_worldbank_dataset(start=start, end=end, use_cache=use_cache)
        if not df_wb.empty:
            frames.append(df_wb)
            log.info("worldbank: %d rows x %d cols", *df_wb.shape)
    except Exception as e:
        log.warning("worldbank collector failed: %s", e)

    # ── 3-e. OECD 경기선행지수 (CLI) ────────────────────────────────────────
    try:
        from collectors.global_.macro import get_oecd_cli_dataset
        df_oecd = get_oecd_cli_dataset(start=start, end=end, use_cache=use_cache)
        if not df_oecd.empty:
            frames.append(df_oecd)
            log.info("oecd cli: %d rows x %d cols", *df_oecd.shape)
    except Exception as e:
        log.warning("oecd cli collector failed: %s", e)

    # ── 3-d. 국내 거시 (ECOS + 국토부 아파트) ───────────────────────────────
    try:
        from collectors.kr.macro import get_ecos_dataset
        df_ecos = get_ecos_dataset(start=start, end=end, use_cache=use_cache)
        if not df_ecos.empty:
            frames.append(df_ecos)
            log.info("ecos: %d rows x %d cols", *df_ecos.shape)
    except Exception as e:
        log.warning("ecos collector failed: %s", e)

    try:
        from collectors.kr.macro import get_molit_apt_price
        df_molit = get_molit_apt_price(start=start, end=end, use_cache=use_cache)
        if not df_molit.empty:
            frames.append(df_molit)
            log.info("molit apt: %d rows x %d cols", *df_molit.shape)
    except Exception as e:
        log.warning("molit collector failed: %s", e)

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

    # ── 5-b. 암호화폐 ccxt (Binance/Upbit 공개 OHLCV) ───────────────────────
    try:
        from collectors.global_.crypto import get_ccxt_dataset
        df_ccxt = get_ccxt_dataset(start=start, end=end, use_cache=use_cache)
        if not df_ccxt.empty:
            frames.append(df_ccxt)
            log.info("ccxt: %d rows x %d cols", *df_ccxt.shape)
    except Exception as e:
        log.warning("ccxt collector failed: %s", e)

    # ── 6. 뉴스 감성 (NewsAPI) ───────────────────────────────────────────────
    try:
        from collectors.global_.alt import get_news_sentiment
        df_news = get_news_sentiment(start=start, end=end, use_cache=use_cache)
        if not df_news.empty:
            frames.append(df_news)
            log.info("news sentiment: %d rows x %d cols", *df_news.shape)
    except Exception as e:
        log.warning("news sentiment collector failed: %s", e)

    # ── 6-b. Google Trends ───────────────────────────────────────────────────
    try:
        from collectors.global_.alt import get_trends_dataset
        df_trends = get_trends_dataset(start=start, end=end, use_cache=use_cache)
        if not df_trends.empty:
            frames.append(df_trends)
            log.info("google trends: %d rows x %d cols", *df_trends.shape)
    except Exception as e:
        log.warning("google trends collector failed: %s", e)

    # ── 6-c. GDELT 지정학 이벤트 ─────────────────────────────────────────────
    try:
        from collectors.global_.alt import get_gdelt_tone
        df_gdelt = get_gdelt_tone(start=start, end=end, use_cache=use_cache)
        if not df_gdelt.empty:
            frames.append(df_gdelt)
            log.info("gdelt: %d rows x %d cols", *df_gdelt.shape)
    except Exception as e:
        log.warning("gdelt collector failed: %s", e)

    # ── 6-d. EPU 경제정책 불확실성 지수 ─────────────────────────────────────
    try:
        from collectors.global_.alt import get_epu_index
        df_epu = get_epu_index(start=start, end=end, use_cache=use_cache)
        if not df_epu.empty:
            frames.append(df_epu)
            log.info("epu: %d rows x %d cols", *df_epu.shape)
    except Exception as e:
        log.warning("epu collector failed: %s", e)

    # ── 6-e. Reddit 커뮤니티 감성 (praw) ────────────────────────────────────
    try:
        from collectors.global_.alt import get_reddit_sentiment
        df_reddit = get_reddit_sentiment(start=start, end=end, use_cache=use_cache)
        if not df_reddit.empty:
            frames.append(df_reddit)
            log.info("reddit sentiment: %d rows x %d cols", *df_reddit.shape)
    except Exception as e:
        log.warning("reddit sentiment collector failed: %s", e)

    # ── 7. 고래 온체인 (Whale Alert + Glassnode) ────────────────────────────
    try:
        from collectors.global_.whale import get_whale_dataset
        df_whale = get_whale_dataset(start=start, end=end, use_cache=use_cache)
        if not df_whale.empty:
            frames.append(df_whale)
            log.info("whale data: %d rows x %d cols", *df_whale.shape)
    except Exception as e:
        log.warning("whale collector failed: %s", e)

    # ── 7-b. CFTC COT 선물 포지셔닝 ────────────────────────────────────────
    try:
        from collectors.global_.cftc import get_cftc_cot
        df_cot = get_cftc_cot(start=start, end=end, use_cache=use_cache)
        if not df_cot.empty:
            frames.append(df_cot)
            log.info("cftc cot: %d rows x %d cols", *df_cot.shape)
    except Exception as e:
        log.warning("cftc cot collector failed: %s", e)

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
        "w1": ("build_w1_report",      "자산 상관 주간 변화"),
        "w2": ("build_weekly_report",  "주간 국면"),
        "w3": ("build_w3_report",      "크립토 상관"),
        "w4": ("build_w4_report",      "KOSPI 3각"),
        "w5": ("build_w5_report",      "예측 적중률"),
        "w6": ("build_w6_report",      "기관 포트폴리오"),
        "m1": ("build_report",         "월간 종합"),
        "m2": ("build_m2_report",      "S-RIM 적정가"),
        "m3": ("build_m3_report",      "경기 사이클"),
        "m4": ("build_m4_report",      "백테스팅"),
        "m5": ("build_m5_report",      "국면별 자산 성과"),
        "m6": ("build_m6_report",      "공포-탐욕 지수"),
    }

    # mode 별 실행 대상 결정
    if mode == "all":
        targets = list(_REPORT_MAP.keys())
    elif mode == "daily":
        targets = ["d1", "d2", "d3", "d4", "d5", "d6"]
    elif mode == "weekly":
        targets = ["w1", "w2", "w3", "w4", "w5", "w6"]
    elif mode == "monthly":
        targets = ["m1", "m2", "m3", "m4", "m5", "m6"]
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
