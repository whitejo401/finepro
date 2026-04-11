# API 키 발급 및 사용 조건 가이드

발급 후 `.env` 파일에 입력한다. `.env.example`을 복사해서 사용.

> **면책 고지**: 이 문서는 각 서비스의 공개 이용약관을 기반으로 작성됐으나, 약관은 수시로 변경된다.
> 상업적 사용 전에는 반드시 각 서비스의 최신 이용약관을 직접 확인할 것.

---

## API 신청 용도 입력 예시

> 각 서비스의 신청 양식에 그대로 붙여넣기 가능하도록 작성했다.
> 본인의 실제 목적에 맞게 수정하여 사용할 것.

### DART (한국어)
```
글로벌 매크로 퀀트 분석 시스템 개인 개발 프로젝트에 활용하고자 합니다.
국내 상장기업의 재무제표(손익계산서, 재무상태표) 및 공시 데이터를 수집하여
ROE, ROA, 부채비율 등 투자지표를 산출하고, 저평가 종목 스크리닝 및
포트폴리오 팩터 분석에 사용할 예정입니다.
수집된 데이터는 개인 투자 분석 및 비상업적 리서치 목적으로만 활용됩니다.
```

### ECOS 한국은행 (한국어)
```
개인 퀀트 투자 분석 도구 개발 목적으로 신청합니다.
기준금리, 소비자물가지수(CPI), GDP 성장률, M2 통화량 등 한국 거시경제 지표를
수집하여 매크로 경제 국면(성장/침체/인플레이션 등)을 분류하고,
국내 주식·채권 시장과의 상관관계 분석에 활용할 계획입니다.
개인 학습 및 투자 연구 목적이며, 데이터는 외부에 재배포하지 않습니다.
```

### 공공데이터포털 (한국어)
```
국내 금융 데이터 분석 파이프라인 개발을 위해 신청합니다.
상장법인 목록 및 기업 기본 정보를 활용하여 특정 시점 기준 유효 종목 유니버스를
구성하고, 백테스팅 분석 시 생존편향을 방지하는 데 사용할 예정입니다.
개인 투자 연구 목적이며 수집 데이터는 외부에 제공하지 않습니다.
```

### 국토교통부 실거래가 (한국어)
```
부동산 시장과 금융 자산 시장 간의 상관관계 분석을 위해 신청합니다.
아파트 실거래가 추이를 금리, 주가 등 금융 지표와 연계하여
매크로 투자 환경 분석에 보조 지표로 활용할 예정입니다.
개인 연구 목적이며 원본 데이터를 그대로 재배포하지 않습니다.
```

### FRED, St. Louis Fed (English)
```
I am developing a personal quantitative investment analysis system that collects
and processes global macroeconomic data. I plan to use FRED API to retrieve
key US economic indicators including CPI, GDP, unemployment rate, Federal Funds
Rate, Treasury yield spreads (10Y-2Y), and high-yield credit spreads.

This data will be used to classify macroeconomic regimes (reflation, overheat,
stagflation, deflation) and analyze correlations with equity and commodity markets.
The project is for personal investment research and non-commercial use.
```

### EIA, U.S. Energy Information Administration (English)
```
I am building a personal macro quantitative research tool that incorporates
commodity market data. I plan to use the EIA API to collect crude oil inventory
levels, U.S. production data, and natural gas prices as inputs for a global
macro regime classification model. This is for personal investment research only.
```

### CoinGecko (English)
```
I am developing a personal portfolio analysis tool for global macro and
cryptocurrency market research. I plan to use the CoinGecko API to retrieve
cryptocurrency market capitalization, Bitcoin dominance, and price data for
correlation analysis with traditional asset classes (equities, commodities, FX).
This is for personal investment research and educational purposes.
```

### NewsAPI (English)
```
I am building a personal financial sentiment analysis pipeline that monitors
global news headlines related to macroeconomic events, central bank policy,
and geopolitical developments. News data will be used for NLP-based sentiment
scoring to serve as a supplementary indicator in a quantitative investment
research system. For personal, non-commercial research use only.
```

