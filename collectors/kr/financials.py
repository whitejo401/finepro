"""
Korean corporate financial statements collector using dart-fss.
Covers: Balance Sheet, Income Statement, Cash Flow — and derived key ratios.

Requires DART_API_KEY in environment. If absent, all functions return empty DataFrames.
"""
from __future__ import annotations

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache
from config import DART_API_KEY

log = get_logger("kr.financials")

# 프로세스 내 종목코드 → corp_code 매핑 메모리 캐시
_CORP_CODE_MAP: dict[str, str] = {}


def get_corp_code(stock_code: str) -> str | None:
    """
    6자리 종목코드 → DART corp_code 변환.

    캐시: 프로세스 내 딕셔너리 (_CORP_CODE_MAP). DART_API_KEY 없으면 None 반환.

    Args:
        stock_code: 6자리 종목코드 (e.g. '005930')
    Returns:
        DART corp_code 문자열, 찾지 못하면 None
    """
    if not DART_API_KEY:
        log.warning("DART_API_KEY not set — cannot resolve corp_code for %s", stock_code)
        return None

    if stock_code in _CORP_CODE_MAP:
        return _CORP_CODE_MAP[stock_code]

    try:
        import dart_fss as dart
        dart.set_api_key(api_key=DART_API_KEY)

        corp_list = dart.get_corp_list()
        corp = corp_list.find_by_stock_code(stock_code)
        if corp is None:
            log.warning("no DART corp found for stock_code=%s", stock_code)
            return None

        corp_code: str = corp.corp_code
        _CORP_CODE_MAP[stock_code] = corp_code
        return corp_code

    except Exception as e:
        log.warning("dart-fss corp_code lookup failed for %s: %s", stock_code, e)
        return None


