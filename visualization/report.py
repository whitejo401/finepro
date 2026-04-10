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
from visualization.charts import plot_correlation_heatmap, plot_cumulative_returns

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
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">생성일: {generated_at} &nbsp;|&nbsp; 데이터 기간: {date_range}</p>
  {sections}
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
            from analysis.regime import regime_summary
            pmi_col = next((c for c in master.columns if "pmi" in c), None)
            cpi_col = next((c for c in master.columns if "cpi" in c), None)
            if pmi_col and cpi_col:
                rsummary = regime_summary(master, pmi_col=pmi_col, cpi_col=cpi_col)
                if rsummary:
                    perf = rsummary.get("performance")
                    current = rsummary.get("current", "")
                    regime_html = f"<p><strong>현재 국면:</strong> {current}</p>"
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
    )

    out.write_text(html, encoding="utf-8")
    log.info("build_report: saved to %s", out)
    return str(out.resolve())
