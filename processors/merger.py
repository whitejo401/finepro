"""
processors/merger.py

여러 collector의 DataFrame을 날짜 인덱스 기준으로 병합해
data/processed/master_{start}_{end}.parquet 파일을 생성하는 모듈.

주요 함수:
  - merge_dataframes : DataFrame 리스트 → outer join + ffill/bfill
  - build_master_dataset : 전체 파이프라인 실행 (수집 → 병합 → 저장)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import pandas as pd

from collectors.base import get_logger
from config import PROCESSED_DIR, DEFAULT_START

log = get_logger("processors.merger")

# 룩어헤드 바이어스 방지: master에 포함되지만 피처로 사용 금지인 타겟 컬럼
# shift(-1) 을 사용해 미래 값을 참조하므로 예측 피처·백테스트 신호에서 반드시 제외
TARGET_COLS: frozenset[str] = frozenset({"kr_kospi_gap"})

# 기본 수집 대상
_DEFAULT_TICKERS_KR = ["005930", "000660", "035420"]  # 삼성전자, SK하이닉스, NAVER
_DEFAULT_TICKERS_GLOBAL = [
    "us_sp500", "kr_kospi", "cmd_wti", "cmd_gold",
    "fx_krw_usd", "fx_dxy", "alt_vix", "rate_us10y",
]


# ---------------------------------------------------------------------------
# 공개 인터페이스
# ---------------------------------------------------------------------------

def process(df: pd.DataFrame, **options) -> pd.DataFrame:
    """
    단일 DataFrame에 표준 후처리를 적용한다 (인터페이스 계약 준수).

    options:
        ffill_limit (int): forward-fill 최대 연속 채움 수 (기본 5)
        bfill_limit (int): backward-fill 최대 연속 채움 수 (기본 1)
    """
    ffill_limit: int = options.get("ffill_limit", 5)
    bfill_limit: int = options.get("bfill_limit", 1)

    if df.empty:
        log.warning("process() received an empty DataFrame")
        return df

    df = df.sort_index()
    df = df.ffill(limit=ffill_limit)
    df = df.bfill(limit=bfill_limit)
    return df


def merge_dataframes(
    dfs: list[pd.DataFrame],
    how: str = "outer",
) -> pd.DataFrame:
    """
    여러 DataFrame을 날짜 인덱스 기준으로 병합한다.

    동작:
      1. 빈 DataFrame은 건너뜀 (경고 로그 출력)
      2. how 방식으로 순차 join
      3. 중복 컬럼명 발생 시 경고 로그 후 `_dup` suffix 부여하여 유지
      4. outer join 결과에 ffill(limit=5) → bfill(limit=1) 적용

    Args:
        dfs: 병합할 DataFrame 리스트. 각 DataFrame은 DatetimeIndex를 가져야 함.
        how: pandas merge how 파라미터 ('outer', 'inner', 'left', 'right')

    Returns:
        병합된 DataFrame (DatetimeIndex, name='date')
    """
    valid: list[pd.DataFrame] = []
    for i, df in enumerate(dfs):
        if df is None or df.empty:
            log.warning("merge_dataframes: index=%d is empty, skipping", i)
            continue
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df = df.copy()
                df.index = pd.to_datetime(df.index)
                df.index.name = "date"
            except Exception as e:
                log.warning(
                    "merge_dataframes: index=%d cannot convert to DatetimeIndex: %s", i, e
                )
                continue
        valid.append(df)

    if not valid:
        log.warning("merge_dataframes: all DataFrames are empty, returning empty DataFrame")
        return pd.DataFrame()

    merged = valid[0]
    for df in valid[1:]:
        # 중복 컬럼 처리: combine_first로 빈 값 보완 후 병합
        overlap = set(merged.columns) & set(df.columns)
        if overlap:
            log.info(
                "merge_dataframes: duplicate columns %s — combine_first 적용 (기존 값 우선)",
                sorted(overlap),
            )
            # 중복 컬럼은 combine_first로 결합 (merged 값 우선, 없으면 df 값 사용)
            for col in overlap:
                merged[col] = merged[col].combine_first(df[col])
            # 중복 컬럼 제외한 나머지만 join
            df = df.drop(columns=list(overlap))

        if df.empty:
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            merged = merged.join(df, how=how)

    merged = merged.sort_index()
    merged.index.name = "date"

    # 중복 날짜 제거 (같은 날짜 인덱스가 여러 번 있으면 첫 번째만 유지)
    if merged.index.duplicated().any():
        n_dup = merged.index.duplicated().sum()
        log.warning("merge_dataframes: 날짜 인덱스 중복 %d건 — 첫 번째 값 유지", n_dup)
        merged = merged[~merged.index.duplicated(keep="first")]

    # 결측값 채움: 일간은 5일(주말), 월간/분기 지표는 최대 66일(분기~3개월) 허용
    merged = merged.ffill(limit=66)
    merged = merged.bfill(limit=1)

    # 파생 컬럼 추가
    merged = _add_derived_columns(merged)

    return merged


def _add_derived_columns(master: pd.DataFrame) -> pd.DataFrame:
    """
    병합 후 파생 컬럼을 추가한다.

    kr_kospi_gap : 다음 거래일 KOSPI 갭 (open[T+1] / close[T] - 1)
                   D-4/D-5 리포트의 갭 예측 타겟 변수로 사용.
    """
    # KOSPI 갭: yfinance KOSPI open/close 컬럼 존재 시 계산
    open_col  = "kr_kospi_open"
    close_col = "kr_kospi_close"
    if open_col in master.columns and close_col in master.columns:
        master = master.copy()
        # shift(-1): 오늘 close 대비 내일 open 수익률
        master["kr_kospi_gap"] = (
            master[open_col].shift(-1) / master[close_col] - 1
        )
        log.info("_add_derived_columns: kr_kospi_gap 추가")

    return master


def build_master_dataset(
    start: str = DEFAULT_START,
    end: Optional[str] = None,
    tickers_kr: Optional[list[str]] = None,
    tickers_global: Optional[list[str]] = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    전체 파이프라인을 실행하여 master parquet을 생성한다.

    순서:
      1. collectors에서 데이터 수집 (각 호출은 try-except로 보호)
      2. merge_dataframes로 병합
      3. data/processed/master_{start}_{end}.parquet 저장 후 반환

    이미 해당 parquet이 존재하면 바로 로드하여 반환한다 (use_cache=True 시).

    Args:
        start        : 수집 시작일 'YYYY-MM-DD'
        end          : 수집 종료일 'YYYY-MM-DD', None이면 오늘
        tickers_kr   : pykrx 6자리 종목코드 리스트
        tickers_global: collectors/global_/market.py TICKERS의 key 리스트
        use_cache    : True면 기존 master parquet 존재 시 재사용

    Returns:
        병합된 master DataFrame
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    tickers_kr = tickers_kr if tickers_kr is not None else _DEFAULT_TICKERS_KR
    tickers_global = tickers_global if tickers_global is not None else _DEFAULT_TICKERS_GLOBAL

    # ── 캐시 확인 ──────────────────────────────────────────────────────────
    out_path = PROCESSED_DIR / f"master_{start}_{end}.parquet"
    if use_cache and out_path.exists():
        log.info("build_master_dataset: loading cached master from %s", out_path)
        return pd.read_parquet(out_path)

    dfs: list[pd.DataFrame] = []

    # ── 글로벌 시장 데이터 (close 가격) ────────────────────────────────────
    if tickers_global:
        try:
            from collectors.global_.market import get_prices  # noqa: PLC0415
            df_global = get_prices(tickers_global, start=start, end=end, use_cache=use_cache)
            dfs.append(df_global)
            log.info("build_master_dataset: global prices shape=%s", df_global.shape)
        except Exception as e:
            log.warning("build_master_dataset: global prices failed: %s", e)

    # ── 국내 주식 OHLCV + 펀더멘털 ─────────────────────────────────────────
    for ticker in tickers_kr:
        # OHLCV
        try:
            from collectors.kr.stock import get_ohlcv  # noqa: PLC0415
            df_ohlcv = get_ohlcv(ticker, start=start, end=end, use_cache=use_cache)
            dfs.append(df_ohlcv)
            log.info(
                "build_master_dataset: kr ohlcv %s shape=%s", ticker, df_ohlcv.shape
            )
        except Exception as e:
            log.warning("build_master_dataset: kr ohlcv %s failed: %s", ticker, e)

        # 펀더멘털 (PER/PBR/DIV)
        try:
            from collectors.kr.stock import get_fundamental  # noqa: PLC0415
            df_fund = get_fundamental(ticker, start=start, end=end, use_cache=use_cache)
            dfs.append(df_fund)
            log.info(
                "build_master_dataset: kr fundamental %s shape=%s", ticker, df_fund.shape
            )
        except Exception as e:
            log.warning(
                "build_master_dataset: kr fundamental %s failed: %s", ticker, e
            )

    # ── 병합 ───────────────────────────────────────────────────────────────
    master = merge_dataframes(dfs, how="outer")

    if master.empty:
        log.warning(
            "build_master_dataset: resulting master DataFrame is empty — check collectors"
        )
        return master

    log.info(
        "build_master_dataset: master shape=%s  date_range=[%s, %s]",
        master.shape,
        master.index.min().date() if not master.empty else "N/A",
        master.index.max().date() if not master.empty else "N/A",
    )

    # ── 저장 ───────────────────────────────────────────────────────────────
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    master.to_parquet(out_path)
    log.info("build_master_dataset: saved to %s", out_path)

    return master
