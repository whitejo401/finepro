"""
visualization/report.py

master DataFrame으로 HTML 리포트를 생성한다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
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
