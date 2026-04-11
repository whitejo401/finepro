"""
collectors/global_/whale.py

암호화폐 고래(대형 거래) 온체인 데이터 수집.

데이터 소스:
  1. Whale Alert API   — 대형 트랜잭션 (≥100만 USD) 알림
  2. CryptoQuant API   — 거래소 BTC 순유입/유출 (무료 플랜)
  3. CoinGecko         — 거래소별 BTC 거래량 (기존 demo key)

출력 컬럼 (master 병합용):
  whale_btc_exchange_inflow   : 거래소 BTC 순유입 (BTC)
  whale_btc_exchange_outflow  : 거래소 BTC 순유출 (BTC)
  whale_btc_exchange_net      : 순유출 - 순유입 (BTC, 양수=유출 우세)
  whale_alert_count           : 당일 ≥min_usd 이동 건수
  whale_alert_volume_usd      : 당일 총 이동 금액 (백만 USD)
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from collectors.base import get_logger
from config import BASE_DIR

log = get_logger("collectors.whale")

CACHE_DIR = BASE_DIR / "data" / "cache" / "whale"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# API endpoints
_WHALE_ALERT_BASE  = "https://api.whale-alert.io/v1"
_CRYPTOQUANT_BASE  = "https://api.cryptoquant.com/v1"


def _load_cache(key: str) -> dict | None:
    p = CACHE_DIR / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _save_cache(key: str, data: dict) -> None:
    p = CACHE_DIR / f"{key}.json"
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception as e:
        log.warning("cache save failed: %s", e)


def _cache_key(*parts: str) -> str:
    return hashlib.md5("_".join(parts).encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Whale Alert API
# ---------------------------------------------------------------------------

def get_whale_alerts(
    start: str,
    end: str | None = None,
    min_usd: int = 1_000_000,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Whale Alert API로 대형 온체인 트랜잭션을 수집한다.

    WHALE_ALERT_API_KEY 환경변수가 없으면 빈 DataFrame 반환.

    Args:
        start   : 시작일 'YYYY-MM-DD'
        end     : 종료일 'YYYY-MM-DD', None이면 오늘
        min_usd : 최소 USD 금액 필터 (기본 100만)
        use_cache: 캐시 사용 여부

    Returns:
        DataFrame (index=datetime, columns: blockchain, symbol,
                   from_owner, to_owner, amount, amount_usd, transaction_type)
        집계 컬럼은 별도 aggregate_whale_alerts() 호출
    """
    import os
    api_key = os.environ.get("WHALE_ALERT_API_KEY", "")
    if not api_key:
        log.warning("get_whale_alerts: WHALE_ALERT_API_KEY 없음 — 스킵")
        return pd.DataFrame()

    end = end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ck = _cache_key("whale_alerts", start, end, str(min_usd))

    if use_cache:
        cached = _load_cache(ck)
        if cached:
            df = pd.DataFrame(cached)
            if not df.empty:
                df.index = pd.to_datetime(df.index)
            return df

    start_ts = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end_ts   = int(datetime.strptime(end,   "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())

    all_txns: list[dict] = []
    cursor_start = start_ts

    # Whale Alert free: 최대 100건/요청, 1000건/월
    max_requests = 10
    for _ in range(max_requests):
        params = {
            "api_key": api_key,
            "start":   cursor_start,
            "end":     end_ts,
            "min_value": min_usd,
            "limit": 100,
            "cursor": 0,
        }
        try:
            resp = requests.get(f"{_WHALE_ALERT_BASE}/transactions", params=params, timeout=15)
            if resp.status_code == 429:
                log.warning("Whale Alert: rate limit (429) — 중단")
                break
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning("Whale Alert API 오류: %s", e)
            break

        txns = data.get("transactions", [])
        if not txns:
            break

        for tx in txns:
            ts = tx.get("timestamp", 0)
            if ts > end_ts:
                continue
            all_txns.append({
                "timestamp":        ts,
                "blockchain":       tx.get("blockchain", ""),
                "symbol":           tx.get("symbol", "").upper(),
                "from_owner":       tx.get("from", {}).get("owner_type", "unknown"),
                "to_owner":         tx.get("to",   {}).get("owner_type", "unknown"),
                "amount":           float(tx.get("amount", 0)),
                "amount_usd":       float(tx.get("amount_usd", 0)),
                "transaction_type": _classify_tx(
                    tx.get("from", {}).get("owner_type", ""),
                    tx.get("to",   {}).get("owner_type", ""),
                ),
            })

        # 마지막 타임스탬프 이후부터 재요청
        last_ts = txns[-1].get("timestamp", end_ts)
        if last_ts >= end_ts or len(txns) < 100:
            break
        cursor_start = last_ts + 1
        time.sleep(0.5)  # rate limit 방지

    if not all_txns:
        return pd.DataFrame()

    df = pd.DataFrame(all_txns)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert(None)
    df = df.set_index("datetime").sort_index()

    _save_cache(ck, df.reset_index().to_dict("list"))
    log.info("get_whale_alerts: %d건 수집 (%s ~ %s, min_usd=%s)", len(df), start, end, f"{min_usd:,}")
    return df


def _classify_tx(from_type: str, to_type: str) -> str:
    """트랜잭션 유형 분류."""
    exchange_types = {"exchange", "exchange_cold_wallet"}
    if from_type in exchange_types and to_type not in exchange_types:
        return "exchange_outflow"   # 거래소 → 개인 (매수/출금)
    elif from_type not in exchange_types and to_type in exchange_types:
        return "exchange_inflow"    # 개인 → 거래소 (매도 준비)
    elif from_type in exchange_types and to_type in exchange_types:
        return "exchange_transfer"  # 거래소 간 이동
    else:
        return "wallet_transfer"    # 지갑 간 이동


def aggregate_whale_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Whale Alert 원시 데이터를 일별로 집계한다.

    Returns:
        DataFrame (index=날짜, columns: whale_alert_count, whale_alert_volume_usd,
                   whale_exchange_inflow_count, whale_exchange_outflow_count)
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.index = df.index.normalize()

    agg = df.groupby(df.index).agg(
        whale_alert_count=("amount_usd", "count"),
        whale_alert_volume_usd=("amount_usd", lambda x: x.sum() / 1e6),  # 백만 USD
    )

    # 유형별 카운트
    if "transaction_type" in df.columns:
        inflow  = df[df["transaction_type"] == "exchange_inflow"].groupby(df[df["transaction_type"] == "exchange_inflow"].index).size().rename("whale_exchange_inflow_count")
        outflow = df[df["transaction_type"] == "exchange_outflow"].groupby(df[df["transaction_type"] == "exchange_outflow"].index).size().rename("whale_exchange_outflow_count")
        agg = agg.join(inflow,  how="left").join(outflow, how="left").fillna(0)

    return agg


# ---------------------------------------------------------------------------
# Glassnode API (무료 티어: 일별 온체인 지표)
# ---------------------------------------------------------------------------

def get_cryptoquant_exchange_flow(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    CryptoQuant API로 BTC 거래소 순유입/유출을 수집한다.

    CRYPTOQUANT_API_KEY 환경변수가 없으면 빈 DataFrame 반환.
    무료 플랜: 일별 데이터, 전체 거래소 합산 유입/유출.

    API 문서: https://cryptoquant.com/docs

    Args:
        start    : 시작일 'YYYY-MM-DD'
        end      : 종료일 'YYYY-MM-DD', None이면 오늘
        use_cache: 캐시 사용 여부

    Returns:
        DataFrame (index=날짜, columns: whale_btc_exchange_inflow,
                   whale_btc_exchange_outflow, whale_btc_exchange_net)
    """
    import os
    api_key = os.environ.get("CRYPTOQUANT_API_KEY", "")
    if not api_key:
        log.warning("get_cryptoquant_exchange_flow: CRYPTOQUANT_API_KEY 없음 — 스킵")
        return pd.DataFrame()

    end = end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ck = _cache_key("cryptoquant_flow", start, end)

    if use_cache:
        cached = _load_cache(ck)
        if cached:
            df = pd.DataFrame(cached)
            if not df.empty and "index" in df.columns:
                df = df.set_index("index")
                df.index = pd.to_datetime(df.index)
            return df

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }

    # CryptoQuant v1 엔드포인트: exchange-flows (전체 거래소 합산)
    # window=day, exchange=all
    endpoints = [
        ("btc/exchange-flows/inflow",  "whale_btc_exchange_inflow",  "inflow_total"),
        ("btc/exchange-flows/outflow", "whale_btc_exchange_outflow", "outflow_total"),
    ]

    frames: list[pd.Series] = []
    for endpoint, col_name, value_key in endpoints:
        params = {
            "window":    "day",
            "exchange":  "all",
            "from":      start,
            "to":        end,
            "limit":     500,
        }
        try:
            resp = requests.get(
                f"{_CRYPTOQUANT_BASE}/{endpoint}",
                headers=headers,
                params=params,
                timeout=20,
            )
            if resp.status_code == 401:
                log.warning("CryptoQuant: 인증 실패 (401) — API 키 확인 필요")
                break
            if resp.status_code == 403:
                log.warning("CryptoQuant: 접근 권한 없음 (403) — 플랜 확인 필요")
                break
            if resp.status_code == 429:
                log.warning("CryptoQuant: 요청 한도 초과 (429) — 잠시 후 재시도")
                time.sleep(5)
                continue
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning("CryptoQuant API 오류 [%s]: %s", endpoint, e)
            continue

        items = data.get("result", {}).get("data", [])
        if not items:
            continue

        series_data: dict = {}
        for item in items:
            # CryptoQuant 응답: {"date": "2024-01-01", "inflow_total": 12345.67, ...}
            date_str = item.get("date") or item.get("datetime", "")
            val = item.get(value_key) or item.get("value")
            if date_str and val is not None:
                try:
                    series_data[pd.Timestamp(date_str)] = float(val)
                except (ValueError, TypeError):
                    continue

        if not series_data:
            continue

        s = pd.Series(series_data, name=col_name)
        s.index = pd.to_datetime(s.index).normalize()
        frames.append(s)
        time.sleep(0.3)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, axis=1)

    # 순유출 = 유출 - 유입 (양수: 거래소 자금 순유출 → 강세 신호)
    if "whale_btc_exchange_inflow" in result.columns and "whale_btc_exchange_outflow" in result.columns:
        result["whale_btc_exchange_net"] = (
            result["whale_btc_exchange_outflow"] - result["whale_btc_exchange_inflow"]
        )

    result.index.name = None
    _save_cache(ck, result.reset_index().rename(columns={result.index.name or "index": "index"}).to_dict("list"))
    log.info("get_cryptoquant_exchange_flow: %d행 수집 (%s ~ %s)", len(result), start, end)
    return result


# ---------------------------------------------------------------------------
# CoinGecko 거래소 BTC 보유량
# ---------------------------------------------------------------------------

def get_coingecko_exchange_reserves(
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    CoinGecko API로 주요 거래소의 BTC 보유량을 수집한다.

    Returns:
        DataFrame (columns: exchange, btc_reserve, btc_reserve_usd, last_updated)
        인덱스: 거래소 ID
    """
    import os
    api_key = os.environ.get("COINGECKO_API_KEY", "")

    ck = _cache_key("coingecko_reserves")
    if use_cache:
        cached = _load_cache(ck)
        if cached:
            return pd.DataFrame(cached)

    exchanges = ["binance", "coinbase", "kraken", "okx", "bybit", "bitfinex"]
    rows: list[dict] = []

    for ex_id in exchanges:
        params: dict = {}
        if api_key:
            params["x_cg_demo_api_key"] = api_key

        try:
            resp = requests.get(
                f"https://api.coingecko.com/api/v3/exchanges/{ex_id}",
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning("CoinGecko exchange [%s]: %s", ex_id, e)
            time.sleep(1)
            continue

        rows.append({
            "exchange":        data.get("name", ex_id),
            "exchange_id":     ex_id,
            "trade_volume_24h_btc": data.get("trade_volume_24h_btc", None),
            "last_updated":    data.get("updated_at", ""),
        })
        time.sleep(0.5)  # rate limit

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("exchange_id")
    _save_cache(ck, df.reset_index().to_dict("list"))
    log.info("get_coingecko_exchange_reserves: %d개 거래소 수집", len(df))
    return df


# ---------------------------------------------------------------------------
# 통합 수집 함수
# ---------------------------------------------------------------------------

def get_whale_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    고래 데이터 통합 수집 — master DataFrame 병합용.

    Whale Alert + Glassnode를 합쳐 일별 집계 DataFrame 반환.

    Returns:
        DataFrame (index=날짜, columns: whale_* 접두사)
    """
    frames: list[pd.DataFrame] = []

    # Whale Alert 집계
    raw_whale = get_whale_alerts(start, end, use_cache=use_cache)
    if not raw_whale.empty:
        agg = aggregate_whale_alerts(raw_whale)
        if not agg.empty:
            frames.append(agg)

    # CryptoQuant 거래소 유입/유출
    df_cq = get_cryptoquant_exchange_flow(start, end, use_cache=use_cache)
    if not df_cq.empty:
        frames.append(df_cq)

    if not frames:
        log.warning("get_whale_dataset: 수집된 고래 데이터 없음")
        return pd.DataFrame()

    from processors.merger import merge_dataframes
    return merge_dataframes(frames)
