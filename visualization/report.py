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
    ("rate_fed",          "연준 기준금리"),
    ("rate_us10y",        "미 10년 금리"),
    ("rate_us2y",         "미 2년 금리"),
    ("rate_spread_10_2",  "10-2년 스프레드"),
    ("rate_hy_spread",    "하이일드 스프레드"),
    ("macro_cpi",         "미 CPI"),
    ("macro_unemployment","미 실업률"),
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
        prev_avail = s.index[s.index < latest_ts]
        if not prev_avail.empty:
            prev_val = s.loc[prev_avail[-1]]
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
