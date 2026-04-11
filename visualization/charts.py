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

# D-1 일간 시황에 사용할 기본 컬럼 (우선순위 순)
_DAILY_COLS = [
    "us_sp500_close", "us_nasdaq_close", "kr_kospi_close",
    "cmd_wti_close", "cmd_gold_close", "fx_krw_usd_close",
    "crypto_btc_close", "crypto_eth_close",
]

# 국면별 색상
_REGIME_COLORS: dict[str, str] = {
    "reflation":   "#2ecc71",  # 초록 — 성장 회복
    "overheat":    "#e67e22",  # 주황 — 과열
    "stagflation": "#e74c3c",  # 빨강 — 스태그플레이션
    "deflation":   "#3498db",  # 파랑 — 디플레이션
}


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

    # rolling spearman 수동 계산 (pandas rolling은 spearman 미지원)
    import math
    rho_values: list[float] = [math.nan] * (window - 1)
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
# plot_daily_returns
# ---------------------------------------------------------------------------

def plot_daily_returns(
    master: pd.DataFrame,
    date: str | None = None,
    cols: list[str] | None = None,
) -> go.Figure:
    """
    지정 날짜의 전일 대비 등락률 수평 바 차트 (D-1 일간 시황용).

    Args:
        master: DatetimeIndex DataFrame
        date  : 'YYYY-MM-DD', None이면 마지막 유효일
        cols  : 대상 컬럼 리스트, None이면 _DAILY_COLS 기본값
    Returns:
        go.Figure — 수평 막대 차트, 양수=초록, 음수=빨강
    """
    if master.empty:
        log.warning("plot_daily_returns: 빈 DataFrame")
        return go.Figure()

    target_cols = [c for c in (cols or _DAILY_COLS) if c in master.columns]
    if not target_cols:
        log.warning("plot_daily_returns: 대상 컬럼 없음")
        return go.Figure()

    df = master[target_cols].dropna(how="all")
    if df.empty:
        return go.Figure()

    # 기준일 결정
    if date is not None:
        ts = pd.Timestamp(date)
        available = df.index[df.index <= ts]
        if available.empty:
            log.warning("plot_daily_returns: %s 이전 데이터 없음", date)
            return go.Figure()
        ref_date = available[-1]
    else:
        ref_date = df.index[-1]

    # 전일 찾기
    prev_dates = df.index[df.index < ref_date]
    if prev_dates.empty:
        log.warning("plot_daily_returns: 전일 데이터 없음 (ref=%s)", ref_date.date())
        return go.Figure()
    prev_date = prev_dates[-1]

    curr = df.loc[ref_date]
    prev = df.loc[prev_date]
    rets = ((curr - prev) / prev.abs()).dropna() * 100  # %

    if rets.empty:
        return go.Figure()

    labels = [_clean_label(c) for c in rets.index]
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in rets.values]
    text = [f"{v:+.2f}%" for v in rets.values]

    fig = go.Figure(go.Bar(
        x=rets.values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=text,
        textposition="outside",
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))

    fig.update_layout(
        title=f"자산별 등락률 — {ref_date.date()} (전일 대비)",
        xaxis=dict(title="%", zeroline=True, zerolinecolor="#bdc3c7", zerolinewidth=1),
        yaxis=dict(autorange="reversed"),
        margin=dict(l=120, r=80, t=60, b=40),
        height=max(300, len(labels) * 40),
    )
    return fig


# ---------------------------------------------------------------------------
# plot_regime_timeline
# ---------------------------------------------------------------------------

