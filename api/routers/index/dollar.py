"""index/dollar — 달러인덱스 엔드포인트."""
import yfinance as yf
from fastapi import APIRouter, HTTPException

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL_DOLLAR = 60 * 10  # 10분

DOLLAR_SYMBOLS = {"DXY": "DX-Y.NYB"}

# 달러인덱스 구성통화 비중 (ICE 기준)
DXY_WEIGHTS = {
    "EUR": 57.6,
    "JPY": 13.6,
    "GBP": 11.9,
    "CAD": 9.1,
    "SEK": 4.2,
    "CHF": 3.6,
}


@router.get("/dollar")
def dollar_index():
    """달러인덱스 현재값·전일대비·30일 추이 및 구성통화 비중."""
    key = "index:dollar"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        ticker = yf.Ticker("DX-Y.NYB")
        hist   = ticker.history(period="35d")  # 30일 추이 + 여유

        if hist.empty or len(hist) < 2:
            raise HTTPException(status_code=502, detail="달러인덱스 데이터 수집 실패")

        latest = hist.iloc[-1]
        prev   = hist.iloc[-2]
        price      = round(float(latest["Close"]), 3)
        change     = round(float(latest["Close"] - prev["Close"]), 3)
        change_pct = round(float((latest["Close"] - prev["Close"]) / prev["Close"] * 100), 2)
        date       = str(hist.index[-1].date())

        # 30일 추이 (최대 30개)
        trend_df = hist.tail(30)
        trend = [
            {"date": str(idx.date()), "close": round(float(row["Close"]), 3)}
            for idx, row in trend_df.iterrows()
        ]

        data = {
            "symbol":     "DX-Y.NYB",
            "name":       "US Dollar Index",
            "price":      price,
            "change":     change,
            "change_pct": change_pct,
            "date":       date,
            "weights":    DXY_WEIGHTS,
            "trend_30d":  trend,
        }
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_DOLLAR)
    return resp
