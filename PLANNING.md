# 프로젝트 기획 문서
> 확정된 기획사항을 기록하는 파일. 세션마다 갱신됨.

---

## 디렉토리 구조 (확정)

```
fine/
├── collectors/
│   ├── __init__.py
│   ├── base.py                 # 공통 베이스 클래스 (캐싱, 로깅)
│   ├── kr/
│   │   ├── __init__.py
│   │   ├── stock.py            # pykrx (주가, PER/PBR, 수급, 공매도)
│   │   ├── financials.py       # dart-fss (재무제표, 공시)
│   │   └── macro.py            # ECOS, 공공데이터포털, 국토부
│   └── global_/
│       ├── __init__.py
│       ├── market.py           # yfinance (지수, 원자재, 환율, VIX)
│       ├── macro.py            # fredapi, wbgapi, OECD, EIA
│       ├── crypto.py           # ccxt, CoinGecko
│       └── alt.py              # NewsAPI, GDELT, pytrends, praw, EPU, CFTC
├── processors/
│   ├── __init__.py
│   ├── cleaner.py              # 타입 정규화, 이상값 제거
│   ├── normalizer.py           # Z-Score, Forward Fill
│   └── merger.py               # 마스터 데이터셋 병합
├── analysis/
│   ├── __init__.py
│   ├── correlation.py          # 상관관계 (Spearman, Rolling)
│   ├── factors.py              # 팩터 분석, 적정가(S-RIM)
│   ├── regime.py               # 매크로 국면 분류
│   └── backtest.py             # 동일가중 교체매매 백테스팅
├── visualization/
│   ├── __init__.py
│   ├── charts.py               # plotly 차트 함수 모음
│   └── report.py               # HTML 리포트 생성
├── data/
│   ├── raw/                    # 수집 원본 (gitignore)
│   ├── processed/              # 처리 완료 (gitignore)
│   └── cache/                  # API 캐시 (gitignore)
├── notebooks/
├── tests/
├── config.py                   # 전역 설정 (경로, 기본값)
├── scheduler/
│   ├── run_daily.bat           # Windows 일간 실행 배치
│   └── setup_task.py           # Windows Task Scheduler 등록
├── .github/workflows/
│   └── daily_pipeline.yml      # GitHub Actions 일간 자동화
├── main.py                     # 파이프라인 실행 진입점
├── requirements.txt
└── .env
```

---

## 데이터 흐름 (확정)

```
collectors/ → data/cache/*.parquet
           ↓
processors/ → data/processed/master_YYYYMMDD.parquet
           ↓
analysis/   → 상관관계 행렬, 국면 시리즈, 팩터 점수, 수익률
           ↓
visualization/ → reports/report_YYYYMMDD.html
```

---

## 인터페이스 계약 (확정)

```python
# 수집기 공통 시그니처
def get_*(identifier, start: str, end: str = None, use_cache: bool = True) -> pd.DataFrame

# 처리기
def process(df: pd.DataFrame, **options) -> pd.DataFrame

# 분석기
def analyze(master: pd.DataFrame, **params) -> pd.DataFrame | dict

# 시각화
def plot_*(data, title: str, **options) -> go.Figure
```

---

## 컬럼 네이밍 컨벤션 (확정)

| 접두사 | 대상 | 예시 |
|--------|------|------|
| `kr_` | 국내 주가/지수 | `kr_kospi`, `kr_005930_close` |
| `kr_fin_` | 국내 재무지표 | `kr_fin_005930_per` |
| `macro_` | 거시경제 | `macro_cpi`, `macro_pmi` |
| `rate_` | 금리/채권 | `rate_us10y`, `rate_fed` |
| `fx_` | 환율 | `fx_krw_usd`, `fx_dxy` |
| `cmd_` | 원자재 | `cmd_wti`, `cmd_gold` |
| `crypto_` | 암호화폐 | `crypto_btc` |
| `alt_` | 시장심리 | `alt_vix`, `alt_putcall` |
| `sent_` | 뉴스/감성 | `sent_epu`, `sent_reddit` |

