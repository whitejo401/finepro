# PLAN — saving (예금·적금·금융상품·ETF)

## 개요
금융감독원 finlife API를 핵심 소스로 예금·적금·ISA·연금저축 상품 비교를 제공한다.
invest 그룹이 시장 분석에 집중한다면, saving은 상품 선택·비교·추천에 특화된다.

---

## 파일 구조

```
api/routers/saving/
├── __init__.py
├── deposit.py      # /saving/deposit, /saving/savings, /saving/special
├── pension.py      # /saving/isa, /saving/pension
├── etf.py          # /saving/etf (invest의 etf와 관점 차이: 배당·장기 중심)
└── recommend.py    # /saving/recommend, /saving/protection
```

---

## 데이터 소스 상세

### 금융감독원 finlife
- **Base URL**: `https://finlife.fss.or.kr/finlifeapi/`
- **인증**: `FINLIFE_API_KEY`
- **주요 API**:
  - `depositProductsSearch` — 예금 상품
  - `savingProductsSearch` — 적금 상품
  - `annuitySavingProductsSearch` — 연금저축 상품
  - `iraProductsSearch` — IRP 상품
- **업데이트 주기**: 주 1~2회 (금리 변동 시 즉시)

### 예금보험공사
- **Base URL**: `https://www.data.go.kr/api/`
- **인증**: `DATA_GO_KR_API_KEY`
- **제공**: 금융기관별 예금자보호 여부, 영업정지 정보

### KRX (pykrx)
- ETF NAV·괴리율·배당이력 (invest와 동일 소스, 캐시 공유)

---

## 엔드포인트 상세

### GET /api/v1/saving/deposit
- **Query params**:
  - `bank` (은행명, 기본 `전체`)
  - `term` (개월, `3`|`6`|`12`|`24`|`36`, 기본 `12`)
  - `amount` (가입금액 만원, 선택 — 우대금리 필터용)
- **캐시**: 1시간
- **로직**: finlife `depositProductsSearch` → 최고금리 내림차순
- **응답**:
```json
{
  "term": 12,
  "items": [
    {
      "bank": "OO저축은행",
      "product": "OO정기예금",
      "rate_basic": 3.80,
      "rate_max": 4.10,
      "conditions": "인터넷뱅킹 가입 시 +0.3%",
      "min_amount": 100,
      "protected": true
    }
  ]
}
```

### GET /api/v1/saving/savings
- **Query params**: `bank`, `term`, `type` (`정액적립식`|`자유적립식`)
- **캐시**: 1시간
- **응답**: 동일 구조

### GET /api/v1/saving/special
- **캐시**: 30분
- **로직**: 전체 예금·적금 조회 → 기준금리 + 1.5% 이상 상품 필터 (특판 추정)
- **응답**: `[{bank, product, rate_max, end_date(추정), type}]`

### GET /api/v1/saving/isa
- **Query params**: `type` (`중개형`|`신탁형`|`서민형`)
- **캐시**: 3시간
- **로직**: finlife ISA 관련 상품 + 세제혜택 정보 정적 텍스트 병합
- **응답**:
```json
{
  "type": "중개형",
  "tax_benefit": "이자·배당 200만원까지 비과세, 초과분 9.9% 분리과세",
  "annual_limit": 2000,
  "products": [...]
}
```

### GET /api/v1/saving/pension
- **Query params**: `type` (`연금저축펀드`|`연금저축보험`|`IRP`)
- **캐시**: 3시간
- **응답**: `[{company, product, yield_1y, yield_3y, fee_pct, tax_benefit}]`

### GET /api/v1/saving/etf
- **Query params**:
  - `category` (`국내주식`|`해외주식`|`채권`|`배당`|`리츠`|`원자재`)
  - `sort` (`dividend_yield`|`volume`|`yield_1y`, 기본 `volume`)
- **캐시**: 10분
- **응답**: `[{ticker, name, price, nav, gap_pct, dividend_yield, yield_ytd, aum_bn}]`

### GET /api/v1/saving/etf/{ticker}
- **캐시**: 5분
- **응답**:
```json
{
  "ticker": "069500",
  "name": "KODEX 200",
  "price": 33500,
  "nav": 33480,
  "gap_pct": 0.06,
  "expense_ratio": 0.15,
  "dividend_yield": 1.8,
  "top_holdings": [{"name":"삼성전자","weight_pct":25.1}],
  "dividend_history": [{"date":"2026-01","amount":120}]
}
```

### GET /api/v1/saving/etf/dividend
- **캐시**: 1시간
- **로직**: 배당 ETF 전체 → 배당률 내림차순
- **응답**: `[{ticker, name, dividend_yield, frequency, next_ex_date}]`

### GET /api/v1/saving/etf/compare
- **Query params**: `tickers` (쉼표 구분, 최대 5개)
- **캐시**: 10분
- **응답**: 비교 테이블 `{tickers: [...], metrics: {expense_ratio, dividend_yield, yield_1y, gap_pct}}`

### GET /api/v1/saving/recommend
- **Query params**:
  - `amount` (가입금액 만원)
  - `term` (목표 기간 개월)
  - `risk` (`낮음`|`보통`|`높음`)
- **캐시**: 1시간
- **로직**:
  - `낮음` → 예금 + 채권 ETF
  - `보통` → 적금 + 배당 ETF
  - `높음` → 성장주 ETF + 연금저축펀드
- **응답**: `{recommended: [{type, product, expected_yield, rationale}]}`

### GET /api/v1/saving/protection
- **Query params**: `bank` (금융기관명)
- **캐시**: 24시간
- **소스**: 예금보험공사
- **응답**: `{bank, protected: true/false, limit: 50000000, note: "저축은행도 1인당 5천만원 보호"}`

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| finlife API 키 없음 | 503 + "금융상품 API 키 미설정" |
| ETF 티커 없음 | 404 |
| compare tickers 6개 이상 | 422 "최대 5개" |

---

## 구현 순서

1. `deposit.py` — 예금·적금 기본 조회
2. `deposit.py` — special (특판 필터 로직)
3. `etf.py` — pykrx 재활용 (목록·상세·배당)
4. `etf.py` — compare
5. `pension.py` — ISA, 연금저축
6. `recommend.py` — 추천 로직
7. `recommend.py` — protection

---

## 의존성
- `pykrx` (기존)
- `requests` (기존)
- 환경변수: `FINLIFE_API_KEY`, `DATA_GO_KR_API_KEY`
