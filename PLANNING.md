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
Phase 12 (API 서버 + 혜택 수집기): FastAPI 주제별 라우터, 복지로/정부24/교육 혜택 수집기    ✅ 완료
```

### 신규 API 키 필요 (Phase 6)

| 키 | 서비스 | 상태 |
|----|--------|------|
| `CRYPTOQUANT_API_KEY` | https://cryptoquant.com | 무료 플랜 price-ohlcv만 지원 → 미사용 |
| `ECOS_API_KEY` | 한국은행 | ✅ 입력 완료 (kr_macro_base_rate/m2/cpi/gdp 수집 중) |
| `REDDIT_CLIENT_ID/SECRET` | Reddit | 심사 중 |

> Whale Alert → 무료 플랜 폐지로 제거. Blockchair/Mempool.space(키 불필요)로 대체.

---

---

## API 서버 구조 (Phase 12, 확정 2026-04-14)

### 위치
`fine/api/` — fine 프로젝트 내 통합 (parquet 직접 참조)

### 디렉토리
```
api/
├── main.py                      # FastAPI 앱, 라우터 등록, CORS
├── core/
│   ├── cache.py                 # 인메모리 TTL 캐시
│   └── response.py              # 공통 응답 포맷 {status, timestamp, data, meta}
└── routers/
    ├── finance/                 # fine 파이프라인 결과 제공
    │   ├── market.py            # /finance/market/snapshot, /history/{symbol}
    │   ├── signal.py            # /finance/signal/kospi
    │   └── report.py            # /finance/report/list, /latest
    ├── benefits/                # 정부 혜택/지원금
    │   ├── central.py           # /benefits/central/welfare, /gov24
    │   └── education.py         # /benefits/education/voucher, /scholarship, /training
    ├── realestate/              # 부동산
    │   └── apt.py               # /realestate/apt/trade
    └── crypto/                  # 암호화폐
        └── market.py            # /crypto/market/snapshot
```

### 엔드포인트 전체 목록
| 그룹 | 엔드포인트 | 캐시 TTL | 설명 |
|------|-----------|---------|------|
| finance | `GET /api/v1/finance/market/snapshot` | 5분 | 글로벌 지수·환율·원자재 최신값 |
| finance | `GET /api/v1/finance/market/history/{symbol}` | 5분 | 심볼 시계열 (기본 90일) |
| finance | `GET /api/v1/finance/signal/kospi` | 1시간 | KOSPI 방향 예측 신호 |
| finance | `GET /api/v1/finance/report/list?type=daily` | 10분 | 리포트 목록 |
| finance | `GET /api/v1/finance/report/latest?type=daily` | — | 최신 HTML 리포트 |
| benefits | `GET /api/v1/benefits/central/welfare` | 6시간 | 복지로 복지서비스 목록 |
| benefits | `GET /api/v1/benefits/central/welfare/{id}` | 6시간 | 복지서비스 상세 |
| benefits | `GET /api/v1/benefits/central/gov24` | 6시간 | 정부24 생애주기 서비스 |
| benefits | `GET /api/v1/benefits/education/voucher` | 6시간 | 평생교육바우처 |
| benefits | `GET /api/v1/benefits/education/scholarship` | 6시간 | 국가장학금 |
| benefits | `GET /api/v1/benefits/education/training` | 6시간 | 국민내일배움카드 직업훈련 |
| realestate | `GET /api/v1/realestate/apt/trade` | 24시간 | 아파트 실거래가 |
| crypto | `GET /api/v1/crypto/market/snapshot` | 1분 | BTC·ETH·도미넌스 |
| exchange | `GET /api/v1/exchange/rates/latest?base=USD` | 10분 | 최신 환율 (ECB 기준, 키 불필요) |
| exchange | `GET /api/v1/exchange/rates/history?base=USD&target=KRW` | 1시간 | 기간별 환율 이력 |
| exchange | `GET /api/v1/exchange/rates/convert?amount=100&base=USD&target=KRW` | — | 환전 계산 |
| exchange | `GET /api/v1/exchange/rates/krw` | 10분 | 원화 기준 주요 통화 (ECOS+frankfurter) |
| weather | `GET /api/v1/weather/forecast/current?city=seoul` | 10분 | 현재 날씨 (기온·체감·습도·UV 등) |
| weather | `GET /api/v1/weather/forecast/daily?city=seoul&days=7` | 30분 | 일별 예보 (최대 16일) |
| weather | `GET /api/v1/weather/forecast/hourly?city=tokyo` | 30분 | 시간별 예보 (48시간) |
| weather | `GET /api/v1/weather/forecast/aqi?city=seoul` | 10분 | 대기질 PM10·PM2.5 + 한국 등급 |
| weather | `GET /api/v1/weather/forecast/cities` | — | 지원 도시 목록 (국내 8개 + 해외 9개) |
| news | `GET /api/v1/news/headlines/top?country=kr&category=technology` | 15분 | 국가별 주요 헤드라인 (NewsAPI) |
| news | `GET /api/v1/news/headlines/search?query=금리` | 30분 | 키워드 뉴스 검색 |
| news | `GET /api/v1/news/geek/latest` | 10분 | GeekNews 최신 IT 기술 뉴스 (RSS, 키 불필요) |
| news | `GET /api/v1/news/geek/trending?days=7` | 1시간 | GeekNews 트렌드 키워드 추출 |
| news | `GET /api/v1/news/geek/category/AI/ML` | 10분 | GeekNews 카테고리별 기사 (AI/ML·보안·오픈소스 등) |

### 실행 방법
```bash
# 개발
uvicorn api.main:app --reload --port 8000

