# Phase 6 세부 기획안

> 대상: 암호화폐 고래 추적 + 기관 포트폴리오 변화 모니터링
> 신규 파일: collectors/global_/whale.py, analysis/crypto_intel.py
> 신규 리포트: build_d6_report (일간), build_w6_report (주간)

---

## 1. 데이터 소스

### 고래 온체인 데이터
| 소스 | 수집 내용 | API |
|------|----------|-----|
| Whale Alert API | 대형 트랜잭션 알림 (≥100만 USD) | REST, 무료 1000건/월 |
| Glassnode | 고래 지갑 주소 수, 거래소 순유입/유출 | REST, 무료 티어 제한 |
| CoinGecko | 거래소별 BTC 보유량 변화 (public) | 기존 키 활용 |

### 기관 포트폴리오 데이터
| 소스 | 수집 내용 | API |
|------|----------|-----|
| SEC EDGAR | 13F 분기 공시 — 기관의 GBTC/ETF 보유량 | REST 무료 |
| bitcointreasuries.net | 상장사 BTC 보유 현황 CSV/스크래핑 | HTML 파싱 |
| CoinGecko Companies | 공개기업 BTC/ETH 보유량 API | 기존 키 활용 |

---

## 2. collectors/global_/whale.py

### 함수 목록

| 함수 | 설명 |
|------|------|
| `get_whale_alerts(start, end, min_usd)` | Whale Alert API로 대형 이동 수집 |
| `get_glassnode_exchange_flow(start, end)` | 거래소 BTC 순유입/유출 (무료 티어) |
| `get_coingecko_exchange_reserves(use_cache)` | CoinGecko 거래소 BTC 보유량 |

### 출력 컬럼 (master 병합용)
- `whale_btc_exchange_inflow`  — 거래소 BTC 순유입 (BTC)
- `whale_btc_exchange_outflow` — 거래소 BTC 순유출 (BTC)
- `whale_alert_count`          — 당일 ≥100만USD 이동 건수
- `whale_alert_volume_usd`     — 당일 총 이동 금액 (USD)

---

## 3. collectors/global_/institutions.py

### 함수 목록

| 함수 | 설명 |
|------|------|
| `get_sec_13f_crypto(cik_list, quarter)` | SEC EDGAR 13F 파싱 (GBTC, IBIT, FBTC 보유량) |
| `get_public_company_btc(use_cache)` | CoinGecko 공개기업 BTC 보유량 |
| `get_bitcoin_etf_flows(start, end)` | 비트코인 현물 ETF 일별 순유입 (yfinance IBIT 등) |

### 추적 대상 기관 (13F)
- MicroStrategy (MSTR): BTC 최대 보유 공개기업
- BlackRock, Fidelity: 현물 ETF 운용사
- ARK Invest: ARKB ETF
- Grayscale: GBTC

### 추적 대상 ETF 티커 (yfinance)
- IBIT (BlackRock), FBTC (Fidelity), ARKB (ARK), GBTC (Grayscale), BITB (Bitwise)

---

## 4. analysis/crypto_intel.py

### 함수 목록

| 함수 | 설명 |
|------|------|
| `whale_signal(master)` | 거래소 순유입 급증 → 매도 압력 신호 |
| `institution_accumulation_signal(inst_df)` | 기관 BTC 누적량 변화 → 축적/분산 신호 |
| `etf_flow_summary(master, lookback_days)` | ETF 순유입 합계 + 추세 |
| `crypto_intel_summary(master, inst_df)` | 전체 요약 dict |

### 해석 기준
- 거래소 유입 ↑ (고래 매도 준비) → 단기 하락 압력
- 거래소 유출 ↑ (콜드월렛 이동) → 장기 보유 증가 → 공급 감소
- ETF 순유입 ↑ + 기관 누적 ↑ → 기관 수요 확인

---

## 5. 신규 리포트

### D-6: 암호화폐 고래·기관 일간 스냅샷
- `reports/daily/d6_crypto_intel_{date}.html`
- 섹션:
  1. 고래 이동 알림 테이블 (당일 ≥100만USD 거래)
  2. 거래소 BTC 순유입/유출 게이지 + 7일 라인
  3. 비트코인 현물 ETF 일별 순유입 바 차트

### W-6: 기관 포트폴리오 변화 주간 리포트
- `reports/weekly/w6_institution_{date}.html`
- 섹션:
  1. 공개기업 BTC 보유량 변화 바 차트 (상위 10개사)
  2. ETF 운용사별 보유량 파이 차트
  3. 주간 기관 축적/분산 신호 요약 카드

---

## 6. .env 추가 키

```
WHALE_ALERT_API_KEY=   # https://whale-alert.io/
GLASSNODE_API_KEY=     # 이미 .env.example에 존재
```

---

## 7. 무료 티어 제한사항 및 대응

| API | 제한 | 대응 |
|-----|------|------|
| Whale Alert | 1000건/월 | 일 1회 수집, ≥100만 USD 필터 |
| Glassnode | 무료: 일별 온체인 지표만 | 거래소 유입/유출 일별 데이터만 사용 |
| SEC EDGAR | 제한 없음 (분기 공시) | 분기별 1회 수집, 캐싱 필수 |
| CoinGecko Companies | 무료 포함 | 기존 demo key 활용 |
