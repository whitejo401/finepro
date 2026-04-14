"""환율 수집기 — frankfurter.app (ECB, 키 불필요) + ECOS (한국은행, KRW 기준)."""
import os
import logging
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

_FRANKFURTER = "https://api.frankfurter.app"
_ECOS = "https://ecos.bok.or.kr/api"

# 주요 통화 목록
MAJOR_CURRENCIES = ["USD", "EUR", "JPY", "GBP", "CNY", "AUD", "CAD", "CHF", "HKD", "SGD"]

# ECOS 환율 통계코드
# 731Y001: 미달러 기준 원화 환율 (매매기준율)
_ECOS_STAT_CODE = "731Y001"
_ECOS_ITEM_CODE_KRW_USD = "0000001"  # 원/달러


def get_latest_rates(base: str = "USD") -> dict:
    """최신 환율 조회 (frankfurter.app — ECB 기준, 영업일 기준 최신).

    Args:
        base: 기준 통화 코드 (예: USD, EUR, KRW)

    Returns:
        {"base": "USD", "date": "2026-04-14", "rates": {"EUR": 0.92, ...}}
    """
    try:
        resp = requests.get(f"{_FRANKFURTER}/latest", params={"base": base}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error("frankfurter 최신 환율 수집 실패 (base=%s): %s", base, e)
        return {}


def get_rate_history(
    base: str = "USD",
    target: str = "KRW",
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """기간별 환율 이력 조회 (frankfurter.app).

    Args:
        base: 기준 통화
        target: 대상 통화
        start: 시작일 YYYY-MM-DD (기본: 90일 전)
        end: 종료일 YYYY-MM-DD (기본: 오늘)

    Returns:
        {"base": "USD", "start_date": ..., "end_date": ..., "rates": {"2026-04-01": {"KRW": 1380}, ...}}
    """
    if not end:
        end = date.today().isoformat()
    if not start:
        start = (date.today() - timedelta(days=90)).isoformat()

    # frankfurter는 KRW 미지원 → USD/EUR 기준으로 조회 후 역산
    if target == "KRW" and base not in ("KRW",):
        return _get_history_via_krw_ecos(base=base, start=start, end=end)

    try:
        url = f"{_FRANKFURTER}/{start}..{end}"
        resp = requests.get(url, params={"base": base, "symbols": target}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error("frankfurter 이력 수집 실패 (%s→%s): %s", base, target, e)
        return {}


def _get_history_via_krw_ecos(base: str, start: str, end: str) -> dict:
    """ECOS에서 원/달러 환율 조회 후 필요 시 교차 환율 계산."""
    krw_usd = _ecos_krw_usd(start=start, end=end)
    if not krw_usd:
        return {}

    if base == "USD":
        rates = {d: {"KRW": v} for d, v in krw_usd.items()}
    else:
        # USD/base 환율을 frankfurter로 가져와 교차 계산
        try:
            url = f"{_FRANKFURTER}/{start}..{end}"
            resp = requests.get(url, params={"base": "USD", "symbols": base}, timeout=15)
            resp.raise_for_status()
            usd_base = resp.json().get("rates", {})
        except Exception as e:
            log.error("교차환율 기준 수집 실패: %s", e)
            return {}

        rates = {}
        for d, krw_per_usd in krw_usd.items():
            base_per_usd = usd_base.get(d, {}).get(base)
            if base_per_usd and base_per_usd != 0:
                rates[d] = {"KRW": round(krw_per_usd / base_per_usd, 4)}

    return {
        "base": base,
        "target": "KRW",
        "start_date": start,
        "end_date": end,
        "source": "ECOS+frankfurter",
        "rates": rates,
    }


def _ecos_krw_usd(start: str, end: str) -> dict[str, float]:
    """ECOS에서 원/달러 매매기준율 조회.

    Returns:
        {"2026-04-01": 1380.5, ...}
    """
    api_key = os.getenv("ECOS_API_KEY", "")
    if not api_key:
        log.warning("ECOS_API_KEY 미설정")
        return {}

    start_d = start.replace("-", "")
    end_d = end.replace("-", "")
    url = (
        f"{_ECOS}/StatisticSearch/{api_key}/json/kr/1/1000/"
        f"{_ECOS_STAT_CODE}/DD/{start_d}/{end_d}/{_ECOS_ITEM_CODE_KRW_USD}"
    )

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("StatisticSearch", {}).get("row", [])
        result = {}
        for row in rows:
            d = row.get("TIME", "")
            v = row.get("DATA_VALUE", "")
            if len(d) == 8 and v:
                try:
                    result[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = float(v)
                except ValueError:
                    pass
        return result
    except Exception as e:
        log.error("ECOS 원/달러 수집 실패: %s", e)
        return {}


def get_krw_rates(currencies: list[str] | None = None) -> dict:
    """원화(KRW) 기준 주요 통화 환율.

    ECOS에서 원/달러를 가져오고, frankfurter로 USD 기준 타 통화를 조회해 교차 계산.

    Args:
        currencies: 조회할 통화 목록 (기본: MAJOR_CURRENCIES에서 KRW 제외)

    Returns:
        {"base": "KRW", "date": ..., "rates": {"USD": 0.000724, "EUR": ..., ...}}
    """
    if currencies is None:
        currencies = [c for c in MAJOR_CURRENCIES if c != "KRW"]

    # 1. 원/달러
    krw_usd_data = _ecos_krw_usd(
        start=(date.today() - timedelta(days=10)).isoformat(),
        end=date.today().isoformat(),
    )
    if not krw_usd_data:
        # fallback: frankfurter EUR/USD 기준으로 역산 시도
        log.warning("ECOS 응답 없음, frankfurter fallback 사용")
        latest = get_latest_rates(base="EUR")
        usd_per_eur = latest.get("rates", {}).get("USD")
        if not usd_per_eur:
            return {}
        # KRW 없으므로 반환 불가
        return {}

    latest_date = max(krw_usd_data.keys())
    krw_per_usd = krw_usd_data[latest_date]

    # 2. USD 기준 타 통화
    try:
        resp = requests.get(
            f"{_FRANKFURTER}/latest",
            params={"base": "USD", "symbols": ",".join(c for c in currencies if c != "USD")},
            timeout=10,
        )
        resp.raise_for_status()
        usd_rates = resp.json().get("rates", {})
    except Exception as e:
        log.error("frankfurter USD 기준 환율 수집 실패: %s", e)
        usd_rates = {}

    # 3. 교차 계산: 1 KRW = ? 외화
    result_rates = {}
    if "USD" in currencies:
        result_rates["USD"] = round(1 / krw_per_usd, 8)
    for cur, usd_per_cur in usd_rates.items():
        if cur in currencies and usd_per_cur:
            # 1 KRW → USD → cur
            result_rates[cur] = round((1 / krw_per_usd) * usd_per_cur, 8)

    return {
        "base": "KRW",
        "date": latest_date,
        "krw_per_usd": krw_per_usd,
        "rates": result_rates,
        "source": "ECOS+frankfurter",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== 최신 환율 (USD 기준) ===")
    print(get_latest_rates("USD"))
    print("\n=== KRW 기준 환율 ===")
    print(get_krw_rates())
