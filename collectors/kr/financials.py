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

# 프로세스 내 종목코드 → corp_code 문자열 캐시
_CORP_CODE_MAP: dict[str, str] = {}
# 프로세스 내 종목코드 → Corp 객체 캐시 (extract_fs 호출용)
_CORP_OBJ_MAP: dict = {}


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
        result = corp_list.find_by_stock_code(stock_code)
        if not result:
            log.warning("no DART corp found for stock_code=%s", stock_code)
            return None

        # find_by_stock_code는 버전에 따라 Corp 또는 list[Corp] 반환
        corp = result[0] if isinstance(result, list) else result
        corp_code: str = corp.corp_code
        _CORP_CODE_MAP[stock_code] = corp_code
        _CORP_OBJ_MAP[stock_code] = corp
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

        company = _CORP_OBJ_MAP.get(ticker)
        if company is None:
            result = dart.get_corp_list().find_by_stock_code(ticker)
            if not result:
                log.warning("Corp object not found for %s", ticker)
                return pd.DataFrame()
            company = result[0] if isinstance(result, list) else result
            _CORP_OBJ_MAP[ticker] = company

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

            year_vals = _extract_from_sheet(sheet, keywords)
            if not year_vals:
                log.warning("account not found (keywords=%s) for %s", keywords, ticker)
                continue

            for year, val in year_vals.items():
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

_META_FIELDS = frozenset(
    {"concept_id", "label_ko", "label_en", "class0", "class1", "class2", "class3", "class4"}
)


def _extract_from_sheet(sheet: pd.DataFrame, keywords: list[str]) -> dict[int, float]:
    """
    dart-fss MultiIndex 컬럼 시트에서 키워드에 해당하는 계정과목의 연도별 값을 추출.

    컬럼 구조: (date_str 'YYYYMMDD' | stmt_name, sub_field)
    계정과목명은 sub_field == 'label_ko' 컬럼에 위치.

    Returns:
        {연도(int): 값(float)} 딕셔너리. 매칭 실패 시 빈 딕셔너리.
    """
    # label_ko 컬럼 탐색
    label_ko_col = next((c for c in sheet.columns if c[1] == "label_ko"), None)
    if label_ko_col is None:
        return {}

    # 키워드로 행 탐색
    row = None
    for kw in keywords:
        mask = sheet[label_ko_col].astype(str).str.contains(kw, na=False)
        if mask.any():
            row = sheet[mask].iloc[0]
            break

    if row is None:
        return {}

    # 연도별 값 수집 (메타 컬럼 제외)
    # BS: 'YYYYMMDD' (단일 날짜) / IS: 'YYYYMMDD-YYYYMMDD' (기간)
    result: dict[int, float] = {}
    for col in sheet.columns:
        if col[1] in _META_FIELDS:
            continue
        date_str = col[0]
        if not isinstance(date_str, str):
            continue
        # 두 가지 날짜 형식 모두 처리
        if len(date_str) == 8 and date_str.isdigit():
            year = int(date_str[:4])   # BS: '20251231'
        elif len(date_str) == 17 and date_str[8] == '-' and date_str[:8].isdigit():
            year = int(date_str[9:13]) # IS: '20250101-20251231' → 종료연도
        else:
            continue
        try:
            val = float(str(row[col]).replace(",", "").strip())
            if not pd.isna(val):
                result[year] = val
        except (ValueError, TypeError):
            pass

    return result
