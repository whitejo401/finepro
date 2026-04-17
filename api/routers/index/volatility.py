"""index/volatility — VIX 변동성 지수 엔드포인트."""
import yfinance as yf
from fastapi import APIRouter, HTTPException

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()

TTL_VIX = 60 * 5  # 5분

VIX_SYMBOLS = {
    "VIX":   "^VIX",
    "VIX9D": "^VIX9D",
    "VIX3M": "^VIX3M",
    "VVIX":  "^VVIX",
}


def _classify_vix(level: float) -> str:
    """VIX 수준 자동 태깅."""
    if level < 15:
        return "저변동성(안도)"
    elif level < 25:
        return "보통"
    elif level <= 35:
        return "불안"
    else:
        return "공황"


def _fetch_vix_value(symbol: str) -> float | None:
    """단일 VIX 계열 심볼 최신값 조회."""
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if hist.empty:
            return None
        return round(float(hist.iloc[-1]["Close"]), 2)
    except Exception:
        return None


@router.get("/vix")
def vix():
    """VIX·VIX9D·VIX3M·VVIX 현재값, 레벨 태그, 기간구조 분류."""
    key = "index:volatility:vix"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        values = {name: _fetch_vix_value(sym) for name, sym in VIX_SYMBOLS.items()}

        vix_val   = values.get("VIX")
        vix9d_val = values.get("VIX9D")
        vix3m_val = values.get("VIX3M")
        vvix_val  = values.get("VVIX")

        if vix_val is None:
            raise HTTPException(status_code=502, detail="VIX 데이터 수집 실패")

        level_tag = _classify_vix(vix_val)

        # 기간구조 판단: VIX9D < VIX < VIX3M → 콘탱고(정상)
        if vix9d_val and vix3m_val:
            if vix9d_val < vix_val < vix3m_val:
                term_structure = "콘탱고(정상)"
            else:
                term_structure = "백워데이션(위험)"
        else:
            term_structure = "데이터 부족"

        data = {
            "VIX":            vix_val,
            "VIX9D":          vix9d_val,
            "VIX3M":          vix3m_val,
            "VVIX":           vvix_val,
            "level_tag":      level_tag,
            "term_structure": term_structure,
        }
        resp = ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cache.set(key, resp, TTL_VIX)
    return resp
