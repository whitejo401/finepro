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
│       ├── crypto.py           # ccxt, CoinGecko, Glassnode
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
| M1 | 환경 설정 | venv, requirements.txt, .env | ⬜ |
| M2 | 첫 수집기 2개 | yfinance + pykrx 동작, parquet 저장 | ⬜ |
| M3 | 처리 파이프라인 | master DataFrame 생성 | ⬜ |
| M4 | 첫 시각화 | KOSPI vs 글로벌·환율·VIX 히트맵 | ⬜ |
| M5 | 거시 추가 | fredapi, 매크로 국면 분류 | ⬜ |
| M6 | 팩터 분석 | PER·ROE vs 수익률, 저평가주 스크리닝 | ⬜ |
| M7 | 백테스팅 | 5년 백테스팅, KOSPI 대비 알파 | ⬜ |
| M8 | 리포트 | HTML 리포트 자동 생성 | ⬜ |

---

## 기술 스택 (확정)

- **언어**: Python 3.12
- **데이터**: pandas, numpy, pyarrow
- **수집**: pykrx, dart-fss, yfinance, fredapi, ccxt 외
- **분석**: scipy, statsmodels
- **시각화**: plotly, matplotlib, seaborn
- **환경**: venv (`.venv/`)