### Reddit (앱 등록 시 description 입력란)
```
Personal financial data research tool. Collects and analyzes sentiment from
finance-related subreddits (r/investing, r/wallstreetbets, r/stocks) to build
a community sentiment index as a contrarian/momentum indicator for personal
investment research. Non-commercial, personal use only.
```

---

## 사용 조건 요약표

| API | 개인 사용 | 상업적 사용 | 데이터 재판매 | 출처 표기 |
|-----|---------|------------|-------------|---------|
| DART | ✅ 무료 | ✅ 가능 | ⚠️ 원출처 표기 시 가능 | 필수 |
| ECOS | ✅ 무료 | ✅ 가능 | ⚠️ 원출처 표기 시 가능 | 필수 |
| 공공데이터포털 | ✅ 무료 | ✅ 가능 (대부분) | ⚠️ 데이터별 확인 | 필수 |
| 국토교통부 | ✅ 무료 | ✅ 가능 | ⚠️ 원출처 표기 시 가능 | 필수 |
| FRED | ✅ 무료 | ✅ 가능 | ⚠️ 대량 재배포 별도 계약 | 권장 |
| EIA | ✅ 무료 | ✅ 가능 | ✅ 가능 (미정부 공개) | 권장 |
| CoinGecko Demo | ✅ 무료 | ⚠️ 소규모 가능 | ❌ 금지 | 필수 |
| NewsAPI | ✅ 무료 | ❌ 비상업적 only | ❌ 금지 | 필수 |
| Reddit | ✅ 무료 | ❌ 비상업적 only | ❌ 금지 | - |
| Whale Alert | ✅ 무료 (월 1,000건) | ❌ 유료 플랜 필요 | ❌ 금지 | 권장 |
| CryptoQuant | ✅ 무료 플랜 존재 | ❌ 유료 플랜 필요 | ❌ 금지 | 권장 |

---

## 블로그 게시 및 광고수익 가능 여부

### 핵심 원칙: 내부 사용 vs 외부 게시 구분

API 약관의 "비상업적 사용" 제한은 **데이터 재배포/재판매**를 막는 것이 주목적이다.
데이터를 수집해 분석한 결과물(차트, 지표, 인사이트)을 게시하는 것은 별개의 문제다.

```
[내부]  API 수집 → 분석/가공              ← 약관 제한과 무관. 모든 API 자유 활용
                        ↓
[외부]  분석 결과물만 게시 (블로그)        ← 이 단계만 조심하면 됨
```

| 게시 콘텐츠 유형 | 예시 | 판단 |
|--------------|------|------|
| **분석 지표** | 매크로 국면 차트, 팩터 점수 추이, 상관관계 히트맵 | ✅ 허용 |
| **파생 수익률** | 전략 백테스팅 수익률, 자산 간 상대 성과 | ✅ 허용 |
| **감성 지수** | Reddit/뉴스 기반 자체 계산 심리 점수 | ✅ 허용 |
| **가격 + 신호 오버레이** | KOSPI 차트 위에 국면/신호 표시 | ✅ 허용 (분석물로 인정) |
| **원시 가격 테이블** | API 응답을 그대로 표/CSV로 게시 | ❌ 피할 것 |
| **뉴스 원문 인용** | NewsAPI 기사 본문 복사 게시 | ❌ 저작권 문제 |
| **Reddit 게시물 원문** | 원문 스크린샷/인용 대량 게시 | ❌ 피할 것 |

### API별 블로그 광고수익 가능 여부 (분석 결과물 게시 기준)