def plot_regime_timeline(
    regime_series: pd.Series,
    title: str = "매크로 국면 타임라인",
) -> go.Figure:
    """
    국면 히스토리를 구간별 컬러 바로 표시 (W-2, M-1 국면 섹션용).

    Args:
        regime_series: classify_regime() 반환값 (DatetimeIndex, 국면명 문자열)
        title        : 차트 제목
    Returns:
        go.Figure — 국면별 색상 구간 바 + 범례
    """
    valid = regime_series.dropna()
    if valid.empty:
        log.warning("plot_regime_timeline: 유효한 국면 데이터 없음")
        return go.Figure()

    # 연속 구간 계산
    segments: list[dict] = []
    prev_regime = None
    seg_start = None

    for ts, regime in valid.items():
        if regime != prev_regime:
            if prev_regime is not None:
                segments.append({"regime": prev_regime, "start": seg_start, "end": ts})
            prev_regime = regime
            seg_start = ts
    if prev_regime is not None:
        segments.append({"regime": prev_regime, "start": seg_start, "end": valid.index[-1]})

    fig = go.Figure()

    # 이미 추가된 범례 항목 추적 (중복 방지)
    shown_legends: set[str] = set()

    for seg in segments:
        regime = seg["regime"]
        color = _REGIME_COLORS.get(regime, "#95a5a6")
        show_legend = regime not in shown_legends
        shown_legends.add(regime)

        fig.add_trace(go.Scatter(
            x=[seg["start"], seg["end"], seg["end"], seg["start"], seg["start"]],
            y=[0, 0, 1, 1, 0],
            fill="toself",
            fillcolor=color,
            line=dict(width=0),
            mode="lines",
            name=regime,
            legendgroup=regime,
            showlegend=show_legend,
            opacity=0.7,
            hovertemplate=(
                f"<b>{regime}</b><br>"
                f"{seg['start'].strftime('%Y-%m-%d')} ~ {seg['end'].strftime('%Y-%m-%d')}"
                "<extra></extra>"
            ),
        ))

    # 현재 국면 텍스트 주석
    current_regime = valid.iloc[-1]
    current_color = _REGIME_COLORS.get(current_regime, "#95a5a6")
    fig.add_annotation(
        x=valid.index[-1], y=1.15,
        text=f"현재: <b>{current_regime}</b>",
        showarrow=False,
        font=dict(size=13, color=current_color),
        xanchor="right",
    )

    fig.update_layout(
        title=title,
        xaxis=dict(title="날짜"),
        yaxis=dict(visible=False, range=[-0.2, 1.4]),
        hovermode="x",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0),
        margin=dict(l=40, r=40, t=80, b=40),
        height=200,
    )
    return fig


# ---------------------------------------------------------------------------
# plot_gauge
# ---------------------------------------------------------------------------

_GAUGE_STEPS = [
    {"range": [0, 20],  "color": "#e74c3c"},
    {"range": [20, 40], "color": "#e67e22"},
    {"range": [40, 60], "color": "#f1c40f"},
    {"range": [60, 80], "color": "#2ecc71"},
    {"range": [80, 100],"color": "#27ae60"},
]


def plot_gauge(
    value: float,
    title: str,
    low_label: str = "극공포",
    high_label: str = "극탐욕",
) -> go.Figure:
    """
    0~100 반원형 게이지 차트.

    Args:
        value     : 0~100 사이 값 (감성 점수는 호출 전 변환 필요)
        title     : 게이지 제목
        low_label : 0 쪽 레이블
        high_label: 100 쪽 레이블
    Returns:
        go.Figure (indicator gauge)
    """
    value = float(max(0.0, min(100.0, value)))

    if value < 20:
        level, needle_color = low_label, "#e74c3c"
    elif value < 40:
        level, needle_color = "부정", "#e67e22"
    elif value < 60:
        level, needle_color = "중립", "#f1c40f"
    elif value < 80:
        level, needle_color = "긍정", "#2ecc71"
    else:
        level, needle_color = high_label, "#27ae60"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={"text": f"{title}<br><span style='font-size:0.8em;color:{needle_color}'>{level}</span>"},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#7f8c8d"},
            "bar": {"color": needle_color, "thickness": 0.25},
            "bgcolor": "white",
            "borderwidth": 1,
            "bordercolor": "#bdc3c7",
            "steps": _GAUGE_STEPS,
            "threshold": {
                "line": {"color": "#2c3e50", "width": 3},
                "thickness": 0.75,
                "value": value,
            },
        },
        number={"suffix": "", "font": {"size": 28}},
    ))

    fig.update_layout(
        margin=dict(l=20, r=20, t=60, b=10),
        height=220,
        annotations=[
            dict(x=0.05, y=0.1, text=low_label, showarrow=False,
                 font=dict(size=11, color="#e74c3c"), xref="paper", yref="paper"),
            dict(x=0.95, y=0.1, text=high_label, showarrow=False,
                 font=dict(size=11, color="#27ae60"), xref="paper", yref="paper"),
        ],
    )
    return fig


# ---------------------------------------------------------------------------
# plot_regime_path
# ---------------------------------------------------------------------------