# 프로덕션
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Next.js 연동
```typescript
// Next.js → FastAPI 호출 예시
const res = await fetch('http://localhost:8000/api/v1/benefits/central/welfare?life_stage=청년')
const { data } = await res.json()
```

---

### 작업 진행 규칙

> **각 파트 구현 시작 전 반드시 세부 기획안 파일을 먼저 생성하고 확인받는다.**
> 파일명: `docs/PLAN_{파트명}.md` (예: `docs/PLAN_D4_kospi_prediction.md`)
> 세부 기획안 포함 내용: 함수 시그니처, 입출력 스펙, 엣지케이스, 구현 순서

---

## 신규 API 그룹 기획 (Phase 13, 확정 2026-04-15)

### 현황 요약

| 상태 | 그룹 수 | 그룹 목록 |
|------|--------|---------|
| 구현 완료 | 7개 | finance, benefits, realestate, crypto, exchange, weather, news |
| 기획 확정 | 15개 | kids, culture, outdoor, travel, price, medical, seasonal, invest, indicator, saving, game, index, transit, card, crypto_intel |

---

### kids — 어린이·학생 무료 체험 행사

**소스:** 한국관광공사 TourAPI, 문화공공데이터광장, KOPIS, 도서관 정보나루, 국립중앙박물관 e뮤지엄

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/kids/events?region=서울&age=초등` | 1시간 | 지역·연령별 무료 체험 행사 통합 목록 |
| `GET /api/v1/kids/events/festival` | 1시간 | 전국 어린이 축제·체험 행사 |
| `GET /api/v1/kids/events/museum` | 3시간 | 박물관·미술관 체험교육 프로그램 |
| `GET /api/v1/kids/events/performance` | 1시간 | 어린이 무료 공연 (아동극·음악회) |
| `GET /api/v1/kids/events/library` | 3시간 | 도서관 어린이 독서·만들기 프로그램 |

---

### culture — 문화행사·축제

**소스:** 한국관광공사 TourAPI, KOPIS, 문화공공데이터광장, 도서관 정보나루

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/culture/events?region=부산&month=05` | 1시간 | 지역·기간별 축제·행사 통합 목록 |
| `GET /api/v1/culture/events/festival` | 1시간 | 전국 축제 (테마·지역 필터) |
| `GET /api/v1/culture/events/performance` | 30분 | 공연 목록 (장르·가격·지역 필터) |
| `GET /api/v1/culture/events/exhibition` | 3시간 | 전시·박물관·미술관 행사 |
| `GET /api/v1/culture/events/trending` | 1시간 | 이번 주 인기 행사 Top10 |

---

### outdoor — 휴양림·캠핑장

