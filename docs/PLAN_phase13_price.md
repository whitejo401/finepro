# PLAN — price (생활물가)

## 개요
오피넷·KAMIS·한국소비자원 참가격을 통해 유가·농산물·생필품 가격을 제공한다.
일상 밀착 데이터로 수요가 높고, 지역별 비교 및 등락 알림에 강점이 있다.

---

## 파일 구조

```
api/routers/price/
├── __init__.py
├── fuel.py         # /price/fuel
├── grocery.py      # /price/grocery
├── consumer.py     # /price/consumer
└── cpi.py          # /price/cpi (ECOS 재활용)
```

---

## 데이터 소스 상세

### 오피넷 (한국석유공사)
- **Base URL**: `http://www.opinet.co.kr/api/`
- **인증**: `apiKey` 쿼리 파라미터
- **주요 엔드포인트**:
  - `avgRecentPrice.do` — 전국/지역 평균 유가
  - `lowTop10.do` — 지역별 최저가 주유소 Top10
  - `recentAllPriceChart.do` — 최근 유가 추이 (일별)
- **지역 코드**: 시도 코드 (서울=01, 부산=02, ...)

### KAMIS (농산물유통정보)
- **Base URL**: `http://www.kamis.or.kr/service/price/xml.do`
- **인증**: `apiKey` + `cert_key`
- **주요 action**: `periodProductList` (기간별 품목 가격)
- **카테고리**: 채소(100), 과일(200), 수산(300), 축산(400), 곡물(500)

### 한국소비자원 참가격
- **Base URL**: `https://www.data.go.kr/api/` (공공데이터포털 경유)
- **제공**: 가공식품·외식·생활용품 가격 (주 1회 업데이트)

---

## 엔드포인트 상세

### GET /api/v1/price/fuel
- **Query params**:
  - `region` (시도명, 기본 "전국")
  - `type` (`휘발유`|`경유`|`LPG`, 기본 `휘발유`)
- **캐시**: 10분
- **로직**:
  1. 오피넷 `avgRecentPrice.do` 호출
  2. 지역 평균가 + 전국 평균 대비 차이 계산
  3. 최저가 주유소 Top5 병합
- **응답**:
```json
{
  "region": "서울",
  "type": "휘발유",
  "avg_price": 1723,
  "national_avg": 1698,
  "diff_from_national": 25,
  "low_top5": [
    {"name": "OO주유소", "price": 1621, "address": "서울 강남구 ..."}
  ],
  "date": "2026-04-15"
}
```

### GET /api/v1/price/fuel/trend
- **Query params**: `days` (7|30|90, 기본 30), `type`
- **캐시**: 1시간
- **응답**: `[{date, national_avg, seoul, busan, ...}]`

### GET /api/v1/price/grocery
- **Query params**:
  - `category` (`채소`|`과일`|`수산`|`축산`|`곡물`)
  - `item` (품목명, 선택)
  - `region` (기본 "전국")
- **캐시**: 1시간
- **로직**: KAMIS `periodProductList` 당일 + 전일 조회 → 등락률 계산
- **응답**:
```json
{
  "category": "채소",
  "date": "2026-04-15",
  "items": [
    {"name": "배추", "unit": "1포기", "price": 3500, "change": -200, "change_pct": -5.4}
  ]
}
```

### GET /api/v1/price/consumer
- **Query params**: `category` (`가공식품`|`외식`|`생활용품`)
- **캐시**: 3시간
- **응답**: 품목별 가격 + 전주 대비 등락

### GET /api/v1/price/cpi
- **캐시**: 6시간
- **소스**: ECOS (기존 `indicator` 그룹과 동일 소스, 캐시 공유)
- **응답**: 최근 12개월 CPI 시계열 + 최신 전월비·전년비

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| 오피넷 API 점검 (주말 새벽 1~5시) | 캐시 반환 + `stale: true` |
| KAMIS 품목 코드 없음 | 422 + 지원 품목 목록 |
| 지역 코드 잘못됨 | 422 + 지원 지역 목록 |

---

## 구현 순서

1. `fuel.py` — 오피넷 연동, 지역별 평균 + Top5
2. `fuel.py` — trend 엔드포인트 추가
3. `grocery.py` — KAMIS 연동
4. `consumer.py` — 참가격 연동
5. `cpi.py` — ECOS 재활용 (indicator 완료 후)

---

## 의존성
- `requests` (기존)
- `pandas` (기존)
- 환경변수: `OPINET_API_KEY`, `KAMIS_API_KEY`, `KAMIS_CERT_KEY`, `DATA_GO_KR_API_KEY`
