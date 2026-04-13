"""
US/Global macroeconomic data collector.

수집 소스:
  - FRED (fredapi): 미국 금리·물가·성장·고용·유동성
  - EIA API v2:     원유재고·생산량·천연가스 가격 (주간)
  - World Bank (wbgapi): 주요국 GDP성장률·CPI·경상수지 (연간)
"""
from __future__ import annotations

import time

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache
from config import EIA_API_KEY, FRED_API_KEY

log = get_logger("global.macro")

# FRED series reference
FRED_SERIES: dict[str, str] = {
    # 물가
    "macro_cpi":          "CPIAUCSL",      # 미국 CPI (월간)
    "macro_pce":          "PCEPI",         # PCE 물가지수 (월간)
    # 성장
    "macro_pmi_us":       "MANEMP",        # 제조업 고용 (PMI 대리변수)
    "macro_gdp_us":       "GDP",           # 미국 GDP (분기)
    "macro_unemployment": "UNRATE",        # 실업률 (월간)
    # 금리/신용
    "rate_fed":           "FEDFUNDS",      # 연방기금금리 (월간)
    "rate_us10y":         "DGS10",         # 10년 국채 (일간)
    "rate_us2y":          "DGS2",          # 2년 국채 (일간)
    "rate_spread_10_2":   "T10Y2Y",        # 장단기 스프레드 (일간)
    "rate_hy_spread":     "BAMLH0A0HYM2",  # 하이일드 스프레드 (일간)
    # 통화/유동성
    "macro_m2_us":        "M2SL",          # M2 통화량 (월간)
    # 주택/실물
    "macro_housing":      "HOUST",         # 주택착공건수 (월간)
    # CBOE 시장심리 (FRED 재배포)
    "alt_vix9d":          "VXVCLS",        # CBOE 9일 VIX (일간)
    # CBOE Put/Call Ratio: CPCE/CPCV/PCALL 등 FRED에 없음 — 대안 없음
}


def _get_fred_client():
    """fredapi Fred 인스턴스 반환. API 키 없으면 None 반환."""
    if not FRED_API_KEY:
        log.warning("FRED_API_KEY is not set — skipping FRED fetch")
        return None
    try:
        from fredapi import Fred
        return Fred(api_key=FRED_API_KEY)
    except ImportError:
        log.warning("fredapi is not installed — run: pip install fredapi")
        return None