def get_financial_statements(
    ticker: str,
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    연간 재무제표 핵심 지표 수집 (dart-fss).

    추출 항목 (컬럼명 접두사: kr_fin_{ticker}_):
        total_assets     : 자산총계
        total_equity     : 자본총계
        revenue          : 매출액
        operating_income : 영업이익
        net_income       : 당기순이익

    Args:
        ticker   : 6자리 종목코드 (e.g. '005930')
        start    : 수집 시작일 'YYYY-MM-DD'
        end      : 수집 종료일 'YYYY-MM-DD', 기본값 오늘
        use_cache: True면 캐시 우선 사용
    Returns:
        DatetimeIndex (회계연도 12-31 기준), 컬럼 = kr_fin_{ticker}_{항목}
        API 키 없거나 호출 실패 시 빈 DataFrame
    """
    if not DART_API_KEY:
        log.warning("DART_API_KEY not set — returning empty DataFrame for %s", ticker)
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"dart_fs_{ticker}_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    corp_code = get_corp_code(ticker)
    if corp_code is None:
        return pd.DataFrame()

    # start를 YYYYMMDD 형식으로 변환
    bgn_de = start.replace("-", "")

    log.info("fetch dart-fss financial statements: %s (corp_code=%s, from %s)", ticker, corp_code, bgn_de)
    try:
        import dart_fss as dart
        dart.set_api_key(api_key=DART_API_KEY)

        company = dart.get_corp(corp_code=corp_code)
        fs = company.extract_fs(bgn_de=bgn_de)
    except Exception as e:
        log.warning("dart-fss extract_fs failed for %s: %s", ticker, e)
        return pd.DataFrame()

    # 항목명 → (재무제표 키, 계정과목 키워드) 매핑
    LABEL_MAP = {
        "total_assets":     ("bs", ["자산총계", "자산 총계"]),
        "total_equity":     ("bs", ["자본총계", "자본 총계"]),
        "revenue":          ("is", ["매출액", "수익(매출액)"]),
        "operating_income": ("is", ["영업이익", "영업이익(손실)"]),
        "net_income":       ("is", ["당기순이익", "당기순이익(손실)", "분기순이익"]),
    }

    records: dict[int, dict[str, float]] = {}

    for col_suffix, (fs_key, keywords) in LABEL_MAP.items():
        col_name = f"kr_fin_{ticker}_{col_suffix}"
        try:
            sheet: pd.DataFrame = fs[fs_key]
            if sheet is None or sheet.empty:
                log.warning("empty sheet '%s' for %s", fs_key, ticker)
                continue

            # dart-fss FinancialStatement 시트는 멀티인덱스 컬럼(연도/분기)을 가짐.
            # 행 인덱스에 계정과목명이 포함됨.
            matched_row = _find_row(sheet, keywords)
            if matched_row is None:
                log.warning("account not found (keywords=%s) for %s", keywords, ticker)
                continue

            for col in sheet.columns:
                year = _extract_year(col)
                if year is None:
                    continue
                val = matched_row[col]
                try:
                    val = float(str(val).replace(",", "").strip())
                except (ValueError, TypeError):
                    continue
                records.setdefault(year, {})[col_name] = val

        except Exception as e:
            log.warning("failed to extract %s for %s: %s", col_suffix, ticker, e)

    if not records:
        log.warning("no financial data extracted for %s", ticker)
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(records, orient="index")
    df.index = pd.to_datetime([f"{y}-12-31" for y in df.index])
    df.index.name = "date"
    df.sort_index(inplace=True)

    # start/end 범위 필터
    df = df.loc[start:end]

    if df.empty:
        log.warning("no data in range %s ~ %s for %s", start, end, ticker)
        return pd.DataFrame()

    if use_cache:
        save_cache(cache_key, df)
    return df


def get_key_ratios(
    ticker: str,
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    재무제표 기반 핵심 비율 계산.

    계산 항목 (컬럼명 접두사: kr_fin_{ticker}_):
        roe        : ROE = 당기순이익 / 자본총계 × 100
        roa        : ROA = 당기순이익 / 자산총계 × 100
        debt_ratio : 부채비율 = (자산총계 - 자본총계) / 자본총계 × 100
        op_margin  : 영업이익률 = 영업이익 / 매출액 × 100

    Args:
        ticker   : 6자리 종목코드
        start    : 수집 시작일 'YYYY-MM-DD'
        end      : 수집 종료일 'YYYY-MM-DD'
        use_cache: 내부 get_financial_statements 호출에 캐시 적용 여부
    Returns:
        DatetimeIndex (회계연도 12-31 기준), 빈 DataFrame on failure
    """
    fs = get_financial_statements(ticker, start, end, use_cache=use_cache)
    if fs.empty:
        log.warning("cannot compute ratios — no financial statements for %s", ticker)
        return pd.DataFrame()

    p = f"kr_fin_{ticker}_"

    def _col(suffix: str) -> pd.Series:
        name = f"{p}{suffix}"
        if name in fs.columns:
            return fs[name]
        return pd.Series(dtype=float, index=fs.index)

    total_assets = _col("total_assets")
    total_equity = _col("total_equity")
    revenue = _col("revenue")
    op_income = _col("operating_income")
    net_income = _col("net_income")

    ratios = pd.DataFrame(index=fs.index)
    ratios[f"{p}roe"] = (net_income / total_equity.replace(0, float("nan"))) * 100
    ratios[f"{p}roa"] = (net_income / total_assets.replace(0, float("nan"))) * 100
    ratios[f"{p}debt_ratio"] = (
        (total_assets - total_equity) / total_equity.replace(0, float("nan"))
    ) * 100
    ratios[f"{p}op_margin"] = (op_income / revenue.replace(0, float("nan"))) * 100

    ratios.index.name = "date"
    return ratios


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _find_row(sheet: pd.DataFrame, keywords: list[str]) -> pd.Series | None:
    """
    dart-fss 시트에서 계정과목 키워드와 일치하는 행을 반환.
    행 인덱스(또는 '계정과목' 컬럼)에서 검색.
    """
    # 인덱스 기반 검색
    for kw in keywords:
        for idx_val in sheet.index:
            if kw in str(idx_val):
                return sheet.loc[idx_val]

    # '계정과목' 컬럼이 존재하는 경우
    for candidate in ("계정과목", "account_nm"):
        if candidate in sheet.columns:
            for kw in keywords:
                mask = sheet[candidate].astype(str).str.contains(kw, na=False)
                if mask.any():
                    return sheet[mask].iloc[0]

    return None


def _extract_year(col) -> int | None:
    """
    dart-fss 컬럼값에서 회계연도(4자리 정수)를 추출.
    컬럼은 문자열('20231231'), Timestamp, tuple 등 다양한 형태일 수 있음.
    """
    col_str = str(col)
    # 'YYYY' 패턴 우선 탐색
    import re
    m = re.search(r"(20\d{2})", col_str)
    if m:
        return int(m.group(1))
    return None
