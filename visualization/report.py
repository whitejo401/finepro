"""
visualization/report.py

master DataFrame으로 HTML 리포트를 생성한다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from collectors.base import get_logger
from config import BASE_DIR
from visualization.charts import (
    plot_correlation_heatmap,
    plot_cumulative_returns,
    plot_daily_returns,
    plot_regime_timeline,
    plot_gauge,
    plot_regime_path,
    plot_rolling_correlation,
    _REGIME_COLORS,
)
from visualization.disclaimer import get_html_disclaimer

log = get_logger("visualization.report")

REPORTS_DIR = BASE_DIR / "reports"

# 리포트에 포함할 주요 close 컬럼 우선순위
_PRIORITY_CLOSE_COLS = [
    "us_sp500_close",
    "kr_kospi_close",
    "cmd_wti_close",
    "cmd_gold_close",
    "fx_krw_usd_close",
    "rate_us10y_close",
    "alt_vix_close",
]

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; margin: 0; padding: 24px; }}
    h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; }}
    h2 {{ color: #34495e; margin-top: 40px; }}
    .chart-container {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
                         padding: 16px; margin-bottom: 32px; }}
    .meta {{ color: #7f8c8d; font-size: 0.85em; margin-bottom: 24px; }}
    .disclaimer {{ background: #f8f9fa; border-left: 4px solid #bdc3c7; padding: 12px 16px;
                   margin-top: 48px; font-size: 0.82em; color: #7f8c8d; line-height: 1.6; }}
    .disclaimer strong {{ color: #555; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">생성일: {generated_at} &nbsp;|&nbsp; 데이터 기간: {date_range}</p>
  {sections}
  <div class="disclaimer">
    {{disclaimer}}
  </div>
</body>
</html>
"""

_SECTION_TEMPLATE = """\
<div class="chart-container">
  <h2>{heading}</h2>
  {chart_html}
</div>
"""


def _fig_to_html(fig) -> str:
    """Figure를 CDN 방식 HTML 문자열로 변환한다."""
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _is_raw_data_safe(df: pd.DataFrame) -> bool:
    """
    리포트 게시 전 원시 데이터 노출 여부를 간단히 체크한다.
    반환값이 False면 경고 로그만 출력 (리포트 생성은 중단하지 않음).
    위반 패턴: 100행 이상의 숫자 컬럼을 그대로 HTML 테이블로 변환하는 행위.
    """
    if len(df) > 100 and len(df.select_dtypes("number").columns) > 5:
        log.warning(
            "build_report: master has %d rows × %d numeric cols — "
            "ensure only derived analysis (not raw prices) is published.",
            len(df), len(df.select_dtypes("number").columns),
        )
        return False
    return True


def _select_close_cols(master: pd.DataFrame, max_cols: int = 20) -> list[str]:
    """히트맵/누적수익률에 쓸 close 컬럼을 선정한다."""
    all_close = [c for c in master.columns if c.endswith("_close")]
    # 우선순위 컬럼을 앞에 배치
    ordered = [c for c in _PRIORITY_CLOSE_COLS if c in all_close]
    rest = [c for c in all_close if c not in ordered]
    selected = (ordered + rest)[:max_cols]
    return selected


