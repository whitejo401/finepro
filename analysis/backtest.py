"""
analysis/backtest.py

동일가중 교체매매 백테스팅 및 성과 지표 계산 모듈.

주요 함수:
  - calc_returns            : 일간 수익률 계산
  - backtest_equal_weight   : 동일가중 교체매매 백테스팅 (누적 수익률 반환)
  - calc_performance_metrics: 샤프 비율, MDD 등 성과 지표 계산
  - run_backtest            : 전체 백테스팅 파이프라인

주의사항:
  - 생존편향 방지: universe에 상폐 종목 데이터를 반드시 포함해야 한다.
    상폐 이전까지의 수익률 데이터를 그대로 유지하고,
    상폐 이후는 NaN으로 처리한다.
  - 룩어헤드 바이어스 방지: 신호는 signal.shift(1)로 1일 지연 적용한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from collectors.base import get_logger

log = get_logger("analysis.backtest")

# 연간 거래일 수 (성과 지표 연환산에 사용)
_TRADING_DAYS_PER_YEAR = 252


def calc_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    일간 수익률 계산.

    Args:
        prices: 날짜 × 종목 종가 DataFrame

    Returns:
        일간 수익률 DataFrame (prices.pct_change() 결과)
    """
    if prices.empty:
        log.warning("calc_returns: 빈 DataFrame 입력 — 빈 결과 반환")
        return pd.DataFrame()

    returns = prices.pct_change(fill_method=None)
    log.debug("calc_returns: shape=%s", returns.shape)
    return returns


def backtest_equal_weight(
    universe: pd.DataFrame,
    signal: pd.DataFrame,
    rebal_freq: str = "ME",
    transaction_cost: float = 0.003,
) -> pd.Series:
    """
    동일가중 교체매매 백테스팅.

    생존편향 방지 주의사항:
      - universe에 상폐 종목을 반드시 포함해야 한다.
        상폐 이전까지의 수익률은 그대로 사용하고, 이후는 NaN으로 처리한다.
        상폐 종목을 제외하면 살아남은 종목만 포함되어 성과가 과대평가된다.

    룩어헤드 바이어스 방지:
      - 리밸런싱일의 신호는 당일 수익률에 즉시 반영하지 않는다.
      - signal.shift(1) 적용으로 신호 확정 다음 날부터 포지션을 취한다.

    거래비용:
      - 리밸런싱 시 교체된 비중만큼 매수/매도 각 transaction_cost 차감.
      - 순 교체 비율(|신규 비중 - 기존 비중|의 합 / 2)에 왕복 비용 적용.

    Args:
        universe        : 날짜 × 종목 일간 수익률 DataFrame
        signal          : 날짜 × 종목 진입 신호 (True/False) DataFrame
        rebal_freq      : 리밸런싱 주기 ('ME'=월말, 'QE'=분기말)
        transaction_cost: 편도 거래비용 (기본 0.3%)

    Returns:
        누적 수익률 pd.Series (index=날짜)
    """
    if universe.empty or signal.empty:
        log.warning("backtest_equal_weight: 빈 입력 — 빈 결과 반환")
        return pd.Series(dtype=float)

    # 인덱스/컬럼 정렬
    universe = universe.sort_index()
    signal = signal.sort_index()

    # 공통 날짜 범위 확보
    common_dates = universe.index.intersection(signal.index)
    if common_dates.empty:
        log.warning("backtest_equal_weight: universe와 signal의 공통 날짜 없음")
        return pd.Series(dtype=float)

    # 공통 종목만 사용
    common_cols = universe.columns.intersection(signal.columns)
    if common_cols.empty:
        log.warning("backtest_equal_weight: universe와 signal의 공통 종목 없음")
        return pd.Series(dtype=float)

    rets = universe.loc[common_dates, common_cols]
    sig = signal.loc[common_dates, common_cols]

    # 룩어헤드 바이어스 방지: 신호를 1일 지연
    _s = sig.shift(1)
    sig_shifted = _s.where(_s.notna(), other=False).astype(bool)

    # 리밸런싱 날짜 계산
    rebal_dates = rets.resample(rebal_freq).last().index
    rebal_dates = rebal_dates[rebal_dates.isin(rets.index)]

    # 일별 포트폴리오 수익률 계산
    portfolio_returns = pd.Series(0.0, index=rets.index)
    current_weights = pd.Series(0.0, index=common_cols)

    for date in rets.index:
        # 리밸런싱 날짜이면 비중 재계산
        if date in rebal_dates:
            # 해당 날짜의 (지연된) 신호로 신규 비중 계산
            selected = sig_shifted.loc[date]
            n_selected = int(selected.sum())

            if n_selected > 0:
                new_weights = pd.Series(0.0, index=common_cols)
                new_weights[selected] = 1.0 / n_selected
            else:
                new_weights = pd.Series(0.0, index=common_cols)

            # 거래비용 계산: 순 교체 비율 × 왕복 비용
            turnover = (new_weights - current_weights).abs().sum() / 2.0
            tc = turnover * transaction_cost * 2  # 매수 + 매도

            current_weights = new_weights

            # 거래비용을 당일 수익률에서 차감
            portfolio_returns.loc[date] -= tc

        # 당일 포트폴리오 수익률
        day_rets = rets.loc[date]
        weighted_ret = (current_weights * day_rets).sum(min_count=1)
        if pd.notna(weighted_ret):
            portfolio_returns.loc[date] += weighted_ret

    # 누적 수익률
    cumulative = (1 + portfolio_returns).cumprod() - 1

    log.info(
        "backtest_equal_weight: rebal_freq=%s, transaction_cost=%.4f, "
        "종목수=%d, 기간=%s~%s, 최종누적수익률=%.4f",
        rebal_freq,
        transaction_cost,
        len(common_cols),
        rets.index.min().date(),
        rets.index.max().date(),
        cumulative.iloc[-1] if not cumulative.empty else float("nan"),
    )
    return cumulative


