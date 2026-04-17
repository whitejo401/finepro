# PLAN — seasonal (계절별 야외시설 개장 일정)

## 개요
여름(물놀이터·해수욕장·계곡)과 겨울(스키장·눈썰매장·빙상장) 계절 시설의
개장·폐장 일정과 현황을 제공한다. `/seasonal/now`가 핵심 — 현재 계절 기준 오픈 시설 전체 목록.

---

## 파일 구조

```
api/routers/seasonal/
├── __init__.py
├── water.py        # /seasonal/water, /seasonal/beach, /seasonal/valley
├── winter.py       # /seasonal/ski, /seasonal/ice
└── now.py          # /seasonal/now
```

---

## 데이터 소스 상세

### 한국관광공사 TourAPI
- `searchKeyword1` — 워터파크·해수욕장·스키장 검색
- `searchFestival1` — 개장 이벤트 날짜 확인

### 공공데이터포털 — 지자체 물놀이장
- 시·군·구별 공공 물놀이터 개장 일정·운영시간
- 인증: `DATA_GO_KR_API_KEY`

### 서울 열린데이터광장
- 한강 물놀이장·공공수영장 운영 현황
- 인증: `SEOUL_API_KEY`

### 행정안전부 물놀이 안전정보 (공공데이터포털)
- 계곡·해수욕장 안전등급, 사고 현황
- 인증: `DATA_GO_KR_API_KEY`

### 공공데이터포털 — 스키장·빙상장
- 전국 스키장·눈썰매장·실내빙상장 운영정보
- 인증: `DATA_GO_KR_API_KEY`

---

## 계절 자동 감지

```python
def get_current_season(month: int) -> str:
    if month in [6, 7, 8]:     return "summer"
    if month in [12, 1, 2]:    return "winter"
    if month in [3, 4, 5]:     return "spring"
    return "autumn"
```

---

## 엔드포인트 상세

### GET /api/v1/seasonal/water
- **Query params**: `region`, `type` (`물놀이터`|`공공수영장`|`워터파크`)
- **캐시**: 1시간
- **로직**: 공공데이터 물놀이장 + 서울 열린데이터(서울인 경우) 병합
- **응답**:
```json
[
  {
    "name": "OO 물놀이터",
    "type": "물놀이터",
    "region": "서울",
    "address": "서울 송파구 ...",
    "open_date": "2026-07-01",
    "close_date": "2026-08-31",
    "hours": "10:00~18:00",
    "admission": "무료",
    "is_open": false,
    "phone": "02-XXX-XXXX"
  }
]
```

### GET /api/v1/seasonal/beach
- **Query params**: `region` (`강원`|`경남`|`전남`|`제주`|`충남`)
- **캐시**: 3시간
- **소스**: TourAPI (contentTypeId=12, 키워드=해수욕장) + 행안부 안전정보
- **응답 추가 필드**: `water_temp`, `wave_height`, `safety_grade` (`A`|`B`|`C`)

### GET /api/v1/seasonal/valley
- **Query params**: `region`
- **캐시**: 3시간
- **소스**: 행안부 물놀이 안전정보
- **응답 추가 필드**: `safety_grade`, `accident_count_ytd`, `congestion` (`여유`|`보통`|`혼잡`)

### GET /api/v1/seasonal/ski
- **Query params**: `region`
- **캐시**: 1시간
- **소스**: TourAPI (키워드=스키장) + 공공데이터 스키장 운영정보
- **응답**:
```json
[
  {
    "name": "OO리조트",
    "region": "강원",
    "address": "...",
    "open_date": "2025-12-01",
    "close_date": "2026-03-15",
    "is_open": false,
    "slopes": {"total": 22, "open": 0},
    "snow_depth_cm": 0,
    "lift_count": 12,
    "url": "https://..."
  }
]
```

### GET /api/v1/seasonal/ice
- **Query params**: `region`, `type` (`실내`|`실외`)
- **캐시**: 3시간
- **소스**: 공공데이터 빙상장 운영정보
- **응답**: `[{name, type, region, address, hours, admission, is_open}]`

### GET /api/v1/seasonal/now
- **캐시**: 30분
- **로직**:
  1. 현재 월 기준 계절 감지
  2. 여름: water + beach + valley 모두 조회 → is_open=true 필터
  3. 겨울: ski + ice 조회 → is_open=true 필터
  4. 봄·가을: 개장 예정(D-7 이내) 시설 포함
- **응답**:
```json
{
  "season": "summer",
  "date": "2026-07-15",
  "open_facilities": {
    "water": [...],
    "beach": [...],
    "valley": [...]
  },
  "opening_soon": [
    {"name": "OO해수욕장", "open_date": "2026-07-20", "days_left": 5}
  ]
}
```

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| 비수기 (`/seasonal/now` 봄·가을) | 개장 예정 시설 위주 반환 + `off_season: true` |
| 날씨 연동 실패 | 날씨 없이 개장 정보만 반환 |

---

## 구현 순서

1. `water.py` — 공공 물놀이장 + 서울 연동
2. `water.py` — beach (TourAPI + 행안부)
3. `water.py` — valley (행안부)
4. `winter.py` — ski
5. `winter.py` — ice
6. `now.py` — 계절 감지 + 통합

---

## 의존성
- `requests` (기존)
- 환경변수: `TOUR_API_KEY`, `DATA_GO_KR_API_KEY`, `SEOUL_API_KEY`
