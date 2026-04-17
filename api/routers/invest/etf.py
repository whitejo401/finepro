"""invest/etf — ETF 목록·상세·배당·비교 엔드포인트."""
import logging
import re
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger(__name__)

TTL_LIST    = 60 * 10    # 10분
TTL_DETAIL  = 60 * 5     # 5분
TTL_DIV     = 60 * 60    # 1시간
TTL_COMPARE = 60 * 10    # 10분

CATEGORY_PATTERNS = {
    "국내주식": re.compile(r"200|코스피|대형|KOSPI200|KRX"),
    "해외주식": re.compile(r"미국|S&P|나스닥|중국|일본|NASDAQ|S&P500|미국S&P"),
    "채권":     re.compile(r"국채|회사채|채권|Bond"),
    "배당":     re.compile(r"배당|고배당|DIV"),
}


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _prev_business_day(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y%m%d")
    delta = 3 if dt.weekday() == 0 else (2 if dt.weekday() == 6 else 1)
    return (dt - timedelta(days=delta)).strftime("%Y%m%d")


def _get_etf_data(date: str):
    """ETF OHLCV + 종목명 딕셔너리 반환. 빈 결과면 전일 재시도."""
    from pykrx import stock as krx
    ohlcv = krx.get_etf_ohlcv_by_ticker(date)
    if ohlcv is None or ohlcv.empty:
        date = _prev_business_day(date)
        ohlcv = krx.get_etf_ohlcv_by_ticker(date)

    time.sleep(0.5)
    name_map = {}
    if ohlcv is not None and not ohlcv.empty:
        for t in ohlcv.index:
            try:
                name_map[str(t)] = krx.get_etf_ticker_name(date, str(t))
            except Exception:
                name_map[str(t)] = str(t)
    return ohlcv, name_map, date


def _build_row(ticker: str, name: str, row) -> dict:
    cls = float(row.get("종가", row.iloc[3])) if "종가" in row.index else float(row.iloc[3])
    vol = int(row.get("거래량", row.iloc[4]))  if "거래량" in row.index else int(row.iloc[4])
    chg = float(row.get("등락률", 0.0))        if "등락률" in row.index else 0.0
    return {"ticker": ticker, "name": name, "price": cls,
            "volume": vol, "change_pct": round(chg, 2)}


@router.get("")
def etf_list(
    category: str = Query(None, description="카테고리 필터: 국내주식|해외주식|채권|배당"),
    sort:     str = Query("volume", description="정렬 기준: volume | change_pct | price"),
):
    """전체 ETF 목록 (카테고리·정렬 옵션)."""
    key = f"invest:etf:list:{category}:{sort}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        today = _today()
        ohlcv, name_map, used_date = _get_etf_data(today)
        if ohlcv is None or ohlcv.empty:
            raise HTTPException(status_code=502, detail="pykrx ETF 데이터 없음")

        rows = []
        pattern = CATEGORY_PATTERNS.get(category) if category else None
        for ticker, row in ohlcv.iterrows():
            name = name_map.get(str(ticker), str(ticker))
            if pattern and not pattern.search(name):
                continue
            rows.append(_build_row(str(ticker), name, row))

        sort_key = sort if sort in ("change_pct", "price") else "volume"
        rows.sort(key=lambda x: x[sort_key], reverse=True)

        resp = ok({"date": used_date, "count": len(rows), "items": rows})
    except HTTPException:
        raise
    except Exception as e:
        log.warning("[invest:etf:list] %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_LIST)
    return resp


@router.get("/dividend")
def etf_dividend():
    """배당 ETF 목록 (이름에 '배당'|'DIV' 포함)."""
    key = "invest:etf:dividend"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        today = _today()
        ohlcv, name_map, used_date = _get_etf_data(today)
        if ohlcv is None or ohlcv.empty:
            raise HTTPException(status_code=502, detail="pykrx ETF 데이터 없음")

        pattern = CATEGORY_PATTERNS["배당"]
        rows = []
        for ticker, row in ohlcv.iterrows():
            name = name_map.get(str(ticker), str(ticker))
            if pattern.search(name):
                rows.append(_build_row(str(ticker), name, row))

        rows.sort(key=lambda x: x["volume"], reverse=True)
        resp = ok({"date": used_date, "count": len(rows), "items": rows})
    except HTTPException:
        raise
    except Exception as e:
        log.warning("[invest:etf:dividend] %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_DIV)
    return resp


@router.get("/compare")
def etf_compare(
    tickers: str = Query(..., description="쉼표 구분 티커 최대 5개 (예: 069500,360750)"),
):
    """ETF 비교 테이블 (최대 5개)."""
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()][:5]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="tickers 파라미터 필요")

    key = f"invest:etf:compare:{','.join(sorted(ticker_list))}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        today = _today()
        ohlcv, name_map, used_date = _get_etf_data(today)
        if ohlcv is None or ohlcv.empty:
            raise HTTPException(status_code=502, detail="pykrx ETF 데이터 없음")

        result = []
        for ticker in ticker_list:
            if ticker in ohlcv.index:
                name = name_map.get(ticker, ticker)
                result.append(_build_row(ticker, name, ohlcv.loc[ticker]))
            else:
                result.append({"ticker": ticker, "name": ticker,
                               "price": None, "volume": None, "change_pct": None,
                               "error": "데이터 없음"})

        resp = ok({"date": used_date, "items": result})
    except HTTPException:
        raise
    except Exception as e:
        log.warning("[invest:etf:compare] %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_COMPARE)
    return resp


@router.get("/{ticker}")
def etf_detail(
    ticker: str = Path(..., description="ETF 티커 (예: 069500)"),
):
    """ETF 상세 (NAV, 괴리율 포함)."""
    key = f"invest:etf:detail:{ticker}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        from pykrx import stock as krx

        today = _today()
        ohlcv, name_map, used_date = _get_etf_data(today)
        if ohlcv is None or ohlcv.empty or ticker not in ohlcv.index:
            raise HTTPException(status_code=404, detail=f"ETF {ticker} 데이터 없음")

        row  = ohlcv.loc[ticker]
        name = name_map.get(ticker, ticker)
        base = _build_row(ticker, name, row)

        # NAV 조회
        nav = None
        premium = None
        try:
            time.sleep(0.5)
            nav_df = krx.get_etf_portfolio_deposit_file(used_date, ticker)
            if nav_df is not None and not nav_df.empty:
                nav_col = next((c for c in nav_df.columns if "NAV" in str(c).upper()), None)
                if nav_col:
                    nav = float(nav_df[nav_col].iloc[0])
        except Exception:
            pass

        if nav and base["price"]:
            premium = round((base["price"] - nav) / nav * 100, 4)

        base["nav"]     = nav
        base["premium"] = premium
        base["date"]    = used_date
        resp = ok(base)
    except HTTPException:
        raise
    except Exception as e:
        log.warning("[invest:etf:detail] %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_DETAIL)
    return resp