def get_fred_series(
    series_key: str,
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    단일 FRED 시리즈 수집.

    Args:
        series_key: FRED_SERIES의 키 (예: 'macro_cpi') 또는 FRED 시리즈 ID 직접 입력
        start: 시작일 'YYYY-MM-DD'
        end:   종료일 'YYYY-MM-DD', 기본값은 오늘
        use_cache: 캐시 사용 여부

    Returns:
        DatetimeIndex, 컬럼명 = series_key 인 DataFrame.
        API 키 없거나 오류 발생 시 빈 DataFrame 반환.
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    fred_id = FRED_SERIES.get(series_key, series_key)
    cache_key = f"fred_{fred_id}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    fred = _get_fred_client()
    if fred is None:
        return pd.DataFrame()

    log.info("fetch FRED: %s (series_key=%s, %s ~ %s)", fred_id, series_key, start, end)
    try:
        raw: pd.Series = fred.get_series(fred_id, observation_start=start, observation_end=end)
    except Exception as e:
        log.warning("FRED fetch error for %s (%s): %s", series_key, fred_id, e)
        return pd.DataFrame()

    if raw.empty:
        log.warning("empty result for %s (%s)", series_key, fred_id)
        return pd.DataFrame()

    df = raw.to_frame(name=series_key)
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    if use_cache:
        save_cache(cache_key, df)

    return df


def get_macro_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
    series_keys: list[str] | None = None,
) -> pd.DataFrame:
    """
    여러 FRED 시리즈를 수집해 하나의 DataFrame으로 병합.

    Args:
        start:       시작일 'YYYY-MM-DD'
        end:         종료일 'YYYY-MM-DD', 기본값은 오늘
        use_cache:   캐시 사용 여부
        series_keys: 수집할 시리즈 키 목록. None이면 FRED_SERIES 전체

    Returns:
        outer join 병합된 DataFrame (Forward Fill 없음 — 상위 processor 책임).
        수집된 시리즈가 없으면 빈 DataFrame 반환.
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    keys = series_keys if series_keys is not None else list(FRED_SERIES.keys())

    sorted_keys = "_".join(sorted(keys))
    cache_key = f"fred_macro_{sorted_keys}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    frames: list[pd.DataFrame] = []
    for key in keys:
        try:
            df = get_fred_series(key, start=start, end=end, use_cache=use_cache)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            log.warning("unexpected error collecting %s: %s", key, e)

    if not frames:
        log.warning("no FRED series collected for keys=%s", keys)
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")

    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)

    log.info(
        "macro dataset ready: %d series, %d rows (%s ~ %s)",
        len(result.columns),
        len(result),
        result.index.min().date() if not result.empty else "N/A",
        result.index.max().date() if not result.empty else "N/A",
    )
    return result


# ---------------------------------------------------------------------------
# EIA API v2
# ---------------------------------------------------------------------------

_EIA_BASE = "https://api.eia.gov/v2"

# key → {route, facets, frequency}
# facets: EIA v2 필터 (예: {"series": "WCRSTUS1"} 또는 {"duoarea": "NUS", "product": "EPC0", "process": "FPF"})
_EIA_SERIES: dict[str, dict] = {
    "eia_crude_stocks": {
        "route": "petroleum/sum/sndw",
        "facets": {"series": "WCRSTUS1"},
        "frequency": "weekly",
    },
    "eia_crude_production": {
        "route": "petroleum/sum/crdsnd",
        "facets": {"duoarea": "NUS", "product": "EPC0", "process": "FPF"},
        "frequency": "monthly",
    },
    "eia_natgas_price": {
        "route": "natural-gas/pri/fut",
        "facets": {"series": "RNGWHHD"},
        "frequency": "weekly",
    },
}


def get_eia_series(
    series_key: str,
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    EIA API v2 단일 시리즈 수집.

    Args:
        series_key: _EIA_SERIES 키 (예: 'eia_crude_stocks')
        start:      'YYYY-MM-DD'
        end:        'YYYY-MM-DD', 기본값 오늘
    Returns:
        DatetimeIndex DataFrame, 컬럼명 = series_key.
        API 키 없거나 오류 시 빈 DataFrame.
    """
    if not EIA_API_KEY:
        log.warning("EIA_API_KEY 없음 — EIA 수집 스킵")
        return pd.DataFrame()

    if series_key not in _EIA_SERIES:
        log.warning("알 수 없는 EIA series_key: %s", series_key)
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    spec = _EIA_SERIES[series_key]
    route = spec["route"]
    facets: dict = spec["facets"]
    frequency: str = spec["frequency"]
    cache_key = f"eia_{series_key}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    url = f"{_EIA_BASE}/{route}/data/"
    params: dict = {
        "api_key": EIA_API_KEY,
        "frequency": frequency,
        "data[0]": "value",
        "start": start[:7],   # EIA v2: YYYY-MM 형식
        "end": end[:7],
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 5000,
    }
    for i, (k, v) in enumerate(facets.items()):
        params[f"facets[{k}][{i}]"] = v

    log.info("fetch EIA: %s (%s, %s ~ %s)", series_key, facets, start[:7], end[:7])
    try:
        import requests
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("EIA 요청 실패 (%s): %s", series_key, e)
        return pd.DataFrame()

    rows = data.get("response", {}).get("data", [])
    if not rows:
        log.warning("EIA 빈 응답: %s", series_key)
        return pd.DataFrame()

    records = []
    for row in rows:
        period = row.get("period")
        value = row.get("value")
        if period is None or value is None:
            continue
        try:
            # EIA 주간 기간 형식: "2023-01-06" 또는 "2023-01"
            date = pd.Timestamp(period)
            records.append({"date": date, series_key: float(value)})
        except Exception:
            continue

    if not records:
        log.warning("EIA 파싱 결과 없음: %s", series_key)
        return pd.DataFrame()

    df = pd.DataFrame(records).set_index("date")
    df.index = pd.DatetimeIndex(df.index)
    df.index.name = "date"
    df.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, df)

    log.info("EIA %s: %d 행 수집", series_key, len(df))
    return df