def calc_performance_metrics(
    returns: pd.Series,
    benchmark: pd.Series = None,
    risk_free_rate: float = 0.03,
) -> dict:
    """
    성과 지표 계산.

    Args:
        returns       : 일간 수익률 pd.Series
        benchmark     : 벤치마크 일간 수익률 pd.Series (없으면 None)
        risk_free_rate: 연간 무위험 수익률 (기본 3%)

    Returns:
        dict with keys:
          - total_return      : 누적 수익률
          - annualized_return : 연환산 수익률
          - annualized_vol    : 연환산 변동성
          - sharpe_ratio      : 샤프 비율
          - max_drawdown      : 최대 낙폭 (음수)
          - win_rate          : 승률 (수익률 > 0인 날 비율)
          - alpha             : 벤치마크 대비 초과 수익 (benchmark 없으면 None)
    """
    empty_metrics: dict = {
        "total_return": None,
        "annualized_return": None,
        "annualized_vol": None,
        "sharpe_ratio": None,
        "max_drawdown": None,
        "win_rate": None,
        "alpha": None,
    }

    if returns is None or returns.empty:
        log.warning("calc_performance_metrics: 빈 returns — 빈 결과 반환")
        return empty_metrics

    valid_rets = returns.dropna()
    if valid_rets.empty:
        log.warning("calc_performance_metrics: 모든 값이 NaN — 빈 결과 반환")
        return empty_metrics

    n = len(valid_rets)

    # 누적 수익률
    total_return = (1 + valid_rets).prod() - 1

    # 연환산 수익률
    years = n / _TRADING_DAYS_PER_YEAR
    annualized_return = (1 + total_return) ** (1.0 / years) - 1 if years > 0 else None

    # 연환산 변동성
    annualized_vol = valid_rets.std() * np.sqrt(_TRADING_DAYS_PER_YEAR)

    # 샤프 비율
    daily_rf = (1 + risk_free_rate) ** (1.0 / _TRADING_DAYS_PER_YEAR) - 1
    excess_daily = valid_rets - daily_rf
    excess_std = excess_daily.std()
    if excess_std == 0 or np.isnan(excess_std):
        sharpe_ratio = None
    else:
        sharpe_ratio = (excess_daily.mean() / excess_std) * np.sqrt(_TRADING_DAYS_PER_YEAR)

    # 최대 낙폭 (MDD)
    cumulative = (1 + valid_rets).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max).replace(0, np.nan) / rolling_max.replace(0, np.nan)
    max_drawdown = drawdown.min()
    if pd.isna(max_drawdown):
        max_drawdown = 0.0

    # 승률
    win_rate = (valid_rets > 0).mean()

    # 알파 (벤치마크 대비 초과 수익)
    alpha = None
    if benchmark is not None and not benchmark.empty:
        # 공통 날짜 기준 정렬
        common_idx = valid_rets.index.intersection(benchmark.dropna().index)
        if len(common_idx) > 0:
            port_total = (1 + valid_rets.loc[common_idx]).prod() - 1
            bench_total = (1 + benchmark.loc[common_idx]).prod() - 1
            alpha = port_total - bench_total
        else:
            log.warning("calc_performance_metrics: returns와 benchmark 공통 날짜 없음")

    metrics = {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_vol": annualized_vol,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "alpha": alpha,
    }

    log.info(
        "calc_performance_metrics: total_return=%.4f, sharpe=%.4f, mdd=%.4f",
        total_return,
        sharpe_ratio if sharpe_ratio is not None else float("nan"),
        max_drawdown,
    )
    return metrics


