"""
analysis/alerts.py
──────────────────
긴급 이벤트 감지 모듈.

check_alerts(master, ref_date) → list[Alert]
  master DataFrame에서 임계값 조건을 검사하고 발동된 알림 목록을 반환한다.
  main.py 매 실행 시 호출되며, 알림이 하나라도 있으면 build_alert_report()가 실행된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from collectors.base import get_logger

log = get_logger("analysis.alerts")

Severity = Literal["critical", "warning", "info"]


@dataclass
class Alert:
    code: str                    # 고유 코드 (예: "VIX_SPIKE")
    severity: Severity           # critical / warning / info
    title: str                   # 리포트 헤더에 출력할 제목
    detail: str                  # 상세 설명 (HTML 포함 가능)
    col: str                     # 트리거된 컬럼명
    value: float                 # 현재값
    threshold: float             # 기준값
    triggered_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)
    context: str = ""            # 배경 설명 (선택)


# ──────────────────────────────────────────────────────────────────────────────
# 개별 조건 함수
# ──────────────────────────────────────────────────────────────────────────────

def _last(series: pd.Series, ref_ts: pd.Timestamp) -> float | None:
    """ref_ts 이하 최신값 반환. 없으면 None."""
    s = series.dropna()
    avail = s.index[s.index <= ref_ts]
    if avail.empty:
        return None
    return float(s.loc[avail[-1]])


def _pct_rank(series: pd.Series, value: float) -> float:
    """시계열 내 value의 백분위 (0~100)."""
    s = series.dropna()
    if s.empty or s.max() == s.min():
        return 50.0
    return float((value - s.min()) / (s.max() - s.min()) * 100)


def _daily_chg(series: pd.Series, ref_ts: pd.Timestamp) -> float | None:
    """ref_ts 기준 전일 대비 % 변화."""
    s = series.dropna()
    avail = s.index[s.index <= ref_ts]
    if len(avail) < 2:
        return None
    cur = float(s.loc[avail[-1]])
    prev = float(s.loc[avail[-2]])
    if prev == 0:
        return None
    return (cur / prev - 1) * 100


# ──────────────────────────────────────────────────────────────────────────────
# 알림 조건 집합
# ──────────────────────────────────────────────────────────────────────────────

def _check_asset_move(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """자산 급등락 감지."""
    alerts: list[Alert] = []
    targets = [
        ("us_sp500_close",   "S&P500",  2.0, "critical"),
        ("kr_kospi_close",   "KOSPI",   2.0, "critical"),
        ("crypto_btc_close", "BTC",     5.0, "warning"),
        ("cmd_gold_close",   "금",       3.0, "warning"),
        ("cmd_wti_close",    "WTI",     4.0, "warning"),
        ("fx_krw_usd_close", "달러/원", 1.5, "warning"),
    ]
    for col, name, threshold, sev in targets:
        if col not in master.columns:
            continue
        chg = _daily_chg(master[col], ref_ts)
        if chg is None:
            continue
        val = _last(master[col], ref_ts)
        if abs(chg) >= threshold:
            direction = "급등" if chg > 0 else "급락"
            alerts.append(Alert(
                code=f"ASSET_MOVE_{col.upper()}",
                severity=sev,
                title=f"{name} {direction} ({chg:+.1f}%)",
                detail=f"{name}이(가) 전일 대비 <b>{chg:+.1f}%</b> {direction}했습니다. 현재값: {val:,.2f}",
                col=col,
                value=chg,
                threshold=threshold,
                triggered_at=ref_ts,
                context=f"기준 임계값: ±{threshold}%",
            ))
    return alerts


def _check_vix(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """VIX 스파이크 감지."""
    alerts: list[Alert] = []
    if "alt_vix_close" not in master.columns:
        return alerts
    vix = _last(master["alt_vix_close"], ref_ts)
    chg = _daily_chg(master["alt_vix_close"], ref_ts)
    if vix is None:
        return alerts

    if vix >= 40:
        alerts.append(Alert(
            code="VIX_EXTREME",
            severity="critical",
            title=f"VIX 극단 공포 ({vix:.1f})",
            detail=f"공포지수 VIX가 <b>{vix:.1f}</b>에 도달했습니다. 40 이상은 금융위기 수준입니다.",
            col="alt_vix_close", value=vix, threshold=40.0, triggered_at=ref_ts,
            context="VIX 40+ : 2008 금융위기, 2020 코로나 충격 수준",
        ))
    elif vix >= 30:
        alerts.append(Alert(
            code="VIX_HIGH",
            severity="warning",
            title=f"VIX 고공포 구간 ({vix:.1f})",
            detail=f"공포지수 VIX가 <b>{vix:.1f}</b>로 고공포 구간(30+)에 진입했습니다.",
            col="alt_vix_close", value=vix, threshold=30.0, triggered_at=ref_ts,
        ))

    if chg is not None and chg >= 15:
        alerts.append(Alert(
            code="VIX_SPIKE",
            severity="critical",
            title=f"VIX 단기 폭등 (+{chg:.1f}%)",
            detail=f"VIX가 하루 만에 <b>{chg:+.1f}%</b> 급등했습니다. 현재: {vix:.1f}",
            col="alt_vix_close", value=chg, threshold=15.0, triggered_at=ref_ts,
            context="단기 VIX 폭등은 블랙스완 이벤트 또는 패닉 매도 신호",
        ))
    return alerts


def _check_yield_curve(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """수익률 곡선 역전/정상화 감지."""
    alerts: list[Alert] = []
    if "rate_spread_10_2" not in master.columns:
        return alerts
    s = master["rate_spread_10_2"].dropna()
    avail = s.index[s.index <= ref_ts]
    if len(avail) < 2:
        return alerts

    cur  = float(s.loc[avail[-1]])
    prev = float(s.loc[avail[-2]])

    if prev > 0 and cur <= 0:
        alerts.append(Alert(
            code="YIELD_INVERSION",
            severity="critical",
            title=f"수익률 곡선 역전 발생 ({cur:+.3f}%)",
            detail=f"10-2년 스프레드가 <b>{prev:+.3f}%</b> → <b>{cur:+.3f}%</b>로 역전됐습니다. 경기 침체 선행 신호입니다.",
            col="rate_spread_10_2", value=cur, threshold=0.0, triggered_at=ref_ts,
            context="수익률 곡선 역전은 과거 평균 12~18개월 후 경기 침체 선행",
        ))
    elif prev <= 0 and cur > 0:
        alerts.append(Alert(
            code="YIELD_NORMALIZATION",
            severity="warning",
            title=f"수익률 곡선 정상화 ({cur:+.3f}%)",
            detail=f"10-2년 스프레드가 역전 해소 → <b>{cur:+.3f}%</b>. 경기 침체 임박 신호로도 해석됩니다.",
            col="rate_spread_10_2", value=cur, threshold=0.0, triggered_at=ref_ts,
            context="역전 해소 직후 실제 침체 시작 경우가 많음 (1990, 2001, 2008)",
        ))
    return alerts


def _check_hy_spread(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """하이일드 스프레드 급등 감지."""
    alerts: list[Alert] = []
    if "rate_hy_spread" not in master.columns:
        return alerts
    s = master["rate_hy_spread"].dropna()
    avail = s.index[s.index <= ref_ts]
    if len(avail) < 5:
        return alerts

    cur    = float(s.loc[avail[-1]])
    prev5  = float(s.loc[avail[-5]])
    chg5d  = cur - prev5
    pct    = _pct_rank(s, cur)

    if chg5d >= 0.5:
        alerts.append(Alert(
            code="HY_SPREAD_SURGE",
            severity="critical",
            title=f"HY 스프레드 급등 (+{chg5d:.2f}%p, 5일)",
            detail=f"하이일드 스프레드가 5일간 <b>+{chg5d:.2f}%p</b> 확대됐습니다. 현재 {cur:.2f}% ({pct:.0f}%ile)",
            col="rate_hy_spread", value=chg5d, threshold=0.5, triggered_at=ref_ts,
            context="HY 스프레드 급등은 신용 경색 조기 신호. 주가 조정 선행 경향",
        ))
    elif pct >= 80:
        alerts.append(Alert(
            code="HY_SPREAD_HIGH",
            severity="warning",
            title=f"HY 스프레드 1년 고점권 ({cur:.2f}%, {pct:.0f}%ile)",
            detail=f"하이일드 스프레드가 1년 내 상위 <b>{pct:.0f}%ile</b>에 위치합니다.",
            col="rate_hy_spread", value=pct, threshold=80.0, triggered_at=ref_ts,
        ))
    return alerts


def _check_sentiment(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """뉴스 감성 극단 감지."""
    alerts: list[Alert] = []
    for col, label in [("sent_news_global", "글로벌 뉴스"), ("sent_news_fed", "연준 뉴스")]:
        if col not in master.columns:
            continue
        val = _last(master[col], ref_ts)
        if val is None:
            continue
        if val <= -0.7:
            alerts.append(Alert(
                code=f"SENTIMENT_EXTREME_NEG_{col.upper()}",
                severity="critical",
                title=f"{label} 감성 극단 부정 ({val:.3f})",
                detail=f"{label} VADER 감성 점수 <b>{val:.3f}</b> — 극도 비관 구간(-0.7 이하)",
                col=col, value=val, threshold=-0.7, triggered_at=ref_ts,
                context="감성 극단 부정 → 역발상 매수 신호 가능성 (공포 극대화)",
            ))
        elif val >= 0.7:
            alerts.append(Alert(
                code=f"SENTIMENT_EXTREME_POS_{col.upper()}",
                severity="warning",
                title=f"{label} 감성 극단 긍정 ({val:.3f})",
                detail=f"{label} VADER 감성 점수 <b>{val:.3f}</b> — 극도 낙관 구간(0.7 이상)",
                col=col, value=val, threshold=0.7, triggered_at=ref_ts,
                context="감성 극단 긍정 → 과열 경고. 과거 천장 근처와 일치하는 경향",
            ))
    return alerts


def _check_google_trends(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """Google Trends 급등 감지 (recession/stock_crash)."""
    alerts: list[Alert] = []
    for col, label, threshold in [
        ("trends_recession",    "경기침체 검색량", 20),
        ("trends_stock_crash",  "주식폭락 검색량", 20),
        ("trends_inflation",    "인플레이션 검색량", 25),
    ]:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        avail = s.index[s.index <= ref_ts]
        if len(avail) < 8:
            continue
        recent4 = float(s.loc[avail[-4:]].mean())
        prev4   = float(s.loc[avail[-8:-4]].mean())
        chg     = recent4 - prev4
        if chg >= threshold:
            alerts.append(Alert(
                code=f"TRENDS_SPIKE_{col.upper()}",
                severity="warning",
                title=f"{label} 급증 (+{chg:.0f}pt, 4주 평균)",
                detail=f"'{label}' 검색량이 4주 평균 기준 <b>+{chg:.0f}pt</b> 급증했습니다. 현재: {recent4:.0f}",
                col=col, value=chg, threshold=float(threshold), triggered_at=ref_ts,
                context="검색량 급증은 대중 공포/관심 확대 신호. 단기 변동성 상승 전조",
            ))
    return alerts


def _check_cftc_extreme(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """CFTC COT 극단 포지션 감지 (역발상)."""
    alerts: list[Alert] = []
    targets = [
        ("cot_sp500_net", "S&P500 선물"),
        ("cot_gold_net",  "금 선물"),
        ("cot_wti_net",   "WTI 선물"),
    ]
    for col, name in targets:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        val = _last(s, ref_ts)
        if val is None:
            continue
        pct = _pct_rank(s, val)
        if pct <= 10:
            alerts.append(Alert(
                code=f"CFTC_EXTREME_SHORT_{col.upper()}",
                severity="info",
                title=f"{name} 극단 매도 포지션 ({pct:.0f}%ile)",
                detail=f"{name} 비상업 순포지션 {val:+,.0f}계약 — 1년 내 하위 <b>{pct:.0f}%ile</b> (역발상 매수 신호)",
                col=col, value=pct, threshold=10.0, triggered_at=ref_ts,
                context="극단 매도 포지션은 역사적으로 해당 자산 반등 선행",
            ))
        elif pct >= 90:
            alerts.append(Alert(
                code=f"CFTC_EXTREME_LONG_{col.upper()}",
                severity="info",
                title=f"{name} 극단 매수 포지션 ({pct:.0f}%ile)",
                detail=f"{name} 비상업 순포지션 {val:+,.0f}계약 — 1년 내 상위 <b>{pct:.0f}%ile</b> (역발상 매도 신호)",
                col=col, value=pct, threshold=90.0, triggered_at=ref_ts,
                context="극단 매수 포지션은 역사적으로 해당 자산 고점 근처",
            ))
    return alerts


def _check_epu(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """EPU 경제정책 불확실성 급등 감지."""
    alerts: list[Alert] = []
    for col, label in [("epu_us", "미국 EPU"), ("epu_global", "글로벌 EPU")]:
        if col not in master.columns:
            continue
        s = master[col].dropna()
        val = _last(s, ref_ts)
        if val is None:
            continue
        pct = _pct_rank(s, val)
        if pct >= 80:
            alerts.append(Alert(
                code=f"EPU_HIGH_{col.upper()}",
                severity="warning",
                title=f"{label} 고불확실성 ({val:.0f}, {pct:.0f}%ile)",
                detail=f"경제정책 불확실성 지수({label})가 1년 내 상위 <b>{pct:.0f}%ile</b>에 위치합니다. 현재: {val:.0f}",
                col=col, value=pct, threshold=80.0, triggered_at=ref_ts,
                context="EPU 고점은 정책 불확실성 확대 → 투자 위축 → 주가 변동성 확대 경향",
            ))
    return alerts


def _check_crypto_dominance(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """BTC 도미넌스 급변 감지."""
    alerts: list[Alert] = []
    if "crypto_btc_dominance" not in master.columns:
        return alerts
    s = master["crypto_btc_dominance"].dropna()
    avail = s.index[s.index <= ref_ts]
    if len(avail) < 7:
        return alerts
    cur  = float(s.loc[avail[-1]])
    prev = float(s.loc[avail[-7]])
    chg  = cur - prev

    if abs(chg) >= 5:
        direction = "상승" if chg > 0 else "하락"
        context = (
            "BTC 도미넌스 급상승 → 알트코인 자금 이탈, 리스크 회피 강화"
            if chg > 0
            else "BTC 도미넌스 급하락 → 알트코인 랠리, 위험선호 확대"
        )
        alerts.append(Alert(
            code="BTC_DOMINANCE_SHIFT",
            severity="info",
            title=f"BTC 도미넌스 급{direction} ({cur:.1f}%, 7일 {chg:+.1f}%p)",
            detail=f"BTC 도미넌스 7일간 <b>{chg:+.1f}%p</b> 변화. 현재 {cur:.1f}%",
            col="crypto_btc_dominance", value=chg, threshold=5.0, triggered_at=ref_ts,
            context=context,
        ))
    return alerts


def _check_regime_shift(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """매크로 국면 전환 감지."""
    alerts: list[Alert] = []
    try:
        from analysis.regime import classify_regime
        pmi_col = next((c for c in master.columns if "pmi" in c), None)
        cpi_col = next((c for c in master.columns if "macro_cpi" in c), None)
        if not pmi_col or not cpi_col:
            return alerts

        regime_s = classify_regime(master[pmi_col], master[cpi_col]).dropna()
        if len(regime_s) < 2:
            return alerts

        avail = regime_s.index[regime_s.index <= ref_ts]
        if len(avail) < 2:
            return alerts

        cur  = regime_s.loc[avail[-1]]
        prev = regime_s.loc[avail[-2]]
        if cur != prev:
            alerts.append(Alert(
                code="REGIME_SHIFT",
                severity="critical",
                title=f"매크로 국면 전환: {prev} → {cur}",
                detail=f"거시 경제 국면이 <b>{prev}</b>에서 <b>{cur}</b>으로 전환됐습니다.",
                col=pmi_col, value=0.0, threshold=0.0, triggered_at=ref_ts,
                context={
                    "deflation":   "경기 수축 + 디플레. 채권·금·현금 선호.",
                    "stagflation": "최악 국면. 주식·채권 동반 하락. 원자재·인플레연동채 선호.",
                    "overheat":    "과열. 원자재·TIPS 선호. 주식 변동성 확대.",
                    "reflation":   "최선호 국면. 주식·산업재·에너지 선호.",
                }.get(cur, ""),
            ))
    except Exception:
        pass
    return alerts


# ──────────────────────────────────────────────────────────────────────────────
# 통합 체크 함수
# ──────────────────────────────────────────────────────────────────────────────

def _check_fear_greed(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """공포탐욕지수 극단 감지 (Alternative.me)."""
    alerts: list[Alert] = []
    if "sent_fear_greed" not in master.columns:
        return alerts
    val = _last(master["sent_fear_greed"], ref_ts)
    if val is None:
        return alerts

    fng_class = ""
    if "sent_fear_greed_class" in master.columns:
        cls_s = master["sent_fear_greed_class"].dropna()
        avail = cls_s.index[cls_s.index <= ref_ts]
        if not avail.empty:
            fng_class = str(cls_s.loc[avail[-1]])

    if val <= 15:
        alerts.append(Alert(
            code="FNG_EXTREME_FEAR",
            severity="critical",
            title=f"공포탐욕지수 극도 공포 ({val:.0f} — {fng_class})",
            detail=f"Alternative.me 공포탐욕지수 <b>{val:.0f}</b> — 역사적 저점 구간. 역발상 매수 신호.",
            col="sent_fear_greed", value=val, threshold=15.0, triggered_at=ref_ts,
            context="F&G 15 이하: 2020-03 코로나(8), 2022-06 루나(6) 수준. 중기 저점과 일치 경향",
        ))
    elif val <= 25:
        alerts.append(Alert(
            code="FNG_FEAR",
            severity="warning",
            title=f"공포탐욕지수 공포 구간 ({val:.0f} — {fng_class})",
            detail=f"Alternative.me 공포탐욕지수 <b>{val:.0f}</b> — 과거 단기 반등 발생 구간",
            col="sent_fear_greed", value=val, threshold=25.0, triggered_at=ref_ts,
        ))
    elif val >= 85:
        alerts.append(Alert(
            code="FNG_EXTREME_GREED",
            severity="warning",
            title=f"공포탐욕지수 극도 탐욕 ({val:.0f} — {fng_class})",
            detail=f"Alternative.me 공포탐욕지수 <b>{val:.0f}</b> — 과열 구간, 단기 고점 리스크",
            col="sent_fear_greed", value=val, threshold=85.0, triggered_at=ref_ts,
            context="F&G 85+ 는 과거 단기 고점과 일치. 포지션 축소 검토 구간",
        ))
    return alerts


def _check_funding_rate(master: pd.DataFrame, ref_ts: pd.Timestamp) -> list[Alert]:
    """Binance 펀딩비율 극단 감지 (과열 롱/숏)."""
    alerts: list[Alert] = []
    if "deriv_btc_funding_cum7d" not in master.columns:
        return alerts
    val = _last(master["deriv_btc_funding_cum7d"], ref_ts)
    if val is None:
        return alerts

    s = master["deriv_btc_funding_cum7d"].dropna()
    pct = _pct_rank(s, val)

    if val > 0 and pct >= 85:
        alerts.append(Alert(
            code="FUNDING_EXTREME_LONG",
            severity="warning",
            title=f"BTC 선물 롱 과열 (7일 누적 펀딩 {val:+.4f}%, {pct:.0f}%ile)",
            detail=f"BTC 7일 누적 펀딩비율 <b>{val:+.4f}%</b> — 롱 포지션 과열. 숏 스퀴즈 또는 급락 가능성.",
            col="deriv_btc_funding_cum7d", value=pct, threshold=85.0, triggered_at=ref_ts,
            context="롱 과열: 레버리지 청산 리스크. 고점 신호로 활용",
        ))
    elif val < 0 and pct <= 15:
        alerts.append(Alert(
            code="FUNDING_EXTREME_SHORT",
            severity="info",
            title=f"BTC 선물 숏 과열 (7일 누적 펀딩 {val:+.4f}%, {pct:.0f}%ile)",
            detail=f"BTC 7일 누적 펀딩비율 <b>{val:+.4f}%</b> — 숏 포지션 과열. 숏 커버 랠리 가능성.",
            col="deriv_btc_funding_cum7d", value=pct, threshold=15.0, triggered_at=ref_ts,
            context="숏 과열: 역발상 매수 신호. 롱 스퀴즈 랠리 경향",
        ))
    return alerts


_CHECKERS = [
    _check_asset_move,
    _check_vix,
    _check_yield_curve,
    _check_hy_spread,
    _check_sentiment,
    _check_fear_greed,
    _check_funding_rate,
    _check_google_trends,
    _check_cftc_extreme,
    _check_epu,
    _check_crypto_dominance,
    _check_regime_shift,
]

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def check_alerts(
    master: pd.DataFrame,
    ref_date: str | None = None,
) -> list[Alert]:
    """
    master DataFrame에서 모든 알림 조건을 검사한다.

    Args:
        master   : build_master_dataset() 또는 main.py merge 결과
        ref_date : 'YYYY-MM-DD', None이면 마지막 유효일

    Returns:
        발동된 Alert 리스트 (severity 순 정렬: critical > warning > info)
    """
    if master.empty:
        return []

    ref_ts = (
        pd.Timestamp(ref_date)
        if ref_date
        else master.index[-1]
    )

    alerts: list[Alert] = []
    for checker in _CHECKERS:
        try:
            alerts.extend(checker(master, ref_ts))
        except Exception as e:
            log.warning("alert checker %s 오류: %s", checker.__name__, e)

    alerts.sort(key=lambda a: _SEVERITY_ORDER.get(a.severity, 9))
    log.info("check_alerts: %d개 알림 발동 (ref=%s)", len(alerts), ref_ts.date())
    return alerts