def build_report(
    master: pd.DataFrame,
    output_path: str | None = None,
) -> str:
    """
    master DataFrame으로 HTML 리포트를 생성한다.

    포함 차트:
      1. 상관관계 히트맵 (Spearman)
      2. 주요 자산 누적 수익률

    Args:
        master      : build_master_dataset() 반환값
        output_path : 저장 경로. None이면 reports/report_{today}.html

    Returns:
        저장된 파일의 절대 경로(str)
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%Y-%m-%d")
    if output_path is None:
        out = REPORTS_DIR / f"report_{today}.html"
    else:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

    _is_raw_data_safe(master)  # 원시 데이터 노출 경고 체크

    if master.empty:
        log.warning("build_report: master DataFrame is empty — generating skeleton report")
        date_range = "N/A"
        sections_html = "<p>데이터가 없습니다.</p>"
    else:
        # 날짜 범위
        try:
            date_range = f"{master.index.min().date()} ~ {master.index.max().date()}"
        except Exception:
            date_range = "N/A"

        close_cols = _select_close_cols(master)
        log.info("build_report: selected %d close columns for charts", len(close_cols))

        sections: list[str] = []

        # ── 1. 상관관계 히트맵 ──────────────────────────────────────────────
        if close_cols:
            fig_corr = plot_correlation_heatmap(
                master[close_cols],
                title="자산 간 Spearman 상관관계",
                method="spearman",
            )
            sections.append(
                _SECTION_TEMPLATE.format(
                    heading="자산 간 상관관계 히트맵",
                    chart_html=_fig_to_html(fig_corr),
                )
            )
        else:
            log.warning("build_report: no close columns found, skipping heatmap")

        # ── 2. 누적 수익률 ──────────────────────────────────────────────────
        if close_cols:
            returns_dict: dict[str, pd.Series] = {}
            for col in close_cols:
                series = master[col].dropna()
                if len(series) < 2:
                    continue
                ret = series.pct_change().dropna()
                label = col.replace("_close", "").replace("_", " ").upper()
                returns_dict[label] = ret

            if returns_dict:
                # us_sp500 이 있으면 벤치마크로 지정
                benchmark_label = None
                for col in ["us_sp500_close"]:
                    candidate = col.replace("_close", "").replace("_", " ").upper()
                    if candidate in returns_dict:
                        benchmark_label = candidate
                        break

                fig_ret = plot_cumulative_returns(
                    returns_dict,
                    title="주요 자산 누적 수익률",
                    benchmark_key=benchmark_label,
                )
                sections.append(
                    _SECTION_TEMPLATE.format(
                        heading="주요 자산 누적 수익률",
                        chart_html=_fig_to_html(fig_ret),
                    )
                )

        # ── 3. 매크로 국면 분류 ─────────────────────────────────────────────
        try:
            from analysis.regime import regime_summary, classify_regime
            pmi_col = next((c for c in master.columns if "pmi" in c), None)
            cpi_col = next((c for c in master.columns if "cpi" in c), None)
            if pmi_col and cpi_col:
                rsummary = regime_summary(master, pmi_col=pmi_col, cpi_col=cpi_col)
                if rsummary:
                    perf = rsummary.get("performance")
                    current = rsummary.get("current", "")
                    regime_html = f"<p><strong>현재 국면:</strong> {current}</p>"
                    # 타임라인 차트 추가
                    regime_series = classify_regime(master[pmi_col], master[cpi_col])
                    fig_timeline = plot_regime_timeline(regime_series)
                    regime_html = _fig_to_html(fig_timeline) + regime_html
                    if perf is not None and not perf.empty:
                        regime_html += perf.round(4).to_html(classes="table")
                    sections.append(_SECTION_TEMPLATE.format(
                        heading="매크로 국면 분류 (Merrill Lynch Clock)",
                        chart_html=regime_html,
                    ))
        except Exception as e:
            log.warning("build_report: regime section failed: %s", e)

        # ── 4. 백테스팅 (단순 buy-and-hold 기준) ───────────────────────────
        try:
            from analysis.backtest import calc_returns, backtest_equal_weight, calc_performance_metrics
            if close_cols:
                price_df = master[[c for c in close_cols if c in master.columns]].dropna(how="all")
                rets = calc_returns(price_df)
                signal = pd.DataFrame(True, index=rets.index, columns=rets.columns)
                cumret = backtest_equal_weight(rets, signal, rebal_freq="ME")
                benchmark_col = next((c for c in ["kr_kospi_close", "us_sp500_close"] if c in price_df.columns), None)
                benchmark_ret = calc_returns(price_df[[benchmark_col]]).iloc[:, 0] if benchmark_col else None
                metrics = calc_performance_metrics(rets.mean(axis=1), benchmark=benchmark_ret)

                fig_bt = go.Figure()
                fig_bt.add_trace(go.Scatter(x=cumret.index, y=(1 + cumret).cumprod() if cumret.max() < 1 else cumret,
                                            name="포트폴리오", line=dict(color="#2ecc71")))
                if benchmark_ret is not None:
                    bm_cum = (1 + benchmark_ret).cumprod()
                    fig_bt.add_trace(go.Scatter(x=bm_cum.index, y=bm_cum,
                                                name=benchmark_col.replace("_close", ""),
                                                line=dict(dash="dash", color="#95a5a6")))
                fig_bt.update_layout(title="동일가중 포트폴리오 vs 벤치마크", yaxis_title="누적 수익률", xaxis_title="날짜")

                metrics_html = "<br>".join([
                    f"<b>연환산 수익률:</b> {metrics.get('annualized_return', 'N/A'):.2%}" if isinstance(metrics.get('annualized_return'), float) else "",
                    f"<b>샤프 비율:</b> {metrics.get('sharpe_ratio', 'N/A'):.2f}" if isinstance(metrics.get('sharpe_ratio'), float) else "",
                    f"<b>최대 낙폭:</b> {metrics.get('max_drawdown', 'N/A'):.2%}" if isinstance(metrics.get('max_drawdown'), float) else "",
                    f"<b>승률:</b> {metrics.get('win_rate', 'N/A'):.1%}" if isinstance(metrics.get('win_rate'), float) else "",
                ])
                sections.append(_SECTION_TEMPLATE.format(
                    heading="백테스팅 결과",
                    chart_html=_fig_to_html(fig_bt) + f"<div style='margin-top:12px'>{metrics_html}</div>",
                ))
        except Exception as e:
            log.warning("build_report: backtest section failed: %s", e)

        sections_html = "\n".join(sections) if sections else "<p>차트를 생성할 데이터가 부족합니다.</p>"

    html = _HTML_TEMPLATE.format(
        title=f"글로벌 매크로 퀀트 리포트 — {today}",
        generated_at=today,
        date_range=date_range if not master.empty else "N/A",
        sections=sections_html,
        disclaimer=get_html_disclaimer(lang="ko", length="full"),
    )

    out.write_text(html, encoding="utf-8")
    log.info("build_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_daily_report  (D-1)
# ---------------------------------------------------------------------------

_DAILY_MACRO_COLS = [
    ("rate_fed",           "연준 기준금리"),
    ("kr_macro_base_rate", "한국 기준금리"),
    ("rate_us10y",         "미 10년 금리"),
    ("rate_us2y",          "미 2년 금리"),
    ("rate_spread_10_2",   "10-2년 스프레드"),
    ("rate_hy_spread",     "하이일드 스프레드"),
    ("macro_cpi",          "미 CPI"),
    ("macro_unemployment", "미 실업률"),
    ("kr_macro_apt_price", "서울 아파트 (만원/㎡)"),
]


def build_daily_report(
    master: pd.DataFrame,
    date: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    D-1 일간 시황 브리핑 HTML 리포트.

    포함 섹션:
      1. 자산별 등락률 바 차트
      2. 주요 거시 지표 현황 테이블

    Args:
        master      : build_master_dataset() 반환값
        date        : 기준일 'YYYY-MM-DD', None이면 마지막 유효일
        output_path : None이면 reports/daily/daily_{date}.html
    Returns:
        저장된 파일의 절대 경로(str)
    """
    daily_dir = REPORTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    # 기준일 결정
    if date is None:
        ref_date = master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today())
    else:
        ref_date = date

    if output_path is None:
        out = daily_dir / f"daily_{ref_date}.html"
    else:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    # ── 1. 자산 등락률 바 차트 ───────────────────────────────────────────────
    fig_ret = plot_daily_returns(master, date=ref_date)
    sections.append(_SECTION_TEMPLATE.format(
        heading="자산별 등락률 (전일 대비)",
        chart_html=_fig_to_html(fig_ret),
    ))

    # ── 2. 거시 지표 현황 테이블 ─────────────────────────────────────────────
    macro_rows = []
    ref_ts = pd.Timestamp(ref_date)
    for col, label in _DAILY_MACRO_COLS:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        if s.empty:
            continue
        avail = s.index[s.index <= ref_ts]
        if avail.empty:
            continue
        latest_ts = avail[-1]
        val = s.loc[latest_ts]
        if isinstance(val, pd.Series):
            val = val.iloc[-1]
        prev_avail = s.index[s.index < latest_ts]
        if not prev_avail.empty:
            prev_val = s.loc[prev_avail[-1]]
            if isinstance(prev_val, pd.Series):
                prev_val = prev_val.iloc[-1]
            chg = val - prev_val
            chg_str = f"{chg:+.3f}"
        else:
            chg_str = "—"
        macro_rows.append((label, f"{val:.3f}", chg_str, latest_ts.strftime("%Y-%m-%d")))

    if macro_rows:
        table_html = (
            "<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
            "<tr style='background:#ecf0f1'>"
            "<th style='padding:6px 12px;text-align:left'>지표</th>"
            "<th style='padding:6px 12px;text-align:right'>현재값</th>"
            "<th style='padding:6px 12px;text-align:right'>전기 대비</th>"
            "<th style='padding:6px 12px;text-align:right'>기준일</th>"
            "</tr>"
        )
        for i, (label, val, chg, dt) in enumerate(macro_rows):
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            color = "#e74c3c" if chg.startswith("+") and "spread" not in label.lower() else (
                "#2ecc71" if chg.startswith("-") else "#333"
            )
            table_html += (
                f"<tr style='background:{bg}'>"
                f"<td style='padding:6px 12px'>{label}</td>"
                f"<td style='padding:6px 12px;text-align:right'>{val}</td>"
                f"<td style='padding:6px 12px;text-align:right;color:{color}'>{chg}</td>"
                f"<td style='padding:6px 12px;text-align:right;color:#999'>{dt}</td>"
                "</tr>"
            )
        table_html += "</table>"
        sections.append(_SECTION_TEMPLATE.format(
            heading="주요 거시 지표 현황",
            chart_html=table_html,
        ))

    # ── 3. CFTC COT 포지셔닝 테이블 ─────────────────────────────────────────
    cot_cols = [
        ("cot_sp500_net", "S&P500 비상업 순포지션"),
        ("cot_gold_net",  "금 비상업 순포지션"),
        ("cot_wti_net",   "WTI 비상업 순포지션"),
    ]
    cot_rows = []
    ref_ts_cot = pd.Timestamp(ref_date)
    for col, label in cot_cols:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        if s.empty:
            continue
        avail = s.index[s.index <= ref_ts_cot]
        if avail.empty:
            continue
        val = float(s.loc[avail[-1]])
        prev = s.index[s.index < avail[-1]]
        chg = f"{val - float(s.loc[prev[-1]]):+,.0f}" if not prev.empty else "—"
        direction = "매수 우세" if val > 0 else "매도 우세"
        cot_rows.append((label, f"{val:+,.0f}", chg, direction, avail[-1].strftime("%Y-%m-%d")))

    if cot_rows:
        cot_tbl = (
            "<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
            "<tr style='background:#ecf0f1'>"
            "<th style='padding:6px 12px;text-align:left'>자산</th>"
            "<th style='padding:6px 12px;text-align:right'>순포지션 (계약)</th>"
            "<th style='padding:6px 12px;text-align:right'>전주 대비</th>"
            "<th style='padding:6px 12px;text-align:right'>방향</th>"
            "<th style='padding:6px 12px;text-align:right'>기준일</th>"
            "</tr>"
        )
        for i, (lbl, val, chg, direction, dt) in enumerate(cot_rows):
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            dir_color = "#2ecc71" if direction == "매수 우세" else "#e74c3c"
            cot_tbl += (
                f"<tr style='background:{bg}'>"
                f"<td style='padding:6px 12px'>{lbl}</td>"
                f"<td style='padding:6px 12px;text-align:right'>{val}</td>"
                f"<td style='padding:6px 12px;text-align:right'>{chg}</td>"
                f"<td style='padding:6px 12px;text-align:right;color:{dir_color};font-weight:bold'>{direction}</td>"
                f"<td style='padding:6px 12px;text-align:right;color:#999'>{dt}</td>"
                "</tr>"
            )
        cot_tbl += "</table>"
        sections.append(_SECTION_TEMPLATE.format(
            heading="CFTC COT 선물 포지셔닝 (비상업)",
            chart_html=cot_tbl,
        ))

    # ── 4. 서울 아파트 실거래가 추이 ─────────────────────────────────────────
    if "kr_macro_apt_price" in master.columns:
        apt = master["kr_macro_apt_price"].dropna()
        if not apt.empty:
            fig_apt = go.Figure()
            fig_apt.add_trace(go.Scatter(
                x=apt.index, y=apt.values,
                mode="lines+markers",
                line=dict(color="#9b59b6", width=2),
                marker=dict(size=6),
                name="아파트 실거래가",
                hovertemplate="%{x|%Y-%m}<br>%{y:,.0f} 만원/㎡<extra></extra>",
            ))
            # 6개월 이동평균
            if len(apt) >= 3:
                ma6 = apt.rolling(3, min_periods=1).mean()
                fig_apt.add_trace(go.Scatter(
                    x=ma6.index, y=ma6.values,
                    mode="lines",
                    line=dict(color="#8e44ad", width=1.5, dash="dot"),
                    name="3개월 MA",
                ))

            # 변화율 통계 카드
            val_latest = float(apt.iloc[-1])
            stats_parts = [f"최신: <b>{val_latest:,.0f} 만원/㎡</b>"]
            for n_months, label in [(3, "3M"), (6, "6M"), (12, "1Y")]:
                if len(apt) > n_months:
                    prev = float(apt.iloc[-1 - n_months])
                    chg = (val_latest / prev - 1) * 100
                    color = "#e74c3c" if chg > 0 else "#2ecc71"
                    stats_parts.append(
                        f"{label}: <span style='color:{color}'>{chg:+.1f}%</span>"
                    )
            stats_html = (
                "<div style='display:flex;gap:24px;flex-wrap:wrap;"
                "font-size:0.95em;margin-bottom:8px'>"
                + "".join(f"<span>{p}</span>" for p in stats_parts)
                + "</div>"
            )

            fig_apt.update_layout(
                title="서울 아파트 실거래가 (국토교통부, 25개구 평균)",
                yaxis=dict(title="만원/㎡"),
                hovermode="x unified",
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="서울 아파트 실거래가",
                chart_html=stats_html + _fig_to_html(fig_apt),
            ))

    # 현재 국면 헤더 카드
    regime_card = ""
    try:
        from analysis.regime import classify_regime
        pmi_col = next((c for c in master.columns if "pmi" in c), None)
        cpi_col = next((c for c in master.columns if "cpi" in c), None)
        if pmi_col and cpi_col:
            regime_s = classify_regime(master[pmi_col], master[cpi_col])
            valid_r = regime_s.dropna()
            if not valid_r.empty:
                current_regime = valid_r.iloc[-1]
                from visualization.charts import _REGIME_COLORS
                color = _REGIME_COLORS.get(current_regime, "#95a5a6")
                regime_card = (
                    f"<div style='display:inline-block;padding:8px 20px;"
                    f"background:{color};color:#fff;border-radius:6px;"
                    f"font-size:1.1em;font-weight:bold;margin-bottom:16px'>"
                    f"현재 국면: {current_regime}</div>"
                )
    except Exception:
        pass

    sections_html = "\n".join(sections)
    html = _HTML_TEMPLATE.format(
        title=f"일간 시황 브리핑 — {ref_date}",
        generated_at=ref_date,
        date_range=ref_date,
        sections=regime_card + sections_html,
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )

    out.write_text(html, encoding="utf-8")
    log.info("build_daily_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_weekly_report  (W-2)
# ---------------------------------------------------------------------------

_REGIME_ASSETS_KO: dict[str, list[str]] = {
    "reflation":   ["주식", "리츠"],
    "overheat":    ["원자재", "에너지주"],
    "stagflation": ["현금", "단기채권"],
    "deflation":   ["장기채권", "금"],
}


def build_weekly_report(
    master: pd.DataFrame,
    week_end: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    W-2 매크로 국면 주간 리포트 HTML.

    포함 섹션:
      1. 현재 국면 강조 카드
      2. 12개월 국면 타임라인 차트
      3. 국면별 권장 자산 테이블

    Args:
        master    : build_master_dataset() 반환값
        week_end  : 주 기준일 'YYYY-MM-DD', None이면 마지막 유효일 포함 주
        output_path: None이면 reports/weekly/weekly_{week_end}.html
    Returns:
        저장된 파일의 절대 경로(str)
    """
    weekly_dir = REPORTS_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    if week_end is None:
        ref_date = master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today())
    else:
        ref_date = week_end

    if output_path is None:
        out = weekly_dir / f"weekly_{ref_date}.html"
    else:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    current_regime = None
    regime_color = "#95a5a6"

    # ── 국면 분류 ────────────────────────────────────────────────────────────
    try:
        from analysis.regime import classify_regime
        pmi_col = next((c for c in master.columns if "pmi" in c), None)
        cpi_col = next((c for c in master.columns if "cpi" in c), None)
        if pmi_col and cpi_col:
            regime_s = classify_regime(master[pmi_col], master[cpi_col])
            valid_r = regime_s.dropna()

            if not valid_r.empty:
                current_regime = valid_r.iloc[-1]
                from visualization.charts import _REGIME_COLORS
                regime_color = _REGIME_COLORS.get(current_regime, "#95a5a6")

                # 최근 12개월만
                cutoff = pd.Timestamp(ref_date) - pd.DateOffset(months=12)
                recent = valid_r[valid_r.index >= cutoff]

                fig_tl = plot_regime_timeline(recent, title="최근 12개월 매크로 국면 타임라인")
                sections.append(_SECTION_TEMPLATE.format(
                    heading="매크로 국면 타임라인 (최근 12개월)",
                    chart_html=_fig_to_html(fig_tl),
                ))
    except Exception as e:
        log.warning("build_weekly_report: 국면 분류 실패: %s", e)

    # ── OECD CLI 차트 ────────────────────────────────────────────────────────
    _CLI_LABELS = {
        "oecd_cli_us": "미국",
        "oecd_cli_kr": "한국",
        "oecd_cli_jp": "일본",
        "oecd_cli_de": "독일",
    }
    cli_cols = [c for c in _CLI_LABELS if c in master.columns]
    if cli_cols:
        cutoff_cli = pd.Timestamp(ref_date) - pd.DateOffset(months=24)
        df_cli = master[cli_cols].loc[master.index >= cutoff_cli].dropna(how="all")
        if not df_cli.empty:
            fig_cli = go.Figure()
            cli_colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12"]
            for i, col in enumerate(cli_cols):
                s = df_cli[col].dropna()
                if not s.empty:
                    fig_cli.add_trace(go.Scatter(
                        x=s.index, y=s.values, mode="lines+markers",
                        name=_CLI_LABELS.get(col, col),
                        line=dict(color=cli_colors[i % len(cli_colors)], width=2),
                        marker=dict(size=4),
                    ))
            fig_cli.add_hline(y=100, line_dash="dash", line_color="#bdc3c7",
                              annotation_text="기준선 100")
            fig_cli.update_layout(
                title="OECD 경기선행지수 (CLI) — 최근 24개월",
                yaxis=dict(title="CLI 지수"),
                hovermode="x unified",
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="OECD 경기선행지수 (CLI)",
                chart_html=_fig_to_html(fig_cli),
            ))

    # ── 국면별 권장 자산 테이블 ───────────────────────────────────────────────
    asset_table = (
        "<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
        "<tr style='background:#ecf0f1'>"
        "<th style='padding:8px 16px;text-align:left'>국면</th>"
        "<th style='padding:8px 16px;text-align:left'>특징</th>"
        "<th style='padding:8px 16px;text-align:left'>권장 자산</th>"
        "</tr>"
    )
    regime_descriptions = {
        "reflation":   ("PMI↑ CPI↓", "성장 회복, 인플레 없음"),
        "overheat":    ("PMI↑ CPI↑", "과열, 인플레 상승"),
        "stagflation": ("PMI↓ CPI↑", "경기 둔화 + 인플레"),
        "deflation":   ("PMI↓ CPI↓", "경기 침체, 디플레"),
    }
    from visualization.charts import _REGIME_COLORS
    for regime, assets in _REGIME_ASSETS_KO.items():
        color = _REGIME_COLORS.get(regime, "#95a5a6")
        is_current = (regime == current_regime)
        bg = f"{color}22" if is_current else "#fff"
        border = f"border-left:4px solid {color}"
        signal, desc = regime_descriptions.get(regime, ("—", "—"))
        badge = " <span style='font-size:0.8em;background:#2c3e50;color:#fff;padding:2px 6px;border-radius:3px'>현재</span>" if is_current else ""
        asset_table += (
            f"<tr style='background:{bg};{border}'>"
            f"<td style='padding:8px 16px;font-weight:bold;color:{color}'>{regime}{badge}</td>"
            f"<td style='padding:8px 16px;color:#666'>{signal} — {desc}</td>"
            f"<td style='padding:8px 16px'>{', '.join(assets)}</td>"
            "</tr>"
        )
    asset_table += "</table>"

    sections.append(_SECTION_TEMPLATE.format(
        heading="국면별 특징 및 권장 자산",
        chart_html=asset_table,
    ))

    # 현재 국면 헤더 카드
    regime_card = ""
    if current_regime:
        recommended = ", ".join(_REGIME_ASSETS_KO.get(current_regime, []))
        regime_card = (
            f"<div style='padding:16px 24px;background:{regime_color}22;"
            f"border-left:6px solid {regime_color};border-radius:4px;margin-bottom:24px'>"
            f"<div style='font-size:1.3em;font-weight:bold;color:{regime_color}'>"
            f"현재 국면: {current_regime}</div>"
            f"<div style='margin-top:8px;color:#555'>권장 자산: {recommended}</div>"
            "</div>"
        )

    sections_html = "\n".join(sections)
    html = _HTML_TEMPLATE.format(
        title=f"주간 매크로 국면 리포트 — {ref_date}",
        generated_at=ref_date,
        date_range=ref_date,
        sections=regime_card + sections_html,
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )

    out.write_text(html, encoding="utf-8")
    log.info("build_weekly_report: saved to %s", out)
    return str(out.resolve())


def date_today() -> date:
    return date.today()


# ---------------------------------------------------------------------------
# build_d2_report  (D-2 연준·금리 감성)
# ---------------------------------------------------------------------------

def build_d2_report(
    master: pd.DataFrame,
    date: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    D-2 연준·금리 감성 스냅샷 HTML 리포트.

    포함 섹션:
      1. 뉴스 감성 게이지 (global + fed)
      2. 감성 점수 30일 라인 차트
      3. 금리 현황 테이블

    Returns: 저장 경로(str)
    """
    daily_dir = REPORTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    ref_date = date or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else daily_dir / f"d2_sentiment_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    # ── 1. 감성 게이지 ──────────────────────────────────────────────────────
    gauge_html = ""
    for col, label in [("sent_news_global", "글로벌 경제 감성"), ("sent_news_fed", "연준 감성")]:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        if s.empty:
            continue
        ref_ts = pd.Timestamp(ref_date)
        avail = s.index[s.index <= ref_ts]
        if avail.empty:
            continue
        val_raw = float(s.loc[avail[-1]])          # -1 ~ 1
        val_100 = (val_raw + 1) / 2 * 100          # 0 ~ 100
        fig = plot_gauge(val_100, title=label, low_label="극부정", high_label="극긍정")
        gauge_html += f"<div style='display:inline-block;width:48%;min-width:220px'>{_fig_to_html(fig)}</div>"

    if gauge_html:
        sections.append(_SECTION_TEMPLATE.format(
            heading="뉴스 감성 점수 (VADER)",
            chart_html=f"<div style='display:flex;gap:8px;flex-wrap:wrap'>{gauge_html}</div>",
        ))

    # ── 2. 감성 30일 라인 차트 ──────────────────────────────────────────────
    sent_cols = [c for c in ["sent_news_global", "sent_news_fed"] if c in master.columns]
    if sent_cols:
        cutoff = pd.Timestamp(ref_date) - pd.Timedelta(days=30)
        df_sent = master[sent_cols].loc[master.index >= cutoff].dropna(how="all")
        if not df_sent.empty:
            fig_line = go.Figure()
            colors_map = {"sent_news_global": "#3498db", "sent_news_fed": "#e74c3c"}
            labels_map = {"sent_news_global": "글로벌 경제", "sent_news_fed": "연준"}
            for col in sent_cols:
                if col in df_sent.columns:
                    s = df_sent[col].dropna()
                    if not s.empty:
                        # 7일 이동평균
                        ma = s.rolling(7, min_periods=1).mean()
                        fig_line.add_trace(go.Scatter(
                            x=s.index, y=s.values, mode="markers",
                            marker=dict(size=4, color=colors_map.get(col, "#95a5a6")),
                            name=labels_map.get(col, col), opacity=0.4, showlegend=True,
                        ))
                        fig_line.add_trace(go.Scatter(
                            x=ma.index, y=ma.values, mode="lines",
                            line=dict(color=colors_map.get(col, "#95a5a6"), width=2),
                            name=f"{labels_map.get(col, col)} (7일 MA)", showlegend=True,
                        ))
            fig_line.add_hline(y=0, line_dash="dot", line_color="#bdc3c7")
            fig_line.update_layout(
                title="뉴스 감성 점수 추이 (최근 30일)",
                yaxis=dict(title="감성 점수 (-1~1)", range=[-1.1, 1.1]),
                hovermode="x unified",
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="감성 점수 추이",
                chart_html=_fig_to_html(fig_line),
            ))

    # ── 3. 금리 현황 테이블 ─────────────────────────────────────────────────
    rate_cols = [
        ("rate_fed",           "연준 기준금리"),
        ("kr_macro_base_rate", "한국 기준금리"),
        ("rate_us10y",         "미 10년 금리"),
        ("rate_us2y",          "미 2년 금리"),
        ("rate_spread_10_2",   "10-2년 스프레드"),
        ("rate_hy_spread",     "하이일드 스프레드"),
    ]
    rows = []
    ref_ts = pd.Timestamp(ref_date)
    for col, label in rate_cols:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        avail = s.index[s.index <= ref_ts]
        if avail.empty:
            continue
        val = float(s.loc[avail[-1]])
        prev = s.index[s.index < avail[-1]]
        chg = f"{val - float(s.loc[prev[-1]]):+.3f}" if not prev.empty else "—"
        rows.append((label, f"{val:.3f}%", chg, avail[-1].strftime("%Y-%m-%d")))

    if rows:
        tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
               "<tr style='background:#ecf0f1'><th style='padding:6px 12px;text-align:left'>지표</th>"
               "<th style='padding:6px 12px;text-align:right'>현재값</th>"
               "<th style='padding:6px 12px;text-align:right'>전기 대비</th>"
               "<th style='padding:6px 12px;text-align:right'>기준일</th></tr>")
        for i, (lbl, val, chg, dt) in enumerate(rows):
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            tbl += (f"<tr style='background:{bg}'><td style='padding:6px 12px'>{lbl}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{val}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{chg}</td>"
                    f"<td style='padding:6px 12px;text-align:right;color:#999'>{dt}</td></tr>")
        tbl += "</table>"
        sections.append(_SECTION_TEMPLATE.format(heading="금리 현황", chart_html=tbl))

    html = _HTML_TEMPLATE.format(
        title=f"연준·금리 감성 스냅샷 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_d2_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_d3_report  (D-3 암호화폐 스냅샷)
# ---------------------------------------------------------------------------

def build_d3_report(
    master: pd.DataFrame,
    date: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    D-3 암호화폐 스냅샷 HTML 리포트.

    포함 섹션:
      1. BTC 도미넌스 게이지
      2. BTC/ETH 등락률 바 차트
      3. BTC/ETH 가격 + 시총 90일 라인 차트

    Returns: 저장 경로(str)
    """
    daily_dir = REPORTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    ref_date = date or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else daily_dir / f"d3_crypto_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    # ── 1. BTC 도미넌스 게이지 ───────────────────────────────────────────────
    if "crypto_btc_dominance" in master.columns:
        s = master["crypto_btc_dominance"].dropna()
        ref_ts = pd.Timestamp(ref_date)
        avail = s.index[s.index <= ref_ts]
        if not avail.empty:
            dom_val = float(s.loc[avail[-1]])
            fig_dom = plot_gauge(dom_val, title="BTC 도미넌스", low_label="알트 우세", high_label="BTC 독주")
            sections.append(_SECTION_TEMPLATE.format(
                heading="BTC 도미넌스",
                chart_html=_fig_to_html(fig_dom),
            ))

    # ── 2. BTC/ETH 등락률 바 차트 ───────────────────────────────────────────
    crypto_ret_cols = [c for c in ["crypto_btc_close", "crypto_eth_close"] if c in master.columns]
    if crypto_ret_cols:
        fig_ret = plot_daily_returns(master, date=ref_date, cols=crypto_ret_cols)
        sections.append(_SECTION_TEMPLATE.format(
            heading="BTC / ETH 등락률 (전일 대비)",
            chart_html=_fig_to_html(fig_ret),
        ))

    # ── 3. 90일 가격 + 시총 라인 차트 ───────────────────────────────────────
    cutoff = pd.Timestamp(ref_date) - pd.Timedelta(days=90)
    crypto_price_cols = [c for c in ["crypto_btc_close", "crypto_eth_close"] if c in master.columns]
    mcap_col = "crypto_total_mcap"

    if crypto_price_cols:
        df_c = master[crypto_price_cols].loc[master.index >= cutoff].dropna(how="all")
        if not df_c.empty:
            fig_price = go.Figure()
            for col in crypto_price_cols:
                label = col.replace("crypto_", "").replace("_close", "").upper()
                s = df_c[col].dropna()
                fig_price.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name=label))

            if mcap_col in master.columns:
                mcap = master[mcap_col].loc[master.index >= cutoff].dropna()
                if not mcap.empty:
                    fig_price.add_trace(go.Scatter(
                        x=mcap.index, y=mcap.values / 1e9,
                        mode="lines", name="시총(십억 USD)",
                        yaxis="y2", line=dict(dash="dot"),
                    ))
                    fig_price.update_layout(
                        yaxis2=dict(title="시총 (십억 USD)", overlaying="y", side="right"),
                    )

            fig_price.update_layout(
                title="암호화폐 가격 추이 (최근 90일)",
                hovermode="x unified",
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="가격 및 시총 추이",
                chart_html=_fig_to_html(fig_price),
            ))

    html = _HTML_TEMPLATE.format(
        title=f"암호화폐 스냅샷 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_d3_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_w3_report  (W-3 크립토 vs 전통자산 롤링 상관)
# ---------------------------------------------------------------------------

def build_w3_report(
    master: pd.DataFrame,
    week_end: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    W-3 크립토 vs 전통자산 롤링 상관관계 주간 리포트.

    포함 섹션:
      1. BTC-S&P500 rolling 30일 Spearman
      2. BTC-Gold rolling 30일 Spearman
      3. BTC-VIX rolling 30일 Spearman
      4. 현재 상관계수 요약 테이블

    Returns: 저장 경로(str)
    """
    weekly_dir = REPORTS_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = week_end or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else weekly_dir / f"w3_crypto_corr_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    summary_rows: list[tuple] = []

    pairs = [
        ("crypto_btc_close", "us_sp500_close",  "BTC vs S&P500"),
        ("crypto_btc_close", "cmd_gold_close",  "BTC vs Gold"),
        ("crypto_btc_close", "alt_vix_close",   "BTC vs VIX"),
    ]

    for col_a, col_b, label in pairs:
        if col_a not in master.columns or col_b not in master.columns:
            continue
        sa = master[col_a].dropna()
        sb = master[col_b].dropna()
        fig = plot_rolling_correlation(sa, sb, window=30, title=f"{label} — Rolling 30일 Spearman")
        sections.append(_SECTION_TEMPLATE.format(heading=label, chart_html=_fig_to_html(fig)))

        # 현재 상관계수 계산
        from scipy import stats as scipy_stats
        common = pd.concat([sa.rename("a"), sb.rename("b")], axis=1).dropna()
        if len(common) >= 30:
            sub = common.tail(30)
            rho, pval = scipy_stats.spearmanr(sub["a"], sub["b"])
            summary_rows.append((label, f"{rho:.3f}", f"{pval:.3f}",
                                  "유의" if pval < 0.05 else "비유의"))

    if summary_rows:
        tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
               "<tr style='background:#ecf0f1'><th style='padding:6px 12px;text-align:left'>자산 쌍</th>"
               "<th style='padding:6px 12px;text-align:right'>Spearman ρ (30일)</th>"
               "<th style='padding:6px 12px;text-align:right'>p-value</th>"
               "<th style='padding:6px 12px;text-align:right'>유의성</th></tr>")
        for i, (lbl, rho, pval, sig) in enumerate(summary_rows):
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            color = "#e74c3c" if float(rho) < 0 else "#2ecc71"
            tbl += (f"<tr style='background:{bg}'><td style='padding:6px 12px'>{lbl}</td>"
                    f"<td style='padding:6px 12px;text-align:right;color:{color};font-weight:bold'>{rho}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{pval}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{sig}</td></tr>")
        tbl += "</table>"
        sections.append(_SECTION_TEMPLATE.format(heading="현재 상관계수 요약 (최근 30일)", chart_html=tbl))

    html = _HTML_TEMPLATE.format(
        title=f"크립토 vs 전통자산 롤링 상관 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_w3_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_w4_report  (W-4 국내 금리·환율·KOSPI 3각 관계)
# ---------------------------------------------------------------------------

def build_w4_report(
    master: pd.DataFrame,
    week_end: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    W-4 국내 금리·환율·KOSPI 3각 관계 주간 리포트.

    포함 섹션:
      1~3. 각 쌍 rolling 30일 Spearman 라인 차트
      4. 현재 상관계수 요약 테이블

    Returns: 저장 경로(str)
    """
    weekly_dir = REPORTS_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = week_end or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else weekly_dir / f"w4_kospi_triangle_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    summary_rows: list[tuple] = []

    pairs = [
        ("kr_kospi_close", "fx_krw_usd_close", "KOSPI vs USD/KRW"),
        ("kr_kospi_close", "rate_us10y",        "KOSPI vs 미 10년 금리"),
        ("fx_krw_usd_close", "rate_us10y",      "USD/KRW vs 미 10년 금리"),
    ]

    for col_a, col_b, label in pairs:
        if col_a not in master.columns or col_b not in master.columns:
            log.warning("build_w4_report: 컬럼 없음 — %s 또는 %s", col_a, col_b)
            continue
        sa = master[col_a].dropna()
        sb = master[col_b].dropna()
        fig = plot_rolling_correlation(sa, sb, window=30, title=f"{label} — Rolling 30일 Spearman")
        sections.append(_SECTION_TEMPLATE.format(heading=label, chart_html=_fig_to_html(fig)))

        from scipy import stats as scipy_stats
        common = pd.concat([sa.rename("a"), sb.rename("b")], axis=1).dropna()
        if len(common) >= 30:
            sub = common.tail(30)
            rho, pval = scipy_stats.spearmanr(sub["a"], sub["b"])
            summary_rows.append((label, f"{rho:.3f}", f"{pval:.3f}",
                                  "유의" if pval < 0.05 else "비유의"))

    if summary_rows:
        tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
               "<tr style='background:#ecf0f1'><th style='padding:6px 12px;text-align:left'>자산 쌍</th>"
               "<th style='padding:6px 12px;text-align:right'>Spearman ρ (30일)</th>"
               "<th style='padding:6px 12px;text-align:right'>p-value</th>"
               "<th style='padding:6px 12px;text-align:right'>유의성</th></tr>")
        for i, (lbl, rho, pval, sig) in enumerate(summary_rows):
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            color = "#e74c3c" if float(rho) < 0 else "#2ecc71"
            tbl += (f"<tr style='background:{bg}'><td style='padding:6px 12px'>{lbl}</td>"
                    f"<td style='padding:6px 12px;text-align:right;color:{color};font-weight:bold'>{rho}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{pval}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{sig}</td></tr>")
        tbl += "</table>"
        sections.append(_SECTION_TEMPLATE.format(heading="현재 상관계수 요약 (최근 30일)", chart_html=tbl))

    html = _HTML_TEMPLATE.format(
        title=f"국내 금리·환율·KOSPI 3각 관계 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_w4_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_m3_report  (M-3 미국 경기 사이클 좌표)
# ---------------------------------------------------------------------------

def build_m3_report(
    master: pd.DataFrame,
    month_end: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    M-3 미국 경기 사이클 좌표 월간 리포트.

    포함 섹션:
      1. PMI-CPI 사분면 이동 경로 (12개월)
      2. 6개 거시 지표 Z-Score 레이더 차트
      3. 현재 국면 + 권장 자산 카드

    Returns: 저장 경로(str)
    """
    monthly_dir = REPORTS_DIR / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = month_end or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else monthly_dir / f"m3_cycle_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    current_regime_name = ""
    regime_color = "#95a5a6"

    # ── 1. PMI-CPI 사분면 이동 경로 ─────────────────────────────────────────
    pmi_col = next((c for c in master.columns if "pmi" in c), None)
    cpi_col = next((c for c in master.columns if "cpi" in c), None)

    if pmi_col and cpi_col:
        fig_path = plot_regime_path(master[pmi_col], master[cpi_col], lookback_months=12)
        sections.append(_SECTION_TEMPLATE.format(
            heading="경기 사이클 좌표 (최근 12개월 이동 경로)",
            chart_html=_fig_to_html(fig_path),
        ))

        # 현재 국면 파악
        try:
            from analysis.regime import classify_regime
            rs = classify_regime(master[pmi_col], master[cpi_col]).dropna()
            if not rs.empty:
                current_regime_name = rs.iloc[-1]
                regime_color = _REGIME_COLORS.get(current_regime_name, "#95a5a6")
        except Exception:
            pass

    # ── 2. 6개 거시 지표 Z-Score 레이더 차트 ────────────────────────────────
    radar_cols = {
        "macro_pmi_us":       "PMI",
        "macro_cpi":          "CPI",
        "macro_gdp_us":       "GDP",
        "macro_unemployment": "실업률",
        "rate_fed":           "기준금리",
        "macro_m2_us":        "M2",
    }
    available = {k: v for k, v in radar_cols.items() if k in master.columns}

    if len(available) >= 3:
        ref_ts = pd.Timestamp(ref_date)
        z_scores: dict[str, float] = {}
        for col, label in available.items():
            s = master[col].dropna()
            avail_idx = s.index[s.index <= ref_ts]
            if avail_idx.empty or s.std() == 0:
                continue
            val = float(s.loc[avail_idx[-1]])
            z = (val - s.mean()) / s.std()
            z_scores[label] = round(float(z), 2)

        # nan/inf 제거
        import math
        z_scores = {k: v for k, v in z_scores.items() if math.isfinite(v)}

        if z_scores:
            cats = list(z_scores.keys()) + [list(z_scores.keys())[0]]
            vals = list(z_scores.values()) + [list(z_scores.values())[0]]
            # hex → rgba 변환 (Plotly fillcolor 호환)
            def _hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
                h = hex_color.lstrip("#")
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return f"rgba({r},{g},{b},{alpha})"

            fig_radar = go.Figure(go.Scatterpolar(
                r=vals, theta=cats, fill="toself",
                fillcolor=_hex_to_rgba(regime_color, 0.2),
                line=dict(color=regime_color),
            ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[-3, 3])),
                title="주요 거시 지표 Z-Score (현재 수준)",
                showlegend=False,
                height=400,
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="거시 지표 Z-Score 레이더",
                chart_html=_fig_to_html(fig_radar),
            ))

    # ── 3. 현재 국면 카드 ───────────────────────────────────────────────────
    if current_regime_name:
        from visualization.report import _REGIME_ASSETS_KO
        recommended = ", ".join(_REGIME_ASSETS_KO.get(current_regime_name, []))
        regime_card = (
            f"<div style='padding:16px 24px;background:{regime_color}22;"
            f"border-left:6px solid {regime_color};border-radius:4px'>"
            f"<div style='font-size:1.3em;font-weight:bold;color:{regime_color}'>"
            f"현재 국면: {current_regime_name}</div>"
            f"<div style='margin-top:8px;color:#555'>권장 자산: {recommended}</div>"
            "</div>"
        )
        sections.append(_SECTION_TEMPLATE.format(heading="현재 국면 요약", chart_html=regime_card))

    html = _HTML_TEMPLATE.format(
        title=f"미국 경기 사이클 좌표 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_m3_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_d4_report  (D-4 오늘 KOSPI 예상)
# ---------------------------------------------------------------------------

def build_d4_report(
    master: pd.DataFrame,
    date: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    D-4 오늘 KOSPI 방향 예측 HTML 리포트.

    포함 섹션:
      1. 신호 신호등 카드 (상승/하락/중립)
      2. 로지스틱 상승 확률 게이지
      3. 상위 선행 변수 상관 테이블
      4. 개별 변수 부호 투표 현황

    Returns: 저장 경로(str)
    """
    daily_dir = REPORTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    ref_date = date or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else daily_dir / f"d4_kospi_pred_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    try:
        from analysis.prediction import build_today_prediction
        pred = build_today_prediction(master)
    except Exception as e:
        log.warning("build_d4_report: 예측 실패: %s", e)
        pred = {}

    signal = pred.get("signal", 0)
    prob_up = pred.get("prob_up")
    top_features = pred.get("top_features")
    vote_detail = pred.get("vote_detail", {})

    # ── 1. 신호 신호등 카드 ─────────────────────────────────────────────────
    if signal == 1:
        sig_color, sig_label, sig_icon = "#2ecc71", "상승 예상", "▲"
    elif signal == -1:
        sig_color, sig_label, sig_icon = "#e74c3c", "하락 예상", "▼"
    else:
        sig_color, sig_label, sig_icon = "#f39c12", "중립", "—"

    signal_card = (
        f"<div style='text-align:center;padding:24px;background:{sig_color}22;"
        f"border:3px solid {sig_color};border-radius:12px;margin-bottom:16px'>"
        f"<div style='font-size:3em;color:{sig_color}'>{sig_icon}</div>"
        f"<div style='font-size:1.6em;font-weight:bold;color:{sig_color};margin-top:8px'>{sig_label}</div>"
        f"<div style='color:#555;margin-top:8px'>기준일: {pred.get('ref_date', ref_date)}</div>"
        f"</div>"
    )
    sections.append(_SECTION_TEMPLATE.format(heading="오늘 KOSPI 방향 예측", chart_html=signal_card))

    # ── 2. 상승 확률 게이지 ─────────────────────────────────────────────────
    if prob_up is not None:
        fig_gauge = plot_gauge(
            prob_up * 100,
            title="KOSPI 상승 확률 (로지스틱)",
            low_label="하락",
            high_label="상승",
        )
        sections.append(_SECTION_TEMPLATE.format(
            heading=f"상승 확률: {prob_up:.1%}",
            chart_html=_fig_to_html(fig_gauge),
        ))

    # ── 3. 상위 선행 변수 상관 테이블 ─────────────────────────────────────
    if top_features is not None and not top_features.empty:
        tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
               "<tr style='background:#ecf0f1'>"
               "<th style='padding:6px 12px;text-align:left'>변수</th>"
               "<th style='padding:6px 12px;text-align:right'>Spearman ρ</th>"
               "<th style='padding:6px 12px;text-align:right'>p-value</th>"
               "<th style='padding:6px 12px;text-align:right'>선행 일수</th>"
               "</tr>")
        for i, row in top_features.iterrows():
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            rho_val = row['spearman_rho']
            color = "#2ecc71" if rho_val > 0 else "#e74c3c"
            tbl += (f"<tr style='background:{bg}'>"
                    f"<td style='padding:6px 12px'>{row['feature']}</td>"
                    f"<td style='padding:6px 12px;text-align:right;color:{color};font-weight:bold'>{rho_val:+.4f}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{row['p_value']:.4f}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{row['lag']}일</td>"
                    "</tr>")
        tbl += "</table>"
        sections.append(_SECTION_TEMPLATE.format(heading="상위 선행 변수 (Spearman 상관)", chart_html=tbl))

    # ── 4. 개별 변수 투표 현황 ───────────────────────────────────────────────
    if vote_detail:
        vote_rows = ""
        for col, sign in vote_detail.items():
            icon = "▲" if sign > 0 else ("▼" if sign < 0 else "—")
            color = "#2ecc71" if sign > 0 else ("#e74c3c" if sign < 0 else "#f39c12")
            vote_rows += (
                f"<div style='display:flex;justify-content:space-between;padding:6px 12px;"
                f"border-bottom:1px solid #eee'>"
                f"<span>{col}</span>"
                f"<span style='color:{color};font-weight:bold'>{icon}</span>"
                f"</div>"
            )
        vote_html = f"<div style='border:1px solid #ddd;border-radius:6px'>{vote_rows}</div>"
        sections.append(_SECTION_TEMPLATE.format(heading="개별 변수 전일 방향 투표", chart_html=vote_html))

    html = _HTML_TEMPLATE.format(
        title=f"오늘 KOSPI 방향 예측 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_d4_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_d5_report  (D-5 미국→KOSPI 선행 분석)
# ---------------------------------------------------------------------------

def build_d5_report(
    master: pd.DataFrame,
    date: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    D-5 미국→KOSPI 선행 분석 HTML 리포트.

    포함 섹션:
      1. OLS 갭 예측 vs 실제 라인 차트 (최근 60일)
      2. R² 추이 라인 차트
      3. 전일 미국 시장 요약 (S&P500, NASDAQ, VIX, 환율)

    Returns: 저장 경로(str)
    """
    daily_dir = REPORTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    ref_date = date or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else daily_dir / f"d5_kospi_lead_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    # ── 1. OLS 갭 예측 ──────────────────────────────────────────────────────
    try:
        from analysis.prediction import rolling_ols_gap
        ols_df = rolling_ols_gap(master)
        if not ols_df.empty:
            cutoff = pd.Timestamp(ref_date) - pd.Timedelta(days=60)
            ols_recent = ols_df[ols_df.index >= cutoff]
            if not ols_recent.empty:
                fig_gap = go.Figure()
                fig_gap.add_trace(go.Scatter(
                    x=ols_recent.index, y=ols_recent["actual_gap"] * 100,
                    mode="lines+markers", name="실제 수익률 (%)",
                    line=dict(color="#3498db"), marker=dict(size=4),
                ))
                fig_gap.add_trace(go.Scatter(
                    x=ols_recent.index, y=ols_recent["predicted_gap"] * 100,
                    mode="lines", name="OLS 예측 (%)",
                    line=dict(color="#e74c3c", dash="dash"),
                ))
                fig_gap.add_hline(y=0, line_dash="dot", line_color="#bdc3c7")
                fig_gap.update_layout(
                    title="KOSPI 갭 예측 vs 실제 (OLS, 최근 60일)",
                    yaxis_title="일간 수익률 (%)",
                    hovermode="x unified",
                )
                sections.append(_SECTION_TEMPLATE.format(
                    heading="OLS 갭 예측 vs 실제",
                    chart_html=_fig_to_html(fig_gap),
                ))

                # R² 추이
                fig_r2 = go.Figure(go.Scatter(
                    x=ols_recent.index, y=ols_recent["r_squared"],
                    mode="lines+markers", name="R²",
                    line=dict(color="#9b59b6"), marker=dict(size=4),
                ))
                fig_r2.update_layout(
                    title="OLS 모델 R² 추이",
                    yaxis=dict(title="R²", range=[0, 1]),
                    hovermode="x",
                )
                sections.append(_SECTION_TEMPLATE.format(
                    heading="모델 설명력 (R²)",
                    chart_html=_fig_to_html(fig_r2),
                ))
    except Exception as e:
        log.warning("build_d5_report: OLS 갭 실패: %s", e)

    # ── 2. 전일 미국 시장 요약 ───────────────────────────────────────────────
    us_cols = [
        ("us_sp500_close",   "S&P 500"),
        ("us_nasdaq_close",  "NASDAQ"),
        ("alt_vix_close",    "VIX"),
        ("fx_krw_usd_close", "USD/KRW"),
        ("rate_us10y",       "미 10년 금리"),
    ]
    us_rows = []
    ref_ts = pd.Timestamp(ref_date)
    for col, label in us_cols:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        avail = s.index[s.index <= ref_ts]
        if avail.empty:
            continue
        val = float(s.loc[avail[-1]])
        prev = s.index[s.index < avail[-1]]
        if not prev.empty:
            prev_val = float(s.loc[prev[-1]])
            chg_pct = (val - prev_val) / abs(prev_val) * 100 if prev_val != 0 else 0
            chg_str = f"{chg_pct:+.2f}%"
        else:
            chg_str = "—"
        us_rows.append((label, f"{val:,.2f}", chg_str, avail[-1].strftime("%Y-%m-%d")))

    if us_rows:
        tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
               "<tr style='background:#ecf0f1'>"
               "<th style='padding:6px 12px;text-align:left'>지표</th>"
               "<th style='padding:6px 12px;text-align:right'>현재값</th>"
               "<th style='padding:6px 12px;text-align:right'>전일 대비</th>"
               "<th style='padding:6px 12px;text-align:right'>기준일</th>"
               "</tr>")
        for i, (lbl, val, chg, dt) in enumerate(us_rows):
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            if chg != "—":
                try:
                    chg_num = float(chg.replace("%", "").replace("+", ""))
                    color = "#2ecc71" if chg_num > 0 else "#e74c3c"
                except ValueError:
                    color = "#333"
            else:
                color = "#333"
            tbl += (f"<tr style='background:{bg}'>"
                    f"<td style='padding:6px 12px'>{lbl}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{val}</td>"
                    f"<td style='padding:6px 12px;text-align:right;color:{color};font-weight:bold'>{chg}</td>"
                    f"<td style='padding:6px 12px;text-align:right;color:#999'>{dt}</td>"
                    "</tr>")
        tbl += "</table>"
        sections.append(_SECTION_TEMPLATE.format(heading="전일 미국 시장 마감 요약", chart_html=tbl))

    html = _HTML_TEMPLATE.format(
        title=f"미국→KOSPI 선행 분석 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_d5_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_w5_report  (W-5 KOSPI 예측 적중률 리뷰)
# ---------------------------------------------------------------------------

def build_w5_report(
    master: pd.DataFrame,
    week_end: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    W-5 KOSPI 예측 적중률 리뷰 주간 리포트.

    포함 섹션:
      1. 누적 적중률 라인 차트
      2. 최근 20일 예측 vs 실제 테이블
      3. 적중률 요약 카드

    Returns: 저장 경로(str)
    """
    weekly_dir = REPORTS_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = week_end or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else weekly_dir / f"w5_pred_accuracy_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    try:
        from analysis.prediction import load_prediction_log, rolling_logit_predict
        pred_log = load_prediction_log()

        # 로그가 없으면 master로 새로 계산
        if pred_log.empty:
            logit_df = rolling_logit_predict(master)
            pred_log = logit_df if not logit_df.empty else pd.DataFrame()
            if not pred_log.empty and "hit" not in pred_log.columns:
                pred_log["hit"] = (pred_log["predicted"] == pred_log["actual"]).astype(int)
            if not pred_log.empty and "cumulative_hit_rate" not in pred_log.columns:
                valid = pred_log.dropna(subset=["hit"])
                if not valid.empty:
                    pred_log.loc[valid.index, "cumulative_hit_rate"] = valid["hit"].expanding().mean()

        if not pred_log.empty:
            valid_log = pred_log.dropna(subset=["hit"])

            # ── 1. 누적 적중률 라인 차트 ─────────────────────────────────────
            if "cumulative_hit_rate" in pred_log.columns:
                hr_series = pred_log["cumulative_hit_rate"].dropna()
                if not hr_series.empty:
                    fig_hr = go.Figure()
                    fig_hr.add_trace(go.Scatter(
                        x=hr_series.index, y=hr_series.values * 100,
                        mode="lines", name="누적 적중률 (%)",
                        line=dict(color="#3498db", width=2),
                    ))
                    fig_hr.add_hline(y=50, line_dash="dot", line_color="#e74c3c",
                                     annotation_text="랜덤 기준 (50%)")
                    fig_hr.update_layout(
                        title="KOSPI 방향 예측 누적 적중률",
                        yaxis=dict(title="적중률 (%)", range=[30, 80]),
                        hovermode="x",
                    )
                    sections.append(_SECTION_TEMPLATE.format(
                        heading="누적 예측 적중률",
                        chart_html=_fig_to_html(fig_hr),
                    ))

            # ── 2. 최근 20일 예측 vs 실제 테이블 ─────────────────────────────
            recent = valid_log.tail(20)
            if not recent.empty:
                tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
                       "<tr style='background:#ecf0f1'>"
                       "<th style='padding:6px 12px;text-align:left'>날짜</th>"
                       "<th style='padding:6px 12px;text-align:right'>예측</th>"
                       "<th style='padding:6px 12px;text-align:right'>실제</th>"
                       "<th style='padding:6px 12px;text-align:right'>적중</th>")
                if "prob_up" in recent.columns:
                    tbl += "<th style='padding:6px 12px;text-align:right'>상승확률</th>"
                tbl += "</tr>"

                for dt, row in recent.iterrows():
                    hit = int(row["hit"]) if "hit" in row and not pd.isna(row["hit"]) else None
                    bg = "#f0fff4" if hit == 1 else ("#fff0f0" if hit == 0 else "#fff")
                    pred_icon = "▲" if row.get("predicted", 0) == 1 else "▼"
                    actual_icon = "▲" if row.get("actual", 0) == 1 else "▼"
                    hit_icon = "O" if hit == 1 else ("X" if hit == 0 else "—")
                    hit_color = "#2ecc71" if hit == 1 else ("#e74c3c" if hit == 0 else "#999")
                    dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
                    tbl += (f"<tr style='background:{bg}'>"
                            f"<td style='padding:6px 12px'>{dt_str}</td>"
                            f"<td style='padding:6px 12px;text-align:right'>{pred_icon}</td>"
                            f"<td style='padding:6px 12px;text-align:right'>{actual_icon}</td>"
                            f"<td style='padding:6px 12px;text-align:right;color:{hit_color};font-weight:bold'>{hit_icon}</td>")
                    if "prob_up" in recent.columns:
                        prob = row.get("prob_up")
                        prob_str = f"{prob:.1%}" if pd.notna(prob) else "—"
                        tbl += f"<td style='padding:6px 12px;text-align:right'>{prob_str}</td>"
                    tbl += "</tr>"
                tbl += "</table>"
                sections.append(_SECTION_TEMPLATE.format(heading="최근 20일 예측 결과", chart_html=tbl))

            # ── 3. 적중률 요약 카드 ───────────────────────────────────────────
            if not valid_log.empty:
                total = len(valid_log)
                hits = int(valid_log["hit"].sum())
                hit_rate = hits / total if total > 0 else 0
                color = "#2ecc71" if hit_rate >= 0.55 else ("#f39c12" if hit_rate >= 0.5 else "#e74c3c")
                summary_card = (
                    f"<div style='display:flex;gap:16px;flex-wrap:wrap'>"
                    f"<div style='flex:1;min-width:140px;text-align:center;padding:16px;"
                    f"background:{color}22;border:2px solid {color};border-radius:8px'>"
                    f"<div style='font-size:2em;font-weight:bold;color:{color}'>{hit_rate:.1%}</div>"
                    f"<div style='color:#555;margin-top:4px'>전체 적중률</div>"
                    f"</div>"
                    f"<div style='flex:1;min-width:140px;text-align:center;padding:16px;"
                    f"background:#ecf0f122;border:2px solid #bdc3c7;border-radius:8px'>"
                    f"<div style='font-size:2em;font-weight:bold;color:#2c3e50'>{total}</div>"
                    f"<div style='color:#555;margin-top:4px'>예측 건수</div>"
                    f"</div>"
                    f"<div style='flex:1;min-width:140px;text-align:center;padding:16px;"
                    f"background:#2ecc7122;border:2px solid #2ecc71;border-radius:8px'>"
                    f"<div style='font-size:2em;font-weight:bold;color:#2ecc71'>{hits}</div>"
                    f"<div style='color:#555;margin-top:4px'>적중 건수</div>"
                    f"</div>"
                    f"</div>"
                )
                sections.append(_SECTION_TEMPLATE.format(heading="예측 정확도 요약", chart_html=summary_card))

    except Exception as e:
        log.warning("build_w5_report: 예측 로그 로드 실패: %s", e)
        sections.append(_SECTION_TEMPLATE.format(
            heading="예측 데이터 없음",
            chart_html="<p>예측 로그가 없거나 데이터가 부족합니다.</p>",
        ))

    html = _HTML_TEMPLATE.format(
        title=f"KOSPI 예측 적중률 리뷰 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_w5_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_m5_report  (M-5 국면별 자산 성과 히트맵)
# ---------------------------------------------------------------------------

def build_m5_report(
    master: pd.DataFrame,
    month_end: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    M-5 국면별 자산 성과 히트맵 월간 리포트.

    포함 섹션:
      1. 국면별 × 자산별 평균 월간 수익률 히트맵
      2. 현재 국면 강조 테이블

    Returns: 저장 경로(str)
    """
    monthly_dir = REPORTS_DIR / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = month_end or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else monthly_dir / f"m5_regime_perf_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    current_regime = None

    # 국면 분류
    pmi_col = next((c for c in master.columns if "pmi" in c), None)
    cpi_col = next((c for c in master.columns if "cpi" in c), None)

    try:
        if pmi_col and cpi_col:
            from analysis.regime import classify_regime, regime_summary
            regime_s = classify_regime(master[pmi_col], master[cpi_col]).dropna()
            current_regime = regime_s.iloc[-1] if not regime_s.empty else None

            # 월간 리샘플 후 국면별 자산 성과 계산
            close_cols = [c for c in _PRIORITY_CLOSE_COLS if c in master.columns]
            if close_cols and not regime_s.empty:
                price_df = master[close_cols].copy()
                # 월간 수익률
                monthly_ret = price_df.resample("ME").last().pct_change(fill_method=None)
                # 국면 (월 말 기준)
                regime_monthly = regime_s.resample("ME").last()

                combined = pd.concat([monthly_ret, regime_monthly.rename("regime")], axis=1).dropna(subset=["regime"])

                regime_perf: dict[str, dict] = {}
                for regime in ["reflation", "overheat", "stagflation", "deflation"]:
                    mask = combined["regime"] == regime
                    sub = combined.loc[mask, close_cols]
                    if sub.empty:
                        continue
                    regime_perf[regime] = sub.mean().to_dict()

                if regime_perf:
                    perf_df = pd.DataFrame(regime_perf).T
                    # 컬럼 이름 정리
                    perf_df.columns = [c.replace("_close", "").replace("_", " ").upper() for c in perf_df.columns]

                    # 히트맵
                    z_vals = perf_df.values * 100  # 퍼센트 단위
                    fig_hm = go.Figure(go.Heatmap(
                        z=z_vals,
                        x=list(perf_df.columns),
                        y=list(perf_df.index),
                        colorscale="RdYlGn",
                        zmid=0,
                        text=[[f"{v:.1f}%" for v in row] for row in z_vals],
                        texttemplate="%{text}",
                        hovertemplate="국면: %{y}<br>자산: %{x}<br>평균 월간수익률: %{text}<extra></extra>",
                    ))
                    # 현재 국면 강조 표시
                    if current_regime and current_regime in perf_df.index:
                        idx = list(perf_df.index).index(current_regime)
                        fig_hm.add_shape(
                            type="rect",
                            x0=-0.5, x1=len(perf_df.columns) - 0.5,
                            y0=idx - 0.5, y1=idx + 0.5,
                            line=dict(color="#2c3e50", width=3),
                        )
                    fig_hm.update_layout(
                        title="국면별 자산 평균 월간 수익률 (%)",
                        height=300,
                        margin=dict(l=100),
                    )
                    sections.append(_SECTION_TEMPLATE.format(
                        heading="국면별 자산 성과 히트맵",
                        chart_html=_fig_to_html(fig_hm),
                    ))

            # 현재 국면 카드
            if current_regime:
                regime_color = _REGIME_COLORS.get(current_regime, "#95a5a6")
                recommended = ", ".join(_REGIME_ASSETS_KO.get(current_regime, []))
                card = (
                    f"<div style='padding:16px 24px;background:{regime_color}22;"
                    f"border-left:6px solid {regime_color};border-radius:4px'>"
                    f"<div style='font-size:1.3em;font-weight:bold;color:{regime_color}'>"
                    f"현재 국면: {current_regime}</div>"
                    f"<div style='margin-top:8px;color:#555'>역사적 성과 기준 권장 자산: {recommended}</div>"
                    "</div>"
                )
                sections.append(_SECTION_TEMPLATE.format(heading="현재 국면 성과 요약", chart_html=card))

    except Exception as e:
        log.warning("build_m5_report: 국면 성과 계산 실패: %s", e)
        sections.append(_SECTION_TEMPLATE.format(
            heading="데이터 부족",
            chart_html=f"<p>국면 성과 계산에 필요한 데이터가 부족합니다: {e}</p>",
        ))

    html = _HTML_TEMPLATE.format(
        title=f"국면별 자산 성과 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_m5_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_m6_report  (M-6 공포-탐욕 지수)
# ---------------------------------------------------------------------------

def build_m6_report(
    master: pd.DataFrame,
    month_end: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    M-6 공포-탐욕 지수 분석 월간 리포트.

    포함 섹션:
      1. 공포-탐욕 지수 게이지 (현재값)
      2. 공포-탐욕 지수 시계열 라인 차트 (최근 12개월)
      3. 구성 지표 기여도 바 차트

    Returns: 저장 경로(str)
    """
    monthly_dir = REPORTS_DIR / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = month_end or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else monthly_dir / f"m6_fear_greed_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    try:
        from analysis.fear_greed import fear_greed_summary, fear_greed_label

        fg_summary = fear_greed_summary(master)
        if not fg_summary:
            raise ValueError("fear_greed_summary 반환값 없음")

        fg_index = fg_summary["index"]
        fg_label = fg_summary["label"]
        fg_series = fg_summary["series"]
        fg_components = fg_summary["components"]

        # ── 1. 공포-탐욕 게이지 ─────────────────────────────────────────────
        fig_gauge = plot_gauge(
            fg_index,
            title=f"공포-탐욕 지수: {fg_index} ({fg_label})",
            low_label="극공포",
            high_label="극탐욕",
        )
        sections.append(_SECTION_TEMPLATE.format(
            heading=f"현재 공포-탐욕 지수: {fg_index} — {fg_label}",
            chart_html=_fig_to_html(fig_gauge),
        ))

        # ── 2. 시계열 라인 차트 ──────────────────────────────────────────────
        if not fg_series.empty:
            cutoff = pd.Timestamp(ref_date) - pd.DateOffset(months=12)
            fg_recent = fg_series[fg_series.index >= cutoff].dropna()
            if not fg_recent.empty:
                # 구간별 색상 배경
                fig_ts = go.Figure()

                # 배경 구간
                zones = [
                    (0,  20, "rgba(231,76,60,0.1)",   "극공포"),
                    (20, 40, "rgba(231,76,60,0.06)",  "공포"),
                    (40, 60, "rgba(243,156,18,0.08)", "중립"),
                    (60, 80, "rgba(46,204,113,0.06)", "탐욕"),
                    (80, 100,"rgba(46,204,113,0.1)",  "극탐욕"),
                ]
                for y0, y1, color, zone_label in zones:
                    fig_ts.add_hrect(y0=y0, y1=y1, fillcolor=color, line_width=0,
                                     annotation_text=zone_label, annotation_position="right")

                fig_ts.add_trace(go.Scatter(
                    x=fg_recent.index, y=fg_recent.values,
                    mode="lines", name="공포-탐욕 지수",
                    line=dict(color="#2c3e50", width=2),
                ))
                fig_ts.add_hline(y=50, line_dash="dot", line_color="#95a5a6")
                fig_ts.update_layout(
                    title="공포-탐욕 지수 추이 (최근 12개월)",
                    yaxis=dict(title="지수 (0~100)", range=[0, 100]),
                    hovermode="x",
                )
                sections.append(_SECTION_TEMPLATE.format(
                    heading="공포-탐욕 지수 추이",
                    chart_html=_fig_to_html(fig_ts),
                ))

        # ── 3. 구성 지표 기여도 바 차트 ────────────────────────────────────
        if fg_components:
            labels = list(fg_components.keys())
            values = list(fg_components.values())
            colors = ["#2ecc71" if v > 0 else "#e74c3c" for v in values]

            fig_comp = go.Figure(go.Bar(
                x=labels, y=values,
                marker_color=colors,
                text=[f"{v:+.3f}" for v in values],
                textposition="outside",
            ))
            fig_comp.add_hline(y=0, line_color="#95a5a6")
            fig_comp.update_layout(
                title="구성 지표 기여도 (방향 보정 Z-Score)",
                yaxis_title="기여 강도",
                showlegend=False,
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="지표별 기여도",
                chart_html=_fig_to_html(fig_comp),
            ))

    except Exception as e:
        log.warning("build_m6_report: 공포-탐욕 계산 실패: %s", e)
        sections.append(_SECTION_TEMPLATE.format(
            heading="데이터 부족",
            chart_html=f"<p>공포-탐욕 지수 계산에 필요한 데이터가 부족합니다: {e}</p>",
        ))

    html = _HTML_TEMPLATE.format(
        title=f"공포-탐욕 지수 분석 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_m6_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_d6_report  (D-6 암호화폐 고래·기관 일간 스냅샷)
# ---------------------------------------------------------------------------

def build_d6_report(
    master: pd.DataFrame,
    date: str | None = None,
    btc_companies_df=None,
    output_path: str | None = None,
) -> str:
    """
    D-6 암호화폐 고래·기관 일간 스냅샷 HTML 리포트.

    포함 섹션:
      1. 고래 온체인 신호 카드 (거래소 유입/유출 현황)
      2. 거래소 유입/유출 7일 라인 차트
      3. 대형 트랜잭션 알림 테이블 (당일)
      4. 비트코인 현물 ETF 성과 테이블

    Args:
        master          : build_master_dataset() 반환값
        date            : 기준일, None이면 마지막 유효일
        btc_companies_df: CoinGecko 공개기업 BTC 보유량 (선택)
        output_path     : None이면 reports/daily/d6_crypto_intel_{date}.html

    Returns: 저장 경로(str)
    """
    daily_dir = REPORTS_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    ref_date = date or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else daily_dir / f"d6_crypto_intel_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    try:
        from analysis.crypto_intel import crypto_intel_summary, whale_flow_summary, etf_flow_summary

        intel = crypto_intel_summary(master, btc_companies_df)
        whale_s = intel.get("whale", {})
        etf_s   = intel.get("etf", {})
        overall_signal = intel.get("overall_signal", 0)
        overall_label  = intel.get("overall_label", "중립")

        # ── 1. 종합 신호 카드 ──────────────────────────────────────────────
        if overall_signal == 1:
            sig_color = "#2ecc71"
        elif overall_signal == -1:
            sig_color = "#e74c3c"
        else:
            sig_color = "#f39c12"

        # 고래 유입/유출 비율
        io_ratio = whale_s.get("inflow_outflow_ratio")
        io_str   = f"{io_ratio:.2f}" if io_ratio is not None else "—"
        net7d    = whale_s.get("net_flow_7d", 0)
        net7d_str = f"{net7d:+,.0f} BTC" if net7d else "—"
        alert_cnt = whale_s.get("alert_count_7d", 0)

        signal_card = (
            f"<div style='display:flex;gap:12px;flex-wrap:wrap'>"
            # 종합 신호
            f"<div style='flex:1;min-width:140px;text-align:center;padding:16px;"
            f"background:{sig_color}22;border:2px solid {sig_color};border-radius:8px'>"
            f"<div style='font-size:1.4em;font-weight:bold;color:{sig_color}'>{overall_label}</div>"
            f"<div style='color:#555;margin-top:6px;font-size:0.9em'>고래·ETF·기관 종합</div>"
            f"</div>"
            # 7일 순유량
            f"<div style='flex:1;min-width:140px;text-align:center;padding:16px;"
            f"background:#ecf0f1;border-radius:8px'>"
            f"<div style='font-size:1.3em;font-weight:bold;color:#2c3e50'>{net7d_str}</div>"
            f"<div style='color:#555;margin-top:6px;font-size:0.9em'>거래소 7일 순유출(BTC)</div>"
            f"</div>"
            # 대형 이동 건수
            f"<div style='flex:1;min-width:140px;text-align:center;padding:16px;"
            f"background:#ecf0f1;border-radius:8px'>"
            f"<div style='font-size:1.3em;font-weight:bold;color:#8e44ad'>{alert_cnt}건</div>"
            f"<div style='color:#555;margin-top:6px;font-size:0.9em'>7일 대형 이동 (≥100만USD)</div>"
            f"</div>"
            # 유입/유출 비율
            f"<div style='flex:1;min-width:140px;text-align:center;padding:16px;"
            f"background:#ecf0f1;border-radius:8px'>"
            f"<div style='font-size:1.3em;font-weight:bold;color:#2980b9'>{io_str}</div>"
            f"<div style='color:#555;margin-top:6px;font-size:0.9em'>30일 유출/유입 비율</div>"
            f"</div>"
            f"</div>"
        )
        sections.append(_SECTION_TEMPLATE.format(heading="고래·기관 종합 신호", chart_html=signal_card))

    except Exception as e:
        log.warning("build_d6_report: 신호 계산 실패: %s", e)

    # ── 2. 거래소 유입/유출 7일 라인 차트 ──────────────────────────────────
    flow_cols = {
        "whale_btc_exchange_inflow":  ("거래소 유입 (BTC)", "#e74c3c"),
        "whale_btc_exchange_outflow": ("거래소 유출 (BTC)", "#2ecc71"),
        "whale_btc_exchange_net":     ("순유출 (BTC)", "#3498db"),
    }
    available_flow = {k: v for k, v in flow_cols.items() if k in master.columns}

    if available_flow:
        cutoff = pd.Timestamp(ref_date) - pd.Timedelta(days=60)
        df_flow = master[[c for c in available_flow]].loc[master.index >= cutoff].dropna(how="all")
        if not df_flow.empty:
            fig_flow = go.Figure()
            for col, (label, color) in available_flow.items():
                if col in df_flow.columns:
                    s = df_flow[col].dropna()
                    if not s.empty:
                        fig_flow.add_trace(go.Scatter(
                            x=s.index, y=s.values, mode="lines",
                            name=label, line=dict(color=color, width=2),
                        ))
            fig_flow.add_hline(y=0, line_dash="dot", line_color="#bdc3c7")
            fig_flow.update_layout(
                title="거래소 BTC 유입/유출 추이 (최근 60일)",
                yaxis_title="BTC",
                hovermode="x unified",
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="거래소 온체인 자금 흐름",
                chart_html=_fig_to_html(fig_flow),
            ))

    # ── 3. 대형 트랜잭션 알림 테이블 ───────────────────────────────────────
    alert_vol_col = "whale_alert_volume_usd"
    alert_cnt_col = "whale_alert_count"
    if alert_cnt_col in master.columns or alert_vol_col in master.columns:
        cutoff14 = pd.Timestamp(ref_date) - pd.Timedelta(days=14)
        alert_cols = [c for c in [alert_cnt_col, alert_vol_col,
                                   "whale_exchange_inflow_count", "whale_exchange_outflow_count"]
                      if c in master.columns]
        df_alert = master[alert_cols].loc[master.index >= cutoff14].dropna(how="all")
        if not df_alert.empty:
            tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
                   "<tr style='background:#ecf0f1'>"
                   "<th style='padding:6px 12px;text-align:left'>날짜</th>"
                   "<th style='padding:6px 12px;text-align:right'>대형 이동 건수</th>"
                   "<th style='padding:6px 12px;text-align:right'>총액 (백만 USD)</th>"
                   "<th style='padding:6px 12px;text-align:right'>거래소 유입</th>"
                   "<th style='padding:6px 12px;text-align:right'>거래소 유출</th>"
                   "</tr>")
            for i, (dt, row) in enumerate(df_alert.tail(14).iterrows()):
                bg = "#fff" if i % 2 == 0 else "#f8f9fa"
                dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
                cnt     = int(row.get(alert_cnt_col, 0)) if alert_cnt_col in row.index else "—"
                vol     = f"{row.get(alert_vol_col, 0):.1f}" if alert_vol_col in row.index else "—"
                inf_cnt = int(row.get("whale_exchange_inflow_count", 0)) if "whale_exchange_inflow_count" in row.index else "—"
                out_cnt = int(row.get("whale_exchange_outflow_count", 0)) if "whale_exchange_outflow_count" in row.index else "—"
                tbl += (f"<tr style='background:{bg}'>"
                        f"<td style='padding:6px 12px'>{dt_str}</td>"
                        f"<td style='padding:6px 12px;text-align:right'>{cnt}</td>"
                        f"<td style='padding:6px 12px;text-align:right'>{vol}</td>"
                        f"<td style='padding:6px 12px;text-align:right;color:#e74c3c'>{inf_cnt}</td>"
                        f"<td style='padding:6px 12px;text-align:right;color:#2ecc71'>{out_cnt}</td>"
                        "</tr>")
            tbl += "</table>"
            sections.append(_SECTION_TEMPLATE.format(heading="최근 14일 대형 트랜잭션 현황", chart_html=tbl))

    # ── 4. ETF 성과 테이블 ──────────────────────────────────────────────────
    try:
        from analysis.crypto_intel import etf_flow_summary
        etf_s = etf_flow_summary(master)
        etf_perf = etf_s.get("etf_performance", {})
        if etf_perf:
            tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
                   "<tr style='background:#ecf0f1'>"
                   "<th style='padding:6px 12px;text-align:left'>ETF</th>"
                   "<th style='padding:6px 12px;text-align:right'>현재가 (USD)</th>"
                   "<th style='padding:6px 12px;text-align:right'>30일 변화</th>"
                   "</tr>")
            for i, (ticker, info) in enumerate(sorted(etf_perf.items())):
                bg = "#fff" if i % 2 == 0 else "#f8f9fa"
                chg = info.get("change_pct", 0)
                color = "#2ecc71" if chg > 0 else "#e74c3c"
                chg_str = f"{chg:+.2f}%" if chg is not None else "—"
                tbl += (f"<tr style='background:{bg}'>"
                        f"<td style='padding:6px 12px;font-weight:bold'>{ticker}</td>"
                        f"<td style='padding:6px 12px;text-align:right'>${info.get('current', 0):,.2f}</td>"
                        f"<td style='padding:6px 12px;text-align:right;color:{color}'>{chg_str}</td>"
                        "</tr>")
            tbl += "</table>"
            avg_chg = etf_s.get("total_etf_aum_change_pct")
            if avg_chg is not None:
                tbl += f"<p style='color:#666;font-size:0.85em'>30일 평균 변화: {avg_chg:+.2f}%</p>"
            sections.append(_SECTION_TEMPLATE.format(heading="비트코인 현물 ETF 현황", chart_html=tbl))
    except Exception as e:
        log.warning("build_d6_report: ETF 테이블 실패: %s", e)

    html = _HTML_TEMPLATE.format(
        title=f"암호화폐 고래·기관 스냅샷 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_d6_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_w6_report  (W-6 기관 포트폴리오 변화 주간)
# ---------------------------------------------------------------------------

def build_w6_report(
    master: pd.DataFrame,
    week_end: str | None = None,
    btc_companies_df=None,
    sec_13f_df=None,
    output_path: str | None = None,
) -> str:
    """
    W-6 기관 포트폴리오 변화 주간 리포트.

    포함 섹션:
      1. 공개기업 BTC 보유량 상위 15개사 바 차트
      2. ETF 운용사별 가격 추이 라인 차트 (12주)
      3. 13F 분기 공시 암호화폐 포지션 테이블

    Args:
        master          : build_master_dataset() 반환값
        week_end        : 주 기준일
        btc_companies_df: CoinGecko 공개기업 BTC 보유량
        sec_13f_df      : SEC 13F 분기 데이터
        output_path     : None이면 reports/weekly/w6_institution_{date}.html

    Returns: 저장 경로(str)
    """
    weekly_dir = REPORTS_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = week_end or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else weekly_dir / f"w6_institution_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    # ── 1. 공개기업 BTC 보유량 바 차트 ────────────────────────────────────
    if btc_companies_df is not None and not btc_companies_df.empty:
        top15 = btc_companies_df.head(15)
        companies = list(top15.index)
        holdings  = list(top15["total_holdings"].values)
        values_usd = list(top15["total_current_value_usd"].values)

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=companies,
            y=holdings,
            marker_color="#f39c12",
            text=[f"{h:,.0f}" for h in holdings],
            textposition="outside",
            name="BTC 보유량",
            customdata=values_usd,
            hovertemplate="%{x}<br>보유량: %{y:,.0f} BTC<br>현재가치: $%{customdata:,.0f}<extra></extra>",
        ))
        fig_bar.update_layout(
            title="공개기업 BTC 보유량 상위 15개사",
            yaxis_title="BTC",
            xaxis_tickangle=-30,
            height=450,
        )
        sections.append(_SECTION_TEMPLATE.format(
            heading="공개기업 BTC 보유 현황 (CoinGecko)",
            chart_html=_fig_to_html(fig_bar),
        ))

        # 요약 카드
        try:
            from analysis.crypto_intel import institution_accumulation_signal
            inst_s = institution_accumulation_signal(btc_companies_df)
            total_btc = inst_s.get("total_btc", 0)
            total_usd = inst_s.get("total_value_usd", 0)
            summary_card = (
                f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin-top:12px'>"
                f"<div style='flex:1;min-width:160px;text-align:center;padding:14px;"
                f"background:#f39c1222;border:2px solid #f39c12;border-radius:8px'>"
                f"<div style='font-size:1.5em;font-weight:bold;color:#f39c12'>{total_btc:,.0f} BTC</div>"
                f"<div style='color:#555;margin-top:4px'>공개기업 총 보유량</div>"
                f"</div>"
                f"<div style='flex:1;min-width:160px;text-align:center;padding:14px;"
                f"background:#ecf0f1;border-radius:8px'>"
                f"<div style='font-size:1.5em;font-weight:bold;color:#2c3e50'>${total_usd/1e9:.1f}B</div>"
                f"<div style='color:#555;margin-top:4px'>현재 총 가치 (USD)</div>"
                f"</div>"
                f"<div style='flex:1;min-width:160px;text-align:center;padding:14px;"
                f"background:#ecf0f1;border-radius:8px'>"
                f"<div style='font-size:1.5em;font-weight:bold;color:#2c3e50'>{len(btc_companies_df)}개사</div>"
                f"<div style='color:#555;margin-top:4px'>보유 기업 수</div>"
                f"</div>"
                f"</div>"
            )
            sections.append(_SECTION_TEMPLATE.format(heading="기관 보유 요약", chart_html=summary_card))
        except Exception as e:
            log.warning("build_w6_report: 기관 요약 실패: %s", e)

    else:
        sections.append(_SECTION_TEMPLATE.format(
            heading="공개기업 BTC 보유 현황",
            chart_html="<p>CoinGecko 기업 데이터를 먼저 수집해주세요 (get_public_company_holdings).</p>",
        ))

    # ── 2. ETF 가격 추이 라인 차트 (12주) ─────────────────────────────────
    etf_close_cols = [c for c in master.columns if c.startswith("etf_") and c.endswith("_close")]
    if etf_close_cols:
        cutoff = pd.Timestamp(ref_date) - pd.Timedelta(weeks=12)
        df_etf = master[etf_close_cols].loc[master.index >= cutoff].dropna(how="all")
        if not df_etf.empty:
            fig_etf = go.Figure()
            colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12",
                      "#9b59b6", "#1abc9c", "#e67e22", "#95a5a6"]
            for i, col in enumerate(etf_close_cols):
                ticker = col.replace("etf_", "").replace("_close", "").upper()
                s = df_etf[col].dropna()
                if s.empty:
                    continue
                # 정규화 (시작=100 기준)
                s_norm = s / s.iloc[0] * 100
                fig_etf.add_trace(go.Scatter(
                    x=s_norm.index, y=s_norm.values,
                    mode="lines", name=ticker,
                    line=dict(color=colors[i % len(colors)], width=2),
                ))
            fig_etf.add_hline(y=100, line_dash="dot", line_color="#bdc3c7",
                               annotation_text="기준 (100)")
            fig_etf.update_layout(
                title="비트코인 ETF 가격 추이 (12주, 시작=100 정규화)",
                yaxis_title="정규화 지수 (시작=100)",
                hovermode="x unified",
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="비트코인 현물 ETF 상대 성과",
                chart_html=_fig_to_html(fig_etf),
            ))

    # ── 3. SEC 13F 테이블 ──────────────────────────────────────────────────
    if sec_13f_df is not None and not sec_13f_df.empty:
        tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
               "<tr style='background:#ecf0f1'>"
               "<th style='padding:6px 12px;text-align:left'>기관</th>"
               "<th style='padding:6px 12px;text-align:left'>증권</th>"
               "<th style='padding:6px 12px;text-align:right'>보유 수량</th>"
               "<th style='padding:6px 12px;text-align:right'>가치 (USD)</th>"
               "<th style='padding:6px 12px;text-align:right'>분기</th>"
               "</tr>")
        for i, row in sec_13f_df.iterrows():
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            tbl += (f"<tr style='background:{bg}'>"
                    f"<td style='padding:6px 12px;font-weight:bold'>{row.get('institution', '')}</td>"
                    f"<td style='padding:6px 12px'>{row.get('security_name', '')}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>{row.get('shares', 0):,}</td>"
                    f"<td style='padding:6px 12px;text-align:right'>${row.get('value_usd', 0):,.0f}</td>"
                    f"<td style='padding:6px 12px;text-align:right;color:#999'>{row.get('quarter', '')}</td>"
                    "</tr>")
        tbl += "</table>"
        sections.append(_SECTION_TEMPLATE.format(heading="SEC 13F 암호화폐 포지션", chart_html=tbl))

    html = _HTML_TEMPLATE.format(
        title=f"기관 암호화폐 포트폴리오 — {ref_date}",
        generated_at=ref_date, date_range=ref_date,
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_w6_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_w1_report  (W-1 자산 간 상관관계 주간 변화)
# ---------------------------------------------------------------------------

def build_w1_report(
    master: pd.DataFrame,
    week_end: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    W-1 자산 간 상관관계 주간 변화 리포트.

    포함 섹션:
      1. 이번 주 Spearman 상관 히트맵
      2. 주간 변화량 히트맵 (이번 주 - 직전 주)
      3. 상관 변화 Top-5 자산 쌍 테이블
    """
    weekly_dir = REPORTS_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = week_end or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date.today()))
    out = Path(output_path) if output_path else weekly_dir / f"w1_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    close_cols = _select_close_cols(master, max_cols=15)

    if len(close_cols) < 2:
        log.warning("build_w1_report: close 컬럼 부족 (%d개)", len(close_cols))
        return _save_empty_report(out, "W-1 자산 상관관계", ref_date)

    ref_ts  = pd.Timestamp(ref_date)
    w0_end  = ref_ts
    w0_start = ref_ts - pd.Timedelta(days=6)   # 이번 주 (5 거래일 ≈ 7일)
    w1_end   = w0_start - pd.Timedelta(days=1)
    w1_start = w1_end   - pd.Timedelta(days=6)  # 직전 주

    df_w0 = master.loc[w0_start:w0_end, close_cols].dropna(how="all")
    df_w1 = master.loc[w1_start:w1_end, close_cols].dropna(how="all")

    # ── 이번 주 히트맵 ────────────────────────────────────────────────────
    if not df_w0.empty and len(df_w0) >= 2:
        try:
            fig_now = plot_correlation_heatmap(df_w0, f"이번 주 자산 상관관계 ({w0_start.date()} ~ {w0_end.date()})")
            sections.append(_SECTION_TEMPLATE.format(
                heading="이번 주 Spearman 상관관계",
                chart_html=_fig_to_html(fig_now),
            ))
        except Exception as e:
            log.warning("build_w1_report: 이번 주 히트맵 실패: %s", e)

    # ── 변화량 히트맵 ─────────────────────────────────────────────────────
    if not df_w0.empty and not df_w1.empty and len(df_w0) >= 2 and len(df_w1) >= 2:
        try:
            corr_now  = df_w0.corr(method="spearman")
            corr_prev = df_w1.corr(method="spearman")
            corr_prev = corr_prev.reindex(index=corr_now.index, columns=corr_now.columns).fillna(0)
            delta = corr_now - corr_prev

            labels = [c.replace("_close", "").replace("_", " ") for c in delta.columns]
            fig_delta = go.Figure(go.Heatmap(
                z=delta.values,
                x=labels, y=labels,
                text=delta.round(2).astype(str).values.tolist(),
                texttemplate="%{text}",
                colorscale="RdBu_r", zmin=-1, zmax=1,
                colorbar=dict(title="Δρ"),
            ))
            fig_delta.update_layout(
                title=f"상관관계 주간 변화 (이번 주 - 직전 주)",
                xaxis=dict(tickangle=-45, tickfont=dict(size=11)),
                yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
                margin=dict(l=120, r=40, t=80, b=120),
            )
            sections.append(_SECTION_TEMPLATE.format(
                heading="상관관계 주간 변화 히트맵",
                chart_html=_fig_to_html(fig_delta),
            ))

            # Top-5 변화 쌍
            pairs = []
            n = len(delta.columns)
            for i in range(n):
                for j in range(i + 1, n):
                    pairs.append((delta.columns[i], delta.columns[j], delta.iloc[i, j]))
            pairs.sort(key=lambda x: abs(x[2]), reverse=True)

            tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
                   "<tr style='background:#ecf0f1'>"
                   "<th style='padding:8px 16px'>자산 A</th>"
                   "<th style='padding:8px 16px'>자산 B</th>"
                   "<th style='padding:8px 16px;text-align:right'>이번 주 ρ</th>"
                   "<th style='padding:8px 16px;text-align:right'>직전 주 ρ</th>"
                   "<th style='padding:8px 16px;text-align:right'>변화 Δρ</th>"
                   "</tr>")
            for a, b, d in pairs[:5]:
                r_now  = round(corr_now.loc[a, b], 3)
                r_prev = round(corr_prev.loc[a, b], 3)
                color  = "#e74c3c" if d > 0 else "#2980b9"
                sign   = "+" if d > 0 else ""
                la = a.replace("_close", "").replace("_", " ")
                lb = b.replace("_close", "").replace("_", " ")
                tbl += (f"<tr>"
                        f"<td style='padding:8px 16px;font-weight:bold'>{la}</td>"
                        f"<td style='padding:8px 16px;font-weight:bold'>{lb}</td>"
                        f"<td style='padding:8px 16px;text-align:right'>{r_now}</td>"
                        f"<td style='padding:8px 16px;text-align:right'>{r_prev}</td>"
                        f"<td style='padding:8px 16px;text-align:right;color:{color};font-weight:bold'>"
                        f"{sign}{round(d, 3)}</td>"
                        "</tr>")
            tbl += "</table>"
            sections.append(_SECTION_TEMPLATE.format(
                heading="상관관계 변화 Top-5 자산 쌍",
                chart_html=tbl,
            ))
        except Exception as e:
            log.warning("build_w1_report: 변화량 히트맵 실패: %s", e)

    html = _HTML_TEMPLATE.format(
        title=f"[W] 자산 간 상관관계 주간 변화 — {ref_date}",
        generated_at=ref_date,
        date_range=f"{w1_start.date()} ~ {w0_end.date()}",
        sections="\n".join(sections) if sections else "<p>데이터 부족으로 히트맵 생성 불가</p>",
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_w1_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_m2_report  (M-2 삼성전자 S-RIM 적정가 & 팩터)
# ---------------------------------------------------------------------------

def build_m2_report(
    master: pd.DataFrame,
    ticker: str = "005930",
    output_path: str | None = None,
) -> str:
    """
    M-2 S-RIM 적정가 & 팩터 리포트.

    S-RIM (Simplified Residual Income Model):
      적정가 = BPS × ROE / COE
      밴드: BPS × ROE / (COE ± 0.02)

    포함 섹션:
      1. S-RIM 적정가 밴드 vs 현재가 라인 차트
      2. ROE 추이 라인
      3. 괴리율 요약 카드
    """
    monthly_dir = REPORTS_DIR / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = master.index[-1].strftime("%Y-%m") if not master.empty else str(date.today())[:7]
    out = Path(output_path) if output_path else monthly_dir / f"m2_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    COE = 0.10  # Cost of Equity: 10% 가정

    # 필요 컬럼 탐색
    price_col = f"kr_{ticker}_close"
    roe_col   = next((c for c in master.columns if ticker in c and "roe" in c.lower()), None)
    bps_col   = next((c for c in master.columns if ticker in c and "bps" in c.lower()), None)

    # DART 데이터 없으면 master에서 PER/PBR로 근사
    per_col = next((c for c in master.columns if ticker in c and "per" in c.lower()), None)
    pbr_col = next((c for c in master.columns if ticker in c and "pbr" in c.lower()), None)

    has_data = (price_col in master.columns) and (roe_col or (per_col and pbr_col))

    if not has_data:
        log.warning("build_m2_report: %s 재무 데이터 없음 — 안내 메시지 출력", ticker)
        msg = (
            "<div style='padding:24px;background:#fff3cd;border-left:4px solid #ffc107;"
            "border-radius:4px'>"
            f"<strong>데이터 없음</strong>: {ticker} 재무 데이터(BPS/ROE/PBR)가 master에 없습니다.<br>"
            "DART API 키 설정 및 수집 실행 후 재시도하세요.<br>"
            "(<code>collectors/kr/financials.py</code> → <code>get_key_ratios()</code>)"
            "</div>"
        )
        sections.append(_SECTION_TEMPLATE.format(heading="S-RIM 분석", chart_html=msg))
    else:
        price_s = master[price_col].dropna()

        # ROE: 직접 컬럼 있으면 사용, 없으면 PBR/PER에서 근사 (ROE ≈ PBR/PER × 순이익 근사는 부정확 — BPS 없으면 스킵)
        if roe_col:
            roe_s = master[roe_col].dropna() / 100  # % → 소수
        elif per_col and pbr_col:
            # ROE = EPS/BPS = (Price/PER) / (Price/PBR) = PBR/PER
            roe_s = (master[pbr_col] / master[per_col]).replace([float("inf"), -float("inf")], float("nan")).dropna()
            log.info("build_m2_report: ROE를 PBR/PER 근사값으로 계산")
        else:
            roe_s = pd.Series(dtype=float)

        # BPS: 직접 없으면 price/PBR으로 역산
        if bps_col:
            bps_s = master[bps_col].dropna()
        elif pbr_col and price_col in master.columns:
            bps_s = (master[price_col] / master[pbr_col]).replace([float("inf"), -float("inf")], float("nan")).dropna()
            log.info("build_m2_report: BPS를 Price/PBR 역산값으로 계산")
        else:
            bps_s = pd.Series(dtype=float)

        if not roe_s.empty and not bps_s.empty:
            common_idx = price_s.index.intersection(roe_s.index).intersection(bps_s.index)
            if len(common_idx) >= 2:
                p  = price_s.reindex(common_idx)
                r  = roe_s.reindex(common_idx)
                b  = bps_s.reindex(common_idx)

                fair_base  = b * r / COE
                fair_upper = b * r / (COE - 0.02)  # COE-2% → 상단
                fair_lower = b * r / (COE + 0.02)  # COE+2% → 하단

                # 괴리율
                last_price = p.iloc[-1]
                last_fair  = fair_base.iloc[-1]
                gap_pct    = (last_price / last_fair - 1) * 100 if last_fair != 0 else float("nan")

                # ── S-RIM 차트 ────────────────────────────────────────────
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=common_idx, y=p.values,  name="현재가",   line=dict(color="#2c3e50", width=2)))
                fig.add_trace(go.Scatter(x=common_idx, y=fair_base.values,  name=f"적정가 (COE={COE*100:.0f}%)", line=dict(color="#27ae60", width=2, dash="dash")))
                fig.add_trace(go.Scatter(x=common_idx, y=fair_upper.values, name="상단 밴드 (COE-2%)", line=dict(color="#e74c3c", width=1, dash="dot")))
                fig.add_trace(go.Scatter(x=common_idx, y=fair_lower.values, name="하단 밴드 (COE+2%)",
                                         fill="tonexty", fillcolor="rgba(39,174,96,0.08)",
                                         line=dict(color="#3498db", width=1, dash="dot")))
                fig.update_layout(title=f"{ticker} S-RIM 적정가 밴드", xaxis_title="날짜", yaxis_title="가격 (원)", hovermode="x unified")
                sections.append(_SECTION_TEMPLATE.format(heading="S-RIM 적정가 밴드 vs 현재가", chart_html=_fig_to_html(fig)))

                # ── ROE 추이 ─────────────────────────────────────────────
                fig_roe = go.Figure(go.Scatter(x=common_idx, y=(r * 100).values, name="ROE (%)", line=dict(color="#8e44ad", width=2)))
                fig_roe.add_hline(y=COE * 100, line_dash="dash", line_color="#e74c3c", annotation_text=f"COE={COE*100:.0f}%")
                fig_roe.update_layout(title=f"{ticker} ROE 추이", xaxis_title="날짜", yaxis_title="ROE (%)")
                sections.append(_SECTION_TEMPLATE.format(heading="ROE 추이", chart_html=_fig_to_html(fig_roe)))

                # ── 괴리율 카드 ───────────────────────────────────────────
                gap_color = "#e74c3c" if gap_pct > 20 else ("#f39c12" if gap_pct > 0 else "#27ae60")
                gap_label = "고평가" if gap_pct > 20 else ("소폭 고평가" if gap_pct > 0 else "저평가")
                card = (
                    f"<div style='display:flex;gap:24px;flex-wrap:wrap'>"
                    f"<div style='padding:20px 28px;background:#f8f9fa;border-radius:8px;min-width:160px'>"
                    f"<div style='font-size:0.85em;color:#7f8c8d'>현재가</div>"
                    f"<div style='font-size:1.6em;font-weight:bold;color:#2c3e50'>{last_price:,.0f}원</div></div>"
                    f"<div style='padding:20px 28px;background:#f8f9fa;border-radius:8px;min-width:160px'>"
                    f"<div style='font-size:0.85em;color:#7f8c8d'>S-RIM 적정가</div>"
                    f"<div style='font-size:1.6em;font-weight:bold;color:#27ae60'>{last_fair:,.0f}원</div></div>"
                    f"<div style='padding:20px 28px;background:{gap_color}18;border-radius:8px;border-left:4px solid {gap_color};min-width:160px'>"
                    f"<div style='font-size:0.85em;color:#7f8c8d'>괴리율</div>"
                    f"<div style='font-size:1.6em;font-weight:bold;color:{gap_color}'>"
                    f"{'+'if gap_pct>0 else ''}{gap_pct:.1f}% ({gap_label})</div></div>"
                    f"</div>"
                )
                sections.append(_SECTION_TEMPLATE.format(heading="S-RIM 괴리율 요약", chart_html=card))

    html = _HTML_TEMPLATE.format(
        title=f"[{ref_date}] {ticker} S-RIM 적정가 & 팩터",
        generated_at=ref_date,
        date_range=f"{master.index[0].date() if not master.empty else ''} ~ {master.index[-1].date() if not master.empty else ''}",
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_m2_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_m4_report  (M-4 동일가중 멀티에셋 백테스팅)
# ---------------------------------------------------------------------------

_M4_ASSETS = [
    "us_sp500_close",
    "kr_kospi_close",
    "cmd_wti_close",
    "cmd_gold_close",
    "rate_us10y_close",
    "crypto_btc_close",
]
_M4_BENCHMARK = "kr_kospi_close"


def build_m4_report(
    master: pd.DataFrame,
    output_path: str | None = None,
) -> str:
    """
    M-4 동일가중 멀티에셋 백테스팅 성과 리포트.

    포함 섹션:
      1. 포트폴리오 vs KOSPI 누적 수익률 라인 차트
      2. 성과 지표 카드 (알파, 샤프, MDD, 연환산 수익률)
      3. 연도별 수익률 테이블
    """
    monthly_dir = REPORTS_DIR / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)

    ref_date = master.index[-1].strftime("%Y-%m") if not master.empty else str(date.today())[:7]
    out = Path(output_path) if output_path else monthly_dir / f"m4_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    # 사용 가능한 자산만 선택
    valid_cols = [c for c in _M4_ASSETS if c in master.columns]
    if len(valid_cols) < 2:
        log.warning("build_m4_report: 자산 데이터 부족 (%d개)", len(valid_cols))
        return _save_empty_report(out, "M-4 백테스팅", ref_date)

    try:
        from analysis.backtest import run_backtest, calc_returns

        # 항상 전체 보유 신호 (동일가중 buy-and-hold)
        def all_in_signal(m: pd.DataFrame) -> pd.DataFrame:
            prices = m[valid_cols].dropna(how="all")
            return pd.DataFrame(True, index=prices.index, columns=valid_cols)

        result = run_backtest(
            master=master,
            price_cols=valid_cols,
            signal_func=all_in_signal,
            rebal_freq="ME",
            transaction_cost=0.001,
            benchmark_col=_M4_BENCHMARK,
        )

        cumul      = result["cumulative"]
        bench_cumul = result["benchmark_cumulative"]
        metrics    = result["metrics"]

        if cumul.empty:
            raise ValueError("백테스팅 결과 없음")

        # ── 누적 수익률 차트 ─────────────────────────────────────────────
        returns_dict: dict[str, pd.Series] = {"멀티에셋 포트폴리오": cumul}
        if not bench_cumul.empty:
            returns_dict["KOSPI (벤치마크)"] = bench_cumul

        fig = plot_cumulative_returns(returns_dict, title="멀티에셋 포트폴리오 vs KOSPI 누적 수익률")
        sections.append(_SECTION_TEMPLATE.format(
            heading="누적 수익률 비교",
            chart_html=_fig_to_html(fig),
        ))

        # ── 성과 지표 카드 ───────────────────────────────────────────────
        def _pct(v) -> str:
            return f"{v*100:.1f}%" if v is not None else "N/A"

        def _f(v, fmt=".2f") -> str:
            return f"{v:{fmt}}" if v is not None else "N/A"

        alpha_color = "#27ae60" if (metrics.get("alpha") or 0) > 0 else "#e74c3c"
        cards_html = (
            f"<div style='display:flex;gap:20px;flex-wrap:wrap'>"
            f"<div style='padding:18px 24px;background:#f8f9fa;border-radius:8px;min-width:140px'>"
            f"<div style='font-size:0.82em;color:#7f8c8d'>연환산 수익률</div>"
            f"<div style='font-size:1.5em;font-weight:bold;color:#2c3e50'>{_pct(metrics.get('annualized_return'))}</div></div>"
            f"<div style='padding:18px 24px;background:#f8f9fa;border-radius:8px;min-width:140px'>"
            f"<div style='font-size:0.82em;color:#7f8c8d'>샤프 비율</div>"
            f"<div style='font-size:1.5em;font-weight:bold;color:#2c3e50'>{_f(metrics.get('sharpe_ratio'))}</div></div>"
            f"<div style='padding:18px 24px;background:#f8f9fa;border-radius:8px;min-width:140px'>"
            f"<div style='font-size:0.82em;color:#7f8c8d'>최대 낙폭 (MDD)</div>"
            f"<div style='font-size:1.5em;font-weight:bold;color:#e74c3c'>{_pct(metrics.get('max_drawdown'))}</div></div>"
            f"<div style='padding:18px 24px;background:{alpha_color}18;border-radius:8px;border-left:4px solid {alpha_color};min-width:140px'>"
            f"<div style='font-size:0.82em;color:#7f8c8d'>KOSPI 대비 알파</div>"
            f"<div style='font-size:1.5em;font-weight:bold;color:{alpha_color}'>"
            f"{'+'if (metrics.get('alpha') or 0)>0 else ''}{_pct(metrics.get('alpha'))}</div></div>"
            f"</div>"
        )
        sections.append(_SECTION_TEMPLATE.format(heading="성과 지표", chart_html=cards_html))

        # ── 연도별 수익률 테이블 ─────────────────────────────────────────
        port_ret = result["returns"]
        if not port_ret.empty:
            annual_port  = (1 + port_ret).resample("YE").prod() - 1
            if not bench_cumul.empty:
                bench_ret = bench_cumul.diff().fillna(bench_cumul.iloc[0])
                annual_bench = (1 + bench_ret).resample("YE").prod() - 1
            else:
                annual_bench = pd.Series(dtype=float)

            tbl = ("<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
                   "<tr style='background:#ecf0f1'>"
                   "<th style='padding:8px 16px'>연도</th>"
                   "<th style='padding:8px 16px;text-align:right'>포트폴리오</th>"
                   "<th style='padding:8px 16px;text-align:right'>KOSPI</th>"
                   "<th style='padding:8px 16px;text-align:right'>초과 수익</th>"
                   "</tr>")
            for yr in annual_port.index:
                yr_str = yr.strftime("%Y")
                p_val  = annual_port.get(yr, float("nan"))
                b_val  = annual_bench.get(yr, float("nan")) if not annual_bench.empty else float("nan")
                excess = (p_val - b_val) if (not pd.isna(p_val) and not pd.isna(b_val)) else float("nan")

                p_color = "#27ae60" if p_val > 0 else "#e74c3c"
                e_color = "#27ae60" if (not pd.isna(excess) and excess > 0) else "#e74c3c"
                tbl += (f"<tr>"
                        f"<td style='padding:8px 16px;font-weight:bold'>{yr_str}</td>"
                        f"<td style='padding:8px 16px;text-align:right;color:{p_color}'>"
                        f"{'+'if p_val>0 else ''}{p_val*100:.1f}%</td>"
                        f"<td style='padding:8px 16px;text-align:right'>"
                        f"{'N/A' if pd.isna(b_val) else f'{b_val*100:.1f}%'}</td>"
                        f"<td style='padding:8px 16px;text-align:right;color:{e_color}'>"
                        f"{'N/A' if pd.isna(excess) else f'{'+'if excess>0 else ''}{excess*100:.1f}%'}</td>"
                        "</tr>")
            tbl += "</table>"
            sections.append(_SECTION_TEMPLATE.format(heading="연도별 수익률", chart_html=tbl))

    except Exception as e:
        log.error("build_m4_report: 백테스팅 실패: %s", e)
        sections.append(_SECTION_TEMPLATE.format(
            heading="백테스팅 오류",
            chart_html=f"<p style='color:#e74c3c'>백테스팅 실행 중 오류: {e}</p>",
        ))

    # 편입 자산 목록
    asset_names = [c.replace("_close", "").replace("_", " ") for c in valid_cols]
    asset_info = (
        f"<p style='color:#7f8c8d;font-size:0.9em'>"
        f"편입 자산 ({len(valid_cols)}개): {', '.join(asset_names)} | "
        f"리밸런싱: 월말 동일가중 | 거래비용: 0.1% 편도</p>"
    )
    sections.insert(0, _SECTION_TEMPLATE.format(heading="백테스팅 조건", chart_html=asset_info))

    html = _HTML_TEMPLATE.format(
        title=f"[{ref_date}] 동일가중 멀티에셋 백테스팅 성과",
        generated_at=ref_date,
        date_range=f"{master.index[0].date() if not master.empty else ''} ~ {master.index[-1].date() if not master.empty else ''}",
        sections="\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_m4_report: saved to %s", out)
    return str(out.resolve())


# ---------------------------------------------------------------------------
# build_alert_report  (긴급 리포트)
# ---------------------------------------------------------------------------

def build_alert_report(
    master: pd.DataFrame,
    alerts: list,
    date: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    긴급 이벤트 감지 시 생성되는 HTML 리포트.

    포함 섹션:
      1. 알림 요약 카드 (severity별 색상)
      2. 알림별 상세 컨텍스트
      3. 주요 자산 스냅샷 (현재값 + 1일/5일/30일 수익률)
      4. 신호 분류 테이블 (critical/warning/info)

    Args:
        master       : 병합된 master DataFrame
        alerts       : check_alerts() 반환값
        date         : 기준일, None이면 마지막 유효일
        output_path  : None이면 reports/alerts/alert_{date}.html

    Returns: 저장 경로(str)
    """
    from analysis.alerts import Alert, _SEVERITY_ORDER

    alerts_dir = REPORTS_DIR / "alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)

    ref_date = date or (master.index[-1].strftime("%Y-%m-%d") if not master.empty else str(date_today()))
    out = Path(output_path) if output_path else alerts_dir / f"alert_{ref_date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    ref_ts = pd.Timestamp(ref_date)
    sections: list[str] = []

    _SEV_COLOR  = {"critical": "#e74c3c", "warning": "#f39c12", "info": "#3498db"}
    _SEV_LABEL  = {"critical": "긴급", "warning": "경고", "info": "참고"}
    _SEV_BG     = {"critical": "#fdf0ef", "warning": "#fef9ec", "info": "#eaf4fb"}

    # ── 1. 알림 요약 카드 ─────────────────────────────────────────────────────
    n_critical = sum(1 for a in alerts if a.severity == "critical")
    n_warning  = sum(1 for a in alerts if a.severity == "warning")
    n_info     = sum(1 for a in alerts if a.severity == "info")

    summary_html = (
        f"<div style='display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px'>"
        f"<div style='padding:12px 24px;background:#e74c3c;color:#fff;border-radius:6px;"
        f"font-size:1.1em;font-weight:bold'>긴급 {n_critical}건</div>"
        f"<div style='padding:12px 24px;background:#f39c12;color:#fff;border-radius:6px;"
        f"font-size:1.1em;font-weight:bold'>경고 {n_warning}건</div>"
        f"<div style='padding:12px 24px;background:#3498db;color:#fff;border-radius:6px;"
        f"font-size:1.1em;font-weight:bold'>참고 {n_info}건</div>"
        f"</div>"
        f"<p style='color:#555;font-size:0.9em'>기준일: {ref_date} | 총 {len(alerts)}개 이벤트 감지</p>"
    )
    sections.append(_SECTION_TEMPLATE.format(
        heading="알림 요약",
        chart_html=summary_html,
    ))

    # ── 2. 알림별 상세 ───────────────────────────────────────────────────────
    alert_cards = ""
    for a in alerts:
        color  = _SEV_COLOR.get(a.severity, "#95a5a6")
        bg     = _SEV_BG.get(a.severity, "#f8f9fa")
        badge  = _SEV_LABEL.get(a.severity, a.severity)
        ctx_html = f"<div style='margin-top:8px;font-size:0.85em;color:#666'>{a.context}</div>" if a.context else ""
        alert_cards += (
            f"<div style='border-left:5px solid {color};background:{bg};"
            f"padding:14px 20px;margin-bottom:12px;border-radius:0 6px 6px 0'>"
            f"<div style='display:flex;align-items:center;gap:10px'>"
            f"<span style='background:{color};color:#fff;padding:2px 8px;"
            f"border-radius:3px;font-size:0.8em;font-weight:bold'>{badge}</span>"
            f"<span style='font-size:1.05em;font-weight:bold;color:{color}'>{a.title}</span>"
            f"</div>"
            f"<div style='margin-top:6px;color:#333'>{a.detail}</div>"
            f"{ctx_html}"
            f"</div>"
        )
    sections.append(_SECTION_TEMPLATE.format(
        heading="이벤트 상세",
        chart_html=alert_cards,
    ))

    # ── 3. 주요 자산 스냅샷 ──────────────────────────────────────────────────
    snap_cols = [
        ("us_sp500_close",    "S&P500",     "{:.2f}"),
        ("kr_kospi_close",    "KOSPI",      "{:.2f}"),
        ("cmd_gold_close",    "금",          "${:.2f}"),
        ("cmd_wti_close",     "WTI",        "${:.2f}"),
        ("fx_krw_usd_close",  "달러/원",    "{:.2f}"),
        ("alt_vix_close",     "VIX",        "{:.2f}"),
        ("crypto_btc_close",  "BTC",        "${:,.0f}"),
        ("rate_us10y_close",  "미10Y",      "{:.2f}%"),
    ]

    def _ret(col: str, n: int) -> str:
        if col not in master.columns:
            return "—"
        s = master[col].dropna()
        avail = s.index[s.index <= ref_ts]
        if len(avail) <= n:
            return "—"
        r = (float(s.loc[avail[-1]]) / float(s.loc[avail[-1 - n]]) - 1) * 100
        color = "#e74c3c" if r > 0 else "#2ecc71"
        return f"<span style='color:{color}'>{r:+.1f}%</span>"

    snap_tbl = (
        "<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
        "<tr style='background:#ecf0f1'>"
        "<th style='padding:6px 12px;text-align:left'>자산</th>"
        "<th style='padding:6px 12px;text-align:right'>현재값</th>"
        "<th style='padding:6px 12px;text-align:right'>1일</th>"
        "<th style='padding:6px 12px;text-align:right'>5일</th>"
        "<th style='padding:6px 12px;text-align:right'>30일</th>"
        "</tr>"
    )
    for i, (col, name, fmt) in enumerate(snap_cols):
        if col not in master.columns:
            continue
        s = master[col].dropna()
        avail = s.index[s.index <= ref_ts]
        if avail.empty:
            continue
        val = float(s.loc[avail[-1]])
        try:
            val_str = fmt.format(val)
        except Exception:
            val_str = f"{val:.2f}"
        bg = "#fff" if i % 2 == 0 else "#f8f9fa"
        snap_tbl += (
            f"<tr style='background:{bg}'>"
            f"<td style='padding:6px 12px;font-weight:bold'>{name}</td>"
            f"<td style='padding:6px 12px;text-align:right'>{val_str}</td>"
            f"<td style='padding:6px 12px;text-align:right'>{_ret(col, 1)}</td>"
            f"<td style='padding:6px 12px;text-align:right'>{_ret(col, 5)}</td>"
            f"<td style='padding:6px 12px;text-align:right'>{_ret(col, 30)}</td>"
            "</tr>"
        )
    snap_tbl += "</table>"
    sections.append(_SECTION_TEMPLATE.format(
        heading="주요 자산 스냅샷",
        chart_html=snap_tbl,
    ))

    # ── 4. 감성·심리 지표 ────────────────────────────────────────────────────
    psych_rows = []
    for col, label, lo, hi in [
        ("alt_vix_close",     "VIX (공포)",            15, 30),
        ("sent_news_global",  "뉴스 감성 (글로벌)",    -0.3, 0.3),
        ("sent_news_fed",     "뉴스 감성 (연준)",      -0.3, 0.3),
        ("epu_us",            "EPU 미국",              100, 250),
        ("trends_recession",  "recession 검색량",       5,  20),
        ("trends_stock_crash","stock crash 검색량",     3,  15),
    ]:
        if col not in master.columns:
            continue
        s_psych = master[col].dropna()
        avail = s_psych.index[s_psych.index <= ref_ts]
        if avail.empty:
            continue
        v = float(s_psych.loc[avail[-1]])
        status = "과열/공포" if v > hi else ("안정" if v < lo else "중립")
        psych_rows.append((label, f"{v:.3f}", status, avail[-1].strftime("%Y-%m-%d")))

    if psych_rows:
        psych_tbl = (
            "<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
            "<tr style='background:#ecf0f1'>"
            "<th style='padding:6px 12px;text-align:left'>지표</th>"
            "<th style='padding:6px 12px;text-align:right'>현재값</th>"
            "<th style='padding:6px 12px;text-align:right'>상태</th>"
            "<th style='padding:6px 12px;text-align:right'>기준일</th>"
            "</tr>"
        )
        for i, (lbl, val, status, dt) in enumerate(psych_rows):
            bg = "#fff" if i % 2 == 0 else "#f8f9fa"
            sc = "#e74c3c" if "공포" in status or "과열" in status else (
                "#2ecc71" if "안정" in status else "#f39c12"
            )
            psych_tbl += (
                f"<tr style='background:{bg}'>"
                f"<td style='padding:6px 12px'>{lbl}</td>"
                f"<td style='padding:6px 12px;text-align:right'>{val}</td>"
                f"<td style='padding:6px 12px;text-align:right;"
                f"color:{sc};font-weight:bold'>{status}</td>"
                f"<td style='padding:6px 12px;text-align:right;color:#999'>{dt}</td>"
                "</tr>"
            )
        psych_tbl += "</table>"
        sections.append(_SECTION_TEMPLATE.format(
            heading="심리·감성 지표",
            chart_html=psych_tbl,
        ))

    # ── 헤더 배너 ─────────────────────────────────────────────────────────────
    banner_color = "#e74c3c" if n_critical > 0 else ("#f39c12" if n_warning > 0 else "#3498db")
    banner = (
        f"<div style='padding:16px 24px;background:{banner_color};color:#fff;"
        f"border-radius:6px;margin-bottom:24px'>"
        f"<div style='font-size:1.4em;font-weight:bold'>긴급 시황 알림 — {ref_date}</div>"
        f"<div style='margin-top:6px;opacity:0.9'>"
        f"총 {len(alerts)}개 이벤트 감지 | 긴급 {n_critical} · 경고 {n_warning} · 참고 {n_info}</div>"
        f"</div>"
    )

    html = _HTML_TEMPLATE.format(
        title=f"긴급 시황 알림 — {ref_date}",
        generated_at=ref_date,
        date_range=ref_date,
        sections=banner + "\n".join(sections),
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    log.info("build_alert_report: saved to %s", out)
    return str(out.resolve())


def _save_empty_report(out: Path, title: str, ref_date: str) -> str:
    """데이터 부족 시 빈 리포트를 저장하고 경로를 반환한다."""
    html = _HTML_TEMPLATE.format(
        title=title,
        generated_at=ref_date,
        date_range=ref_date,
        sections="<p style='color:#e74c3c'>데이터 부족으로 리포트를 생성할 수 없습니다.</p>",
        disclaimer=get_html_disclaimer(lang="ko", length="short"),
    )
    out.write_text(html, encoding="utf-8")
    return str(out.resolve())
