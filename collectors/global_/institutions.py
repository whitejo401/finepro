"""
collectors/global_/institutions.py

기관 투자자 암호화폐 포트폴리오 데이터 수집.

데이터 소스:
  1. CoinGecko Companies API — 공개기업 BTC/ETH 보유량
  2. yfinance — 비트코인 현물 ETF 일별 가격 + 추정 유입량
  3. SEC EDGAR — 13F 분기 공시 (GBTC/ETF 보유량)

출력:
  - 공개기업 BTC/ETH 보유량 DataFrame
  - ETF 일별 AUM 추이 DataFrame
  - 13F 기관 보유량 DataFrame
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

log = get_logger("collectors.institutions")

CACHE_DIR = BASE_DIR / "data" / "cache" / "institutions"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


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
# CoinGecko 공개기업 BTC/ETH 보유량
# ---------------------------------------------------------------------------

def get_public_company_holdings(
    coin: str = "bitcoin",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    CoinGecko API로 공개기업 BTC/ETH 보유량 현황을 수집한다.

    Args:
        coin     : 'bitcoin' 또는 'ethereum'
        use_cache: 캐시 사용 여부 (하루 단위 캐싱)

    Returns:
        DataFrame (index: company_name, columns: symbol, total_holdings,
                   total_entry_value_usd, total_current_value_usd,
                   percentage_of_total_supply, country)
    """
    import os
    api_key = os.environ.get("COINGECKO_API_KEY", "")

    ck = _cache_key("companies", coin, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    if use_cache:
        cached = _load_cache(ck)
        if cached:
            df = pd.DataFrame(cached)
            if "company_name" in df.columns:
                df = df.set_index("company_name")
            return df

    params: dict = {}
    if api_key:
        params["x_cg_demo_api_key"] = api_key

    try:
        resp = requests.get(
            f"https://api.coingecko.com/api/v3/companies/public_treasury/{coin}",
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("get_public_company_holdings [%s]: %s", coin, e)
        return pd.DataFrame()

    companies = data.get("companies", [])
    if not companies:
        return pd.DataFrame()

    rows = []
    for c in companies:
        rows.append({
            "company_name":              c.get("name", ""),
            "symbol":                    c.get("symbol", ""),
            "country":                   c.get("country", ""),
            "total_holdings":            c.get("total_holdings", 0),
            "total_entry_value_usd":     c.get("total_entry_value_usd", 0),
            "total_current_value_usd":   c.get("total_current_value_usd", 0),
            "percentage_of_total_supply": c.get("percentage_of_total_supply", 0),
        })

    df = pd.DataFrame(rows).set_index("company_name")
    # 보유량 기준 내림차순 정렬
    df = df.sort_values("total_holdings", ascending=False)

    _save_cache(ck, df.reset_index().to_dict("list"))
    log.info("get_public_company_holdings [%s]: %d개 기업", coin, len(df))
    return df


# ---------------------------------------------------------------------------
# 비트코인 현물 ETF 일별 데이터 (yfinance)
# ---------------------------------------------------------------------------

# 미국 비트코인 현물 ETF 티커
_BTC_ETF_TICKERS = {
    "IBIT":  "BlackRock iShares Bitcoin ETF",
    "FBTC":  "Fidelity Wise Origin Bitcoin ETF",
    "ARKB":  "ARK 21Shares Bitcoin ETF",
    "BITB":  "Bitwise Bitcoin ETF",
    "HODL":  "VanEck Bitcoin ETF",
    "BTCO":  "Invesco Galaxy Bitcoin ETF",
    "GBTC":  "Grayscale Bitcoin Trust ETF",
    "BRRR":  "Valkyrie Bitcoin Fund",
}


def get_bitcoin_etf_data(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    비트코인 현물 ETF의 일별 종가 및 거래량을 수집한다.

    yfinance를 사용하며, AUM(추정)은 종가 × 거래량으로 근사한다.

    Args:
        start    : 시작일 'YYYY-MM-DD'
        end      : 종료일 'YYYY-MM-DD', None이면 오늘
        use_cache: 캐시 사용 여부

    Returns:
        DataFrame (index=날짜, MultiIndex columns: (ticker, 'close'/'volume'))
    """
    end = end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ck = _cache_key("btc_etf", start, end)

    if use_cache:
        cached = _load_cache(ck)
        if cached:
            try:
                df = pd.DataFrame(cached)
                df.index = pd.to_datetime(df.index)
                return df
            except Exception:
                pass

    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance 미설치 — pip install yfinance")
        return pd.DataFrame()

    tickers = list(_BTC_ETF_TICKERS.keys())
    try:
        raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    except Exception as e:
        log.warning("get_bitcoin_etf_data: yfinance 오류: %s", e)
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        try:
            close_col = ("Close", ticker) if ("Close", ticker) in raw.columns else None
            vol_col   = ("Volume", ticker) if ("Volume", ticker) in raw.columns else None
            if close_col is None:
                continue
            sub = pd.DataFrame()
            sub[f"etf_{ticker.lower()}_close"]  = raw[close_col]
            if vol_col:
                sub[f"etf_{ticker.lower()}_volume"] = raw[vol_col]
            frames.append(sub)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, axis=1)
    result.index = pd.to_datetime(result.index).normalize()
    result = result.dropna(how="all")

    _save_cache(ck, result.to_dict("list"))
    log.info("get_bitcoin_etf_data: %d행 × %d ETF 수집 (%s ~ %s)",
             len(result), len(frames), start, end)
    return result


# ---------------------------------------------------------------------------
# SEC EDGAR 13F 파싱 (분기별 기관 보유량)
# ---------------------------------------------------------------------------

# 추적 대상 기관 CIK (SEC 고유 식별자)
_INSTITUTION_CIKS = {
    "MicroStrategy":  "1050446",
    "BlackRock":      "1364742",
    "Fidelity":       "315066",
    "ARK Invest":     "1579982",
    "Grayscale":      "1588272",
    "Galaxy Digital": "1899287",
    "VanEck":         "1137360",
}

# 추적 대상 암호화폐 관련 증권 이름 키워드
_CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "crypto",
    "GBTC", "IBIT", "FBTC", "ARKB", "BITB", "HODL",
]


def get_sec_13f_crypto(
    quarter: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    SEC EDGAR에서 주요 기관의 13F 분기 공시를 파싱하여
    암호화폐 관련 보유량을 반환한다.

    Args:
        quarter  : 'YYYY-QN' 형식 (예: '2024-Q4'). None이면 최근 분기 추정
        use_cache: 캐시 사용 여부

    Returns:
        DataFrame (columns: institution, security_name, shares, value_usd, quarter)
    """
    if quarter is None:
        now = datetime.now(timezone.utc)
        q = (now.month - 1) // 3
        quarter = f"{now.year}-Q{q}" if q > 0 else f"{now.year - 1}-Q4"

    ck = _cache_key("sec_13f", quarter)
    if use_cache:
        cached = _load_cache(ck)
        if cached:
            return pd.DataFrame(cached)

    # 분기 → SEC 제출 날짜 범위 변환
    year, q_str = quarter.split("-")
    q_num = int(q_str[1])
    # 13F는 분기 종료 후 45일 이내 제출
    quarter_end_months = {1: "03", 2: "06", 3: "09", 4: "12"}
    end_month = quarter_end_months[q_num]
    filing_date = f"{year}-{end_month}-01"

    all_rows: list[dict] = []

    for institution, cik in _INSTITUTION_CIKS.items():
        try:
            rows = _fetch_13f_holdings(cik, institution, filing_date, quarter)
            all_rows.extend(rows)
        except Exception as e:
            log.warning("SEC 13F [%s, CIK=%s]: %s", institution, cik, e)
        time.sleep(0.2)  # SEC rate limit: 10 req/sec

    if not all_rows:
        log.warning("get_sec_13f_crypto: 수집된 13F 데이터 없음 (%s)", quarter)
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    _save_cache(ck, df.to_dict("list"))
    log.info("get_sec_13f_crypto: %d건 수집 (%s)", len(df), quarter)
    return df


def _fetch_13f_holdings(
    cik: str,
    institution: str,
    filing_date: str,
    quarter: str,
) -> list[dict]:
    """단일 기관의 13F 보유 목록에서 암호화폐 관련 항목을 추출한다."""
    headers = {"User-Agent": "FinancialDataPipeline contact@example.com"}

    # 1단계: 최근 13F 제출 목록 조회
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    try:
        resp = requests.get(submissions_url, headers=headers, timeout=15)
        resp.raise_for_status()
        submissions = resp.json()
    except Exception as e:
        log.warning("SEC submissions [CIK=%s]: %s", cik, e)
        return []

    # 13F-HR 제출 찾기
    filings = submissions.get("filings", {}).get("recent", {})
    forms      = filings.get("form", [])
    accessions = filings.get("accessionNumber", [])
    dates      = filings.get("filingDate", [])

    target_accession = None
    for form, acc, dt in zip(forms, accessions, dates):
        if form == "13F-HR" and dt <= filing_date:
            target_accession = acc.replace("-", "")
            break

    if not target_accession:
        return []

    # 2단계: 13F XML 파일 파싱
    acc_formatted = f"{target_accession[:10]}-{target_accession[10:12]}-{target_accession[12:]}"
    index_url = (
        f"https://www.sec.gov/Archives/edgar/full-index/"
        f"{acc_formatted[:4]}/QTR{(int(acc_formatted[5:7])-1)//3+1}/"
    )

    # 직접 infotable XML URL 구성
    xml_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
        f"{target_accession}/infotable.xml"
    )

    try:
        resp = requests.get(xml_url, headers=headers, timeout=20)
        if resp.status_code == 404:
            # XML 파일명이 다를 수 있음 — index 페이지에서 찾기
            idx_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR&dateb=&owner=include&count=10&search_text="
            return []
        resp.raise_for_status()
    except Exception as e:
        log.warning("SEC 13F XML [CIK=%s]: %s", cik, e)
        return []

    import xml.etree.ElementTree as ET
    rows: list[dict] = []
    try:
        # namespace 처리
        xml_content = resp.text
        xml_content = xml_content.replace(' xmlns="', ' xmlnsi="')  # namespace 제거 trick
        root = ET.fromstring(xml_content)

        for info in root.iter("infoTable"):
            name_el    = info.find("nameOfIssuer")
            shares_el  = info.find("sshPrnamt") or info.find("shrsOrPrnAmt")
            value_el   = info.find("value")
            if name_el is None:
                continue

            security_name = (name_el.text or "").strip()
            # 암호화폐 관련 키워드 필터
            name_lower = security_name.lower()
            if not any(kw.lower() in name_lower for kw in _CRYPTO_KEYWORDS):
                continue

            try:
                shares = int(shares_el.text.replace(",", "")) if shares_el is not None and shares_el.text else 0
            except ValueError:
                shares = 0
            try:
                value_usd = int(value_el.text.replace(",", "")) * 1000 if value_el is not None and value_el.text else 0
            except ValueError:
                value_usd = 0

            rows.append({
                "institution":    institution,
                "security_name":  security_name,
                "shares":         shares,
                "value_usd":      value_usd,
                "quarter":        quarter,
            })
    except ET.ParseError as e:
        log.warning("SEC 13F XML 파싱 오류 [%s]: %s", institution, e)

    return rows


# ---------------------------------------------------------------------------
# 통합 수집 함수
# ---------------------------------------------------------------------------

def get_institution_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> dict:
    """
    기관 데이터 통합 수집.

    Returns:
        {
            'btc_companies' : DataFrame (공개기업 BTC 보유량),
            'eth_companies' : DataFrame (공개기업 ETH 보유량),
            'etf_daily'    : DataFrame (ETF 일별 데이터, master 병합용),
            'sec_13f'      : DataFrame (13F 분기 데이터),
        }
    """
    return {
        "btc_companies": get_public_company_holdings("bitcoin",  use_cache=use_cache),
        "eth_companies": get_public_company_holdings("ethereum", use_cache=use_cache),
        "etf_daily":     get_bitcoin_etf_data(start, end, use_cache=use_cache),
        "sec_13f":       get_sec_13f_crypto(use_cache=use_cache),
    }