**소스:** 고캠핑 API(공공데이터포털), 국립자연휴양림관리소, 산림청 산림복지서비스, 한국관광공사 TourAPI

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/outdoor/camping?region=강원&type=글램핑` | 6시간 | 지역·타입별 캠핑장 목록 (일반·글램핑·카라반) |
| `GET /api/v1/outdoor/camping/{id}` | 6시간 | 캠핑장 상세 (시설·사진·예약링크) |
| `GET /api/v1/outdoor/forest?region=경기` | 6시간 | 지역별 자연휴양림 목록·예약 가능 여부 |
| `GET /api/v1/outdoor/healing?region=충북` | 12시간 | 치유의숲·산림욕장 목록 |
| `GET /api/v1/outdoor/recommend?date=2026-05-10` | 1시간 | 날짜 기반 추천 (날씨 API 연동) |

---

### travel — 호텔·콘도·여행 할인 이벤트

**소스:** 한국관광공사 TourAPI, 공공데이터포털(숙박대전·여행가는달), NewsAPI(재활용)

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/travel/stay?region=제주&type=호텔` | 3시간 | 지역·유형별 숙박시설 목록 |
| `GET /api/v1/travel/stay/{id}` | 6시간 | 숙박시설 상세 (사진·등급·편의시설) |
| `GET /api/v1/travel/discount/events` | 1시간 | 현재 진행 중인 정부 주관 할인 행사 목록 |
| `GET /api/v1/travel/discount/festival` | 1시간 | 숙박대전·여행가는달 행사 정보 |
| `GET /api/v1/travel/packages?region=강원` | 3시간 | 지역별 여행 패키지·코스 추천 |

---

### price — 생활물가

**소스:** 오피넷(한국석유공사), 한국소비자원 참가격, 농산물유통정보 KAMIS, 한국은행 ECOS(재활용)

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/price/fuel?region=서울&type=휘발유` | 10분 | 지역별 주유소 유가 + 최저가 순위 |
| `GET /api/v1/price/fuel/trend?days=30` | 1시간 | 유가 추이 (전국 평균) |
| `GET /api/v1/price/grocery?category=채소` | 1시간 | 농축수산물 가격 (전일 대비 등락) |
| `GET /api/v1/price/consumer?category=가공식품` | 3시간 | 생필품·외식 가격 비교 |
| `GET /api/v1/price/cpi` | 6시간 | 소비자물가지수 추이 (ECOS 재활용) |

---

### medical — 의료·보건

**소스:** 중앙응급의료센터, 건강보험심사평가원 HIRA, 식품의약품안전처, 국민건강보험공단

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/medical/hospital?region=서울&dept=소아과` | 1시간 | 지역·진료과목별 병원 목록 + 평가등급 |
| `GET /api/v1/medical/pharmacy?lat=37.5&lon=126.9` | 10분 | 현재 위치 근처 운영 중인 약국 |
| `GET /api/v1/medical/emergency?region=경기` | 5분 | 응급실 현황 (병상 수·대기·운영여부) |
| `GET /api/v1/medical/aed?lat=37.5&lon=126.9` | 24시간 | 근처 AED 위치 |
| `GET /api/v1/medical/drug?name=타이레놀` | 24시간 | 의약품 허가·성분·주의사항 |
| `GET /api/v1/medical/checkup?region=부산` | 24시간 | 건강검진 기관 목록 |

---

### seasonal — 계절별 야외시설 개장 일정