def plot_regime_path(
    pmi_series: pd.Series,
    cpi_series: pd.Series,
    lookback_months: int = 12,
    title: str = "미국 경기 사이클 좌표 (PMI-CPI)",
) -> go.Figure:
    """
    PMI-CPI 2차원 사분면 플롯 + 최근 N개월 이동 경로 (M-3용).

    축: PMI 변화율 Z-Score (x), CPI 변화율 Z-Score (y)
    사분면: reflation(우하), overheat(우상), stagflation(좌상), deflation(좌하)

    Args:
        pmi_series     : PMI 시계열 (월별)
        cpi_series     : CPI 시계열 (월별)
        lookback_months: 경로 표시 개월 수
        title          : 차트 제목
    Returns:
        go.Figure
    """
    if pmi_series.dropna().empty or cpi_series.dropna().empty:
        log.warning("plot_regime_path: PMI 또는 CPI 데이터 없음")
        return go.Figure()

    pmi_a, cpi_a = pmi_series.align(cpi_series, join="inner")
    combined = pd.concat([pmi_a.rename("pmi"), cpi_a.rename("cpi")], axis=1).dropna()

    if len(combined) < 7:
        log.warning("plot_regime_path: 데이터 부족 (%d행)", len(combined))
        return go.Figure()

    # 6개월 변화율
    pmi_chg = combined["pmi"].diff(6).dropna()
    cpi_chg = combined["cpi"].diff(6).dropna()

    # Z-Score 정규화
    def _zscore(s: pd.Series) -> pd.Series:
        std = s.std()
        if std == 0:
            return s * 0
        return (s - s.mean()) / std

    pmi_z = _zscore(pmi_chg)
    cpi_z = _zscore(cpi_chg)

    df_path = pd.concat([pmi_z.rename("pmi_z"), cpi_z.rename("cpi_z")], axis=1).dropna()

    # 최근 lookback_months 개월
    df_recent = df_path.tail(lookback_months)
    if df_recent.empty:
        return go.Figure()

    n = len(df_recent)
    xs = df_recent["pmi_z"].values
    ys = df_recent["cpi_z"].values
    dates = [t.strftime("%Y-%m") for t in df_recent.index]

    # 점 크기: 오래된 것 작게, 최신 크게
    sizes = [6 + i * (18 / max(n - 1, 1)) for i in range(n)]
    colors = [f"rgba(44,62,80,{0.2 + 0.8 * i / max(n - 1, 1)})" for i in range(n)]

    fig = go.Figure()

    # 사분면 배경 (shapes)
    axis_range = max(abs(xs).max(), abs(ys).max()) * 1.4 + 0.5
    quad_configs = [
        (0, axis_range, 0, axis_range, "#e67e22", "overheat"),       # 우상
        (-axis_range, 0, 0, axis_range, "#e74c3c", "stagflation"),   # 좌상
        (-axis_range, 0, -axis_range, 0, "#3498db", "deflation"),    # 좌하
        (0, axis_range, -axis_range, 0, "#2ecc71", "reflation"),     # 우하
    ]
    for x0, x1, y0, y1, color, label in quad_configs:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=color, opacity=0.08, line_width=0)
        fig.add_annotation(
            x=(x0 + x1) / 2, y=(y0 + y1) / 2,
            text=label, showarrow=False,
            font=dict(size=13, color=color, family="Arial Black"),
            opacity=0.5,
        )

    # 경로 라인
    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode="lines",
        line=dict(color="#95a5a6", width=1.5, dash="dot"),
        showlegend=False,
        hoverinfo="skip",
    ))

    # 포인트
    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode="markers+text",
        text=[d if i == n - 1 else "" for i, d in enumerate(dates)],
        textposition="top right",
        marker=dict(size=sizes, color=colors, line=dict(width=1, color="#2c3e50")),
        hovertemplate=[f"{d}<br>PMI_z: {x:.2f}<br>CPI_z: {y:.2f}<extra></extra>"
                       for d, x, y in zip(dates, xs, ys)],
        showlegend=False,
    ))

    # 최신 점 강조
    current_regime_name = ""
    if ys[-1] >= 0 and xs[-1] >= 0:
        current_regime_name = "overheat"
    elif ys[-1] >= 0 and xs[-1] < 0:
        current_regime_name = "stagflation"
    elif ys[-1] < 0 and xs[-1] < 0:
        current_regime_name = "deflation"
    else:
        current_regime_name = "reflation"

    latest_color = _REGIME_COLORS.get(current_regime_name, "#2c3e50")
    fig.add_trace(go.Scatter(
        x=[xs[-1]], y=[ys[-1]],
        mode="markers",
        marker=dict(size=16, color=latest_color, symbol="star",
                    line=dict(width=2, color="#fff")),
        name=f"현재 ({dates[-1]})",
        hovertemplate=f"{dates[-1]}<br>PMI_z: {xs[-1]:.2f}<br>CPI_z: {ys[-1]:.2f}<extra></extra>",
    ))

    # 중심선
    fig.add_hline(y=0, line_dash="dash", line_color="#7f8c8d", line_width=1)
    fig.add_vline(x=0, line_dash="dash", line_color="#7f8c8d", line_width=1)

    fig.update_layout(
        title=title,
        xaxis=dict(title="PMI 변화율 Z-Score (↑성장 개선)", zeroline=False,
                   range=[-axis_range, axis_range]),
        yaxis=dict(title="CPI 변화율 Z-Score (↑인플레 상승)", zeroline=False,
                   range=[-axis_range, axis_range]),
        hovermode="closest",
        margin=dict(l=60, r=40, t=80, b=60),
        height=480,
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
