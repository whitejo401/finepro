"""invest/stock — 국내 주식 스냅샷·종목 상세·공모주 엔드포인트."""
import os
import logging
import time
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger(__name__)

TTL_SNAPSHOT = 60 * 5      # 5분
TTL_TICKER   = 60 * 10     # 10분
TTL_IPO      = 60 * 60     # 1시간

INDEX_CODE = {"KOSPI": "1001", "KOSDAQ": "2001"}


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _prev_business_day(date_str: str) -> str:
    """주말이면 금요일, 그 외엔 하루 전 영업일 반환."""
    dt = datetime.strptime(date_str, "%Y%m%d")
    delta = 1
    if dt.weekday() == 0:   # 월요일
        delta = 3
    elif dt.weekday() == 6: # 일요일
        delta = 2
    return (dt - timedelta(days=delta)).strftime("%Y%m%d")


def _get_ohlcv_by_ticker(date: str, market: str):
    """pykrx 전체 종목 OHLCV, 빈 결과면 전일 재시도."""
    from pykrx import stock as krx
    df = krx.get_market_ohlcv_by_ticker(date, market=market)
    if df is None or df.empty:
        prev = _prev_business_day(date)
        log.info("retry with prev business day: %s → %s", date, prev)
        df = krx.get_market_ohlcv_by_ticker(prev, market=market)
    return df


def _get_index_ohlcv(fromdate: str, todate: str, index_code: str):
    from pykrx import stock as krx
    df = krx.get_index_ohlcv_by_date(fromdate, todate, index_code)
    return df


