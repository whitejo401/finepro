"""index/commodity — 원자재 선물 엔드포인트."""
import yfinance as yf
from fastapi import APIRouter, HTTPException

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL_COMMODITY = 60 * 10  # 10분

COMMODITY_SYMBOLS = {
    "금":     "GC=F",
    "WTI원유": "CL=F",
    "구리":   "HG=F",
    "은":     "SI=F",
}


@router.get("/commodity")
def commodity():
    """주요 원자재 선물 현재가·등락률 (금·WTI원유·구리·은)."""
    key = "index:commodity"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        results = []
        for name, symbol in COMMODITY_SYMBOLS.items():
            try:
                hist = yf.Ticker(symbol).history(period="5d")
                if hist.empty or len(hist) < 2:
                    results.append({"symbol": symbol, "name": name, "error": "데이터 없음"})
                    continue
                latest = hist.iloc[-1]
                prev   = hist.iloc[-2]
                price      = round(float(latest["Close"]), 3)
                change     = round(float(latest["Close"] - prev["Close"]), 3)
                change_pct = round(float((latest["Close"] - prev["Close"]) / prev["Close"] * 100), 2)
                date       = str(hist.index[-1].date())
                results.append({
                    "symbol":     symbol,
                    "name":       name,
                    "price":      price,
                    "change":     change,
                    "change_pct": change_pct,
                    "date":       date,
                })
            except Exception:
                results.append({"symbol": symbol, "name": name, "error": "조회 실패"})

        resp = ok(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_COMMODITY)
    return resp