**소스:** 한국관광공사 TourAPI, 공공데이터포털(물놀이장·스키장), 서울 열린데이터광장, 행정안전부 물놀이 안전정보

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/seasonal/water?region=서울` | 1시간 | 지역별 물놀이터·공공수영장 개장 현황 |
| `GET /api/v1/seasonal/beach?region=강원` | 3시간 | 해수욕장 개장·폐장일, 수온·파고 |
| `GET /api/v1/seasonal/valley?region=경기` | 3시간 | 계곡 안전등급 + 혼잡도 |
| `GET /api/v1/seasonal/ski?region=강원` | 1시간 | 스키장·눈썰매장 개장 여부·슬로프 상태 |
| `GET /api/v1/seasonal/ice?region=서울` | 3시간 | 실내외 빙상장·공공 아이스링크 운영 현황 |
| `GET /api/v1/seasonal/now` | 30분 | 현재 계절 기준 오픈 중인 시설 전체 목록 |

---

### invest — 투자 정보

**소스:** KRX(pykrx 재활용), DART(dart-fss 재활용), KOFIA, 한국은행 ECOS(재활용), 금융감독원 금융상품통합비교, 한국수출입은행

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/invest/stock/snapshot?market=KOSPI` | 5분 | 시장 전체 현황 (지수·거래량·상승/하락 종목 수) |
| `GET /api/v1/invest/stock/{ticker}` | 10분 | 종목 상세 (주가·재무·공시·수급) |
| `GET /api/v1/invest/stock/ipo` | 1시간 | 공모주 일정·수요예측 결과·청약 일정 |
| `GET /api/v1/invest/fund?type=국내주식형` | 1시간 | 펀드 수익률·설정액·운용사별 비교 |
| `GET /api/v1/invest/etf?category=레버리지` | 10분 | ETF 목록·괴리율·거래량 |
| `GET /api/v1/invest/rate/deposit?bank=전체` | 3시간 | 은행별 예금·적금 금리 비교 |
| `GET /api/v1/invest/rate/bond` | 1시간 | 국채·회사채·CD 수익률 |
| `GET /api/v1/invest/rate/base` | 6시간 | 한국은행 기준금리 추이 |

---

### indicator — 주요 경제지표

**소스:** 한국은행 ECOS(재활용), 통계청 KOSIS, 관세청 무역통계, FRED(재활용), OECD API(재활용), World Bank(재활용)

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/indicator/inflation?country=KR` | 6시간 | CPI·PPI·PCE 최신값 + 전월비·전년비 |
| `GET /api/v1/indicator/gdp?country=KR` | 12시간 | GDP 성장률 (분기·연간) |
| `GET /api/v1/indicator/employment?country=KR` | 6시간 | 실업률·고용률·비농업고용 |
| `GET /api/v1/indicator/trade?country=KR` | 6시간 | 수출입 금액·증감률·무역수지 |
| `GET /api/v1/indicator/pmi?country=KR` | 6시간 | 제조업·서비스업 PMI |
| `GET /api/v1/indicator/money?country=KR` | 6시간 | M2·통화승수·대출증감 |
| `GET /api/v1/indicator/dashboard` | 1시간 | 주요 지표 한눈에 (서프라이즈 인덱스 포함) |
| `GET /api/v1/indicator/calendar` | 1시간 | 이번 달 주요 경제지표 발표 일정 |

---

### saving — 예금·적금·금융상품·ETF

**소스:** 금융감독원 금융상품통합비교, 예금보험공사, KRX(재활용), KOFIA, 한국은행 ECOS(재활용)

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/saving/deposit?bank=전체&term=12` | 1시간 | 은행별 정기예금 금리 비교 |
| `GET /api/v1/saving/savings?bank=전체&term=12` | 1시간 | 적금 금리 비교 (단리·복리·자유적립) |
| `GET /api/v1/saving/special` | 30분 | 현재 특판 고금리 예·적금 상품 목록 |
| `GET /api/v1/saving/isa` | 3시간 | ISA 계좌 상품 비교 (중개형·신탁형·서민형) |
| `GET /api/v1/saving/pension` | 3시간 | 연금저축·IRP 상품 수익률 비교 |
| `GET /api/v1/saving/etf?category=국내주식` | 10분 | ETF 목록 (카테고리·운용사·거래량 필터) |
| `GET /api/v1/saving/etf/{ticker}` | 5분 | ETF 상세 (NAV·괴리율·구성종목·배당이력) |
| `GET /api/v1/saving/etf/dividend` | 1시간 | 배당 ETF 순위 (배당률·지급주기) |
| `GET /api/v1/saving/etf/compare?tickers=069500,360750` | 10분 | ETF 간 수익률·비용·괴리율 비교 |
| `GET /api/v1/saving/recommend?amount=1000만&term=12&risk=낮음` | 1시간 | 금액·기간·위험성향 기반 상품 추천 |
| `GET /api/v1/saving/protection?bank=새마을금고` | 24시간 | 금융기관별 예금자보호 여부 확인 |