@router.get("/snapshot")
def stock_snapshot(
    market: str = Query("KOSPI", description="시장 (KOSPI | KOSDAQ)"),
):
    """전체 종목 OHLCV 스냅샷 + 지수 현황 + 상승/하락/보합 + 상한가/하한가 종목."""
    market = market.upper()
    if market not in INDEX_CODE:
        raise HTTPException(status_code=400, detail="market은 KOSPI 또는 KOSDAQ")

    key = f"invest:stock:snapshot:{market}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from pykrx import stock as krx

        today = _today()
        df = _get_ohlcv_by_ticker(today, market)
        if df is None or df.empty:
            raise HTTPException(status_code=502, detail="pykrx 종목 데이터 없음")

        # 실제 조회 날짜 (재시도했을 수 있으므로 df 기반이 아닌 today 우선)
        snapshot_date = today

        # 지수 — 최근 2거래일 가져와서 전일 대비 계산
        idx_code = INDEX_CODE[market]
        fromdate = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        idx_df = _get_index_ohlcv(fromdate, today, idx_code)

        index_info = {}
        if idx_df is not None and len(idx_df) >= 2:
            latest = idx_df.iloc[-1]
            prev   = idx_df.iloc[-2]
            close_val  = float(latest.get("종가", latest.iloc[3]) if "종가" in idx_df.columns else latest.iloc[3])
            prev_val   = float(prev.get("종가",   prev.iloc[3])   if "종가" in idx_df.columns else prev.iloc[3])
            change_pct = round((close_val - prev_val) / prev_val * 100, 2) if prev_val else 0.0
            index_info = {"value": close_val, "change_pct": change_pct}
        elif idx_df is not None and len(idx_df) == 1:
            close_val = float(idx_df.iloc[-1].get("종가", idx_df.iloc[-1].iloc[3]))
            index_info = {"value": close_val, "change_pct": 0.0}

        # 등락률 컬럼 탐색
        chg_col = next((c for c in df.columns if "등락률" in str(c)), None)
        vol_col = next((c for c in df.columns if "거래량" in str(c)), None)
        cls_col = next((c for c in df.columns if "종가" in str(c)), None)
        name_col = None

        # 종목명 매핑 시도
        try:
            name_map = {t: krx.get_market_ticker_name(t) for t in df.index[:200]}
        except Exception:
            name_map = {}

        advance   = 0
        decline   = 0
        unchanged = 0
        rows = []

        for ticker, row in df.iterrows():
            chg = float(row[chg_col]) if chg_col else 0.0
            vol = int(row[vol_col])   if vol_col else 0
            cls = float(row[cls_col]) if cls_col else 0.0
            name = name_map.get(str(ticker), str(ticker))

            if chg > 0:
                advance += 1
            elif chg < 0:
                decline += 1
            else:
                unchanged += 1

            rows.append({"ticker": str(ticker), "name": name, "price": cls,
                         "change_pct": round(chg, 2), "volume": vol})

        rows_sorted = sorted(rows, key=lambda x: x["change_pct"], reverse=True)
        top_gainers = [{"ticker": r["ticker"], "name": r["name"],
                        "change_pct": r["change_pct"]} for r in rows_sorted[:5]]
        top_losers  = [{"ticker": r["ticker"], "name": r["name"],
                        "change_pct": r["change_pct"]} for r in rows_sorted[-5:][::-1]]

        data = {
            "market": market,
            "date": snapshot_date,
            "index": index_info,
            "advance": advance,
            "decline": decline,
            "unchanged": unchanged,
            "top_gainers": top_gainers,
            "top_losers":  top_losers,
        }
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        log.warning("[invest:stock:snapshot] %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_SNAPSHOT)
    return resp


@router.get("/ipo")
def stock_ipo():
    """최근 60일 공모주 공시 목록 (DART 증권신고서 pblntf_ty=B)."""
    key = "invest:stock:ipo"
    cached = cache.get(key)
    if cached:
        return cached

    dart_key = os.getenv("DART_API_KEY")
    if not dart_key:
        raise HTTPException(status_code=503, detail="DART_API_KEY 미설정")

    today  = datetime.now().strftime("%Y%m%d")
    bgn_de = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key":  dart_key,
        "pblntf_ty":  "B",
        "bgn_de":     bgn_de,
        "end_de":     today,
        "page_count": 20,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        body = r.json()
        items = []
        for item in body.get("list", []):
            items.append({
                "title":    item.get("report_nm", ""),
                "date":     item.get("rcept_dt", ""),
                "company":  item.get("corp_name", ""),
                "rcept_no": item.get("rcept_no", ""),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no', '')}",
            })
        resp = ok({"count": len(items), "items": items})
    except HTTPException:
        raise
    except Exception as e:
        log.warning("[invest:stock:ipo] %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(key, resp, TTL_IPO)
    return resp


@router.get("/{ticker}")
def stock_detail(
    ticker: str = Path(..., description="6자리 종목코드 (예: 005930)"),
):
    """종목 상세: 주가·PER·PBR·외인수급 + 최신 DART 공시 3건."""
    key = f"invest:stock:detail:{ticker}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from pykrx import stock as krx

        today    = _today()
        fromdate = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        # OHLCV
        ohlcv_df = krx.get_market_ohlcv(fromdate, today, ticker)
        if ohlcv_df is None or ohlcv_df.empty:
            raise HTTPException(status_code=404, detail=f"종목 {ticker} 데이터 없음")

        latest_ohlcv = ohlcv_df.iloc[-1]
        price = float(latest_ohlcv.get("종가", latest_ohlcv.iloc[3]))
        prev_price = float(ohlcv_df.iloc[-2].get("종가", ohlcv_df.iloc[-2].iloc[3])) if len(ohlcv_df) >= 2 else price
        change_pct = round((price - prev_price) / prev_price * 100, 2) if prev_price else 0.0

        # 종목명
        try:
            name = krx.get_market_ticker_name(ticker)
        except Exception:
            name = ticker

        # PER/PBR
        time.sleep(0.5)
        fund_df = krx.get_market_fundamental(fromdate, today, ticker)
        per, pbr = None, None
        if fund_df is not None and not fund_df.empty:
            last_fund = fund_df.iloc[-1]
            per = float(last_fund.get("PER", last_fund.iloc[0])) if "PER" in fund_df.columns else None
            pbr = float(last_fund.get("PBR", last_fund.iloc[1])) if "PBR" in fund_df.columns else None

        # 외인/기관 수급 (최근 1거래일)
        time.sleep(0.5)
        foreign_net = None
        inst_net    = None
        try:
            inv_df = krx.get_market_trading_volume_by_investor(fromdate, today, ticker)
            if inv_df is not None and not inv_df.empty:
                last_inv = inv_df.iloc[-1]
                foreign_col = next((c for c in inv_df.columns if "외국인" in str(c)), None)
                inst_col    = next((c for c in inv_df.columns if "기관" in str(c)), None)
                if foreign_col:
                    foreign_net = int(last_inv[foreign_col])
                if inst_col:
                    inst_net = int(last_inv[inst_col])
        except Exception as e:
            log.warning("[invest:stock:detail] investor data failed for %s: %s", ticker, e)

    except HTTPException:
        raise
    except Exception as e:
        log.warning("[invest:stock:detail] pykrx error for %s: %s", ticker, e)
        raise HTTPException(status_code=500, detail=str(e))

    # DART 공시
    latest_disclosures = []
    dart_key = os.getenv("DART_API_KEY")
    if dart_key:
        try:
            bgn_de = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            end_de = _today()
            url = "https://opendart.fss.or.kr/api/list.json"
            params = {
                "crtfc_key":  dart_key,
                "corp_name":  name,
                "bgn_de":     bgn_de,
                "end_de":     end_de,
                "page_count": 3,
            }
            r = requests.get(url, params=params, timeout=8)
            if r.status_code == 200:
                for item in r.json().get("list", []):
                    latest_disclosures.append({
                        "title": item.get("report_nm", ""),
                        "date":  item.get("rcept_dt", ""),
                    })
        except Exception as e:
            log.warning("[invest:stock:detail] dart disclosure failed: %s", e)

    data = {
        "ticker":               ticker,
        "name":                 name,
        "price":                price,
        "change_pct":           change_pct,
        "per":                  per,
        "pbr":                  pbr,
        "foreign_net":          foreign_net,
        "institution_net":      inst_net,
        "latest_disclosures":   latest_disclosures,
    }
    resp = ok(data)
    cache.set(key, resp, TTL_TICKER)
    return resp
