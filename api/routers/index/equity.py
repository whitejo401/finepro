"""index/equity — 글로벌 주식 지수 엔드포인트."""
import yfinance as yf
from fastapi import APIRouter, HTTPException

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL_SNAPSHOT = 60 * 5   # 5분
TTL_REGION   = 60 * 5   # 5분

US_SYMBOLS     = {"S&P500": "^GSPC", "NASDAQ": "^IXIC", "DOW": "^DJI", "RUSSELL2000": "^RUT"}
KOREA_SYMBOLS  = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}
ASIA_SYMBOLS   = {"NIKKEI": "^N225", "HANGSENG": "^HSI", "SHANGHAI": "000001.SS", "TAIWAN": "^TWII"}
EUROPE_SYMBOLS = {"DAX": "^GDAXI", "FTSE100": "^FTSE", "CAC40": "^FCHI", "STOXX50": "^STOXX50E"}


def _fetch_quote(name: str, symbol: str) -> dict:
    """단일 심볼 현재가·등락률 계산."""
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if hist.empty or len(hist) < 2:
            return {"symbol": symbol, "name": name, "error": "데이터 없음"}
        latest = hist.iloc[-1]
        prev   = hist.iloc[-2]
        price  = round(float(latest["Close"]), 2)
        change = round(float(latest["Close"] - prev["Close"]), 2)
        change_pct = round(float((latest["Close"] - prev["Close"]) / prev["Close"] * 100), 2)
        date = str(hist.index[-1].date())
        return {
            "symbol": symbol,
            "name": name,
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "date": date,
        }
    except Exception:
        return {"symbol": symbol, "name": name, "error": "조회 실패"}


def _fetch_group(symbols: dict) -> list[dict]:
    """심볼 그룹 전체 조회."""
    return [_fetch_quote(name, sym) for name, sym in symbols.items()]


@router.get("/snapshot")
def equity_snapshot():
    """US + KOREA + ASIA + EUROPE 전체 현재가·등락률 스냅샷."""
    key = "index:equity:snapshot"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        all_symbols = {**US_SYMBOLS, **KOREA_SYMBOLS, **ASIA_SYMBOLS, **EUROPE_SYMBOLS}
        data = {
            "us":     _fetch_group(US_SYMBOLS),
            "korea":  _fetch_group(KOREA_SYMBOLS),
            "asia":   _fetch_group(ASIA_SYMBOLS),
            "europe": _fetch_group(EUROPE_SYMBOLS),
        }
        resp = ok(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_SNAPSHOT)
    return resp


@router.get("/us")
def equity_us():
    """미국 4대 지수 (S&P500, NASDAQ, DOW, RUSSELL2000)."""
    key = "index:equity:us"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        data = _fetch_group(US_SYMBOLS)
        resp = ok(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_REGION)
    return resp


@router.get("/asia")
def equity_asia():
    """아시아 주요 지수 (NIKKEI, HANGSENG, SHANGHAI, TAIWAN)."""
    key = "index:equity:asia"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        data = _fetch_group(ASIA_SYMBOLS)
        resp = ok(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_REGION)
    return resp


@router.get("/europe")
def equity_europe():
    """유럽 주요 지수 (DAX, FTSE100, CAC40, STOXX50)."""
    key = "index:equity:europe"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        data = _fetch_group(EUROPE_SYMBOLS)
        resp = ok(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_REGION)
    return resp