def get_eia_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    모든 EIA 시리즈를 수집해 outer join으로 병합.

    Returns:
        DatetimeIndex DataFrame — eia_crude_stocks, eia_crude_production, eia_natgas_price
    """
    if not EIA_API_KEY:
        log.warning("EIA_API_KEY 없음 — get_eia_dataset 스킵")
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"eia_dataset_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    frames: list[pd.DataFrame] = []
    for key in _EIA_SERIES:
        try:
            df = get_eia_series(key, start=start, end=end, use_cache=use_cache)
            if not df.empty:
                frames.append(df)
            time.sleep(0.3)  # EIA 속도 제한 회피
        except Exception as e:
            log.warning("EIA %s 수집 오류: %s", key, e)

    if not frames:
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")
    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)

    log.info("EIA dataset: %d 컬럼, %d 행", len(result.columns), len(result))
    return result


# ---------------------------------------------------------------------------
# World Bank (wbgapi)
# ---------------------------------------------------------------------------

# indicator → column name
_WB_INDICATORS: dict[str, str] = {
    "NY.GDP.MKTP.KD.ZG": "wb_gdp_growth_us",    # 미국 GDP 성장률 (%)
    "FP.CPI.TOTL.ZG":    "wb_cpi_us",            # 미국 CPI 인플레이션 (%)
    "BN.CAB.XOKA.GD.ZS": "wb_current_acct_us",   # 미국 경상수지 (% of GDP)
}

_WB_ECONOMIES: dict[str, str] = {
    "USA": "us",
    "CHN": "cn",
    "KOR": "kr",
    "JPN": "jp",
    "DEU": "de",
}


def get_worldbank_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    World Bank 주요국 연간 거시지표 수집.

    wbgapi 패키지 사용 (pip install wbgapi). 키 불필요.

    Returns:
        DatetimeIndex(연간) DataFrame, 컬럼 예: wb_gdp_growth_us, wb_cpi_cn, ...
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    start_year = int(start[:4])
    end_year = int(end[:4])

    cache_key = f"worldbank_{start_year}_{end_year}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    try:
        import wbgapi as wb  # type: ignore
    except ImportError:
        log.warning("wbgapi 패키지 없음 — pip install wbgapi")
        return pd.DataFrame()

    indicator_ids = list(_WB_INDICATORS.keys())
    economy_ids = list(_WB_ECONOMIES.keys())
    # World Bank는 1~2년 발표 지연 — 데이터 누락 방지를 위해 5년 전부터 요청 후 필터
    _current_year = pd.Timestamp.today().year
    fetch_start = max(start_year - 2, 2000)
    fetch_end = min(_current_year, end_year + 1)
    years = range(fetch_start, fetch_end + 1)

    log.info(
        "fetch World Bank: %d 지표 × %d 국가 (%d ~ %d)",
        len(indicator_ids), len(economy_ids), start_year, end_year,
    )

    frames: list[pd.DataFrame] = []
    for ind_id, col_base in _WB_INDICATORS.items():
        try:
            raw = wb.data.DataFrame(ind_id, economy=economy_ids, time=years)
            # raw: index=economy (CHN, USA, ...), columns=YR20xx
            if raw.empty:
                continue
            # 컬럼이 YRxxxx 형식인지 확인
            year_cols = [c for c in raw.columns if str(c).startswith("YR")]
            if not year_cols:
                log.warning("World Bank %s: 연도 컬럼 없음 — %s", ind_id, raw.columns.tolist())
                continue
            raw = raw[year_cols]
            # col_base에서 지표 약어 추출 (wb_gdp_growth_us → gdp_growth)
            base_parts = col_base.split("_")  # ['wb', 'gdp', 'growth', 'us']
            indicator_short = "_".join(base_parts[1:-1])  # 'gdp_growth'
            for eco_id, eco_suffix in _WB_ECONOMIES.items():
                if eco_id not in raw.index:
                    continue
                series = raw.loc[eco_id].dropna()
                dates = []
                values = []
                for yr_col, val in series.items():
                    yr_str = str(yr_col).replace("YR", "")
                    try:
                        dates.append(pd.Timestamp(f"{yr_str}-12-31"))
                        values.append(float(val))
                    except Exception:
                        continue
                if not dates:
                    continue
                col_name = f"wb_{indicator_short}_{eco_suffix}"
                df_eco = pd.DataFrame({"date": dates, col_name: values})
                df_eco = df_eco.set_index("date")
                df_eco.index.name = "date"
                df_eco.sort_index(inplace=True)
                # 요청 범위로 필터
                df_eco = df_eco.loc[
                    str(start_year):str(end_year)
                ]
                if not df_eco.empty:
                    frames.append(df_eco)
        except Exception as e:
            log.warning("World Bank %s 수집 오류: %s", ind_id, e)

    if not frames:
        log.warning("World Bank: 수집된 데이터 없음")
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")
    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)

    log.info("World Bank dataset: %d 컬럼, %d 행", len(result.columns), len(result))
    return result


# ---------------------------------------------------------------------------
# OECD 경기선행지수 (CLI)
# ---------------------------------------------------------------------------

_OECD_CLI_COUNTRIES: dict[str, str] = {
    "USA": "oecd_cli_us",
    "KOR": "oecd_cli_kr",
    "JPN": "oecd_cli_jp",
    "DEU": "oecd_cli_de",
}


def get_oecd_cli_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    OECD Composite Leading Indicators (CLI) 수집.

    OECD SDMX v2 REST API (sdmx.oecd.org) 사용. 키 불필요.
    미국·한국·일본·독일 월간 CLI (진폭조정, 100 기준).

    Returns:
        DatetimeIndex(월말) DataFrame:
          oecd_cli_us, oecd_cli_kr, oecd_cli_jp, oecd_cli_de
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"oecd_cli_{start[:7]}_{end[:7]}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    # 요청 범위에 맞는 lastNObservations 계산 (OECD v2는 start/end 파라미터 미지원)
    months = (
        (pd.Timestamp(end).year - pd.Timestamp(start).year) * 12
        + (pd.Timestamp(end).month - pd.Timestamp(start).month)
        + 3  # 여유분
    )

    # OECD SDMX v2 API: DSD_STES@DF_CLI v4.0
    # c[] 필터가 서버 측에서 무시되므로 전체 수신 후 Python에서 필터링
    # MEASURE=LI (Composite Leading Indicator), ADJUSTMENT=AA, TRANSFORMATION=IX
    base_url = (
        "https://sdmx.oecd.org/public/rest/v2/data/dataflow/"
        "OECD.SDD.STES/DSD_STES@DF_CLI/4.0/*"
    )
    qs = (
        f"lastNObservations={max(months, 24)}"
        "&format=csvfilewithlabels"
        "&dimensionAtObservation=TIME_PERIOD"
    )
    url = f"{base_url}?{qs}"

    log.info("fetch OECD CLI: %s ~ %s (lastN=%d)", start[:7], end[:7], max(months, 24))
    try:
        import requests
        resp = requests.get(url, timeout=120, headers={"Accept-Encoding": "gzip"})
        resp.raise_for_status()
    except Exception as e:
        log.warning("OECD CLI fetch 실패: %s", e)
        return pd.DataFrame()

    try:
        from io import StringIO
        text = resp.text.lstrip("\ufeff")
        df_raw = pd.read_csv(StringIO(text))
    except Exception as e:
        log.warning("OECD CLI CSV 파싱 실패: %s", e)
        return pd.DataFrame()

    if "TIME_PERIOD" not in df_raw.columns or "OBS_VALUE" not in df_raw.columns:
        log.warning("OECD CLI: 예상 컬럼 없음 — %s", df_raw.columns.tolist()[:10])
        return pd.DataFrame()

    area_col = next(
        (c for c in df_raw.columns if c == "REF_AREA" or "AREA" in c.upper()),
        None,
    )
    if area_col is None:
        log.warning("OECD CLI: REF_AREA 컬럼 없음")
        return pd.DataFrame()

    # MEASURE=LI, ADJUSTMENT=AA, TRANSFORMATION=IX 필터 (가능한 경우)
    if "MEASURE" in df_raw.columns:
        df_raw = df_raw[df_raw["MEASURE"] == "LI"]
    if "ADJUSTMENT" in df_raw.columns:
        df_raw = df_raw[df_raw["ADJUSTMENT"] == "AA"]
    if "TRANSFORMATION" in df_raw.columns:
        df_raw = df_raw[df_raw["TRANSFORMATION"] == "IX"]

    our_countries = set(_OECD_CLI_COUNTRIES.keys())
    df_raw = df_raw[df_raw[area_col].isin(our_countries)]

    frames: list[pd.DataFrame] = []
    for country_code, col_name in _OECD_CLI_COUNTRIES.items():
        sub = df_raw[df_raw[area_col] == country_code][
            ["TIME_PERIOD", "OBS_VALUE"]
        ].copy()
        if sub.empty:
            log.info("OECD CLI: %s 데이터 없음", country_code)
            continue
        sub["date"] = pd.to_datetime(
            sub["TIME_PERIOD"].str[:7], format="%Y-%m", errors="coerce"
        )
        sub["date"] = sub["date"] + pd.offsets.MonthEnd(0)
        sub = sub.dropna(subset=["date"])
        sub["OBS_VALUE"] = pd.to_numeric(sub["OBS_VALUE"], errors="coerce")
        sub = sub.dropna(subset=["OBS_VALUE"])
        sub = sub.set_index("date")[["OBS_VALUE"]].rename(
            columns={"OBS_VALUE": col_name}
        )
        sub.index.name = "date"
        sub.sort_index(inplace=True)
        sub = sub.loc[start:end]
        frames.append(sub)
        log.info("OECD CLI %s (%s): %d 행", country_code, col_name, len(sub))

    if not frames:
        log.warning("OECD CLI: 파싱된 데이터 없음")
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")
    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)

    log.info("OECD CLI dataset: %d 컬럼, %d 행", len(result.columns), len(result))
    return result
