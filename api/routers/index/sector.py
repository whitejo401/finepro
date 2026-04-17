"""index/sector — 미국 섹터 ETF 엔드포인트."""
import yfinance as yf
from fastapi import APIRouter, HTTPException

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL_SECTOR = 60 * 10  # 10분

SECTOR_SYMBOLS = {
    "기술":      "XLK",
    "에너지":    "XLE",
    "금융":      "XLF",
    "헬스케어":  "XLV",
    "산업":      "XLI",
    "유틸리티":  "XLU",
    "경기소비재": "XLY",
    "필수소비재": "XLP",
    "소재":      "XLB",
    "부동산":    "XLRE",
}


@router.get("/sector")
def sector():
    """미국 10개 섹터 ETF 현재가·등락률 (change_pct 내림차순 정렬)."""
    key = "index:sector"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        results = []
        for sector_name, symbol in SECTOR_SYMBOLS.items():
            try:
                hist = yf.Ticker(symbol).history(period="5d")
                if hist.empty or len(hist) < 2:
                    results.append({
                        "symbol": symbol,
                        "sector": sector_name,
                        "error": "데이터 없음",
                    })
                    continue
                latest = hist.iloc[-1]
                prev   = hist.iloc[-2]
                price      = round(float(latest["Close"]), 2)
                change     = round(float(latest["Close"] - prev["Close"]), 2)
                change_pct = round(float((latest["Close"] - prev["Close"]) / prev["Close"] * 100), 2)
                date       = str(hist.index[-1].date())
                results.append({
                    "symbol":     symbol,
                    "sector":     sector_name,
                    "price":      price,
                    "change":     change,
                    "change_pct": change_pct,
                    "date":       date,
                })
            except Exception:
                results.append({"symbol": symbol, "sector": sector_name, "error": "조회 실패"})

        # change_pct 내림차순 정렬 (에러 항목은 후순위)
        results.sort(
            key=lambda x: x.get("change_pct", float("-inf")),
            reverse=True,
        )
        resp = ok(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_SECTOR)
    return resp
