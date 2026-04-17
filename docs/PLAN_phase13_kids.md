# PLAN — kids (어린이·학생 무료 체험 행사)

## 개요
TourAPI·문화공공데이터광장·KOPIS·도서관 정보나루·국립중앙박물관을 연동해
어린이·학생 대상 무료 체험 행사를 지역·연령별로 통합 제공한다.

---

## 파일 구조

```
api/routers/kids/
├── __init__.py
├── events.py       # /kids/events (통합), /kids/events/festival
├── museum.py       # /kids/events/museum
├── performance.py  # /kids/events/performance
└── library.py      # /kids/events/library
```

---

## 데이터 소스 상세

### 한국관광공사 TourAPI
- culture 그룹과 동일 소스, 키워드 `어린이`·`체험`·`무료` 필터 추가

### 문화공공데이터광장
- 박물관·미술관 교육·체험 프로그램 (무료 한정)

### KOPIS
- 어린이 장르 필터: `장르코드=AAAB` (아동)
- 가격 0원 필터

### 도서관 정보나루
- **Base URL**: `https://data4library.kr/api/`
- **인증**: `LIBRARY_API_KEY`
- **API**: `libSrchByEvent` — 도서관 행사 목록

### 국립중앙박물관 e뮤지엄
- **Base URL**: `https://www.emuseum.go.kr/openapi/`
- **인증**: `EMUSEUM_API_KEY`
- **제공**: 교육·체험 프로그램 (대부분 무료)

---

## 연령 그룹 정의

```python
AGE_GROUPS = {
    "영유아": (0, 6),
    "초등": (7, 13),
    "중고등": (14, 19),
    "전체": (0, 99)
}
```

---

## 엔드포인트 상세

### GET /api/v1/kids/events
- **Query params**: `region`, `age` (`영유아`|`초등`|`중고등`|`전체`), `month`
- **캐시**: 1시간
- **로직**: 4개 소스 병렬 호출 → 무료 행사만 필터 → 연령 태그 매핑 → 날짜순 병합
- **응답**:
```json
{
  "total": 34,
  "items": [
    {
      "title": "봄꽃 만들기 체험",
      "type": "체험",
      "organizer": "서울시립미술관",
      "region": "서울",
      "venue": "서울시립미술관 교육실",
      "age_group": "초등",
      "admission": "무료",
      "start_date": "2026-04-20",
      "end_date": "2026-04-20",
      "registration_url": "...",
      "source": "문화공공데이터"
    }
  ]
}
```

### GET /api/v1/kids/events/festival
- **Query params**: `region`, `month`
- **캐시**: 1시간
- **소스**: TourAPI (키워드=어린이|체험, contentTypeId=15)
- **필터**: 무료 또는 어린이 무료 명시 행사 우선

### GET /api/v1/kids/events/museum
- **Query params**: `region`, `age`
- **캐시**: 3시간
- **소스**: 문화공공데이터광장 + e뮤지엄
- **응답 추가 필드**: `capacity` (정원), `reservation_required` (사전예약 여부)

### GET /api/v1/kids/events/performance
- **Query params**: `region`, `age`
- **캐시**: 1시간
- **소스**: KOPIS 장르코드 `AAAB` (아동) + 가격 0원
- **응답**: `[{title, venue, date_range, target_age, description, poster_url}]`

### GET /api/v1/kids/events/library
- **Query params**: `region`, `age`
- **캐시**: 3시간
- **소스**: 도서관 정보나루 `libSrchByEvent`
- **응답**: `[{library_name, program_title, target, date_range, registration_url}]`

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| 소스 중 일부 실패 | 나머지 소스로 부분 응답, `partial: true` 플래그 |
| 결과 0건 | 200 + `items: []` + `tip: "검색 조건을 넓혀보세요"` |

---

## 구현 순서

1. `performance.py` — KOPIS 아동 공연 (culture 그룹 재활용)
2. `library.py` — 도서관 정보나루 연동
3. `museum.py` — 문화광장 + e뮤지엄
4. `events.py` — 통합 목록 (festival 포함)

---

## 의존성
- `requests` (기존)
- 환경변수: `TOUR_API_KEY`, `KOPIS_API_KEY`, `CULTURE_API_KEY`, `LIBRARY_API_KEY`, `EMUSEUM_API_KEY`
