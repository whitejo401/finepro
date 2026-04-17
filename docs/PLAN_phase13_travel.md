# PLAN — travel (호텔·콘도·여행 할인 이벤트)

## 개요
TourAPI 숙박 정보와 정부 주관 여행 할인 행사(숙박대전·여행가는달)를 연동한다.
민간 플랫폼(야놀자·여기어때) 공개 API 부재로 정부 지원 이벤트 중심으로 구성한다.

---

## 파일 구조

```
api/routers/travel/
├── __init__.py
├── stay.py         # /travel/stay, /travel/stay/{id}
├── discount.py     # /travel/discount/events, /travel/discount/festival
└── packages.py     # /travel/packages
```

---

## 데이터 소스 상세

### 한국관광공사 TourAPI
- `searchKeyword1` + contentTypeId=32 (숙박) — 숙박시설 검색
- `detailCommon1` — 숙박 상세
- `detailImage1` — 이미지

### 공공데이터포털 — 대한민국 숙박대전
- 연 2회 (봄·가을) 한국관광공사 주관
- 참여 숙소 목록, 할인율, 기간 제공

### 공공데이터포털 — 여행가는달
- 매년 4월·10월 진행
- 국내 여행 할인 쿠폰, 패키지 정보

---

## 숙박 타입 코드

```python
STAY_TYPES = {
    "호텔": "호텔",
    "콘도": "콘도미니엄",
    "펜션": "펜션",
    "게스트하우스": "게스트하우스",
    "모텔": "모텔",
    "한옥": "한옥",
    "리조트": "관광호텔"
}
```

---

## 엔드포인트 상세

### GET /api/v1/travel/stay
- **Query params**:
  - `region` (시도명, 필수)
  - `type` (숙박 타입, 선택)
  - `grade` (`5성`|`4성`|`3성`, 선택 — 호텔만 해당)
  - `pet` (bool, 반려동물)
- **캐시**: 3시간
- **소스**: TourAPI `searchKeyword1` (contentTypeId=32)
- **응답**:
```json
{
  "region": "제주",
  "total": 152,
  "items": [
    {
      "id": "tour_stay_001",
      "name": "OO호텔",
      "type": "호텔",
      "grade": "5성",
      "address": "제주시 ...",
      "phone": "064-XXX-XXXX",
      "checkin": "15:00",
      "checkout": "11:00",
      "amenities": ["수영장", "스파", "레스토랑"],
      "thumbnail": "https://...",
      "lat": 33.4,
      "lon": 126.5
    }
  ]
}
```

### GET /api/v1/travel/stay/{id}
- **캐시**: 6시간
- **응답 추가**: `images`, `rooms` (객실 종류 목록), `nearby` (근처 관광지 3개)
- **near 로직**: TourAPI `locationBasedList` 반경 5km 관광지 조회

### GET /api/v1/travel/discount/events
- **캐시**: 1시간
- **로직**: 현재 날짜 기준 진행 중인 정부 여행 할인 이벤트 전체
- **소스**: 숙박대전 + 여행가는달 + TourAPI 이벤트 키워드 검색
- **응답**:
```json
[
  {
    "title": "대한민국 숙박대전",
    "organizer": "한국관광공사",
    "discount": "최대 50% 할인",
    "start": "2026-04-01",
    "end": "2026-04-30",
    "target": "참여 숙박업소 전체",
    "url": "https://..."
  }
]
```

### GET /api/v1/travel/discount/festival
- **캐시**: 1시간
- **로직**: 숙박대전·여행가는달 참여 숙소 목록 + 할인율
- **응답**: `[{name, region, type, original_price(추정), discount_pct, booking_url}]`

### GET /api/v1/travel/packages
- **Query params**: `region`
- **캐시**: 3시간
- **소스**: TourAPI `searchKeyword1` 키워드=패키지·코스
- **응답**: `[{title, region, duration_days, highlights, thumbnail}]`

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| 숙박대전 미운영 기간 | `discount/festival` → 빈 배열 + `next_event` 필드로 다음 행사 일정 안내 |
| TourAPI 한도 초과 | 503 + Retry-After 헤더 |
| region 누락 (/stay) | 422 |

---

## 구현 순서

1. `stay.py` — 숙박시설 목록 (TourAPI contentTypeId=32)
2. `stay.py` — 상세 + 근처 관광지
3. `discount.py` — 진행 중 이벤트 통합
4. `discount.py` — 숙박대전·여행가는달 참여 숙소
5. `packages.py`

---

## 의존성
- `requests` (기존)
- 환경변수: `TOUR_API_KEY`, `DATA_GO_KR_API_KEY`
