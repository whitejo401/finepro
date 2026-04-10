# Financial Data Project - Claude Code Instructions

## 프로젝트 개요
글로벌 매크로 퀀트 인텔리전스 시스템 구축.
뉴스/지표/데이터가 상호작용하여 자산 시장에 미치는 영향을 수집·분석·예측하는 파이프라인.

## 기술 스택
- **언어**: Python 3.10+
- **데이터**: pandas, numpy
- **시각화**: plotly, matplotlib
- **환경**: 가상환경 사용 (.venv 또는 conda)
- **설정/시크릿**: .env 파일 (절대 커밋 금지)

## 확정된 데이터 소스 (23개)

### 국내 주식
- pykrx - KOSPI/KOSDAQ 주가, PER/PBR, 외국인/기관 수급, 공매도
- dart-fss - 재무제표, 배당공시 (DART API)
- 한국투자증권 KIS API - 실시간 시세, 분봉 (계좌 필요)

### 국내 거시경제
- ECOS API (한국은행) - 금리, M2, GDP, CPI
- 공공데이터포털 API - 상장법인 정보, 기업공시
- 국토교통부 실거래가 API - 부동산 실거래

### 글로벌 (yfinance로 통합)
- 전 세계 주식·ETF·지수·선물(원유/금/구리)·환율·VIX

### 미국/글로벌 거시
- fredapi - FRED (CPI/PCE/PMI/고용/M2/GDP/국채금리/하이일드스프레드)
- wbgapi - World Bank (200+ 국가 거시지표)
- OECD API - 경기선행지수(CLI), 국가별 PMI
- EIA API - 원유재고, 생산량, 가스가격

### 암호화폐
- ccxt - 100+ 거래소 통합 (업비트, 바이낸스 등)
- CoinGecko API - 시총, 도미넌스, 메타데이터
- Glassnode - 온체인 데이터 (무료 계층 제한)

### 시장 심리/포지셔닝
- CBOE API - Put/Call Ratio, VIX 세부
- CFTC COT Report - 선물 포지셔닝 (주간 CSV)

### 뉴스/대체 데이터
- NewsAPI - 뉴스 헤드라인 (무료 키)
- GDELT Project - 지정학 이벤트 수치화
- EPU Index - 경제정책 불확실성 지수 (CSV)
- pytrends - Google Trends 심리 대리 지표
- praw - Reddit 커뮤니티 감성
- SEC EDGAR - 미국 기업 공시

## 디렉토리 구조 (목표)
```
fine/
├── data/
│   ├── raw/          # 수집된 원시 데이터
│   ├── processed/    # 정제/병합된 데이터
│   └── cache/        # API 응답 캐시
├── collectors/       # 데이터 수집 모듈 (소스별)
├── processors/       # 데이터 정제, 병합, Z-Score 정규화
├── analysis/         # 상관관계, 팩터 분석, 국면 분류
├── strategies/       # 백테스팅 전략
├── notebooks/        # 탐색적 분석 Jupyter
├── .env              # API 키 (커밋 금지)
└── .env.example      # 키 목록 템플릿
```

## 코딩 규칙
- API 키는 반드시 환경 변수로 관리, 코드에 하드코딩 금지
- 외부 API 호출 시 rate limit과 에러 처리 포함
- 데이터 수집 함수는 캐싱 옵션을 지원해야 함 (불필요한 API 재호출 방지)
- 파일명: snake_case, 클래스명: PascalCase
- 각 수집기는 독립적으로 실행 가능해야 함

## API 키 목록 (.env에 저장)
```
DART_API_KEY=
ECOS_API_KEY=
DATA_GO_KR_API_KEY=
MOLIT_API_KEY=
FRED_API_KEY=
EIA_API_KEY=
NEWS_API_KEY=
COINGECKO_API_KEY=
GLASSNODE_API_KEY=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
KIS_APP_KEY=
KIS_APP_SECRET=
```
