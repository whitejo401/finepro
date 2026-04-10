"""
visualization/charts.py

plotly 기반 차트 함수 모음.
모든 함수는 go.Figure를 반환한다.
"""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from collectors.base import get_logger

log = get_logger("visualization.charts")

# 컬럼 suffix 패턴: _close, _open, _high, _low, _volume, _adj_close 등
_SUFFIX_RE = re.compile(r"_(close|open|high|low|volume|adj_close)$", re.IGNORECASE)


def _clean_label(col: str) -> str:
    """컬럼명에서 OHLCV suffix를 제거해 레이블을 정리한다."""
    return _SUFFIX_RE.sub("", col)


# ---------------------------------------------------------------------------
# plot_correlation_heatmap
# ---------------------------------------------------------------------------

def plot_correlation_heatmap(
    df: pd.DataFrame,
    title: str,
    **options,
) -> go.Figure:
    """
    Spearman(기본) 또는 Pearson 상관관계 히트맵.

    options:
        method (str): 'spearman' | 'pearson'  (기본 'spearman')
    """
    if df.empty:
        log.warning("plot_correlation_heatmap: empty DataFrame, returning empty Figure")
        return go.Figure()

    method: str = options.get("method", "spearman")

    numeric = df.select_dtypes(include="number").dropna(axis=1, how="all")
    if numeric.empty:
        log.warning("plot_correlation_heatmap: no numeric columns")
        return go.Figure()

    corr = numeric.corr(method=method)

    labels = [_clean_label(c) for c in corr.columns]

    # 셀 텍스트: 소수점 2자리
    text = corr.round(2).astype(str).values.tolist()

    fig = go.Figure(
        go.Heatmap(
            z=corr.values,
            x=labels,
            y=labels,
            text=text,
            texttemplate="%{text}",
            colorscale="RdBu_r",
            zmin=-1,
            zmax=1,
            colorbar=dict(title="ρ"),
        )
    )
    fig.update_layout(
        title=title,
        xaxis=dict(tickangle=-45, tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
        margin=dict(l=120, r=40, t=80, b=120),
    )
    return fig


# ---------------------------------------------------------------------------
# plot_cumulative_returns
# ---------------------------------------------------------------------------

def plot_cumulative_returns(
    returns_dict: dict[str, pd.Series],
    title: str,
    **options,
) -> go.Figure:
    """
    여러 자산의 누적 수익률 비교 라인 차트.

    options:
        benchmark_key (str): 이 키에 해당하는 시리즈를 점선으로 표시
    """
    if not returns_dict:
        log.warning("plot_cumulative_returns: empty returns_dict, returning empty Figure")
        return go.Figure()

    benchmark_key: str | None = options.get("benchmark_key", None)

    fig = go.Figure()

    for name, series in returns_dict.items():
        if series is None or series.dropna().empty:
            log.warning("plot_cumulative_returns: '%s' is empty, skipping", name)
            continue

        cum = (1 + series).cumprod()
        # 첫 유효값 기준 1.0 정규화
        first_valid = cum.first_valid_index()
        if first_valid is not None:
            cum = cum / cum[first_valid]

        is_benchmark = (name == benchmark_key)
        fig.add_trace(
            go.Scatter(
                x=cum.index,
                y=cum.values,
                mode="lines",
                name=name,
                line=dict(dash="dash" if is_benchmark else "solid"),
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Cumulative Return (base=1)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ---------------------------------------------------------------------------
# plot_rolling_correlation
# ---------------------------------------------------------------------------

def plot_rolling_correlation(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int = 60,
    title: str = "",
    **options,
) -> go.Figure:
    """
    두 시리즈의 Rolling Spearman 상관계수 라인 차트.

    scipy.stats.spearmanr 를 rolling window에 적용한다.
    x축: 날짜, y축: 상관계수 (-1 ~ 1), 0 기준선 포함.
    """
    if series_a.dropna().empty or series_b.dropna().empty:
        log.warning("plot_rolling_correlation: one or both series are empty")
        return go.Figure()

    # 공통 인덱스 정렬
    combined = pd.concat([series_a.rename("a"), series_b.rename("b")], axis=1).dropna()
    if len(combined) < window:
        log.warning(
            "plot_rolling_correlation: not enough data (%d rows) for window=%d",
            len(combined), window,
        )
        return go.Figure()

    def _spearman(sub: pd.DataFrame) -> float:
        rho, _ = stats.spearmanr(sub["a"], sub["b"])
        return float(rho)

    rolling_corr = combined.rolling(window).apply(
        lambda _: None  # placeholder — 아래에서 수동 계산
    )["a"]  # 사용하지 않음

    # rolling spearman 수동 계산 (pandas rolling은 spearman 미지원)
    rho_values: list[float | None] = [None] * (window - 1)
    for i in range(window - 1, len(combined)):
        sub = combined.iloc[i - window + 1 : i + 1]
        rho, _ = stats.spearmanr(sub["a"], sub["b"])
        rho_values.append(float(rho))

    rho_series = pd.Series(rho_values, index=combined.index)

    name_a = series_a.name or "A"
    name_b = series_b.name or "B"
    display_title = title or f"Rolling {window}d Spearman: {name_a} vs {name_b}"

    fig = go.Figure()

    # 0 기준선
    fig.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)

    fig.add_trace(
        go.Scatter(
            x=rho_series.index,
            y=rho_series.values,
            mode="lines",
            name=f"ρ ({window}d)",
            line=dict(color="#1f77b4"),
        )
    )

    fig.update_layout(
        title=display_title,
        xaxis_title="Date",
        yaxis=dict(title="Spearman ρ", range=[-1.05, 1.05]),
        hovermode="x unified",
    )
    return fig


# ---------------------------------------------------------------------------
# plot_factor_distribution
# ---------------------------------------------------------------------------

def plot_factor_distribution(
    df: pd.DataFrame,
    factor: str,
    sector_col: str | None = None,
    title: str = "",
) -> go.Figure:
    """
    팩터 분포 박스플롯.
    sector_col 지정 시 섹터별, 없으면 전체 분포.
    """
    if df.empty:
        log.warning("plot_factor_distribution: empty DataFrame")
        return go.Figure()

    if factor not in df.columns:
        log.warning("plot_factor_distribution: factor '%s' not in DataFrame columns", factor)
        return go.Figure()

    display_title = title or f"Distribution of {_clean_label(factor)}"
    fig = go.Figure()

    if sector_col and sector_col in df.columns:
        sectors = sorted(df[sector_col].dropna().unique())
        for sector in sectors:
            subset = df.loc[df[sector_col] == sector, factor].dropna()
            fig.add_trace(
                go.Box(
                    y=subset.values,
                    name=str(sector),
                    boxpoints="outliers",
                )
            )
        fig.update_layout(
            title=display_title,
            xaxis_title=sector_col,
            yaxis_title=_clean_label(factor),
        )
    else:
        values = df[factor].dropna()
        fig.add_trace(
            go.Box(
                y=values.values,
                name=_clean_label(factor),
                boxpoints="outliers",
            )
        )
        fig.update_layout(
            title=display_title,
            yaxis_title=_clean_label(factor),
        )

    return fig
