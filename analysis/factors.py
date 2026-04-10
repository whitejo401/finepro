"""
팩터 분석 모듈.

S-RIM 적정가 산출, Spearman 팩터 상관계수, 저평가 종목 스크리닝을 제공한다.
컬럼 네이밍 컨벤션은 kr_fin_{ticker}_per / _pbr / _roe, kr_{ticker}_close를 따른다.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy import stats

from collectors.base import get_logger

log = get_logger("analysis.factors")


# ---------------------------------------------------------------------------
# S-RIM 적정가
# ---------------------------------------------------------------------------

def calc_intrinsic_value(
    equity: float,
    roe: float,
    required_return: float = 0.10,
) -> float:
    """
    S-RIM 적정가.

    적정가 = 자기자본 × ROE / 요구수익률
    roe가 0 이하이거나 required_return이 0이면 NaN 반환.
    """
    if roe <= 0 or required_return == 0:
        return float("nan")
    return equity * roe / required_return


def calc_intrinsic_value_series(
    equity_series: pd.Series,
    roe_series: pd.Series,
    required_return: float = 0.10,
) -> pd.Series:
    """
    Series 버전. 날짜별 S-RIM 적정가 계산.

    roe <= 0 또는 required_return == 0인 항목은 NaN.
    """
    if equity_series.empty or roe_series.empty:
        return pd.Series(dtype=float)

    if required_return == 0:
        log.warning("required_return=0, returning NaN series")
        return pd.Series(np.nan, index=equity_series.index)

    aligned_equity, aligned_roe = equity_series.align(roe_series, join="inner")
    result = aligned_equity * aligned_roe / required_return
    result[aligned_roe <= 0] = np.nan
    result.name = "intrinsic_value"
    return result


# ---------------------------------------------------------------------------
# 팩터 상관계수
# ---------------------------------------------------------------------------

def factor_spearman(
    factor_series: pd.Series,
    return_series: pd.Series,
) -> dict:
    """
    팩터와 미래 수익률 간 Spearman 상관계수.

    Returns:
        {'spearman': float, 'p_value': float, 'n': int}
        입력이 비어 있거나 유효 관측치가 2개 미만이면 NaN/0 반환.
    """
    if factor_series.empty or return_series.empty:
        return {"spearman": float("nan"), "p_value": float("nan"), "n": 0}

    combined = pd.concat([factor_series, return_series], axis=1).dropna()
    n = len(combined)
    if n < 2:
        return {"spearman": float("nan"), "p_value": float("nan"), "n": n}

    rho, p = stats.spearmanr(combined.iloc[:, 0], combined.iloc[:, 1])
    return {"spearman": float(rho), "p_value": float(p), "n": n}


def factor_correlation_table(
    factor_df: pd.DataFrame,
    return_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    팩터별 × 수익률기간별 Spearman 상관계수 테이블.

    index=팩터명, columns=수익률 기간, 값=상관계수 문자열.
    p < 0.05이면 '*' 접미사 표시.
    빈 입력이면 빈 DataFrame 반환.
    """
    if factor_df.empty or return_df.empty:
        return pd.DataFrame()

    records: dict[str, dict[str, str]] = {}
    for factor_col in factor_df.columns:
        row: dict[str, str] = {}
        for ret_col in return_df.columns:
            res = factor_spearman(factor_df[factor_col], return_df[ret_col])
            rho = res["spearman"]
            if np.isnan(rho):
                row[ret_col] = "NaN"
            else:
                marker = "*" if res["p_value"] < 0.05 else ""
                row[ret_col] = f"{rho:.3f}{marker}"
        records[factor_col] = row

    result = pd.DataFrame.from_dict(records, orient="index")
    result.index.name = "factor"
    return result


# ---------------------------------------------------------------------------
# 저평가 종목 스크리닝
# ---------------------------------------------------------------------------

