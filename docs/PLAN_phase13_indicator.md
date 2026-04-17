# PLAN — indicator (주요 경제지표)

## 개요
ECOS·KOSIS·FRED·OECD·World Bank 등 기존 수집기를 재활용해 경제지표 전용 API를 구성한다.
핵심 부가가치는 **서프라이즈 인덱스** (예측치 vs 실제치)와 **발표 캘린더** 제공이다.

---

## 파일 구조

```
api/routers/indicator/
├── __init__.py
├── inflation.py    # /indicator/inflation
├── growth.py       # /indicator/gdp
├── employment.py   # /indicator/employment
├── trade.py        # /indicator/trade
├── pmi.py          # /indicator/pmi
├── money.py        # /indicator/money
├── dashboard.py    # /indicator/dashboard (통합)
└── calendar.py     # /indicator/calendar
```

---

## 국가 코드 지원

| country 파라미터 | 설명 |
|-----------------|------|
| `KR` | 한국 (ECOS + KOSIS) |
| `US` | 미국 (FRED) |
| `OECD` | OECD 평균 |
| `CN`, `JP`, `DE` | World Bank |

---

## 엔드포인트 상세

### GET /api/v1/indicator/inflation?country=KR
- **캐시**: 6시간
- **소스**:
  - KR: ECOS `901Y009` (CPI 전월비), `901Y010` (CPI 전년비), PPI
  - US: FRED `CPIAUCSL`, `PCEPI`, `PPIFIS`
- **응답**:
```json
{
  "country": "KR",
  "data": {
    "cpi": {"latest": 2.1, "prev_month": 2.0, "prev_year": 3.2, "date": "2026-03"},
    "ppi": {"latest": 1.8, "date": "2026-03"},
    "pce": null
  }
}
```

### GET /api/v1/indicator/gdp?country=KR
- **캐시**: 12시간
- **소스**: ECOS `200Y001` (실질GDP 성장률), World Bank `NY.GDP.MKTP.KD.ZG`
- **응답**: 최근 8분기 시계열 + 전년 동기 대비 성장률

### GET /api/v1/indicator/employment?country=KR
- **캐시**: 6시간
- **소스**:
  - KR: KOSIS 경제활동인구조사 (실업률, 고용률)
  - US: FRED `UNRATE`, `PAYEMS` (비농업고용)
- **응답**: `{unemployment_rate, employment_rate, nonfarm_payroll(US only), date}`

### GET /api/v1/indicator/trade?country=KR
- **캐시**: 6시간
- **소스**: 관세청 무역통계 API (수출입 금액, 전년비 증감률, 무역수지)
- **응답**:
```json
{
  "export": {"amount_usd_bn": 55.2, "yoy_pct": 3.1},
  "import": {"amount_usd_bn": 52.1, "yoy_pct": -1.2},
  "balance": 3.1,
  "date": "2026-03"
}
```

### GET /api/v1/indicator/pmi?country=KR
- **캐시**: 6시간
- **소스**: OECD API (CLI 포함), FRED `MANEMP` (US)
- **응답**: `{manufacturing, services, composite, threshold: 50, date}`
- **추가**: 50 기준 확장/수축 자동 태깅

### GET /api/v1/indicator/money?country=KR
- **캐시**: 6시간
- **소스**: ECOS `101Y004` (M2), `121Y006` (대출)
- **응답**: `{m2_yoy_pct, loan_growth_pct, base_rate, date}`

### GET /api/v1/indicator/dashboard
- **캐시**: 1시간
- **로직**: 위 모든 지표를 KR·US 동시 조회 후 합산
- **서프라이즈 인덱스 계산**:
  ```python
  # 컨센서스는 직전 6개월 평균으로 대리 추정
  surprise = (actual - consensus) / std_dev(recent_6m)
  ```
- **응답 추가 필드**: `surprise_index` per 지표, `macro_score` (-2 ~ +2 종합 점수)

### GET /api/v1/indicator/calendar
- **캐시**: 1시간
- **소스**: FRED release dates + ECOS 발표 일정 (정적 매핑 테이블 유지)
- **응답**: 이번 달 주요 발표 일정
```json
[
  {"date":"2026-04-10","country":"US","indicator":"CPI","period":"2026-03","importance":"high"},
  {"date":"2026-04-25","country":"KR","indicator":"GDP","period":"2026-Q1","importance":"high"}
]
```

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| ECOS 키 없음 | KR 지표 제외, US만 반환 |
| 관세청 API 점검 | 직전 캐시 반환 |
| country 코드 미지원 | 422 + 지원 국가 목록 반환 |

---

## 구현 순서

1. `inflation.py` — KR CPI 먼저, US PCE 추가
2. `growth.py`
3. `trade.py` — 관세청 API 연동
4. `employment.py`
5. `pmi.py` — OECD CLI 포함
6. `money.py`
7. `dashboard.py` — 서프라이즈 인덱스
8. `calendar.py` — 발표 일정 정적 테이블

---

## 의존성
- `fredapi` (기존)
- `ecos` / `requests` ECOS API (기존)
- `wbgapi` (기존)
- `collectors/global_/macro.py` 로직 재활용