---

### game — 인기 게임 정보·스탯 계산·쿠폰·이벤트

**소스:** 넥슨 Open API, Riot Games API, 크래프톤 PUBG API, Neople API, 펄어비스 API, 엔씨소프트 PLAYNC, 비공식 커뮤니티 API(쿠키런·오븐스매시), 각 게임사 RSS

| 게임 | 소스 | 전적 | 스탯계산 | 쿠폰 | 이벤트 |
|------|------|------|---------|------|--------|
| LoL·발로란트·TFT | Riot API | O | O | O | O |
| 배틀그라운드 | 크래프톤 API | O | - | O | O |
| 메이플스토리 | 넥슨 API | O | O | O | O |
| FC온라인 | 넥슨 API | O | - | O | O |
| 던전앤파이터 | Neople API | O | O | O | O |
| 검은사막 | 펄어비스 API | O | - | O | O |
| 쿠키런: 킹덤 | 비공식 API + RSS | - | O | O | O |
| 오븐스매시 | 비공식 위키 + RSS | - | O | O | O |

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/game/lol/summoner/{name}` | 5분 | LoL 소환사 전적·티어·KDA |
| `GET /api/v1/game/lol/match/{name}?count=20` | 5분 | 최근 매치 상세 |
| `GET /api/v1/game/valorant/player/{name}` | 5분 | 발로란트 티어·헤드샷률·에이전트 통계 |
| `GET /api/v1/game/pubg/player/{name}` | 5분 | 배그 시즌 스탯 (KD·생존시간·탑10율) |
| `GET /api/v1/game/maple/character/{name}` | 10분 | 메이플 캐릭터 스탯·장비·유니온 |
| `GET /api/v1/game/maple/calc/damage` | — | 최종 데미지 계산 (공격력·보스데미지·방무·크리) |
| `GET /api/v1/game/maple/calc/starforce?item=에테르넬&star=22` | — | 스타포스 기댓값 (평균 비용·파괴 확률) |
| `GET /api/v1/game/lol/calc/dps?champion=제이스` | — | 챔피언 빌드별 초당 딜량 계산 |
| `GET /api/v1/game/lol/meta/tier` | 30분 | 현 패치 챔피언 티어표 (포지션별) |
| `GET /api/v1/game/cookierun/cookie/{name}` | 6시간 | 쿠키런 킹덤 쿠키 상세 (등급·타입·스탯·스킬) |
| `GET /api/v1/game/cookierun/deck/calc` | — | 덱 전투력 계산 |
| `GET /api/v1/game/ovensmash/character/{name}` | 6시간 | 오븐스매시 캐릭터 스탯·스킬·특성 |
| `GET /api/v1/game/ovensmash/calc/combo` | — | 콤보·데미지 계산기 |
| `GET /api/v1/game/devsisters/news` | 30분 | 쿠키런·오븐스매시 공지·이벤트·쿠폰 |
| `GET /api/v1/game/coupon?game=maple` | 10분 | 게임별 현재 유효한 쿠폰 코드 목록 |
| `GET /api/v1/game/coupon/all` | 10분 | 전체 게임 쿠폰 통합 목록 (만료일 포함) |
| `GET /api/v1/game/event?game=lol` | 30분 | 게임별 진행 중 이벤트 목록 (기간·보상) |
| `GET /api/v1/game/event/all` | 30분 | 전체 게임 이벤트 통합 캘린더 |
| `GET /api/v1/game/event/ending?days=3` | 30분 | N일 내 종료 예정 이벤트 |
| `GET /api/v1/game/maintenance` | 10분 | 현재 점검 중인 게임 목록·예상 복구 시간 |

---

### index — 글로벌 주요 지수

**소스:** yfinance(재활용), FRED(재활용), CBOE(재활용)

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/index/snapshot` | 5분 | 전체 주요 지수 현재가·등락률 한눈에 |
| `GET /api/v1/index/us` | 5분 | 미국 4대 지수 (S&P·나스닥·다우·러셀) |
| `GET /api/v1/index/asia` | 5분 | 아시아 지수 (한국·일본·중국·대만) |
| `GET /api/v1/index/europe` | 5분 | 유럽 지수 (DAX·FTSE·CAC·STOXX) |
| `GET /api/v1/index/dollar` | 10분 | 달러인덱스 현재값·추이·구성통화 비중 |
| `GET /api/v1/index/vix` | 5분 | VIX·VIX9D·VIX3M·VVIX + 공포/탐욕 해석 |
| `GET /api/v1/index/sector` | 10분 | 미국 섹터별 등락률 히트맵 |
| `GET /api/v1/index/bond` | 10분 | 미국채 2·10·30년물 + 장단기 스프레드 |
| `GET /api/v1/index/commodity` | 10분 | 원자재 지수·금·WTI·구리 |
| `GET /api/v1/index/history/{symbol}?days=90` | 10분 | 지수 시계열 (일봉) |
| `GET /api/v1/index/correlation` | 1시간 | 주요 지수 간 상관관계 행렬 |