def _extract_ticker(col: str, prefix: str) -> str | None:
    """컬럼명에서 티커 추출. e.g. 'kr_fin_005930_per' -> '005930'"""
    pattern = rf"^{re.escape(prefix)}(.+)_(?:per|pbr|roe|div)$"
    m = re.match(pattern, col)
    return m.group(1) if m else None


def screen_undervalued(
    fundamental_df: pd.DataFrame,
    price_df: pd.DataFrame,
    per_threshold: float = 15.0,
    pbr_threshold: float = 1.5,
    roe_min: float = 0.08,
    equity_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    저평가 종목 스크리닝.

    조건: PER < per_threshold AND PBR < pbr_threshold AND ROE > roe_min
    equity_df가 있으면 S-RIM 괴리율(=(현재가 - 적정가) / 적정가)도 추가.

    fundamental_df 컬럼 형식: kr_fin_{ticker}_per, kr_fin_{ticker}_pbr, kr_fin_{ticker}_roe
    price_df 컬럼 형식: kr_{ticker}_close
    equity_df 컬럼 형식: kr_fin_{ticker}_equity (자기자본, 주당)

    Returns:
        조건 충족 종목 DataFrame. 컬럼: ticker, per, pbr, roe, price, [intrinsic, gap_pct]
        빈 입력이면 빈 DataFrame 반환.
    """
    if fundamental_df.empty or price_df.empty:
        return pd.DataFrame()

    # 최신 행(마지막 유효 데이터)
    fund_last = fundamental_df.ffill().iloc[-1]
    price_last = price_df.ffill().iloc[-1]
    equity_last = equity_df.ffill().iloc[-1] if equity_df is not None and not equity_df.empty else None

    # fundamental_df에서 티커 목록 수집
    tickers: set[str] = set()
    for col in fundamental_df.columns:
        t = _extract_ticker(col, "kr_fin_")
        if t:
            tickers.add(t)

    if not tickers:
        log.warning("fundamental_df에서 티커를 추출할 수 없습니다. 컬럼명을 확인하세요.")
        return pd.DataFrame()

    rows = []
    for ticker in sorted(tickers):
        per_col = f"kr_fin_{ticker}_per"
        pbr_col = f"kr_fin_{ticker}_pbr"
        roe_col = f"kr_fin_{ticker}_roe"
        price_col = f"kr_{ticker}_close"

        # 필수 컬럼 존재 여부 확인
        if per_col not in fund_last.index or pbr_col not in fund_last.index:
            log.debug("티커 %s: per/pbr 컬럼 없음, 건너뜀", ticker)
            continue
        if roe_col not in fund_last.index:
            log.debug("티커 %s: roe 컬럼 없음, 건너뜀", ticker)
            continue
        if price_col not in price_last.index:
            log.debug("티커 %s: price 컬럼 없음, 건너뜀", ticker)
            continue

        per = fund_last[per_col]
        pbr = fund_last[pbr_col]
        roe = fund_last[roe_col]
        price = price_last[price_col]

        # NaN 건너뜀
        if any(pd.isna(v) for v in [per, pbr, roe, price]):
            continue

        # 스크리닝 조건
        if not (per < per_threshold and pbr < pbr_threshold and roe > roe_min):
            continue

        row: dict = {
            "ticker": ticker,
            "per": per,
            "pbr": pbr,
            "roe": roe,
            "price": price,
        }

        # S-RIM 괴리율 계산
        if equity_last is not None:
            equity_col = f"kr_fin_{ticker}_equity"
            if equity_col in equity_last.index:
                equity = equity_last[equity_col]
                if not pd.isna(equity):
                    intrinsic = calc_intrinsic_value(equity, roe)
                    row["intrinsic"] = intrinsic
                    if not np.isnan(intrinsic) and intrinsic != 0:
                        row["gap_pct"] = (price - intrinsic) / intrinsic
                    else:
                        row["gap_pct"] = float("nan")

        rows.append(row)

    if not rows:
        log.info("조건을 충족하는 종목이 없습니다.")
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    return result.reset_index(drop=True)
