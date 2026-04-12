"""
collectors/global_/whale.py

암호화폐 고래(대형 거래) 온체인 데이터 수집.

데이터 소스 (모두 무료, API 키 불필요):
  1. Blockchair API    — BTC/ETH 대형 트랜잭션 필터 (≥100만 USD), 키 불필요, 1440 req/일
  2. Mempool.space API — Bitcoin 최근 블록 대형 트랜잭션, 키 불필요, 제한 없음

※ Whale Alert    → 유료 전용 정책으로 제거 (2024년 이후 무료 플랜 폐지)
※ CryptoQuant    → 무료 플랜은 price-ohlcv 만 제공, exchange-flows 는 유료 전용

출력 컬럼 (master 병합용):
  whale_alert_count           : 당일 ≥min_usd 대형 이동 건수
  whale_alert_volume_usd      : 당일 총 이동 금액 (백만 USD)
  whale_consolidation_ratio   : 통합 트랜잭션 비율 (input > output → 거래소 유입 추정)
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from collectors.base import get_logger
from config import BASE_DIR

log = get_logger("collectors.whale")

CACHE_DIR = BASE_DIR / "data" / "cache" / "whale"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# API endpoints (모두 공개, 키 불필요)
_BLOCKCHAIR_BASE = "https://api.blockchair.com"
_MEMPOOL_BASE    = "https://mempool.space/api"

# Blockchair 1440 req/day 보호: 요청 간 최소 간격(초)
_BLOCKCHAIR_MIN_INTERVAL = 0.7


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
# Blockchair API — 대형 트랜잭션 (키 불필요, 1440 req/일)
# ---------------------------------------------------------------------------

def get_large_transactions_blockchair(
    start: str,
    end: str | None = None,
    coin: str = "bitcoin",
    min_usd: int = 1_000_000,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Blockchair API로 대형 온체인 트랜잭션을 수집한다.

    API 키 불필요. 1440 req/일 제한. BTC/ETH/LTC 등 41개 체인 지원.

    Args:
        start    : 시작일 'YYYY-MM-DD'
        end      : 종료일 'YYYY-MM-DD', None이면 오늘
        coin     : 'bitcoin' | 'ethereum' | 'litecoin' 등
        min_usd  : 최소 출력 USD 금액 (기본 100만)
        use_cache: 캐시 사용 여부

    Returns:
        DataFrame (index=datetime UTC, columns: hash, coin, input_count,
                   output_count, output_total_usd, tx_type)
    """
    end = end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ck = _cache_key("blockchair", coin, start, end, str(min_usd))

    if use_cache:
        cached = _load_cache(ck)
        if cached:
            df = pd.DataFrame(cached)
            if not df.empty and "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.set_index("datetime")
            return df

    # 날짜 범위를 하루 단위로 분할 → 요청 수 절약
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt   = datetime.strptime(end,   "%Y-%m-%d")
    all_rows: list[dict] = []
    consecutive_errors = 0
    _MAX_CONSECUTIVE_ERRORS = 3  # 연속 실패 시 조기 종료

    current = start_dt
    while current <= end_dt:
        date_str  = current.strftime("%Y-%m-%d")
        date_next = (current + timedelta(days=1)).strftime("%Y-%m-%d")

        # Blockchair 필터: 시간 범위 + 최소 USD 출력
        params = {
            "q": f"time({date_str}..{date_next}),output_total_usd({min_usd}..)",
            "s": "time(desc)",
            "limit": 100,
            "offset": 0,
        }

        try:
            resp = requests.get(
                f"{_BLOCKCHAIR_BASE}/{coin}/transactions",
                params=params,
                timeout=20,
                headers={"Accept": "application/json"},
            )
            if resp.status_code in (429, 430):
                consecutive_errors += 1
                log.warning(
                    "Blockchair: 요청 한도 초과 (%d) — %s 스킵 (연속 실패 %d/%d)",
                    resp.status_code, date_str, consecutive_errors, _MAX_CONSECUTIVE_ERRORS,
                )
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    log.warning("Blockchair: 연속 %d회 실패 — IP 블랙리스트 추정, 수집 중단", _MAX_CONSECUTIVE_ERRORS)
                    break
                current += timedelta(days=1)
                time.sleep(5)
                continue
            if resp.status_code == 402:
                log.warning("Blockchair: 유료 기능 요청 (402) — 파라미터 확인 필요")
                break
            resp.raise_for_status()
            data = resp.json()
            consecutive_errors = 0  # 성공 시 리셋
        except Exception as e:
            consecutive_errors += 1
            log.warning("Blockchair [%s %s]: %s (연속 실패 %d/%d)",
                        coin, date_str, e, consecutive_errors, _MAX_CONSECUTIVE_ERRORS)
            if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                log.warning("Blockchair: 연속 %d회 실패 — 수집 중단", _MAX_CONSECUTIVE_ERRORS)
                break
            current += timedelta(days=1)
            time.sleep(_BLOCKCHAIR_MIN_INTERVAL)
            continue

        rows = data.get("data", [])
        for row in rows:
            dt_str = row.get("time", "")
            if not dt_str:
                continue
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

            input_count  = int(row.get("input_count", 1))
            output_count = int(row.get("output_count", 1))

            all_rows.append({
                "datetime":         dt,
                "hash":             row.get("hash", "")[:16],  # 축약 저장
                "coin":             coin,
                "input_count":      input_count,
                "output_count":     output_count,
                "output_total_usd": float(row.get("output_total_usd", 0)),
                # 휴리스틱 분류: input > output → 통합(거래소 유입 추정)
                #               input < output → 분배(거래소 유출 추정)
                "tx_type": _classify_tx_heuristic(input_count, output_count),
            })

        current += timedelta(days=1)
        time.sleep(_BLOCKCHAIR_MIN_INTERVAL)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows).set_index("datetime").sort_index()
    _save_cache(ck, df.reset_index().to_dict("list"))
    log.info("get_large_transactions_blockchair [%s]: %d건 (%s ~ %s, ≥$%s)",
             coin, len(df), start, end, f"{min_usd:,}")
    return df


