"""
CFTC COT (Commitment of Traders) 보고서 수집기.

미국 상품선물거래위원회(CFTC)가 매주 금요일 오후 3:30 ET 공개하는
주간 선물 포지셔닝 데이터를 수집.

수집 대상:
  - S&P 500 E-Mini (CME) : 비상업적 롱/숏 포지션
  - 골드 (COMEX)         : 비상업적 롱/숏 포지션
  - WTI 원유 (NYMEX)     : 비상업적 롱/숏 포지션
  - 미국 달러 인덱스 (ICE): 비상업적 롱/숏 포지션

컬럼명 규칙: cot_ 접두사
  cot_{asset}_noncomm_long  : 비상업적 순매수 롱 포지션
  cot_{asset}_noncomm_short : 비상업적 순매도 숏 포지션
  cot_{asset}_net           : 비상업적 순포지션 (long - short)

데이터 소스:
  - CFTC 공식 사이트: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
  - 연도별 CSV: https://www.cftc.gov/files/dea/history/fut_fin_xls_{year}.zip
  - 최신 데이터: https://www.cftc.gov/files/dea/history/fut_fin_xls_2024.zip
  - 키 불필요 (무료 공개 데이터)
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache

log = get_logger("global.cftc")

_CFTC_BASE = "https://www.cftc.gov/files/dea/history"
_CFTC_ZIP_PATTERN = "deacot{year}.zip"   # Legacy Combined (모든 자산, CSV)

# 주요 자산 검색어 (Market and Exchange Names 컬럼 기준, 부분 대문자 매칭)
_COT_ASSETS: dict[str, str] = {
    "sp500": "E-MINI S&P 500 - CHICAGO MERCANTILE",  # MICRO 제외
    "gold":  "GOLD - COMMODITY EXCHANGE",
    "wti":   "CRUDE OIL, LIGHT SWEET-WTI",           # ICE 버전 (NYMEX 버전 구분)
}

# COT Legacy 컬럼명 (공백 포함)
_LONG_COL  = "Noncommercial Positions-Long (All)"
_SHORT_COL = "Noncommercial Positions-Short (All)"
_DATE_COL  = "As of Date in Form YYYY-MM-DD"
_ASSET_COL = "Market and Exchange Names"


def _download_cot_year(year: int) -> pd.DataFrame | None:
    """연도별 COT 데이터 ZIP 다운로드 및 파싱 (CSV txt 버전 우선)."""
    url = f"{_CFTC_BASE}/{_CFTC_ZIP_PATTERN.format(year=year)}"
    try:
        import requests
        resp = requests.get(url, timeout=120)
        if resp.status_code == 404:
            log.warning("CFTC %d 데이터 없음 (404)", year)
            return None
        resp.raise_for_status()
    except Exception as e:
        log.warning("CFTC %d 다운로드 실패: %s", year, e)
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            names = z.namelist()
            target = next(
                (n for n in names if n.lower().endswith((".txt", ".csv"))),
                None,
            )
            if target is None:
                log.warning("CFTC %d: ZIP 내 텍스트 파일 없음 — %s", year, names)
                return None
            with z.open(target) as f:
                df = pd.read_csv(f, low_memory=False)
    except Exception as e:
        log.warning("CFTC %d ZIP 파싱 실패: %s", year, e)
        return None

    return df


def _extract_asset(df: pd.DataFrame, asset_key: str, search_str: str) -> pd.DataFrame:
    """전체 COT DataFrame에서 특정 자산 필터링 후 컬럼 정리."""
    if _ASSET_COL not in df.columns:
        return pd.DataFrame()

    mask = df[_ASSET_COL].str.upper().str.contains(search_str, na=False)
    sub = df[mask].copy()
    if sub.empty:
        return pd.DataFrame()

    if _DATE_COL not in sub.columns or _LONG_COL not in sub.columns or _SHORT_COL not in sub.columns:
        return pd.DataFrame()

    sub = sub[[_DATE_COL, _LONG_COL, _SHORT_COL]].copy()
    sub.columns = ["date", f"cot_{asset_key}_noncomm_long", f"cot_{asset_key}_noncomm_short"]
    sub["date"] = pd.to_datetime(sub["date"], errors="coerce")
    sub = sub.dropna(subset=["date"])
    sub[f"cot_{asset_key}_net"] = (
        pd.to_numeric(sub[f"cot_{asset_key}_noncomm_long"], errors="coerce")
        - pd.to_numeric(sub[f"cot_{asset_key}_noncomm_short"], errors="coerce")
    )
    sub = sub.set_index("date")
    sub.index.name = "date"
    sub.sort_index(inplace=True)
    return sub


def get_cftc_cot(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    CFTC COT 주간 선물 포지셔닝 데이터 수집.

    Args:
        start: 'YYYY-MM-DD'
        end:   'YYYY-MM-DD', 기본값 오늘
    Returns:
        DatetimeIndex(주간 화요일 기준) DataFrame:
          cot_sp500_noncomm_long/short/net
          cot_gold_noncomm_long/short/net
          cot_wti_noncomm_long/short/net
          cot_dollar_noncomm_long/short/net
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    start_year = int(start[:4])
    end_year = int(end[:4])
    cache_key = f"cftc_cot_{start_year}_{end_year}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch CFTC COT: %d ~ %d", start_year, end_year)

    all_years: list[pd.DataFrame] = []
    for year in range(start_year, end_year + 1):
        year_cache_key = f"cftc_raw_{year}"
        year_df = None

        if use_cache:
            year_df = load_cache(year_cache_key)

        if year_df is None:
            year_df = _download_cot_year(year)
            if year_df is not None and use_cache:
                save_cache(year_cache_key, year_df)

        if year_df is not None:
            all_years.append(year_df)

    if not all_years:
        log.warning("CFTC: 수집된 연도 데이터 없음")
        return pd.DataFrame()

    full_df = pd.concat(all_years, ignore_index=True)
    log.info("CFTC 전체 로드: %d 행", len(full_df))

    asset_frames: list[pd.DataFrame] = []
    for asset_key, search_str in _COT_ASSETS.items():
        try:
            df_asset = _extract_asset(full_df, asset_key, search_str)
            if not df_asset.empty:
                df_asset = df_asset.loc[start:end]
                if not df_asset.empty:
                    asset_frames.append(df_asset)
                    log.info("CFTC %s: %d 행", asset_key, len(df_asset))
            else:
                log.warning("CFTC %s: 검색 결과 없음 (검색어=%r)", asset_key, search_str)
        except Exception as e:
            log.warning("CFTC %s 추출 오류: %s", asset_key, e)

    if not asset_frames:
        return pd.DataFrame()

    result = asset_frames[0]
    for df in asset_frames[1:]:
        result = result.join(df, how="outer")
    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)

    log.info("CFTC COT dataset: %d 컬럼, %d 행", len(result.columns), len(result))
    return result