---

## MVP 마일스톤 (확정)

| 단계 | 목표 | 완료 기준 | 상태 |
|------|------|----------|------|
| M1 | 환경 설정 | venv, requirements.txt, .env | ✅ |
| M2 | 첫 수집기 2개 | yfinance + pykrx 동작, parquet 저장 | ✅ |
| M3 | 처리 파이프라인 | master DataFrame 생성 | ✅ |
| M4 | 첫 시각화 | KOSPI vs 글로벌·환율·VIX 히트맵 | ✅ |
| M5 | 거시 추가 | fredapi, 매크로 국면 분류 | ✅ |
| M6 | 팩터 분석 | PER·ROE vs 수익률, 저평가주 스크리닝 | ✅ |
| M7 | 백테스팅 | 5년 백테스팅, KOSPI 대비 알파 | ✅ |
| M8 | 리포트 | HTML 리포트 자동 생성 | ✅ |

---

## 기술 스택 (확정)

- **언어**: Python 3.12
- **데이터**: pandas, numpy, pyarrow
- **수집**: pykrx, dart-fss, yfinance, fredapi, ccxt 외
- **분석**: scipy, statsmodels
- **시각화**: plotly, matplotlib, seaborn
- **환경**: venv (`.venv/`)

---

## 블로그 콘텐츠 기획 (확정 2026-04-12)

> 각 파트 구현 전 세부 기획안(`PLAN_*.md`)을 먼저 생성하고 확인 후 진행한다.

### 디렉토리 구조 추가 (예정)
```
analysis/
├── prediction.py       # 미국→KOSPI 예측 모델 (신규)
├── sentiment.py        # 감성 이동평균, 복합 감성 점수 (신규)
└── fear_greed.py       # 공포-탐욕 지수 (신규)
data/processed/
└── prediction_log.parquet  # 예측 정확도 트래킹 로그
```

---

### 일간 (Daily)

| # | 제목 형식 | 사용 데이터 | 분석 방법 | 시각화 | 구현 복잡도 |
|---|-----------|-------------|-----------|--------|------------|
| D-1 | `[일간 시황] YYYY-MM-DD` | 글로벌 지수 8개, VIX, 금리, 원자재, 암호화폐 | 전일 대비 pct_change, VIX 레벨 분류 | 자산별 등락 수평 막대 + 숫자 카드 | 하 |
| D-2 | `[연준·금리 감성] YYYY-MM-DD` | sent_news_fed, sent_news_global, rate 계열 | VADER 7일 이동평균, 장단기 스프레드 레벨 | 감성 게이지 + 금리 이중축 라인 | 하 |
| D-3 | `[암호화폐 스냅샷] YYYY-MM-DD` | crypto_btc/eth_close, btc_dominance, total_mcap | 24h 변화율, 도미넌스 | 도미넌스 게이지 + 시총 면적 차트 | 하 |
| D-4 | `[오늘 KOSPI 예상] YYYY-MM-DD` | us_sp500, rate_spread_10_2, rate_hy_spread, alt_vix, fx_krw_usd, sent_news_global → kr_kospi (lag=1) | 다수결 방향 신호 + 로지스틱 회귀 확률 | 신호등 UI + 확률 게이지 + 선행 상관 순위 막대 | 중 |
| D-5 | `[미국→한국 시장 선행 분석] YYYY-MM-DD` | 미국 전일 종가 변수들 → KOSPI 갭 (open/close-1) | OLS 갭 예측(S&P500_ret + KRW_ret), 롤링 선행 상관 추이 | 산점도 + 회귀선 + 롤링 상관계수 라인 | 중 |

### 주간 (Weekly)

