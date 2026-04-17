"""
visualization/index.py
──────────────────────
리포트 인덱스 페이지 생성기.

build_index_page(master, output_path) → str
  - 생성된 모든 HTML 리포트를 카테고리별로 나열
  - 현재 핵심 지표 요약 카드
  - 최신 알림 배너
  - reports/index.html 로 저장
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from collectors.base import get_logger
from config import BASE_DIR

log = get_logger("visualization.index")

REPORTS_DIR = BASE_DIR / "reports"

# 리포트 메타데이터
_REPORT_META: dict[str, dict] = {
    # 일간
    "daily":          {"label": "D-1 일간 시황",         "emoji": "📊", "freq": "매일"},
    "d2_sentiment":   {"label": "D-2 연준·금리·감성",    "emoji": "📰", "freq": "매일"},
    "d3_crypto":      {"label": "D-3 암호화폐",          "emoji": "₿",  "freq": "매일"},
    "d4_":            {"label": "D-4 KOSPI 예측",        "emoji": "🎯", "freq": "매일"},
    "d5_":            {"label": "D-5 미국→KOSPI 선행",   "emoji": "🔭", "freq": "매일"},
    "d6_crypto_intel":{"label": "D-6 고래·기관·온체인",  "emoji": "🐳", "freq": "매일"},
    # 주간
    "weekly":         {"label": "W-2 매크로 국면",        "emoji": "🌍", "freq": "주간"},
    "w1_":            {"label": "W-1 자산 상관 변화",     "emoji": "🔗", "freq": "주간"},
    "w3_crypto_corr": {"label": "W-3 크립토 상관",        "emoji": "🔄", "freq": "주간"},
    "w4_kospi":       {"label": "W-4 KOSPI 3각",          "emoji": "📐", "freq": "주간"},
    "w5_":            {"label": "W-5 예측 적중률",        "emoji": "✅", "freq": "주간"},
    "w6_":            {"label": "W-6 기관 포트폴리오",    "emoji": "🏦", "freq": "주간"},
    # 월간
    "report_":        {"label": "M-1 월간 종합",          "emoji": "📋", "freq": "월간"},
    "m2_":            {"label": "M-2 S-RIM 적정가",       "emoji": "💰", "freq": "월간"},
    "m3_cycle":       {"label": "M-3 경기 사이클",        "emoji": "🔃", "freq": "월간"},
    "m4_":            {"label": "M-4 백테스팅",           "emoji": "📈", "freq": "월간"},
    "m5_":            {"label": "M-5 국면별 자산 성과",   "emoji": "🎨", "freq": "월간"},
    "m6_":            {"label": "M-6 공포-탐욕 지수",     "emoji": "😱", "freq": "월간"},
    # 알림
    "alert":          {"label": "긴급 알림",              "emoji": "🚨", "freq": "이벤트"},
}

_FREQ_ORDER = {"매일": 0, "주간": 1, "월간": 2, "이벤트": 3}
_FREQ_COLOR = {"매일": "#3498db", "주간": "#2ecc71", "월간": "#9b59b6", "이벤트": "#e74c3c"}


def _scan_reports() -> dict[str, list[dict]]:
    """reports/ 디렉토리를 스캔해 카테고리별 최신 파일 목록 반환."""
    categories: dict[str, list[dict]] = {"매일": [], "주간": [], "월간": [], "이벤트": []}

    for html_path in sorted(REPORTS_DIR.rglob("*.html"), reverse=True):
        stem = html_path.stem
        rel   = html_path.relative_to(REPORTS_DIR)

        meta = None
        for prefix, m in _REPORT_META.items():
            if stem.startswith(prefix):
                meta = m
                break
        if meta is None:
            continue

        freq  = meta["freq"]
        mtime = datetime.fromtimestamp(html_path.stat().st_mtime)
        categories[freq].append({
            "path":    str(rel).replace("\\", "/"),
            "label":   meta["label"],
            "emoji":   meta["emoji"],
            "stem":    stem,
            "mtime":   mtime,
            "freq":    freq,
        })

    # 각 카테고리 내 label 기준 최신 1개만 유지
    deduped: dict[str, list[dict]] = {k: [] for k in categories}
    for freq, items in categories.items():
        seen: set[str] = set()
        for item in items:
            if item["label"] not in seen:
                deduped[freq].append(item)
                seen.add(item["label"])

    return deduped


def _signal_cards(master: pd.DataFrame) -> str:
    """현재 핵심 지표 요약 카드 HTML."""
    if master.empty:
        return ""

    ref_ts = master.index[-1]

    def _last(col: str):
        if col not in master.columns:
            return None
        s = master[col].dropna()
        avail = s.index[s.index <= ref_ts]
        return float(s.loc[avail[-1]]) if not avail.empty else None

    def _chg1d(col: str):
        if col not in master.columns:
            return None
        s = master[col].dropna()
        avail = s.index[s.index <= ref_ts]
        if len(avail) < 2:
            return None
        return (float(s.loc[avail[-1]]) / float(s.loc[avail[-2]]) - 1) * 100

    signals = [
        ("S&P500",   "us_sp500_close",      "{:,.0f}",  "%"),
        ("KOSPI",    "kr_kospi_close",       "{:,.2f}",  "%"),
        ("BTC",      "crypto_btc_close",     "${:,.0f}", "%"),
        ("금",        "cmd_gold_close",       "${:,.0f}", "%"),
        ("WTI",      "cmd_wti_close",        "${:,.1f}", "%"),
        ("달러/원",   "fx_krw_usd_close",    "{:,.1f}",  "%"),
        ("VIX",      "alt_vix_close",        "{:.1f}",   "pt"),
        ("미10Y",    "rate_us10y_close",     "{:.2f}%",  "bp"),
        ("F&G",      "sent_fear_greed",      "{:.0f}",   "pt"),
    ]

    cards_html = ""
    for name, col, fmt, unit in signals:
        val = _last(col)
        if val is None:
            continue
        chg = _chg1d(col)
        try:
            val_str = fmt.format(val)
        except Exception:
            val_str = f"{val:.2f}"

        if chg is not None:
            chg_color = "#e74c3c" if chg > 0 else "#2ecc71" if chg < 0 else "#95a5a6"
            chg_str   = f"<span style='color:{chg_color};font-size:0.8em'>{chg:+.1f}{unit}</span>"
        else:
            chg_str = ""

        cards_html += (
            f"<div style='background:#fff;border-radius:8px;padding:12px 16px;"
            f"box-shadow:0 1px 4px rgba(0,0,0,0.1);min-width:110px;text-align:center'>"
            f"<div style='font-size:0.75em;color:#999;margin-bottom:4px'>{name}</div>"
            f"<div style='font-size:1.1em;font-weight:bold;color:#2c3e50'>{val_str}</div>"
            f"<div style='margin-top:2px'>{chg_str}</div>"
            f"</div>"
        )

    if not cards_html:
        return ""

    return (
        f"<div style='display:flex;flex-wrap:wrap;gap:10px;margin-bottom:24px'>"
        f"{cards_html}"
        f"</div>"
    )


def _alert_banner() -> str:
    """가장 최근 긴급 리포트 배너."""
    alert_dir = REPORTS_DIR / "alerts"
    if not alert_dir.exists():
        return ""
    alerts = sorted(alert_dir.glob("alert_*.html"), reverse=True)
    if not alerts:
        return ""
    latest = alerts[0]
    rel    = latest.relative_to(REPORTS_DIR)
    mtime  = datetime.fromtimestamp(latest.stat().st_mtime)
    return (
        f"<div style='background:#fdf0ef;border-left:5px solid #e74c3c;"
        f"padding:12px 20px;border-radius:0 6px 6px 0;margin-bottom:20px'>"
        f"<span style='background:#e74c3c;color:#fff;padding:2px 8px;"
        f"border-radius:3px;font-size:0.85em;font-weight:bold;margin-right:8px'>긴급</span>"
        f"<a href='{str(rel).replace(chr(92), '/')}' "
        f"style='color:#e74c3c;font-weight:bold;text-decoration:none'>"
        f"최신 긴급 리포트 — {latest.stem.replace('alert_', '')}</a>"
        f"<span style='color:#999;font-size:0.8em;margin-left:12px'>"
        f"생성: {mtime.strftime('%Y-%m-%d %H:%M')}</span>"
        f"</div>"
    )


def _report_card(item: dict, freq: str) -> str:
    """개별 리포트 카드 HTML."""
    color   = _FREQ_COLOR.get(freq, "#95a5a6")
    mtime   = item["mtime"].strftime("%m-%d %H:%M")
    return (
        f"<a href='{item['path']}' style='text-decoration:none'>"
        f"<div style='background:#fff;border-radius:8px;padding:14px 18px;"
        f"box-shadow:0 1px 4px rgba(0,0,0,0.08);border-top:3px solid {color};"
        f"transition:box-shadow 0.2s' "
        f"onmouseover=\"this.style.boxShadow='0 4px 12px rgba(0,0,0,0.15)'\" "
        f"onmouseout=\"this.style.boxShadow='0 1px 4px rgba(0,0,0,0.08)'\">"
        f"<div style='font-size:1.1em;font-weight:bold;color:#2c3e50'>"
        f"{item['emoji']} {item['label']}</div>"
        f"<div style='font-size:0.8em;color:#999;margin-top:4px'>최신: {mtime}</div>"
        f"</div></a>"
    )


def build_index_page(
    master: pd.DataFrame | None = None,
    output_path: str | None = None,
) -> str:
    """
    리포트 인덱스 페이지를 생성하고 reports/index.html 로 저장한다.

    Args:
        master      : 신호 카드용 최신 master DataFrame (None이면 카드 생략)
        output_path : None이면 reports/index.html

    Returns: 저장 경로(str)
    """
    out = Path(output_path) if output_path else REPORTS_DIR / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    categories = _scan_reports()
    now_str    = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 신호 카드
    signal_html = _signal_cards(master) if master is not None and not master.empty else ""

    # 알림 배너
    alert_html = _alert_banner()

    # 카테고리별 섹션
    sections_html = ""
    for freq in ["매일", "주간", "월간", "이벤트"]:
        items = categories.get(freq, [])
        if not items:
            continue
        color = _FREQ_COLOR[freq]
        cards = "\n".join(_report_card(item, freq) for item in items)
        sections_html += (
            f"<div style='margin-bottom:32px'>"
            f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:12px'>"
            f"<span style='display:inline-block;width:4px;height:24px;"
            f"background:{color};border-radius:2px'></span>"
            f"<h2 style='margin:0;font-size:1.1em;color:#2c3e50'>{freq} 리포트</h2>"
            f"<span style='background:{color}22;color:{color};padding:2px 10px;"
            f"border-radius:12px;font-size:0.8em'>{len(items)}개</span>"
            f"</div>"
            f"<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px'>"
            f"{cards}"
            f"</div></div>"
        )

    # 전체 리포트 개수
    total = sum(len(v) for v in categories.values())

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>글로벌 매크로 퀀트 인텔리전스 — 리포트 허브</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f0f2f5; color: #333; padding: 24px; }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    h1 {{ font-size: 1.4em; color: #2c3e50; margin-bottom: 4px; }}
    .subtitle {{ color: #999; font-size: 0.85em; margin-bottom: 20px; }}
    a {{ color: inherit; }}
  </style>
</head>
<body>
<div class="container">
  <h1>글로벌 매크로 퀀트 인텔리전스</h1>
  <p class="subtitle">리포트 허브 | 총 {total}개 | 마지막 업데이트: {now_str}</p>

  {alert_html}
  {signal_html}
  {sections_html}

  <p style="color:#bbb;font-size:0.75em;margin-top:16px;text-align:right">
    ⚠ 본 리포트는 자동 생성된 참고 자료이며 투자 권유가 아닙니다.
  </p>
</div>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    log.info("build_index_page: saved to %s (%d reports)", out, total)
    return str(out.resolve())