| API | 내부 수집·분석 | 분석 결과물 블로그 게시 | 비고 |
|-----|------------|-------------------|------|
| **DART** | ✅ | ✅ | 출처 표기 필수 |
| **ECOS** | ✅ | ✅ | 출처 표기 필수 |
| **공공데이터포털** | ✅ | ✅ | 출처 표기 필수 |
| **국토교통부** | ✅ | ✅ | 출처 표기 필수 |
| **FRED** | ✅ | ✅ | 출처 표기 권장 |
| **EIA** | ✅ | ✅ | Public Domain, 제한 없음 |
| **pykrx (KRX)** | ✅ | ⚠️ 분석 결과는 가능, 시세 직접 게시는 그레이존 | yfinance 대체 권장 |
| **CoinGecko Demo** | ✅ | ✅ 분석 결과물 기준 허용 | 원시 가격 테이블 게시 금지 |
| **NewsAPI 무료** | ✅ | ✅ 감성 점수 등 가공 지표 | 뉴스 원문/헤드라인 직접 게시 금지 |
| **Reddit 무료** | ✅ | ✅ 감성 지수, 언급량 차트 | 게시물 원문 인용 금지 |
| **Whale Alert 무료** | ✅ | ✅ 유입/유출 추이, 신호 차트 | 원시 트랜잭션 목록 재배포 금지 |
| **CryptoQuant 무료** | ✅ | ✅ 거래소 유입/유출 차트 | 원시 데이터 재배포 금지, 출처 표기 권장 |

> **결론**: 이 프로젝트의 게시 방향(상관관계·국면·팩터·백테스팅 결과 차트)은
> 모든 API에서 **무료 플랜으로도 광고수익 블로그 게시 가능**하다.

### pykrx / KRX 데이터 보완 사항

KRX 원시 시세를 직접 게시하는 경우에만 그레이존이다.
분석 결과(상관관계, 수익률, 국면 오버레이)는 문제없다.
순수 가격 차트가 필요한 경우 **yfinance의 `^KS11`(KOSPI), `^KQ11`(KOSDAQ)** 으로 대체하면 깔끔하다.

### 출처 표기 예시 (블로그 하단 또는 차트 캡션)

```
데이터 출처: 금융감독원 DART, 한국은행 ECOS, Federal Reserve Bank of St. Louis (FRED),
Yahoo Finance, U.S. Energy Information Administration (EIA)
본 분석은 투자 조언이 아니며 투자 결과에 대한 책임은 본인에게 있습니다.
```

---

