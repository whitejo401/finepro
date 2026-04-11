"""
analysis/crypto_intel.py

암호화폐 고래 + 기관 데이터 분석 및 신호 생성.

해석 기준:
  고래 거래소 유입 ↑  → 단기 매도 압력 (bearish)
  고래 거래소 유출 ↑  → 장기 보유 증가, 공급 감소 (bullish)
  ETF 순유입 ↑       → 기관 수요 확인 (bullish)
  기관 BTC 축적 ↑    → 장기 강세 신호
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from collectors.base import get_logger

log = get_logger("analysis.crypto_intel")


# ---------------------------------------------------------------------------
# 고래 신호 (거래소 유입/유출 기반)
# ---------------------------------------------------------------------------

def whale_signal(
    master: pd.DataFrame,
    lookback: int = 30,
) -> pd.Series:
    """
    고래 거래소 유입/유출 비율로 단기 매도 압력 신호를 생성한다.

    신호:
      +1 : 거래소 유출 우세 (long-term hodl ↑, 공급 감소 → 강세)
      -1 : 거래소 유입 우세 (매도 준비 ↑, 단기 하락 압력)
       0 : 중립

    Args:
        master  : master DataFrame (whale_btc_exchange_* 컬럼 필요)
        lookback: Z-Score 계산 기간

    Returns:
        pd.Series (index=날짜, values: +1/-1/0), name='whale_signal'
    """
    inflow_col  = "whale_btc_exchange_inflow"
    outflow_col = "whale_btc_exchange_outflow"
    net_col     = "whale_btc_exchange_net"

    # net 컬럼이 있으면 우선 사용
    if net_col in master.columns:
        net = master[net_col].dropna()
    elif inflow_col in master.columns and outflow_col in master.columns:
        net = master[outflow_col].dropna() - master[inflow_col].dropna()
        net = net.dropna()
    else:
        log.warning("whale_signal: 고래 유입/유출 컬럼 없음")
        return pd.Series(dtype=float)

    # Z-Score 기반 이상 감지
    roll_mean = net.rolling(lookback, min_periods=10).mean()
    roll_std  = net.rolling(lookback, min_periods=10).std()
    z = (net - roll_mean) / roll_std.replace(0, np.nan)
    z = z.fillna(0)

    signal = pd.Series(0.0, index=net.index)
    signal[z > 1.0]  =  1.0   # 유출 급증 → 강세
    signal[z < -1.0] = -1.0   # 유입 급증 → 약세

    signal.name = "whale_signal"
    return signal


def whale_flow_summary(
    master: pd.DataFrame,
    lookback_days: int = 30,
) -> dict:
    """
    최근 고래 유입/유출 현황 요약.

    Returns:
        {
            'net_flow_7d'    : float (7일 순유입, 양수=유입, BTC),
            'net_flow_30d'   : float (30일 순유입, BTC),
            'alert_count_7d' : int   (최근 7일 대형 이동 건수),
            'signal'         : +1/-1/0,
            'signal_label'   : str,
            'inflow_outflow_ratio': float,  # > 1 이면 유출 > 유입
        }
    """
    result: dict = {}

    inflow_col  = "whale_btc_exchange_inflow"
    outflow_col = "whale_btc_exchange_outflow"
    net_col     = "whale_btc_exchange_net"
    alert_col   = "whale_alert_count"

    ref_ts = master.index[-1] if not master.empty else None
    if ref_ts is None:
        return result

    for days, key in [(7, "7d"), (30, "30d")]:
        cutoff = ref_ts - pd.Timedelta(days=days)
        if net_col in master.columns:
            net_s = master.loc[master.index >= cutoff, net_col].dropna()
            result[f"net_flow_{key}"] = float(net_s.sum()) if not net_s.empty else 0.0
        elif inflow_col in master.columns and outflow_col in master.columns:
            inf = master.loc[master.index >= cutoff, inflow_col].dropna().sum()
            out = master.loc[master.index >= cutoff, outflow_col].dropna().sum()
            result[f"net_flow_{key}"] = float(out - inf)  # 유출 - 유입 (양수=유출 우세)

    # 대형 이동 건수 (7일)
    if alert_col in master.columns:
        cutoff7 = ref_ts - pd.Timedelta(days=7)
        cnt = master.loc[master.index >= cutoff7, alert_col].dropna().sum()
        result["alert_count_7d"] = int(cnt)

    # 유입/유출 비율 (최근 30일)
    if inflow_col in master.columns and outflow_col in master.columns:
        cutoff30 = ref_ts - pd.Timedelta(days=30)
        inf_total  = float(master.loc[master.index >= cutoff30, inflow_col].dropna().sum())
        out_total  = float(master.loc[master.index >= cutoff30, outflow_col].dropna().sum())
        result["inflow_outflow_ratio"] = round(out_total / inf_total, 3) if inf_total > 0 else None

    # 신호 결정
    sig_series = whale_signal(master)
    if not sig_series.empty:
        result["signal"] = int(sig_series.iloc[-1])
    else:
        result["signal"] = 0

    labels = {1: "공급 감소 (강세)", -1: "매도 압력 (약세)", 0: "중립"}
    result["signal_label"] = labels.get(result["signal"], "중립")

    return result


# ---------------------------------------------------------------------------
# ETF 순유입 분석
# ---------------------------------------------------------------------------

def etf_flow_summary(
    master: pd.DataFrame,
    lookback_days: int = 30,
) -> dict:
    """
    비트코인 현물 ETF 보유량 추이 요약.

    master 내 etf_*_close 컬럼을 사용한다.

    Returns:
        {
            'total_etf_aum_change_pct': float (30일 ETF 가격 평균 변화율 %),
            'etf_count'               : int   (수집된 ETF 수),
            'top_etf'                 : str   (거래량 기준 최대 ETF),
            'etf_performance'         : dict  {ticker: {'change_pct': float, 'current': float}},
        }
    """
    etf_close_cols = [c for c in master.columns if c.startswith("etf_") and c.endswith("_close")]

    if not etf_close_cols:
        return {}

    cutoff = master.index[-1] - pd.Timedelta(days=lookback_days) if not master.empty else None
    result: dict = {"etf_count": len(etf_close_cols), "etf_performance": {}}

    changes: list[float] = []
    for col in etf_close_cols:
        ticker = col.replace("etf_", "").replace("_close", "").upper()
        s = master[col].dropna()
        if s.empty or len(s) < 2:
            continue
        current_val = float(s.iloc[-1])
        if cutoff is not None:
            past = s[s.index >= cutoff]
            if not past.empty:
                start_val = float(past.iloc[0])
                chg_pct = (current_val - start_val) / abs(start_val) * 100 if start_val != 0 else 0
            else:
                chg_pct = 0.0
        else:
            chg_pct = 0.0

        result["etf_performance"][ticker] = {
            "change_pct": round(chg_pct, 2),
            "current": round(current_val, 2),
        }
        if math.isfinite(chg_pct):
            changes.append(chg_pct)

    if changes:
        result["total_etf_aum_change_pct"] = round(sum(changes) / len(changes), 2)

    # 거래량 기준 최대 ETF (etf_*_volume 컬럼 활용)
    vol_cols = {c.replace("_volume", "").replace("etf_", "").upper(): c
                for c in master.columns if c.startswith("etf_") and c.endswith("_volume")}
    if vol_cols:
        vols = {}
        for ticker, col in vol_cols.items():
            s = master[col].dropna()
            if not s.empty:
                vols[ticker] = float(s.iloc[-1])
        if vols:
            result["top_etf"] = max(vols, key=vols.__getitem__)

    return result


# ---------------------------------------------------------------------------
# 기관 보유량 분석
# ---------------------------------------------------------------------------

def institution_accumulation_signal(
    btc_companies_df: pd.DataFrame,
    prev_btc_companies_df: pd.DataFrame | None = None,
) -> dict:
    """
    공개기업 BTC 보유량 변화로 기관 축적/분산 신호를 생성한다.

    Args:
        btc_companies_df     : 현재 분기 보유량 DataFrame (get_public_company_holdings 반환값)
        prev_btc_companies_df: 이전 분기 보유량 (None이면 변화 계산 불가)

    Returns:
        {
            'total_btc'         : float (전체 공개기업 BTC 보유량 합계),
            'top10_holders'     : list[dict] (상위 10개사),
            'new_buyers'        : list[str]  (신규 진입 기업),
            'sellers'           : list[str]  (보유량 감소 기업),
            'signal'            : +1/-1/0,
            'signal_label'      : str,
            'total_value_usd'   : float,
        }
    """
    if btc_companies_df is None or btc_companies_df.empty:
        return {}

    result: dict = {}

    # 전체 보유량
    total_btc = float(btc_companies_df["total_holdings"].sum())
    total_usd = float(btc_companies_df["total_current_value_usd"].sum())
    result["total_btc"] = round(total_btc, 2)
    result["total_value_usd"] = round(total_usd, 0)

    # 상위 10개사
    top10 = btc_companies_df.head(10).reset_index()
    result["top10_holders"] = [
        {
            "company":     row.get("company_name", row.get("index", "")),
            "symbol":      row.get("symbol", ""),
            "holdings":    row.get("total_holdings", 0),
            "value_usd":   row.get("total_current_value_usd", 0),
            "pct_supply":  row.get("percentage_of_total_supply", 0),
            "country":     row.get("country", ""),
        }
        for _, row in top10.iterrows()
    ]

    # 이전 분기 대비 변화
    result["new_buyers"] = []
    result["sellers"]    = []

    if prev_btc_companies_df is not None and not prev_btc_companies_df.empty:
        current_companies = set(btc_companies_df.index)
        prev_companies    = set(prev_btc_companies_df.index)

        result["new_buyers"] = list(current_companies - prev_companies)

        # 보유량 감소 기업
        common = current_companies & prev_companies
        for company in common:
            cur_hold  = btc_companies_df.loc[company, "total_holdings"]
            prev_hold = prev_btc_companies_df.loc[company, "total_holdings"]
            if cur_hold < prev_hold:
                result["sellers"].append(company)

        # 축적/분산 신호
        net_change = total_btc - float(prev_btc_companies_df["total_holdings"].sum())
        if net_change > 0:
            result["signal"] = 1
            result["signal_label"] = f"기관 축적 (+{net_change:,.0f} BTC)"
        elif net_change < 0:
            result["signal"] = -1
            result["signal_label"] = f"기관 분산 ({net_change:,.0f} BTC)"
        else:
            result["signal"] = 0
            result["signal_label"] = "변화 없음"
    else:
        result["signal"] = 0
        result["signal_label"] = "이전 데이터 없음"

    return result


# ---------------------------------------------------------------------------
# 통합 요약
# ---------------------------------------------------------------------------

def crypto_intel_summary(
    master: pd.DataFrame,
    btc_companies_df: pd.DataFrame | None = None,
) -> dict:
    """
    고래 + ETF + 기관 데이터 통합 요약.

    Returns:
        {
            'whale'      : whale_flow_summary 반환값,
            'etf'        : etf_flow_summary 반환값,
            'institution': institution_accumulation_signal 반환값,
            'overall_signal': +1/-1/0,
            'overall_label' : str,
        }
    """
    whale_s = whale_flow_summary(master)
    etf_s   = etf_flow_summary(master)
    inst_s  = institution_accumulation_signal(btc_companies_df) if btc_companies_df is not None else {}

    # 종합 신호 (단순 다수결)
    signals = [
        whale_s.get("signal", 0),
        1 if (etf_s.get("total_etf_aum_change_pct") or 0) > 2 else (
            -1 if (etf_s.get("total_etf_aum_change_pct") or 0) < -2 else 0),
        inst_s.get("signal", 0),
    ]
    vote = sum(signals)
    if vote > 0:
        overall = 1
        overall_label = "기관·고래 강세 우세"
    elif vote < 0:
        overall = -1
        overall_label = "기관·고래 약세 우세"
    else:
        overall = 0
        overall_label = "중립"

    return {
        "whale":          whale_s,
        "etf":            etf_s,
        "institution":    inst_s,
        "overall_signal": overall,
        "overall_label":  overall_label,
    }
