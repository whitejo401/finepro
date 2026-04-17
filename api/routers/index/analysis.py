"""index/analysis — 과거 이력 및 상관관계 분석 엔드포인트."""
import urllib.parse
import logging

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query, Path

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.index.analysis")

TTL_HISTORY     = 60 * 10      # 10분
TTL_CORRELATION = 60 * 60      # 1시간

# 상관관계 분석 대상 심볼
CORR_SYMBOLS = {
    "S&P500":   "^GSPC",
    "NASDAQ":   "^IXIC",
    "KOSPI":    "^KS11",
    "NIKKEI":   "^N225",
    "DXY":      "DX-Y.NYB",
    "VIX":      "^VIX",
    "금":       "GC=F",
    "WTI":      "CL=F",
}


@router.get("/history/{symbol}")
def history(
    symbol: str = Path(..., description="yfinance 심볼 (URL 인코딩 허용, 예: %5EGSPC → ^GSPC)"),
    days:   int = Query(90, ge=1, le=365, description="조회 기간(일, 기본 90, 최대 365)"),
):
    """단일 심볼 OHLCV 이력 조회.

    - symbol은 URL 디코딩 처리 (%5E → ^)
    - days 기본값 90, 최대 365
    """
    # URL 디코딩 (%5E → ^)
    decoded_symbol = urllib.parse.unquote(symbol)
    key = f"index:analysis:history:{decoded_symbol}:{days}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        hist = yf.Ticker(decoded_symbol).history(period=f"{days}d")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"심볼 '{decoded_symbol}' 데이터 없음")

        records = [
            {
                "date":   str(idx.date()),
                "open":   round(float(row["Open"]),   4),
                "high":   round(float(row["High"]),   4),
                "low":    round(float(row["Low"]),    4),
                "close":  round(float(row["Close"]),  4),
                "volume": int(row["Volume"]),
            }
            for idx, row in hist.iterrows()
        ]

        data = {
            "symbol": decoded_symbol,
            "days":   days,
            "count":  len(records),
            "ohlcv":  records,
        }
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_HISTORY)
    return resp


@router.get("/correlation")
def correlation():
    """최근 60일 일봉 수익률 Pearson 상관관계 행렬.

    대상: S&P500, NASDAQ, KOSPI, NIKKEI, DXY, VIX, 금, WTI
    """
    key = "index:analysis:correlation"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        # 멀티 다운로드 (60일 + 여유)
        symbols = list(CORR_SYMBOLS.values())
        names   = list(CORR_SYMBOLS.keys())

        raw = yf.download(symbols, period="65d", progress=False, auto_adjust=True)
        if raw.empty:
            raise HTTPException(status_code=502, detail="상관관계 데이터 수집 실패")

        # Close 컬럼 추출 및 이름 매핑
        close = raw["Close"].copy()
        # symbol → name 역매핑
        sym_to_name = {v: k for k, v in CORR_SYMBOLS.items()}
        close.columns = [sym_to_name.get(c, c) for c in close.columns]

        # 일봉 수익률 → Pearson 상관계수
        returns = close.pct_change().dropna()
        corr_matrix = returns.corr()

        # 결측 처리 후 직렬화
        corr_dict = {}
        for col in corr_matrix.columns:
            corr_dict[col] = {
                row: (round(float(val), 4) if pd.notna(val) else None)
                for row, val in corr_matrix[col].items()
            }

        data = {
            "period_days": 60,
            "assets":      names,
            "matrix":      corr_dict,
        }
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_CORRELATION)
    return resp
