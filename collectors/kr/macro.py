"""
국내 거시경제 데이터 수집기.

수집 소스:
  - 한국은행 ECOS API: 기준금리·M2·CPI·GDP 등 (ECOS_API_KEY 필요)
  - 국토교통부 실거래가 API: 서울 아파트 월평균 거래가격 지수 (MOLIT_API_KEY 필요)

컬럼명 규칙: kr_macro_ 접두사
  kr_macro_base_rate  : 한국은행 기준금리 (%)
  kr_macro_m2         : M2 통화량 (조원)
  kr_macro_cpi        : 소비자물가지수
  kr_macro_apt_price  : 서울 아파트 월평균 거래단가 (만원/㎡)
"""
from __future__ import annotations

import time
import urllib.parse

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache
from config import ECOS_API_KEY, MOLIT_API_KEY

log = get_logger("kr.macro")

# ---------------------------------------------------------------------------
# 한국은행 ECOS API
# ---------------------------------------------------------------------------

_ECOS_BASE = "https://ecos.bok.or.kr/api"

# stat_code, cycle, item_code1, col_name
_ECOS_SERIES: list[tuple[str, str, str, str]] = [
    ("722Y001", "M", "0101000", "kr_macro_base_rate"),   # 기준금리 (월, 연%)
    ("161Y006", "M", "BBHA00",  "kr_macro_m2"),          # M2 평잔 원계열 (월, 십억원)
    ("901Y009", "M", "0",       "kr_macro_cpi"),         # 소비자물가지수 (월)
    ("200Y104", "Q", "1400",    "kr_macro_gdp"),         # 실질GDP 계절조정 (분기, 십억원)
]


def get_ecos_series(
    stat_code: str,
    cycle: str,
    item_code: str,
    col_name: str,
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    ECOS API 단일 통계 수집.

    Args:
        stat_code:  통계표코드 (예: '722Y001')
        cycle:      주기 'MM'(월), 'QQ'(분기), 'YY'(연)
        item_code:  항목코드
        col_name:   결과 컬럼명
        start:      'YYYY-MM-DD'
        end:        'YYYY-MM-DD', 기본값 오늘
    Returns:
        DatetimeIndex DataFrame, 컬럼명 = col_name.
        API 키 없거나 오류 시 빈 DataFrame.
    """
    if not ECOS_API_KEY:
        log.warning("ECOS_API_KEY 없음 — ECOS 수집 스킵 (%s)", col_name)
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")

    # ECOS 기간 포맷: 'YYYYMM' (월), 'YYYYQ1'~'YYYYQ4' (분기)
    def _to_ecos_period(date_str: str, is_end: bool = False) -> str:
        ts = pd.Timestamp(date_str)
        if cycle == "M":
            return ts.strftime("%Y%m")
        elif cycle == "Q":
            q = (ts.month - 1) // 3 + 1
            return f"{ts.year}Q{q}"
        elif cycle == "Y":
            return str(ts.year)
        return ts.strftime("%Y%m")

    start_period = _to_ecos_period(start)
    end_period = _to_ecos_period(end, is_end=True)
    cache_key = f"ecos_{stat_code}_{item_code}_{start_period}_{end_period}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    url = (
        f"{_ECOS_BASE}/StatisticSearch/{ECOS_API_KEY}/json/kr/1/1000/"
        f"{stat_code}/{cycle}/{start_period}/{end_period}/{item_code}"
    )

    log.info("fetch ECOS: %s (%s ~ %s)", col_name, start_period, end_period)
    try:
        import requests
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("ECOS 요청 실패 (%s): %s", col_name, e)
        return pd.DataFrame()

    rows = data.get("StatisticSearch", {}).get("row", [])
    if not rows:
        log.warning("ECOS 빈 응답: %s", col_name)
        return pd.DataFrame()

    records = []
    for row in rows:
        time_str = row.get("TIME", "")
        data_value = row.get("DATA_VALUE", "")
        if not time_str or not data_value:
            continue
        try:
            value = float(data_value.replace(",", ""))
            # 기간 → 날짜 변환 ('202301' → 2023-01-31, '2023Q1' → 2023-03-31)
            if "Q" in time_str:
                year, q = int(time_str[:4]), int(time_str[-1])
                month = q * 3
                date = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
            elif len(time_str) == 6:
                date = pd.Timestamp(time_str + "01") + pd.offsets.MonthEnd(0)
            elif len(time_str) == 4:
                date = pd.Timestamp(year=int(time_str), month=12, day=31)
            else:
                continue
            records.append({"date": date, col_name: value})
        except Exception:
            continue

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).set_index("date")
    df.index = pd.DatetimeIndex(df.index)
    df.index.name = "date"
    df.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, df)

    log.info("ECOS %s: %d 행", col_name, len(df))
    return df


def get_ecos_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    ECOS 주요 지표 수집 통합.

    Returns:
        DatetimeIndex DataFrame — kr_macro_base_rate, kr_macro_m2, kr_macro_cpi, kr_macro_gdp
    """
    if not ECOS_API_KEY:
        log.warning("ECOS_API_KEY 없음 — get_ecos_dataset 스킵")
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"ecos_dataset_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    frames: list[pd.DataFrame] = []
    for stat_code, cycle, item_code, col_name in _ECOS_SERIES:
        try:
            df = get_ecos_series(
                stat_code, cycle, item_code, col_name,
                start=start, end=end, use_cache=use_cache,
            )
            if not df.empty:
                frames.append(df)
            time.sleep(0.2)
        except Exception as e:
            log.warning("ECOS %s 수집 오류: %s", col_name, e)

    if not frames:
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")
    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)

    log.info("ECOS dataset: %d 컬럼, %d 행", len(result.columns), len(result))
    return result


