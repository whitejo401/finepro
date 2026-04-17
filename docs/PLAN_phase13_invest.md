# PLAN — invest (투자 정보)

## 개요
KRX(pykrx)·DART(dart-fss)·KOFIA·ECOS 등 기존 수집기를 재활용해 국내 투자 정보 API를 구성한다.
finance 그룹이 글로벌 매크로 신호에 집중하는 반면, invest는 개별 종목·공모주·펀드·금리에 집중한다.

---

## 파일 구조

```
api/routers/invest/
├── __init__.py
├── stock.py        # /invest/stock/snapshot, /{ticker}, /ipo
├── fund.py         # /invest/fund
├── etf.py          # /invest/etf
└── rate.py         # /invest/rate/deposit, /bond, /base
```

---

## 데이터 소스 상세

### KRX (pykrx)
- 시장 전체 현황, 개별 종목 주가·PER·PBR·수급
- 이미 `collectors/kr/stock.py`에서 사용 중 → 재활용

### DART (dart-fss)
- 개별 종목 재무제표, 최신 공시
- 이미 `collectors/kr/financials.py`에서 사용 중 → 재활용

### KOFIA (금융투자협회)
- **Base URL**: `http://dis.kofia.or.kr/`
- **인증**: 무료 (키 불필요)
- **제공**: 펀드 수익률, 설정액, 운용사 정보

### 금융감독원 금융상품통합비교 (finlife)
- **Base URL**: `https://finlife.fss.or.kr/finlifeapi/`
- **인증**: `FINLIFE_API_KEY`
- **제공**: 예금·적금·대출 금리 상품

### 한국수출입은행
- **Base URL**: `https://www.koreaexim.go.kr/site/program/financial/exchangeJSON`
- **인증**: `apiKey`
- **제공**: 국제금리 (SOFR, 연준금리 등)

---

## 엔드포인트 상세

### GET /api/v1/invest/stock/snapshot
- **Query params**: `market` (`KOSPI`|`KOSDAQ`, 기본 `KOSPI`)
- **캐시**: 5분
- **로직**: pykrx `stock.get_market_ohlcv_by_ticker()` 당일 데이터
- **응답**:
```json
{
  "market": "KOSPI",
  "date": "2026-04-15",
  "index": 2650.3,
  "index_change_pct": 0.43,
  "advance": 412,
  "decline": 285,
  "unchanged": 63,
  "volume": 450000000,
  "top_gainers": [{"ticker":"005930","name":"삼성전자","change_pct":3.2}],
  "top_losers": [...]
}
```

### GET /api/v1/invest/stock/{ticker}
- **Path param**: `ticker` (6자리 종목코드)
- **캐시**: 10분
- **로직**: pykrx 주가·수급 + DART 최신 공시 3건 + 재무 요약 병합
- **응답**:
```json
{
  "ticker": "005930",
  "name": "삼성전자",
  "price": 75000,
  "change_pct": 1.2,
  "per": 14.2,
  "pbr": 1.3,
  "foreign_net": 125000000,
  "institution_net": -50000000,
  "latest_disclosures": [{"title":"분기보고서","date":"2026-03-30","url":"..."}],
  "financials": {"revenue": 280e12, "op_profit": 35e12, "net_profit": 28e12}
}
```

### GET /api/v1/invest/stock/ipo
- **캐시**: 1시간
- **소스**: DART 증권신고서 조회 + KRX 신규상장 일정
- **응답**:
```json
[
  {
    "name": "OO바이오",
    "demand_forecast": {"start":"2026-04-20","end":"2026-04-21","competition_ratio": 850},
    "subscription": {"start":"2026-04-24","end":"2026-04-25"},
    "listing_date": "2026-04-30",
    "offering_price": 15000,
    "market": "KOSDAQ"
  }
]
```

### GET /api/v1/invest/fund
- **Query params**: `type` (`국내주식형`|`해외주식형`|`채권형`|`혼합형`|`MMF`), `sort` (`yield_1y`|`aum`, 기본 `yield_1y`)
- **캐시**: 1시간
- **응답**: `[{name, company, aum_bn, yield_1m, yield_3m, yield_1y, fee_pct}]`

### GET /api/v1/invest/etf
- **Query params**: `category` (선택), `sort` (`volume`|`yield_1m`, 기본 `volume`)
- **캐시**: 10분
- **응답**: `[{ticker, name, price, nav, spread_pct, volume, yield_ytd}]`

### GET /api/v1/invest/rate/deposit
- **Query params**: `bank` (기본 `전체`), `term` (개월, 기본 12)
- **캐시**: 3시간
- **소스**: finlife `depositProductsSearch`
- **응답**: 금리 내림차순 정렬 `[{bank, product_name, rate_max, rate_min, conditions}]`

### GET /api/v1/invest/rate/bond
- **캐시**: 1시간
- **소스**: ECOS 국채·회사채·CD금리
- **응답**: `{gov_3y, gov_5y, gov_10y, corp_aa, corp_bbb, cd_91d, date}`

### GET /api/v1/invest/rate/base
- **캐시**: 6시간
- **소스**: ECOS 기준금리 시계열
- **응답**: 최근 24개월 `[{date, rate}]` + 다음 금통위 일정

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| 장 마감 후 실시간 호출 | 직전 영업일 데이터 반환 + `trading_day` 명시 |
| 종목코드 없음 | 404 "종목 없음" |
| DART 조회 실패 | 공시 제외하고 주가·수급만 반환 |
| finlife API 점검 | 캐시 반환 |

---

## 구현 순서

1. `stock.py` — snapshot (pykrx 재활용)
2. `stock.py` — {ticker} 상세 (DART 병합)
3. `stock.py` — IPO 일정
4. `rate.py` — bond, base (ECOS 재활용)
5. `rate.py` — deposit (finlife 신규 연동)
6. `etf.py` — pykrx 재활용
7. `fund.py` — KOFIA 신규 연동

---

## 의존성
- `pykrx` (기존)
- `dart-fss` (기존)
- `fredapi`, `ecos` (기존)
- 환경변수: `DART_API_KEY`, `ECOS_API_KEY`, `FINLIFE_API_KEY`
