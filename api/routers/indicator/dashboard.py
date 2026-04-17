"""indicator/dashboard — 매크로 대시보드 (전 지표 통합)."""
import logging

from fastapi import APIRouter

from api.core.cache import cache
from api.core.response import ok

router = APIRouter()
log = logging.getLogger("api.indicator.dashboard")

TTL = 60 * 60  # 1시간


def surprise(series: list[float]) -> float:
    """서프라이즈 인덱스: 최근 실제값과 과거 평균의 표준화 편차."""
    if len(series) < 2:
        return 0.0
    hist = series[:-1]
    actual = series[-1]
    mean = sum(hist) / len(hist)
    std = (sum((x - mean) ** 2 for x in hist) / len(hist)) ** 0.5
    return round((actual - mean) / std, 2) if std > 0 else 0.0


def _safe_get_inflation(country: str) -> dict:
    try:
        from api.routers.indicator.inflation import (
            _build_kr_cpi, _build_us_cpi, _build_us_ppi, _build_us_pce,
        )
        if country == "KR":
            return {"cpi": _build_kr_cpi(), "ppi": None, "pce": None}
        return {
            "cpi": _build_us_cpi(),
            "ppi": _build_us_ppi(),
            "pce": _build_us_pce(),
        }
    except Exception as e:
        log.warning("inflation 수집 실패 (%s): %s", country, e)
        return {"cpi": None, "ppi": None, "pce": None}


def _safe_get_gdp(country: str) -> dict:
    try:
        from api.routers.indicator.growth import (
            _ecos_fetch_quarterly, _parse_ecos_quarterly,
            _fred_series, _parse_fred_quarterly,
        )
        if country == "KR":
            rows = _ecos_fetch_quarterly("200Y001")
            series = _parse_ecos_quarterly(rows)
        else:
            obs = _fred_series("A191RL1Q225SBEA", limit=12)
            series = _parse_fred_quarterly(obs)
        return {"series": series, "latest": series[-1] if series else None}
    except Exception as e:
        log.warning("gdp 수집 실패 (%s): %s", country, e)
        return {"series": [], "latest": None}


def _safe_get_employment(country: str) -> dict:
    try:
        from api.routers.indicator.employment import (
            _ecos_fetch, _parse_ecos_latest,
            _fred_series, _parse_fred_latest, _fred_mom_change,
        )
        if country == "KR":
            return {
                "unemployment": _parse_ecos_latest(_ecos_fetch("901Y027")),
                "employment_rate": _parse_ecos_latest(_ecos_fetch("901Y026")),
                "nonfarm_payrolls": None,
            }
        return {
            "unemployment": _parse_fred_latest(_fred_series("UNRATE", limit=3)),
            "employment_rate": None,
            "nonfarm_payrolls": _fred_mom_change("PAYEMS"),
        }
    except Exception as e:
        log.warning("employment 수집 실패 (%s): %s", country, e)
        return {"unemployment": None, "employment_rate": None, "nonfarm_payrolls": None}


def _safe_get_pmi(country: str) -> dict:
    try:
        from api.routers.indicator.pmi import _get_oecd_cli, _get_fred_pmi
        cli = _get_oecd_cli(country)
        mfg = _get_fred_pmi() if country == "US" else None
        return {"manufacturing_pmi": mfg, "oecd_cli": cli}
    except Exception as e:
        log.warning("pmi 수집 실패 (%s): %s", country, e)
        return {"manufacturing_pmi": None, "oecd_cli": None}


def _safe_get_money(country: str) -> dict:
    try:
        from api.routers.indicator.money import (
            _ecos_fetch, _parse_ecos_latest,
            _fred_series, _parse_fred_latest_with_yoy,
        )
        if country == "KR":
            return {
                "m2": _parse_ecos_latest(_ecos_fetch("101Y004")),
                "loan_growth": _parse_ecos_latest(_ecos_fetch("121Y006")),
            }
        return {
            "m2": _parse_fred_latest_with_yoy(_fred_series("M2SL", limit=24)),
            "loan_growth": None,
        }
    except Exception as e:
        log.warning("money 수집 실패 (%s): %s", country, e)
        return {"m2": None, "loan_growth": None}


def _compute_macro_score(country_data: dict) -> float:
    """서프라이즈 인덱스 평균 → macro_score (-2 ~ +2 대략)."""
    surprises: list[float] = []

    # GDP 시리즈
    gdp = country_data.get("gdp", {})
    gdp_series = [s["growth_pct"] for s in gdp.get("series", []) if s.get("growth_pct") is not None]
    if len(gdp_series) >= 2:
        surprises.append(surprise(gdp_series[-6:]))

    # CPI 전년비 시리즈는 단일 최신값만 있어 서프라이즈 계산 불가 → 스킵
    # PMI CLI
    pmi = country_data.get("pmi", {})
    cli = pmi.get("oecd_cli")
    if cli and cli.get("latest") is not None:
        # 100 기준 편차 (간단 정규화)
        normalized = round((cli["latest"] - 100) / 1.5, 2)
        surprises.append(normalized)

    if not surprises:
        return 0.0
    return round(sum(surprises) / len(surprises), 2)


@router.get("/dashboard")
def dashboard():
    """매크로 대시보드 — KR·US 전 지표 통합.

    각 지표의 최근 6개월 평균을 컨센서스로 사용한 서프라이즈 인덱스와
    종합 macro_score를 함께 제공합니다.
    """
    key = "indicator:dashboard"
    cached = cache.get(key)
    if cached:
        return cached

    result = {}
    for country in ("KR", "US"):
        country_data = {
            "inflation": _safe_get_inflation(country),
            "gdp": _safe_get_gdp(country),
            "employment": _safe_get_employment(country),
            "pmi": _safe_get_pmi(country),
            "money": _safe_get_money(country),
        }
        macro_score = _compute_macro_score(country_data)
        result[country.lower()] = {
            **country_data,
            "macro_score": macro_score,
        }

    resp = ok(result)
    cache.set(key, resp, TTL)
    return resp