# ---------------------------------------------------------------------------
# 국토교통부 실거래가 API — 서울 아파트
# ---------------------------------------------------------------------------

_MOLIT_BASE = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# 서울 주요 구 법정동 코드 (5자리)
_SEOUL_DISTRICTS = [
    "11110",  # 종로구
    "11140",  # 중구
    "11170",  # 용산구
    "11200",  # 성동구
    "11215",  # 광진구
    "11230",  # 동대문구
    "11260",  # 중랑구
    "11290",  # 성북구
    "11305",  # 강북구
    "11320",  # 도봉구
    "11350",  # 노원구
    "11380",  # 은평구
    "11410",  # 서대문구
    "11440",  # 마포구
    "11470",  # 양천구
    "11500",  # 강서구
    "11530",  # 구로구
    "11545",  # 금천구
    "11560",  # 영등포구
    "11590",  # 동작구
    "11620",  # 관악구
    "11650",  # 서초구
    "11680",  # 강남구
    "11710",  # 송파구
    "11740",  # 강동구
]


def _fetch_molit_month(district_code: str, deal_ymd: str) -> list[dict]:
    """
    특정 구·거래년월의 아파트 실거래 데이터 수집.

    Returns:
        list of dicts with keys: deal_ymd, area, price_per_sqm
    """
    if not MOLIT_API_KEY:
        return []

    params = {
        "serviceKey": MOLIT_API_KEY,
        "pageNo": 1,
        "numOfRows": 1000,
        "LAWD_CD": district_code,
        "DEAL_YMD": deal_ymd,
    }

    try:
        import requests
        resp = requests.get(_MOLIT_BASE, params=params, timeout=30)
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        log.debug("MOLIT 요청 실패 (%s, %s): %s", district_code, deal_ymd, e)
        return []

    # XML 파싱
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(text)
        items = root.findall(".//item")
    except Exception:
        return []

    records = []
    for item in items:
        try:
            area_str = (item.findtext("excluUseAr") or "").strip()
            price_str = (item.findtext("dealAmount") or "").strip().replace(",", "")
            if not area_str or not price_str:
                continue
            area = float(area_str)
            price_manwon = float(price_str)  # 단위: 만원
            if area <= 0:
                continue
            price_per_sqm = price_manwon / area  # 만원/㎡
            records.append({"price_per_sqm": price_per_sqm})
        except Exception:
            continue

    return records


def get_molit_apt_price(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    서울 아파트 월평균 실거래 단가 지수 수집.

    국토교통부 실거래가 API(MOLIT_API_KEY)를 사용해
    서울 25개 구의 월별 아파트 거래 평균 단가(만원/㎡)를 산출.

    Args:
        start: 'YYYY-MM-DD'
        end:   'YYYY-MM-DD', 기본값 오늘
    Returns:
        DatetimeIndex(월말) DataFrame, 컬럼: kr_macro_apt_price
        API 키 없거나 오류 시 빈 DataFrame
    """
    if not MOLIT_API_KEY:
        log.warning("MOLIT_API_KEY 없음 — 아파트 실거래가 수집 스킵")
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"molit_apt_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    # 월별 기간 생성
    months = pd.period_range(start=start[:7], end=end[:7], freq="M")
    log.info("MOLIT 아파트 실거래가 수집: %d개월 × %d개구", len(months), len(_SEOUL_DISTRICTS))

    monthly_avg: dict[pd.Timestamp, float] = {}

    for period in months:
        deal_ymd = period.strftime("%Y%m")
        all_prices: list[float] = []

        for district in _SEOUL_DISTRICTS:
            records = _fetch_molit_month(district, deal_ymd)
            all_prices.extend(r["price_per_sqm"] for r in records)
            time.sleep(0.05)  # 속도 제한

        if all_prices:
            avg_price_manwon = sum(all_prices) / len(all_prices)  # 이미 만원/㎡
            date_key = pd.Timestamp(period.to_timestamp("M").date()) + pd.offsets.MonthEnd(0)
            monthly_avg[date_key] = round(avg_price_manwon, 1)
            log.info("MOLIT %s: 평균 %.0f 만원/㎡ (%d건)", deal_ymd, avg_price_manwon, len(all_prices))
        else:
            log.warning("MOLIT %s: 거래 데이터 없음", deal_ymd)

    if not monthly_avg:
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(
        monthly_avg, orient="index", columns=["kr_macro_apt_price"]
    )
    df.index = pd.DatetimeIndex(df.index)
    df.index.name = "date"
    df.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, df)

    log.info("MOLIT 아파트 실거래가: %d 개월", len(df))
    return df