def _classify_tx_heuristic(input_count: int, output_count: int) -> str:
    """
    입출력 수 기반 트랜잭션 유형 휴리스틱 분류.

    input > output*2  → 통합(consolidation): 여러 지갑 → 하나로 모음 → 거래소 유입 추정
    output > input*2  → 분배(distribution):  하나에서 → 여럿으로 → 거래소 유출 추정
    otherwise         → 일반 이전(transfer)
    """
    if input_count > output_count * 2:
        return "consolidation"   # 거래소 유입 추정 (매도 준비)
    elif output_count > input_count * 2:
        return "distribution"    # 거래소 유출 추정 (장기 보유)
    else:
        return "transfer"


def aggregate_large_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Blockchair 대형 트랜잭션 원시 데이터를 일별로 집계한다.

    Returns:
        DataFrame (index=날짜, columns: whale_alert_count, whale_alert_volume_usd,
                   whale_consolidation_ratio)
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.index = pd.to_datetime(df.index).normalize()

    agg = df.groupby(df.index).agg(
        whale_alert_count=("output_total_usd", "count"),
        whale_alert_volume_usd=("output_total_usd", lambda x: x.sum() / 1e6),
    )

    # 통합 비율 (높을수록 거래소 유입 압력 추정)
    if "tx_type" in df.columns:
        consolidation = (df["tx_type"] == "consolidation").groupby(df.index).sum()
        total = df.groupby(df.index).size()
        agg["whale_consolidation_ratio"] = (consolidation / total).round(3)

    return agg


# ---------------------------------------------------------------------------
# Mempool.space — Bitcoin 최근 블록 대형 트랜잭션 (키 불필요, BTC 특화)
# ---------------------------------------------------------------------------

