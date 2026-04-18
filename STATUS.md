# 프로젝트 현황 (세션 재개용)
> 세션 종료 시 항상 이 파일을 최신 상태로 갱신한다.
> 재개 시 이 파일만 읽으면 컨텍스트 복구 가능.

---

## 현재 단계

**Phase 14 — 퀀트 파이프라인 버그 수정 및 고도화**
마지막 작업일: 2026-04-17

---

## 파이프라인 현황 (main.py)

```
python main.py --mode all --start 2025-01-01
```

- 데이터 수집 → merge → 리포트 생성 전체 흐름 동작 확인
- master: **1068행 × 99컬럼** (2025-01-01 ~ 2026-04-17)
- 리포트 생성: d1~d6 / w1~w6 / m1~m6 중 **20/22 성공, 2개 에러**

### 에러 목록 (우선 수정 대상)

| 코드 | 리포트 | 에러 메시지 | 근본 원인 | 수정 위치 |
|------|--------|------------|----------|----------|
| w3 | 크립토 상관 | `cannot reindex on an axis with duplicate labels` | CoinGecko + ccxt 둘 다 `crypto_btc_close`, `crypto_eth_close` 수집 → merge 후 중복 컬럼 | `processors/merger.py` `merge_dataframes()` 또는 `collectors/global_/crypto.py` |
| m4 | 백테스팅 | `The truth value of a Series is ambiguous` | `analysis/backtest.py` 또는 `visualization/report.py build_m4_report()` 내 `if signal:` 형태 비교 | `visualization/report.py:build_m4_report` 또는 `analysis/backtest.py` |

### 데이터 수집 경고 (버그는 아니지만 개선 필요)

| 수집기 | 상태 | 원인 |
|--------|------|------|
| pykrx 수급 | 스킵 | KRX API 변경 (`get_market_net_purchases_of_equities_by_investor` 없음) |
| Reddit 감성 | 스킵 | `REDDIT_CLIENT_ID/SECRET` 미설정 |
| World Bank | 빈 데이터 | 2025~2026 최신 데이터 미발표 |
| GDELT | 429 | Too Many Requests (rate limit) |
| Blockchair | 스킵 | 연속 3회 430 (IP 한도) |

---

## Phase 14 완료 내역

| 항목 | 상태 | 비고 |
|------|------|------|
| w3 중복 컬럼 버그 | ✅ 완료 | `merger.py` combine_first + 중복 인덱스 제거 |
| m4 백테스팅 Series 모호성 | ✅ 완료 | `report.py` 스칼라 강제 변환 |
| 예측 모델 고도화 | ✅ 완료 | RF + LightGBM + 앙상블 추가 |
| GitHub Actions 자동화 | ✅ 완료 | 평일 KST 06:00 자동 실행 |
| pykrx 수급 수집 복구 | ✅ 완료 | pykrx 1.2.7 업그레이드 + KRX_ID/KRX_PW 환경변수로 로그인 지원 |

**현재 파이프라인**: `main.py --mode all` 실행 시 **22/22 리포트 성공 (ERROR 0건)**

## 다음 할 일

1. **GitHub Secrets 등록** — 레포 Settings → Secrets에 `.env` 키 등록해야 GitHub Actions 실제 실행 가능
   - 필요 키: `FRED_API_KEY`, `EIA_API_KEY`, `COINGECKO_API_KEY`, `NEWS_API_KEY`, `ECOS_API_KEY`, `DATA_GO_KR_API_KEY`, `MOLIT_API_KEY`
2. **앙상블 예측 리포트 연동** — `build_d4_report`에 RF/LightGBM 확률 표시 추가
3. **pykrx 수급 대안 소스 탐색** — 네이버 금융 또는 DART 기관투자자 공시

---

## Phase 13 API 서버 현황

23개 그룹, 152개 엔드포인트 전체 완료.
`api/main.py`에 모든 라우터 등록. 서버 실행: `uvicorn api.main:app --reload`

---

## 핵심 파일 위치

| 파일 | 용도 |
|------|------|
| `main.py` | 파이프라인 진입점 (수집 → 병합 → 리포트) |
| `processors/merger.py` | DataFrame 병합, 중복 컬럼 처리 |
| `analysis/prediction.py` | KOSPI 방향/갭 예측 |
| `analysis/backtest.py` | 동일가중 백테스팅, 성과 지표 |
| `analysis/regime.py` | 매크로 경기 국면 분류 (ML Clock) |
| `visualization/report.py` | 리포트 생성 (d1~m6 전체) |
| `reports/` | 생성된 HTML 리포트 |
| `api/main.py` | FastAPI 앱 진입점 |
| `.env` | API 키 (커밋 금지) |

---

## 추가 필요 API 키

| 키 | 용도 | 상태 |
|----|------|------|
| `GITHUB_TOKEN` | crypto_intel 개발활동 (없으면 60req/hr) | 미입력 |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Reddit 커뮤니티 감성 | 미입력 |
| `KRX_ID` / `KRX_PW` | pykrx 1.2.7+ 투자자별 수급 수집 | ✅ 입력완료 |
