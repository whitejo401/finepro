# API 키 발급 가이드

발급 후 `.env` 파일에 입력한다. `.env.example`을 복사해서 사용.

---

## 목차
1. [DART (전자공시)](#1-dart-전자공시)
2. [한국투자증권 KIS](#2-한국투자증권-kis)
3. [ECOS (한국은행)](#3-ecos-한국은행)
4. [공공데이터포털](#4-공공데이터포털)
5. [국토교통부 실거래가](#5-국토교통부-실거래가)
6. [FRED (미국 연준)](#6-fred-미국-연준)
7. [EIA (미국 에너지정보청)](#7-eia-미국-에너지정보청)
8. [CoinGecko](#8-coingecko)
9. [Glassnode](#9-glassnode)
10. [NewsAPI](#10-newsapi)
11. [Reddit](#11-reddit)

---

## 1. DART (전자공시)

**용도**: 재무제표, 배당공시, 사업보고서 (dart-fss)  
**무료**: 무제한  
**발급 소요**: 즉시

### 발급 방법
1. https://opendart.fss.or.kr 접속
2. 우측 상단 **인증키 신청/관리** 클릭
3. 회원가입 (이메일 인증)
4. 로그인 후 **인증키 신청** → 용도 입력 (예: 개인 투자 분석)
5. 신청 즉시 발급

```env
DART_API_KEY=your_40char_key_here
```

> 일 10,000건 제한. 재무제표 전체 수집 시 여러 날로 나눠 실행 권장.

---

## 2. 한국투자증권 KIS

**용도**: 실시간 시세, 분봉 데이터  
**무료**: 계좌 개설 필수 (모의투자 계좌 가능)  
**발급 소요**: 1~2 영업일

### 발급 방법
1. https://apiportal.koreainvestment.com 접속
2. 한국투자증권 계좌 없으면 먼저 개설 (비대면 가능)
3. 사이트 로그인 후 **앱 등록** → 앱 이름/설명 입력
4. **모의투자** 선택 (실전은 계좌 심사 필요)
5. APP KEY / APP SECRET 발급

```env
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
```

> 현재 프로젝트는 EOD 데이터만 사용하므로 KIS는 선택사항. pykrx로 대체 가능.

---

## 3. ECOS (한국은행)

**용도**: 기준금리, M2, GDP, CPI (한국)  
**무료**: 무제한  
**발급 소요**: 즉시

### 발급 방법
1. https://ecos.bok.or.kr 접속
2. 우측 상단 **로그인** → **회원가입**
3. 로그인 후 상단 메뉴 **OPEN API** → **인증키 신청**
4. 이용 목적 입력 후 신청 → 즉시 발급

```env
ECOS_API_KEY=your_key_here
```

> 일 10,000건 제한. 주요 통계 코드: 722Y001(기준금리), 901Y009(CPI), 200Y001(GDP).

---

## 4. 공공데이터포털

**용도**: 상장법인 목록, 기업공시 정보  
**무료**: 무제한  
**발급 소요**: 즉시~1 영업일

### 발급 방법
1. https://data.go.kr 접속
2. 회원가입 → 로그인
3. 원하는 API 검색 (예: "상장법인목록") → **활용신청**
4. 신청 목적 입력 → 자동 승인 (대부분 즉시)
5. **마이페이지** → **오픈API** → **인증키** 확인

```env
DATA_GO_KR_API_KEY=your_key_here
```

> 하나의 키로 공공데이터포털 내 모든 API 사용 가능.

---

## 5. 국토교통부 실거래가

**용도**: 아파트/토지 실거래가  
**무료**: 무제한  
**발급 소요**: 공공데이터포털과 동일

### 발급 방법
- 공공데이터포털(data.go.kr)에서 **국토교통부 실거래가** 검색 후 활용신청
- 발급된 키는 `DATA_GO_KR_API_KEY`와 동일 (별도 키 불필요한 경우도 있음)
- API별로 별도 키가 필요한 경우 각 API 상세 페이지에서 신청

```env
MOLIT_API_KEY=your_key_here
```

---

## 6. FRED (미국 연준)

**용도**: 미국 CPI, GDP, 금리, 실업률, M2 등 거시지표  
**무료**: 무제한  
**발급 소요**: 즉시

### 발급 방법
1. https://fred.stlouisfed.org 접속
2. 우측 상단 **My Account** → **Create an Account** (이메일 인증)
3. 로그인 후 **My Account** → **API Keys** → **Request API Key**
4. 용도 입력 (예: Personal research and investment analysis) → 즉시 발급

```env
FRED_API_KEY=your_32char_lowercase_key
```

> 키는 반드시 32자 소문자 영숫자. 일 120,000 요청 제한 (사실상 무제한).

---

## 7. EIA (미국 에너지정보청)

**용도**: 원유재고, 원유생산량, 천연가스 가격  
**무료**: 무제한  
**발급 소요**: 즉시

### 발급 방법
1. https://www.eia.gov/opendata/register.php 접속
2. 이름, 이메일, 조직 입력 → **Register** 클릭
3. 이메일로 발송된 API 키 확인 (수분 내)

```env
EIA_API_KEY=your_key_here
```

---

## 8. CoinGecko

**용도**: 암호화폐 시총, 도미넌스, 메타데이터  
**무료 (Demo)**: 분당 30 요청  
**발급 소요**: 즉시

### 발급 방법 (무료 Demo 키)
1. https://www.coingecko.com/en/api 접속
2. **Get Your API Key** → 회원가입
3. 로그인 후 **Developer Dashboard** → **Add New Key**
4. 키 이름 입력 → 즉시 발급

```env
COINGECKO_API_KEY=CG-your_demo_key
```

> 무료 Demo 키로 대부분 기능 사용 가능. Pro는 유료($129/월~).  
> API 키 없이도 공개 엔드포인트 사용 가능 (분당 10-30 요청).

---

## 9. Glassnode

**용도**: 온체인 데이터 (활성주소, 고래 움직임 등)  
**무료 (Starter)**: 일부 지표만 제공  
**발급 소요**: 즉시

### 발급 방법
1. https://glassnode.com 접속
2. **Sign Up** → 이메일 인증
3. 로그인 후 우측 상단 계정 → **API** → API 키 확인

```env
GLASSNODE_API_KEY=your_key_here
```

> 무료 티어 제한: 주요 온체인 지표 약 20개, 일간 데이터만.  
> 고급 지표(SOPR, NUPL 등)는 유료 플랜($39/월~) 필요.

---

## 10. NewsAPI

**용도**: 글로벌 뉴스 헤드라인 수집  
**무료 (Developer)**: 월 100 요청 (개인 비상업용)  
**발급 소요**: 즉시

### 발급 방법
1. https://newsapi.org 접속
2. **Get API Key** → 이름, 이메일, 비밀번호 입력
3. 이메일 인증 → 즉시 발급

```env
NEWS_API_KEY=your_32char_key
```

> 무료 티어: 지난 한 달 뉴스만, 실시간 불가.  
> 상업적 사용 또는 더 많은 요청은 유료 플랜($449/월~).

---

## 11. Reddit

**용도**: 커뮤니티 감성 분석 (r/wallstreetbets, r/investing 등)  
**무료**: 무제한  
**발급 소요**: 즉시

### 발급 방법
1. https://www.reddit.com 계정 생성 (이미 있으면 로그인)
2. https://www.reddit.com/prefs/apps 접속
3. 페이지 하단 **create another app** 클릭
4. 입력:
   - name: `financial-data-bot` (임의 이름)
   - type: **script** 선택
   - description: (임의)
   - redirect uri: `http://localhost:8080`
5. **create app** 클릭
6. 생성된 앱에서:
   - `CLIENT_ID`: 앱 이름 아래 짧은 문자열
   - `CLIENT_SECRET`: **secret** 항목

```env
REDDIT_CLIENT_ID=your_14char_client_id
REDDIT_CLIENT_SECRET=your_27char_secret
REDDIT_USER_AGENT=financial-data-bot/1.0 by u/your_username
```

> `REDDIT_USER_AGENT` 형식 규칙: `앱이름/버전 by u/레딧유저명`  
> 분당 60 요청 제한.

---

## 키 입력 방법

`.env.example`을 `.env`로 복사 후 주석 없이 값만 입력:

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

API 키 없이도 동작하는 수집기가 있으므로 단계적으로 진행 권장:

| 우선순위 | API | 이유 |
|---------|-----|------|
| 필수 | DART | 국내 재무제표 (무료, 즉시) |
| 필수 | FRED | 미국 거시지표 핵심 (무료, 즉시) |
| 권장 | ECOS | 한국 금리/CPI (무료, 즉시) |
| 권장 | CoinGecko | 암호화폐 (무료 Demo) |
| 선택 | NewsAPI | 뉴스 감성 |
| 선택 | Reddit | 커뮤니티 감성 |
| 선택 | Glassnode | 온체인 (무료 제한 큼) |
| 선택 | KIS | pykrx로 대체 가능 |
| 선택 | EIA | 원유 상세 데이터 |