## 목차
1. [DART (전자공시)](#1-dart-전자공시)
2. [ECOS (한국은행)](#2-ecos-한국은행)
3. [공공데이터포털](#3-공공데이터포털)
4. [국토교통부 실거래가](#4-국토교통부-실거래가)
5. [FRED (미국 연준)](#5-fred-미국-연준)
6. [EIA (미국 에너지정보청)](#6-eia-미국-에너지정보청)
7. [CoinGecko](#7-coingecko)
8. [NewsAPI](#8-newsapi)
9. [Reddit](#9-reddit)
10. [Whale Alert](#10-whale-alert)
11. [CryptoQuant](#11-cryptoquant)

---

## 1. DART (전자공시)

**용도**: 재무제표, 배당공시, 사업보고서 (dart-fss)  
**무료**: 무제한 | **발급 소요**: 즉시

### 사용 조건
- **라이선스**: 공공누리 제1유형 (출처표시)
- **개인 사용**: 제한 없음
- **상업적 사용**: 허용. 서비스/제품에 활용 가능
- **데이터 재배포**: 원출처(금융감독원 DART) 표기 시 가능
- **금지 사항**: DART 데이터를 유사 공시 서비스로 그대로 재판매하는 행위
- **약관 확인**: https://opendart.fss.or.kr/intro/about.do

### 발급 방법
1. https://opendart.fss.or.kr 접속
2. 우측 상단 **인증키 신청/관리** 클릭
3. 회원가입 (이메일 인증)
4. 로그인 후 **인증키 신청** → 용도 입력 후 즉시 발급

```env
DART_API_KEY=your_40char_key_here
```

> 일 10,000건 제한. 재무제표 전체 수집 시 여러 날로 나눠 실행 권장.

---

## 2. ECOS (한국은행)

**용도**: 기준금리, M2, GDP, CPI (한국)  
**무료**: 무제한 | **발급 소요**: 즉시

### 사용 조건
- **라이선스**: 공공누리 제1유형 (출처표시)
- **개인 사용**: 제한 없음
- **상업적 사용**: 허용. 출처(한국은행 경제통계시스템) 표기 조건으로 상업적 활용 가능
- **데이터 재배포**: 원출처 표기 시 가능
- **금지 사항**: 한국은행의 공식 입장인 것처럼 오해를 유발하는 방식으로 사용하는 행위
- **약관 확인**: https://ecos.bok.or.kr (이용 가이드 > 이용 약관)

### 발급 방법
1. https://ecos.bok.or.kr 접속
2. 회원가입 → 로그인
3. **OPEN API** → **인증키 신청** → 즉시 발급

```env
ECOS_API_KEY=your_key_here
```

> 일 10,000건 제한. 주요 통계 코드: 722Y001(기준금리), 901Y009(CPI), 200Y001(GDP).

---

## 3. 공공데이터포털

**용도**: 상장법인 목록, 기업공시 정보  
**무료**: 무제한 | **발급 소요**: 즉시~1 영업일

### 사용 조건
- **라이선스**: 데이터별로 공공누리 유형이 다름 (각 API 상세 페이지에서 확인)
  - 제1유형 (출처표시): 상업적 사용 허용 — 대부분 해당
  - 제2유형 (출처표시+상업금지): 상업적 사용 **불가**
  - 제4유형 (출처표시+변경금지): 원본 그대로만 사용 가능
- **개인 사용**: 제한 없음
- **상업적 사용**: 제1유형 데이터는 허용. 활용 전 각 API의 라이선스 유형 반드시 확인
- **데이터 재배포**: 유형에 따라 다름. 원출처 표기 필수
- **약관 확인**: https://data.go.kr (이용약관, 각 API 상세 페이지 라이선스 표기)

### 발급 방법
1. https://data.go.kr 접속 → 회원가입 → 로그인
2. 원하는 API 검색 → **활용신청**
3. **마이페이지** → **오픈API** → **인증키** 확인

```env
DATA_GO_KR_API_KEY=your_key_here
```

> 하나의 키로 공공데이터포털 내 모든 API 사용 가능.

---

## 4. 국토교통부 실거래가

**용도**: 아파트/토지 실거래가  
**무료**: 무제한 | **발급 소요**: 즉시

### 사용 조건
- **라이선스**: 공공누리 제1유형 (출처표시)
- **개인/상업적 사용**: 모두 허용. 출처(국토교통부) 표기 필수
- **데이터 재배포**: 원출처 표기 시 가능
- **금지 사항**: 국토교통부 공식 서비스인 것처럼 오해를 유발하는 방식으로 사용
- **약관 확인**: https://data.go.kr (국토교통부 실거래가 API 상세 페이지)

### 발급 방법
- 공공데이터포털에서 **국토교통부 실거래가** 검색 후 활용신청
- 키는 `DATA_GO_KR_API_KEY`와 동일 키 사용 (별도 발급 불필요한 경우 대부분)

```env
MOLIT_API_KEY=your_key_here
```

---

## 5. FRED (미국 연준)

**용도**: 미국 CPI, GDP, 금리, 실업률, M2 등 거시지표  
**무료**: 무제한 | **발급 소요**: 즉시

### 사용 조건
- **개인 사용**: 제한 없음
- **상업적 사용**: 허용. 내부 분석, 리포트, 서비스에 활용 가능
- **데이터 재배포**:
  - 소량 인용/시각화: 출처(Federal Reserve Bank of St. Louis) 표기 시 허용
  - 대량 재배포 또는 경쟁 데이터 서비스 구축: **별도 라이선스 계약 필요**
- **출처 표기**: 권장 형식 — `Source: Federal Reserve Bank of St. Louis (FRED)`
- **주의**: FRED 데이터 자체는 공공 도메인이나, 일부 시리즈는 제3자 제공 데이터로 별도 약관 적용 (각 시리즈 페이지에서 "Source" 확인)
- **약관 확인**: https://fred.stlouisfed.org/legal

### 발급 방법
1. https://fred.stlouisfed.org → **My Account** → **Create an Account**
2. 로그인 후 **My Account** → **API Keys** → **Request API Key**
3. 용도 입력 → 즉시 발급

```env
FRED_API_KEY=your_32char_lowercase_key
```

> 키는 반드시 32자 소문자 영숫자. 일 120,000 요청 제한 (사실상 무제한).

---

## 6. EIA (미국 에너지정보청)

**용도**: 원유재고, 원유생산량, 천연가스 가격  
**무료**: 무제한 | **발급 소요**: 수분 내

### 사용 조건
- **라이선스**: 미국 연방정부 공개 데이터 (Public Domain)
- **개인/상업적 사용**: 모두 허용. 제한 없음
- **데이터 재배포/재판매**: 허용. 미국 정부 데이터는 저작권 없음
- **출처 표기**: 법적 의무는 없으나 `Source: U.S. Energy Information Administration (EIA)` 표기 권장
- **약관 확인**: https://www.eia.gov/about/copyrights_reuse.php

### 발급 방법
1. https://www.eia.gov/opendata/register.php 접속
2. 이름, 이메일, 조직 입력 → **Register**
3. 이메일로 발송된 API 키 확인 (수분 내)

```env
EIA_API_KEY=your_key_here
```

---

## 7. CoinGecko

**용도**: 암호화폐 시총, 도미넌스, 메타데이터  
**무료 (Demo)**: 분당 30 요청 | **발급 소요**: 즉시

### 사용 조건

- **Demo (무료) 플랜**: 분당 30 요청. 개인 및 소규모 내부 분석 용도 허용
- **금지 사항**: CoinGecko 데이터를 제3자에게 재판매하거나 유사 데이터 서비스 구축에 사용하는 행위
- **약관 확인**: https://www.coingecko.com/en/api/pricing (Terms of Service 링크 포함)

### 발급 방법
1. https://www.coingecko.com/en/api 접속 → **Get Your API Key** → 회원가입
2. **Developer Dashboard** → **Add New Key** → 즉시 발급

```env
COINGECKO_API_KEY=CG-your_demo_key
```

---

## 8. NewsAPI

**용도**: 글로벌 뉴스 헤드라인 수집  
**무료 (Developer)**: 월 100 요청 | **발급 소요**: 즉시

### 사용 조건

- **무료 Developer 키**: 개인 비상업적 사용 허용
- **뉴스 원문 재배포 금지**: 헤드라인/메타데이터만 활용 가능. 기사 원문 복사 금지
- **감성 분석 목적**: 제목/요약을 내부에서 분석해 감성 점수로 가공하는 것은 허용 범위 내
- **약관 확인**: https://newsapi.org/terms

### 발급 방법
1. https://newsapi.org → **Get API Key** → 회원가입 → 이메일 인증

```env
NEWS_API_KEY=your_32char_key
```

---

## 9. Reddit

**용도**: 커뮤니티 감성 분석 (r/wallstreetbets, r/investing 등)  
**무료**: 소규모 비상업적 | **발급 소요**: 즉시

### 사용 조건

> Reddit은 2023년 6월 API 정책을 대폭 변경했다. 상업적 사용 전 반드시 최신 약관 확인 필요.

- **무료 사용**: 개인 비상업적, 연구/학술 목적 허용 (일 100,000 요청 이하)
- **콘텐츠 저작권**: 게시물 원문 그대로의 재배포 금지. 감성 점수·언급량 등 가공 지표는 허용
- **약관 확인**: https://www.redditinc.com/policies/data-api-terms

### 발급 방법
1. https://www.reddit.com/prefs/apps 접속
2. **create another app** → type: **script** 선택
3. redirect uri: `http://localhost:8080`
4. **create app** → CLIENT_ID (앱 이름 아래 짧은 문자열), CLIENT_SECRET (secret 항목)

```env
REDDIT_CLIENT_ID=your_14char_client_id
REDDIT_CLIENT_SECRET=your_27char_secret
REDDIT_USER_AGENT=financial-data-bot/1.0 by u/your_username
```

> `REDDIT_USER_AGENT` 형식: `앱이름/버전 by u/레딧유저명` — Reddit 정책상 필수

---

## 10. Whale Alert

**용도**: 대형 온체인 트랜잭션 알림 (≥100만 USD BTC/ETH/USDT 이동)  
**무료 (Starter)**: 월 1,000건 | **발급 소요**: 즉시

### 서비스 개요

Whale Alert은 블록체인 상의 대형 자금 이동을 실시간으로 탐지한다.  
거래소 입출금, 지갑 간 이동, 스테이블코인 민팅 등을 포함하며  
"고래(whale)"의 매도 준비 여부를 판단하는 핵심 온체인 지표로 활용된다.

| 플랜 | 요청 수 | 조회 가능 기간 | 가격 |
|------|---------|--------------|------|
| Starter (무료) | 월 1,000건 | 최근 7일 | 무료 |
| Basic | 월 10,000건 | 최근 30일 | 약 $10/월 |
| Professional | 무제한 | 최대 5년 | 별도 문의 |

### 사용 조건

- **개인 비상업적 사용**: 제한 없음
- **상업적 사용**: 유료 플랜 필요
- **데이터 재배포**: 원시 트랜잭션 데이터 재판매 금지. 분석 결과물 게시는 가능
- **약관 확인**: https://whale-alert.io/terms

### 발급 방법

1. https://whale-alert.io 접속 → 우측 상단 **Sign Up**
2. 이메일/구글 계정으로 회원가입 → 이메일 인증
3. 로그인 후 **Dashboard** → **API** 탭 → **API Key** 확인 (즉시 발급)

```env
WHALE_ALERT_API_KEY=your_key_here
```

### 무료 플랜 활용 전략

월 1,000건 제한을 효율적으로 사용하는 방법:

```
- 일 1회 수집 → 하루 약 33건 사용 가능
- min_value=1,000,000 (100만 USD) 필터 적용 → 노이즈 제거
- 7일 이내 데이터만 조회 가능하므로 매일 실행 필수
- 캐시 활용: 당일 이미 수집된 데이터는 API 호출 생략
```

### API 응답 예시

```json
{
  "blockchain": "bitcoin",
  "symbol": "BTC",
  "from": {"owner": "unknown", "owner_type": "unknown"},
  "to": {"owner": "Binance", "owner_type": "exchange"},
  "amount": 1500.0,
  "amount_usd": 95000000,
  "timestamp": 1712000000
}
```

**트랜잭션 유형 해석:**
- `unknown → exchange`: 개인 지갑 → 거래소 유입 → **단기 매도 신호** (약세)
- `exchange → unknown`: 거래소 → 개인 지갑 이탈 → **장기 보유 신호** (강세)
- `exchange → exchange`: 거래소 간 이동 → 유동성 이동 (중립)

---

## 11. CryptoQuant

**용도**: 거래소 BTC/ETH 유입/유출, 고래 트랜잭션, 펀딩비, 미결제약정 등 온체인 지표  
**무료 플랜**: 일부 지표 일별 데이터 | **발급 소요**: 즉시

> **Glassnode 대체**: Glassnode API는 Professional Plan($999/월) 전용이라 무료 사용 불가.  
> CryptoQuant은 무료 플랜에서 거래소 유입/유출 등 핵심 온체인 지표를 제공한다.

### 서비스 개요

CryptoQuant은 거래소 온체인 데이터 분석에 특화된 플랫폼으로,  
고래의 거래소 입출금 동향, 펀딩비, 미결제약정 등 시장 심리 지표를 제공한다.

| 플랜 | 접근 지표 | 데이터 주기 | 가격 |
|------|---------|-----------|------|
| Free | 주요 온체인 지표 (제한적) | 일별 | 무료 |
| Premium | 200+ 지표 | 1시간 | 약 $29~49/월 |
| Enterprise | 전체 + 알림 | 실시간 | 별도 문의 |

### 무료 플랜에서 수집 가능한 주요 지표

| 지표 | API 엔드포인트 | 해석 |
|------|--------------|------|
| 거래소 BTC 유입 | `btc/exchange-flows/inflow` | 거래소로 들어온 BTC → 매도 압력 |
| 거래소 BTC 유출 | `btc/exchange-flows/outflow` | 거래소에서 나간 BTC → 장기 보유 |
| 거래소 순유출 | 유출 - 유입 계산 | 양수 = 공급 감소 → 강세 신호 |

> 거래소 유입 급증 → 고래가 매도 준비 중 (단기 하락 압력)  
> 거래소 유출 급증 → 고래가 콜드월렛으로 이동 (장기 보유 의사)

### 사용 조건

- **무료 사용**: 개인 비상업적 사용 허용
- **상업적 사용**: 유료 플랜 필요. 분석 결과물 블로그 게시는 출처 표기 시 허용
- **데이터 재배포**: 원시 데이터 재판매/재배포 금지. 차트·분석물 게시 가능
- **약관 확인**: https://cryptoquant.com/terms

### 발급 방법

1. https://cryptoquant.com 접속 → **Sign Up** (우측 상단)
2. 이메일 또는 구글 계정으로 회원가입 → 이메일 인증
3. 로그인 후 우측 상단 프로필 → **Account Settings**
4. **API** 탭 → **Create New API Key** → 즉시 발급

```env
CRYPTOQUANT_API_KEY=your_bearer_token_here
```

> 발급된 키는 Bearer Token 방식으로 사용:  
> `Authorization: Bearer YOUR_API_KEY`

### API 요청 예시

```bash
# 거래소 BTC 유입 (전체 거래소 합산, 일별)
curl -H "Authorization: Bearer YOUR_KEY" \
  "https://api.cryptoquant.com/v1/btc/exchange-flows/inflow?window=day&exchange=all&limit=30"
```

응답 형식:
```json
{
  "result": {
    "data": [
      {"date": "2024-04-10", "inflow_total": 23456.78},
      {"date": "2024-04-11", "inflow_total": 18234.56}
    ]
  }
}
```

### 무료 플랜 활용 전략

```
- 일 1회 수집으로 일별 트렌드 파악
- exchange=all (전체 거래소 합산) 사용 → 요청 수 최소화
- 캐싱 필수: 동일 날짜 데이터는 재수집 생략
- 무료 플랜 요청 한도 초과 시 429 응답 → 다음날 재수집
```

### 신청 용도 입력 예시 (English)

```
I am building a personal quantitative cryptocurrency analysis system.
I plan to use CryptoQuant API to collect Bitcoin exchange inflow/outflow data
as on-chain indicators for identifying whale accumulation or distribution patterns.
This is for personal investment research and non-commercial use only.
```

---

## 키 입력 방법

`.env`에 주석 없이 값만 입력:

```bash
# 잘못된 입력 (주석이 값으로 인식됨)
FRED_API_KEY=           # https://fred.stlouisfed.org

# 올바른 입력
FRED_API_KEY=abc123def456...
```

입력 후 동작 확인:
```bash
python -c "from config import FRED_API_KEY; print(bool(FRED_API_KEY))"
# True 출력되면 정상
```

---

## 우선순위 추천

| 우선순위 | API | 이유 |
|---------|-----|------|
| 필수 | DART | 국내 재무제표, 상업적 가능, 무료 즉시 |
| 필수 | FRED | 미국 거시지표 핵심, 상업적 가능, 무료 즉시 |
| 권장 | ECOS | 한국 금리/CPI, 상업적 가능, 무료 즉시 |
| 권장 | 공공데이터포털 | 상장법인 목록, 대부분 상업적 가능 |
| 권장 | EIA | 원유 데이터, 완전 공개, 제한 없음 |
| 권장 | CoinGecko | 무료 Demo 키로 사용 가능 |
| 참고 | NewsAPI | 내부 감성 분석용. 원문 재배포 금지 |
| 참고 | Reddit | 내부 감성 분석용. 게시물 원문 재배포 금지 |
| 권장 | Whale Alert | 고래 매도 압력 신호. 무료 월 1,000건으로 일 1회 수집 가능 |
| 권장 | CryptoQuant | 거래소 BTC 유입/유출 핵심 지표. 무료 플랜으로 일별 데이터 수집 가능 |