| # | 제목 형식 | 사용 데이터 | 분석 방법 | 시각화 | 구현 복잡도 |
|---|-----------|-------------|-----------|--------|------------|
| W-1 | `[W{n}] 자산 간 상관관계 주간 변화` | 전체 *_close | 이번 주 vs 직전 주 Spearman 행렬 비교, top-5 쌍 추출 | 상관 히트맵 + 변화량 히트맵 | 하 |
| W-2 | `[W{n}] 매크로 국면은 지금 어디인가` | macro_pmi_us, macro_cpi, rate_fed, rate_spread_10_2 | classify_regime() + 12개월 국면 히스토리 | 타임라인 컬러 바 + 현재 국면 카드 | 하 |
| W-3 | `[W{n}] 크립토 vs 전통자산 롤링 상관` | crypto_btc, us_sp500, cmd_gold, alt_vix | rolling_spearman(window=30) 3쌍 | 3개 라인 오버레이 | 하 |
| W-4 | `[W{n}] 국내 금리·환율·KOSPI 3각 관계` | kr_kospi, fx_krw_usd, rate_us10y, rate_spread_10_2 | rolling Spearman(30일) + 산점도 | 롤링 상관 라인 + 산점도 | 하 |
| W-5 | `[W{n}] 미국→KOSPI 예측 주간 적중률 리뷰` | prediction_log.parquet | 주간 예측 vs 실제 집계, VIX 레짐별 분석 | Rolling Hit Rate 라인 + Confusion Matrix | 중 |

### 월간 (Monthly)

| # | 제목 형식 | 사용 데이터 | 분석 방법 | 시각화 | 구현 복잡도 |
|---|-----------|-------------|-----------|--------|------------|
| M-1 | `[YYYY-MM] 글로벌 매크로 월간 종합 리포트` | master 전체 | build_report() 확장 (국면+수익률+상관+백테스팅) | 기존 HTML 리포트 4섹션 | 하 |
| M-2 | `[YYYY-MM] 삼성전자 S-RIM 적정가 & 팩터` | kr_fin_005930_* | S-RIM 적정가 vs 현재가 괴리율, ROE-수익률 IC | S-RIM 밴드 라인 차트 | 하 |
| M-3 | `[YYYY-MM] 미국 경기 사이클 좌표` | macro_pmi_us, macro_cpi, macro_gdp_us, macro_unemployment | Z-Score 정규화 후 PMI-CPI 사분면 좌표, 12개월 이동 경로 | 사분면 플롯 (4국면 배경 + 경로) | 중 |
| M-4 | `[YYYY-MM] 동일가중 멀티에셋 백테스팅 성과` | 6개 자산 close | run_backtest() 월말 리밸런싱, KOSPI 대비 알파/샤프/MDD | 누적 수익률 vs 벤치마크 + 성과 테이블 | 하 |
| M-5 | `[YYYY-MM] 국면별 자산 성과: 지금 무엇을 사야 하나` | macro_pmi_us, macro_cpi, 전체 *_close | regime_asset_performance() 4국면×자산 평균수익률 | 국면×자산 평균수익률 히트맵 | 중 |
| M-6 | `[YYYY-MM] 공포-탐욕 지수 분석` | alt_vix, rate_hy_spread, sent_news_global, crypto_btc_dominance, rate_spread_10_2 | 5개 지표 Z-Score 가중 합산 0~100 지수, 30일 이동평균 | 게이지 + 히스토리 라인 | 중 |

---

### 추가 구현 필요 항목 (우선순위 순)