def get_mempool_large_txs(
    min_btc: float = 10.0,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Mempool.space API로 최근 Bitcoin 블록의 대형 트랜잭션을 수집한다.

    키 불필요. 최근 10블록(약 100분) 내 대형 거래만 조회.
    Blockchair로 커버 안 되는 당일 실시간 보완용.

    Args:
        min_btc  : 최소 BTC 출력 금액 (기본 10 BTC)
        use_cache: 캐시 사용 여부 (캐시 TTL: 1시간)

    Returns:
        DataFrame (index=datetime, columns: txid, output_btc, output_count, fee_rate)
    """
    ck = _cache_key("mempool", str(min_btc),
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H"))  # 1시간 캐시

    if use_cache:
        cached = _load_cache(ck)
        if cached:
            df = pd.DataFrame(cached)
            if not df.empty and "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.set_index("datetime")
            return df

    # 최근 블록 해시 목록 조회
    try:
        resp = requests.get(f"{_MEMPOOL_BASE}/v1/blocks", timeout=10)
        resp.raise_for_status()
        blocks = resp.json()  # 최근 15블록
    except Exception as e:
        log.warning("Mempool.space 블록 조회 실패: %s", e)
        return pd.DataFrame()

    satoshi = 1e8  # 1 BTC = 1억 satoshi
    min_sat = int(min_btc * satoshi)
    all_rows: list[dict] = []

    for block in blocks[:10]:  # 최근 10블록
        block_hash = block.get("id", "")
        block_time = block.get("timestamp", 0)
        if not block_hash:
            continue

        try:
            resp = requests.get(
                f"{_MEMPOOL_BASE}/block/{block_hash}/txs/0",
                timeout=15,
            )
            resp.raise_for_status()
            txs = resp.json()
        except Exception as e:
            log.warning("Mempool.space 블록 tx 조회 실패 [%s]: %s", block_hash[:8], e)
            time.sleep(0.5)
            continue

        for tx in txs:
            # 출력 총량 계산
            total_out = sum(v.get("value", 0) for v in tx.get("vout", []))
            if total_out < min_sat:
                continue

            output_count = len(tx.get("vout", []))
            input_count  = len(tx.get("vin", []))
            fee = tx.get("fee", 0)
            vsize = tx.get("size", 1)

            all_rows.append({
                "datetime":     datetime.fromtimestamp(block_time, tz=timezone.utc).replace(tzinfo=None),
                "txid":         tx.get("txid", "")[:16],
                "output_btc":   round(total_out / satoshi, 4),
                "output_count": output_count,
                "input_count":  input_count,
                "fee_rate":     round(fee / vsize, 1) if vsize > 0 else 0,
                "tx_type":      _classify_tx_heuristic(input_count, output_count),
            })

        time.sleep(0.3)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows).set_index("datetime").sort_index()
    _save_cache(ck, df.reset_index().to_dict("list"))
    log.info("get_mempool_large_txs: %d건 (≥%.1f BTC, 최근 10블록)", len(df), min_btc)
    return df


# ---------------------------------------------------------------------------
# CryptoQuant 메모
# ---------------------------------------------------------------------------
# 무료 플랜은 /v1/my/discovery/endpoints 기준
# {btc,eth,trx,xrp,alt,erc20,stablecoin}/market-data/price-ohlcv 만 허용.
# exchange-flows (inflow/outflow) 등 온체인 지표는 유료 플랜 전용.
# price-ohlcv 는 CoinGecko/yfinance 로 이미 커버되므로 이 파이프라인에서 사용하지 않음.


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

    Blockchair 대형 트랜잭션 + CryptoQuant 거래소 유입/유출을 합쳐 일별 집계 반환.

    Returns:
        DataFrame (index=날짜, columns: whale_* 접두사)
    """
    frames: list[pd.DataFrame] = []

    # Blockchair 대형 트랜잭션 집계 (키 불필요)
    raw_blockchair = get_large_transactions_blockchair(start, end, use_cache=use_cache)
    if not raw_blockchair.empty:
        agg = aggregate_large_transactions(raw_blockchair)
        if not agg.empty:
            frames.append(agg)

    if not frames:
        log.warning("get_whale_dataset: 수집된 고래 데이터 없음")
        return pd.DataFrame()

    from processors.merger import merge_dataframes
    return merge_dataframes(frames)