---

### transit — 교통요금

**소스:** 공공데이터포털(코레일·고속버스), 한국도로공사, 서울 열린데이터광장, ODsay API

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/transit/train?from=서울&to=부산` | 6시간 | 열차 구간 운임 (KTX·일반·좌석 등급별) |
| `GET /api/v1/transit/bus?from=서울&to=강릉` | 6시간 | 고속버스 요금·소요시간·시간표 |
| `GET /api/v1/transit/highway?from=서울&to=부산` | 24시간 | 고속도로 통행료 (차종별) |
| `GET /api/v1/transit/subway?region=서울` | 24시간 | 지하철 기본요금·거리비례 요금표 |
| `GET /api/v1/transit/route/fare?from=강남역&to=인천공항` | 10분 | 출발지→목적지 최적경로 + 총 요금 |
| `GET /api/v1/transit/compare?from=서울&to=부산` | 6시간 | 교통수단별 요금·시간 비교 |

---

### card — 카드 혜택

**소스:** 금융감독원 금융상품통합비교, 각 카드사 Open API, 하이픈 API

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/card/search?category=주유&company=전체` | 3시간 | 카테고리별 혜택 카드 목록 (할인율 순) |
| `GET /api/v1/card/{id}` | 6시간 | 카드 상세 (연회비·혜택·전월실적 조건) |
| `GET /api/v1/card/compare?ids=카드A,카드B,카드C` | 6시간 | 카드 간 혜택 비교표 |
| `GET /api/v1/card/recommend?spend=주유:30만,카페:10만` | 1시간 | 지출 패턴 기반 최적 카드 추천 |
| `GET /api/v1/card/event` | 30분 | 현재 진행 중인 카드사 이벤트·프로모션 |
| `GET /api/v1/card/annual_fee?benefit=항공마일리지` | 6시간 | 연회비 대비 혜택 효율 순위 |

---

### crypto_intel — 코인 투자 인텔리전스

**소스:** CoinGecko API(재활용), GitHub API(무료·토큰 선택), Bitcoin Treasuries(공개 스크래핑), SoSoValue ETF(무료 REST), CoinGlass ETF Flow(무료 티어)

#### 1) 섹터·분류

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/crypto_intel/sector/list` | 6시간 | 전체 코인 섹터·카테고리 목록 (DeFi·Layer1·GameFi 등) |
| `GET /api/v1/crypto_intel/sector/{sector}` | 10분 | 섹터별 코인 목록 (시총·24h 등락률·도미넌스 비중) |
| `GET /api/v1/crypto_intel/sector/heatmap` | 10분 | 섹터 성과 히트맵 (24h·7d·30d 수익률) |
| `GET /api/v1/crypto_intel/coin/{id}/profile` | 1시간 | 코인 프로필 (섹터·태그·체인·런치일·백서링크) |

**소스 매핑:**
- CoinGecko `/coins/categories` → 섹터 목록·시총합·등락률
- CoinGecko `/coins/markets?category={id}` → 섹터 내 코인 상세
- CoinGecko `/coins/{id}` → categories, links, description

---

#### 2) 기관 보유량·ETF 자금흐름

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/crypto_intel/institution/treasury` | 6시간 | 상장사·기관 BTC·ETH 보유량 순위 (회사명·수량·시가) |
| `GET /api/v1/crypto_intel/institution/etf/flow` | 10분 | 미국 현물 BTC ETF 일간 자금유입출 (AUM·넷플로우) |
| `GET /api/v1/crypto_intel/institution/etf/holdings` | 1시간 | ETF별 BTC 보유량·AUM·운용사 비교 |
| `GET /api/v1/crypto_intel/institution/etf/history?days=90` | 1시간 | ETF 자금흐름 누적 시계열 |