| 우선순위 | 항목 | 파일 | 용도 | 상태 |
|----------|------|------|------|------|
| 상 | `analysis/prediction.py` 신규 | 신규 | lag_correlation_rank, majority_vote_signal, rolling_logit_predict | ✅ |
| 상 | `charts.py` — `plot_gauge()` | 추가 | 공포-탐욕·감성·확률 게이지 | ✅ |
| 상 | `charts.py` — `plot_regime_path()` | 추가 | PMI-CPI 사분면 이동 경로 | ✅ |
| 중 | `analysis/sentiment.py` 신규 | 신규 | 감성 이동평균, 복합 감성 점수 | ✅ |
| 중 | `analysis/fear_greed.py` 신규 | 신규 | 공포-탐욕 지수 계산 | ✅ |
| 중 | `visualization/blog_formatter.py` 신규 | 신규 | 블로그 플랫폼 변환·배포 | ✅ |
| 중 | `collectors/global_/whale.py` 신규 | 신규 | Whale Alert + Glassnode 고래 온체인 | ✅ |
| 중 | `collectors/global_/institutions.py` 신규 | 신규 | CoinGecko 기업 BTC, ETF, SEC 13F | ✅ |
| 중 | `analysis/crypto_intel.py` 신규 | 신규 | 고래 신호, ETF 분석, 기관 축적/분산 | ✅ |
| 중 | `collectors/kr/stock.py` — 수급 추가 | 수정 | pykrx 외인·기관 순매수 | ✅ |
| 중 | `collectors/global_/market.py` — 섹터 ETF 추가 | 수정 | XLK/XLE/XLF/XLV/XLI | ✅ |
| 중 | `processors/merger.py` — KOSPI 갭 컬럼 | 수정 | kr_kospi_gap = open(T+1)/close(T)-1 | ✅ |
| 하 | `analysis/regime.py` — `regime_transition_matrix()` | 추가 | 국면 천이 확률 행렬 | ✅ |

---

### 구현 단계 로드맵

```
Phase 1 (기존 모듈 조합): D-1, W-2, M-1, M-4                          ✅ 완료
Phase 2 (plot_gauge + plot_regime_path 추가): D-2, D-3, W-3, W-4, M-3 ✅ 완료
Phase 3 (prediction.py): D-4, D-5, W-5                                ✅ 완료
Phase 4 (sentiment.py + fear_greed.py): M-5, M-6                      ✅ 완료
Phase 5 (blog_formatter.py): 블로그 플랫폼 자동 변환·배포               ✅ 완료
Phase 6 (whale.py + institutions.py + crypto_intel.py): D-6, W-6      ✅ 완료
Phase 7 (미구현 리포트): W-1, M-2, M-4                                 ✅ 완료
Phase 8 (데이터 소스 확장): EIA, World Bank, pytrends, GDELT, EPU, CFTC, kr/macro.py ✅ 완료
Phase 9 (마무리): OECD CLI, CBOE P/C(FRED CPCE), ccxt→main.py, 자동화 스케줄러     ✅ 완료
Phase 10 (Reddit 감성): praw get_reddit_sentiment(), vaderSentiment, main.py 6-e     ✅ 완료
Phase 11 (버그수정·고도화): OECD CLI 0행 버그, 부동산 리포트, BTC ETF 활성화, 긴급리포트  ✅ 완료
```

### 신규 API 키 필요 (Phase 6)

| 키 | 서비스 | 상태 |
|----|--------|------|
| `CRYPTOQUANT_API_KEY` | https://cryptoquant.com | 무료 플랜 price-ohlcv만 지원 → 미사용 |
| `ECOS_API_KEY` | 한국은행 | ✅ 입력 완료 (kr_macro_base_rate/m2/cpi/gdp 수집 중) |
| `REDDIT_CLIENT_ID/SECRET` | Reddit | 심사 중 |

> Whale Alert → 무료 플랜 폐지로 제거. Blockchair/Mempool.space(키 불필요)로 대체.

---

### 작업 진행 규칙

> **각 파트 구현 시작 전 반드시 세부 기획안 파일을 먼저 생성하고 확인받는다.**
> 파일명: `docs/PLAN_{파트명}.md` (예: `docs/PLAN_D4_kospi_prediction.md`)
> 세부 기획안 포함 내용: 함수 시그니처, 입출력 스펙, 엣지케이스, 구현 순서