def run_backtest(
    master: pd.DataFrame,
    price_cols: list[str],
    signal_func,
    rebal_freq: str = "ME",
    transaction_cost: float = 0.003,
    benchmark_col: str = "kr_kospi_close",
) -> dict:
    """
    백테스팅 전체 파이프라인.

    Args:
        master          : build_master_dataset()이 반환한 master DataFrame
        price_cols      : 수익률 계산에 사용할 close 컬럼명 리스트
        signal_func     : (master: pd.DataFrame) -> pd.DataFrame 신호 생성 함수.
                          반환값은 날짜 × 종목 bool DataFrame이어야 한다.
        rebal_freq      : 리밸런싱 주기 ('ME'=월말, 'QE'=분기말)
        transaction_cost: 편도 거래비용 (기본 0.3%)
        benchmark_col   : 벤치마크로 사용할 master 컬럼명

    Returns:
        dict:
          - 'returns'             : 포트폴리오 일간 수익률 pd.Series
          - 'cumulative'          : 누적 수익률 pd.Series
          - 'benchmark_cumulative': 벤치마크 누적 수익률 pd.Series (없으면 빈 Series)
          - 'metrics'             : calc_performance_metrics 결과 dict
    """
    empty_result = {
        "returns": pd.Series(dtype=float),
        "cumulative": pd.Series(dtype=float),
        "benchmark_cumulative": pd.Series(dtype=float),
        "metrics": calc_performance_metrics(pd.Series(dtype=float)),
    }

    if master is None or master.empty:
        log.warning("run_backtest: 빈 master DataFrame — 빈 결과 반환")
        return empty_result

    # 유효한 price_cols만 필터링
    valid_price_cols = [c for c in price_cols if c in master.columns]
    if not valid_price_cols:
        log.warning("run_backtest: price_cols %s 중 master에 존재하는 컬럼 없음", price_cols)
        return empty_result

    # 1. 가격 데이터 추출 → 일간 수익률 계산
    prices = master[valid_price_cols]
    universe_returns = calc_returns(prices)

    # 2. 신호 생성
    try:
        signal = signal_func(master)
    except Exception as e:
        log.error("run_backtest: signal_func 실행 중 오류: %s", e)
        return empty_result

    if signal is None or signal.empty:
        log.warning("run_backtest: signal_func이 빈 신호 반환 — 빈 결과 반환")
        return empty_result

    # 3. 백테스팅 실행 → 누적 수익률
    cumulative = backtest_equal_weight(
        universe=universe_returns,
        signal=signal,
        rebal_freq=rebal_freq,
        transaction_cost=transaction_cost,
    )

    if cumulative.empty:
        return empty_result

    # 누적 수익률에서 일간 수익률 역산
    portfolio_returns = cumulative.diff()
    portfolio_returns.iloc[0] = cumulative.iloc[0]

    # 4. 벤치마크 처리
    benchmark_returns: pd.Series | None = None
    benchmark_cumulative = pd.Series(dtype=float)

    if benchmark_col and benchmark_col in master.columns:
        bench_prices = master[benchmark_col].dropna()
        benchmark_returns = bench_prices.pct_change().dropna()
        benchmark_cumulative = (1 + benchmark_returns).cumprod() - 1
        log.info(
            "run_backtest: 벤치마크=%r, 기간=%s~%s",
            benchmark_col,
            benchmark_cumulative.index.min().date() if not benchmark_cumulative.empty else "N/A",
            benchmark_cumulative.index.max().date() if not benchmark_cumulative.empty else "N/A",
        )
    else:
        if benchmark_col:
            log.warning("run_backtest: benchmark_col=%r 이 master에 없음", benchmark_col)

    # 5. 성과 지표 계산
    metrics = calc_performance_metrics(
        returns=portfolio_returns,
        benchmark=benchmark_returns,
        risk_free_rate=0.03,
    )

    log.info(
        "run_backtest: 완료 — 누적수익률=%.4f, 샤프=%.4f, MDD=%.4f",
        cumulative.iloc[-1] if not cumulative.empty else float("nan"),
        metrics["sharpe_ratio"] if metrics["sharpe_ratio"] is not None else float("nan"),
        metrics["max_drawdown"] if metrics["max_drawdown"] is not None else float("nan"),
    )

    return {
        "returns": portfolio_returns,
        "cumulative": cumulative,
        "benchmark_cumulative": benchmark_cumulative,
        "metrics": metrics,
    }
