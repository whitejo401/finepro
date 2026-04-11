"""
visualization/blog_formatter.py

HTML 리포트 → 블로그 플랫폼 게시 가능한 형태로 변환.

지원 플랫폼:
  - tistory  : HTML 직접 게시 (스킨 호환 CSS 추가)
  - velog    : 마크다운 변환 (차트는 이미지 링크 또는 제거)
  - github   : HTML 그대로 사용 (CDN plotly 포함)
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from collectors.base import get_logger
from config import BASE_DIR

log = get_logger("visualization.blog_formatter")

BLOG_DIR = BASE_DIR / "reports" / "blog"

# 티스토리 호환 추가 CSS
_TISTORY_CSS = """
<style>
  /* 티스토리 스킨 충돌 방지 */
  .fg-report-wrap { max-width: 860px; margin: 0 auto; font-family: 'Noto Sans KR', sans-serif; }
  .fg-report-wrap table { width: 100%; border-collapse: collapse; font-size: 0.9em; margin: 12px 0; }
  .fg-report-wrap th { background: #f5f5f5; padding: 7px 12px; text-align: left; border-bottom: 2px solid #ddd; }
  .fg-report-wrap td { padding: 6px 12px; border-bottom: 1px solid #eee; }
  .fg-report-wrap h2 { font-size: 1.25em; color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px; margin: 28px 0 12px; }
  .fg-chart { background: #fff; border-radius: 8px; padding: 12px; margin-bottom: 24px; border: 1px solid #eee; }
  .fg-disclaimer { font-size: 0.78em; color: #999; border-top: 1px solid #eee; margin-top: 40px; padding-top: 12px; line-height: 1.7; }
</style>
"""

# Velog용 마크다운 헤더 템플릿
_VELOG_HEADER = """\
---
title: "{title}"
date: {date}
tags: [{tags}]
---

"""


def extract_report_summary(report_path: str | Path) -> dict:
    """
    HTML 리포트에서 핵심 수치를 추출한다.

    <table> 내 숫자값과 제목(h1, h2)을 파싱하여 요약 dict 반환.

    Args:
        report_path: HTML 리포트 파일 경로

    Returns:
        {
            'title'  : str,
            'date'   : str,
            'tables' : list[list[list[str]]],   # tables[i][row][col]
            'headings': list[str],
        }
    """
    path = Path(report_path)
    if not path.exists():
        log.warning("extract_report_summary: 파일 없음 — %s", path)
        return {}

    html = path.read_text(encoding="utf-8")

    # 제목 추출
    title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
    title = title_m.group(1).strip() if title_m else path.stem

    # 날짜 추출 (파일명에서)
    date_m = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    date_str = date_m.group(1) if date_m else str(date.today())

    # h2 헤딩 추출
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.IGNORECASE | re.DOTALL)
    headings = [re.sub(r"<[^>]+>", "", h).strip() for h in headings]

    # 테이블 추출
    tables: list[list[list[str]]] = []
    for table_html in re.findall(r"<table[^>]*>(.*?)</table>", html, re.IGNORECASE | re.DOTALL):
        rows: list[list[str]] = []
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.IGNORECASE | re.DOTALL):
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.IGNORECASE | re.DOTALL)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)

    return {
        "title": title,
        "date": date_str,
        "tables": tables,
        "headings": headings,
    }


def add_og_meta(
    html: str,
    title: str,
    description: str,
    image_url: str = "",
) -> str:
    """
    HTML에 Open Graph 메타 태그를 삽입한다.

    기존 <head> 태그 내에 삽입. head가 없으면 html 앞에 추가.

    Args:
        html       : 원본 HTML 문자열
        title      : og:title
        description: og:description
        image_url  : og:image URL (없으면 생략)

    Returns:
        OG 메타 태그가 추가된 HTML 문자열
    """
    og_tags = [
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{description}">',
        '<meta property="og:type" content="article">',
    ]
    if image_url:
        og_tags.append(f'<meta property="og:image" content="{image_url}">')

    og_block = "\n  ".join(og_tags)

    if "<head>" in html.lower():
        html = re.sub(
            r"(<head[^>]*>)",
            r"\1\n  " + og_block,
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        html = og_block + "\n" + html

    return html


def _strip_plotly_js(html: str) -> str:
    """plotly.js CDN 스크립트 태그를 제거한다 (Velog용)."""
    html = re.sub(
        r'<script[^>]*src="https://cdn\.plot\.ly[^"]*"[^>]*></script>',
        "",
        html,
        flags=re.IGNORECASE,
    )
    # 인라인 plotly div도 제거
    html = re.sub(
        r'<div[^>]*id="[^"]*plotly[^"]*"[^>]*>.*?</div>',
        "[차트: 이미지 버전 준비 중]",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return html


def _tables_to_markdown(tables: list[list[list[str]]]) -> str:
    """추출된 테이블 목록을 마크다운 테이블 문자열로 변환한다."""
    md_parts: list[str] = []
    for rows in tables:
        if not rows:
            continue
        header = rows[0]
        sep = [":---" if i == 0 else "---:" for i in range(len(header))]
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(sep) + " |",
        ]
        for row in rows[1:]:
            # 열 수 맞추기
            padded = row + [""] * max(0, len(header) - len(row))
            lines.append("| " + " | ".join(padded[:len(header)]) + " |")
        md_parts.append("\n".join(lines))
    return "\n\n".join(md_parts)


def generate_post_summary(
    master: pd.DataFrame,
    date_str: str | None = None,
) -> str:
    """
    오늘의 핵심 수치로 블로그 서문용 마크다운을 생성한다.

    포함 수치:
      - S&P 500, KOSPI 등락률
      - VIX 수준
      - USD/KRW 환율
      - 현재 매크로 국면

    Args:
        master   : build_master_dataset() 반환값
        date_str : 기준일 'YYYY-MM-DD', None이면 마지막 유효일

    Returns:
        마크다운 서문 문자열
    """
    if master.empty:
        return "> 데이터가 없습니다.\n"

    ref_date = date_str or master.index[-1].strftime("%Y-%m-%d")
    ref_ts = pd.Timestamp(ref_date)

    lines: list[str] = [
        f"## 오늘의 시장 요약 — {ref_date}\n",
    ]

    # 주요 지표 수집
    snapshot = [
        ("us_sp500_close",   "S&P 500",   True,  ".1f"),
        ("kr_kospi_close",   "KOSPI",      True,  ".1f"),
        ("alt_vix_close",    "VIX",        False, ".2f"),
        ("fx_krw_usd_close", "USD/KRW",    False, ".1f"),
        ("crypto_btc_close", "BTC (USD)",  True,  ",.0f"),
    ]

    rows: list[str] = []
    for col, label, show_pct, fmt in snapshot:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        avail = s.index[s.index <= ref_ts]
        if avail.empty:
            continue
        val = float(s.loc[avail[-1]])
        val_str = f"{val:{fmt}}"
        prev = s.index[s.index < avail[-1]]
        if show_pct and not prev.empty:
            prev_val = float(s.loc[prev[-1]])
            pct = (val - prev_val) / abs(prev_val) * 100 if prev_val else 0
            arrow = "▲" if pct > 0 else "▼"
            rows.append(f"- **{label}**: {val_str} ({arrow} {abs(pct):.2f}%)")
        else:
            rows.append(f"- **{label}**: {val_str}")

    lines.extend(rows)
    lines.append("")

    # 현재 국면 추가
    try:
        from analysis.regime import classify_regime
        pmi_col = next((c for c in master.columns if "pmi" in c), None)
        cpi_col = next((c for c in master.columns if "cpi" in c), None)
        if pmi_col and cpi_col:
            rs = classify_regime(master[pmi_col], master[cpi_col]).dropna()
            if not rs.empty:
                regime = rs.iloc[-1]
                lines.append(f"> 현재 매크로 국면: **{regime}**\n")
    except Exception:
        pass

    return "\n".join(lines)


def format_for_blog(
    report_path: str | Path,
    platform: str = "tistory",
    output_dir: str | Path | None = None,
) -> str:
    """
    HTML 리포트를 블로그 플랫폼에 맞게 변환하여 저장한다.

    Args:
        report_path: 원본 HTML 리포트 경로
        platform   : 'tistory' | 'velog' | 'github'
        output_dir : 저장 디렉토리. None이면 reports/blog/{date}/

    Returns:
        저장된 파일의 절대 경로(str)
    """
    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"리포트 파일 없음: {path}")

    summary = extract_report_summary(path)
    title = summary.get("title", path.stem)
    date_str = summary.get("date", str(date.today()))
    headings = summary.get("headings", [])
    tables = summary.get("tables", [])

    # 출력 디렉토리
    if output_dir is None:
        out_dir = BLOG_DIR / date_str
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html = path.read_text(encoding="utf-8")
    platform = platform.lower()

    # ── 플랫폼별 처리 ────────────────────────────────────────────────────────

    if platform == "tistory":
        # 티스토리: CSS 추가 + OG 메타 삽입 + 본문을 div.fg-report-wrap으로 감싸기
        description = "  ".join(headings[:3]) if headings else title

        # body 내용 추출 후 래핑
        body_m = re.search(r"<body[^>]*>(.*?)</body>", html, re.IGNORECASE | re.DOTALL)
        if body_m:
            body_content = body_m.group(1)
            wrapped = f'<div class="fg-report-wrap">{body_content}</div>'
            html = html[:body_m.start(1)] + wrapped + html[body_m.end(1):]

        # CSS 삽입
        html = re.sub(r"</head>", _TISTORY_CSS + "\n</head>", html, count=1, flags=re.IGNORECASE)

        # OG 메타
        html = add_og_meta(html, title, description)

        out_path = out_dir / f"post_{platform}.html"
        out_path.write_text(html, encoding="utf-8")

    elif platform == "velog":
        # Velog: 마크다운 변환 (Plotly 차트 제거, 테이블→마크다운)
        description = "  ".join(headings[:3]) if headings else title
        tags = "매크로, 퀀트, 시장분석, 글로벌경제"

        md_header = _VELOG_HEADER.format(
            title=title,
            date=date_str,
            tags=tags,
        )

        # 요약 서문
        md_body = f"# {title}\n\n"
        md_body += f"> {description}\n\n"

        # 섹션 헤딩
        for h in headings:
            md_body += f"## {h}\n\n"

        # 테이블
        if tables:
            md_body += "---\n\n"
            md_body += _tables_to_markdown(tables)
            md_body += "\n\n"

        md_body += "\n---\n\n*본 분석은 투자 참고용이며, 투자 권유가 아닙니다.*\n"

        md_content = md_header + md_body
        out_path = out_dir / f"post_{platform}.md"
        out_path.write_text(md_content, encoding="utf-8")

    else:  # github
        # GitHub Pages: HTML 그대로 사용, OG 메타만 추가
        description = "  ".join(headings[:3]) if headings else title
        html = add_og_meta(html, title, description)
        out_path = out_dir / f"post_{platform}.html"
        out_path.write_text(html, encoding="utf-8")

    log.info("format_for_blog [%s]: saved to %s", platform, out_path)
    return str(out_path.resolve())


def format_all_reports(
    reports_dir: str | Path | None = None,
    platform: str = "tistory",
    date_str: str | None = None,
) -> list[str]:
    """
    지정 날짜의 모든 HTML 리포트를 블로그 포맷으로 변환한다.

    Args:
        reports_dir: 리포트 루트 디렉토리. None이면 BASE_DIR/reports
        platform   : 변환 대상 플랫폼
        date_str   : 기준일 'YYYY-MM-DD'. None이면 오늘

    Returns:
        변환된 파일 경로 목록
    """
    if reports_dir is None:
        reports_dir = BASE_DIR / "reports"
    reports_dir = Path(reports_dir)
    date_str = date_str or str(date.today())

    html_files: list[Path] = []
    for subdir in ["daily", "weekly", "monthly"]:
        d = reports_dir / subdir
        if d.exists():
            html_files.extend(d.glob(f"*{date_str}*.html"))

    if not html_files:
        log.warning("format_all_reports: %s 날짜 리포트 없음", date_str)
        return []

    out_dir = BLOG_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[str] = []
    for f in sorted(html_files):
        try:
            out = format_for_blog(f, platform=platform, output_dir=out_dir)
            results.append(out)
        except Exception as e:
            log.warning("format_for_blog 실패 [%s]: %s", f.name, e)

    log.info("format_all_reports: %d개 변환 완료 → %s", len(results), out_dir)
    return results
