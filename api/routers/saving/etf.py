"""saving/etf — ETF 목록·상세·배당·비교 엔드포인트 (장기저축 관점)."""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_LIST   = 600    # 10분
TTL_DETAIL = 300    # 5분
TTL_DIV    = 3600   # 1시간

# 카테고리별 대표 ETF 티커 (pykrx 조회 기준점)
CATEGORY_TICKERS = {
    "국내주식": ["069500", "102110", "114800"],
    "해외주식": ["360750", "133690", "195930"],
    "채권":     ["114820", "148070", "130730"],
    "배당":     ["280940", "285010", "176710"],
    "리츠":     ["329200", "334700", "432320"],
    "원자재":   ["132030", "411060", "319640"],
}


def _get_etf_data(ticker: str) -> dict | None:
    try:
        from pykrx import stock
        today = datetime.now().strftime("%Y%m%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        df = stock.get_etf_ohlcv_by_date(week_ago, today, ticker)
        if df.empty:
            return None
        last = df.iloc[-1]
        name = stock.get_market_ticker_name(ticker)
        nav_df = stock.get_etf_portfolio_deposit_file(ticker, today)

        return {
            "ticker": ticker,
            "name": name,
            "price": int(last.get("종가", 0)),
            "volume": int(last.get("거래량", 0)),
            "change_pct": round(float(last.get("등락률", 0)), 2),
        }
    except Exception as e:
        logger.debug("ETF %s 조회 실패: %s", ticker, e)
        return None


@router.get("")
def etf_list(
    category: str = Query("국내주식", description="국내주식·해외주식·채권·배당·리츠·원자재"),
    sort: str = Query("volume", description="dividend_yield·volume·yield_1y"),
):
    """카테고리별 ETF 목록 (장기저축 관점)."""
    if category not in CATEGORY_TICKERS:
        raise HTTPException(status_code=422, detail=f"지원 카테고리: {list(CATEGORY_TICKERS.keys())}")

    cache_key = f"saving:etf:list:{category}:{sort}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    tickers = CATEGORY_TICKERS[category]
    items = []
    for t in tickers:
        data = _get_etf_data(t)
        if data:
            items.append(data)

    if sort == "volume":
        items.sort(key=lambda x: x.get("volume") or 0, reverse=True)

    resp = ok(items, meta={"category": category, "count": len(items)})
    cache.set(cache_key, resp, TTL_LIST)
    return resp


@router.get("/dividend")
def etf_dividend():
    """배당 ETF 목록 (배당률 내림차순)."""
    cached = cache.get("saving:etf:dividend")
    if cached:
        return cached

    tickers = CATEGORY_TICKERS["배당"]
    items = []
    for t in tickers:
        data = _get_etf_data(t)
        if data:
            items.append(data)

    resp = ok(items, meta={"count": len(items), "note": "배당 ETF 카테고리 (배당률 데이터는 pykrx Pro 필요)"})
    cache.set("saving:etf:dividend", resp, TTL_DIV)
    return resp


@router.get("/compare")
def etf_compare(
    tickers: str = Query(..., description="쉼표 구분 티커 (최대 5개, 예: 069500,360750)"),
):
    """ETF 간 수익률·비용·괴리율 비교."""
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) > 5:
        raise HTTPException(status_code=422, detail="최대 5개 티커 비교 가능")

    cache_key = f"saving:etf:compare:{','.join(sorted(ticker_list))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    results = []
    for t in ticker_list:
        data = _get_etf_data(t)
        if data:
            results.append(data)
        else:
            results.append({"ticker": t, "error": "데이터 없음"})

    resp = ok(results, meta={"tickers": ticker_list, "count": len(results)})
    cache.set(cache_key, resp, TTL_LIST)
    return resp


@router.get("/{ticker}")
def etf_detail(ticker: str = Path(description="ETF 티커 (예: 069500)")):
    """ETF 상세 (가격·NAV·거래량)."""
    cache_key = f"saving:etf:detail:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    data = _get_etf_data(ticker)
    if not data:
        raise HTTPException(status_code=404, detail=f"ETF {ticker} 데이터 없음")

    resp = ok(data)
    cache.set(cache_key, resp, TTL_DETAIL)
    return resp