**소스 매핑:**
- Bitcoin Treasuries (`bitcointreasuries.net/api`) → 기업 BTC 보유 공개 데이터 (HTML 스크래핑 또는 비공식 JSON)
- SoSoValue (`sosovalue.com`) → ETF AUM·넷플로우 무료 REST API
- CoinGlass (`coinglass.com/api`) → ETF 자금흐름 무료 티어

**엣지케이스:**
- Bitcoin Treasuries 스크래핑 실패 시 CoinGecko `public_companies_bitcoin` 폴백
- ETF 데이터는 미국 장 마감 후 갱신 → TTL 10분이나 실제 변경은 1일 1회

---

#### 3) 개발 활동 (GitHub 기반)

| 엔드포인트 | 캐시 | 설명 |
|-----------|------|------|
| `GET /api/v1/crypto_intel/dev/{id}/activity` | 1시간 | 개발 활동 요약 (커밋수·기여자·PR·이슈·스타·포크) |
| `GET /api/v1/crypto_intel/dev/{id}/commits?days=30` | 1시간 | 최근 커밋 로그 (날짜·메시지·작성자·레포) |
| `GET /api/v1/crypto_intel/dev/{id}/releases` | 3시간 | 최근 릴리즈·버전 이력 (날짜·태그·변경요약) |
| `GET /api/v1/crypto_intel/dev/ranking?sector=layer1&limit=20` | 3시간 | 개발 활동 상위 코인 순위 (4주 커밋수 기준) |
| `GET /api/v1/crypto_intel/dev/{id}/pulse` | 1시간 | 개발 건강도 점수 (0~100, 커밋빈도·기여자다양성·이슈해결률 합산) |

**소스 매핑:**
- CoinGecko `/coins/{id}` → `developer_data` (forks, stars, subscribers, total_issues, closed_issues, pull_requests_merged, commit_activity_4_weeks, code_additions_deletions_4_weeks)
- GitHub REST API v3 → `GET /repos/{owner}/{repo}/commits`, `/releases` (토큰 없이 60req/hr, 토큰 있으면 5000req/hr)
- GitHub 레포 주소: CoinGecko `links.repos_url.github[0]` 에서 추출

**개발 건강도 점수 산출 로직 (pulse):**
```
commit_score   = min(commit_activity_4_weeks / 100, 1.0) * 40
contributor_score = min(contributors_30d / 20, 1.0) * 30
issue_score    = (closed_issues / max(total_issues,1)) * 20
freshness_score = 1.0 if last_commit < 7days else 0.5 if < 30days else 0.0) * 10
pulse = (commit_score + contributor_score + issue_score + freshness_score) * 100
```

---

#### 필요 API 키

| 키 | 서비스 | 필수 여부 |
|----|--------|---------|
| `COINGECKO_API_KEY` | CoinGecko Demo | 기존 키 재활용 |
| `GITHUB_TOKEN` | GitHub REST API | 선택 (없으면 60req/hr, 있으면 5000req/hr) |

> SoSoValue·CoinGlass·Bitcoin Treasuries는 키 불필요 (공개 무료)

---

### 그룹 간 주요 연동 관계

```
weather  ──→ outdoor, seasonal, travel   (날씨 기반 추천)
price    ──→ transit, card               (주유 최저가 + 할인카드)
indicator──→ invest, saving, index       (매크로 → 자산배분 신호)
finance  ──→ invest, index               (글로벌 매크로 + 국내 투자)
kids     ──→ culture, seasonal           (어린이 체험 + 계절 시설)
travel   ──→ outdoor, seasonal           (숙박 + 캠핑/물놀이)
```
