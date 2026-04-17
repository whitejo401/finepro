# PLAN — outdoor (휴양림·캠핑장)

## 개요
고캠핑 API·국립자연휴양림관리소·산림청을 연동해 전국 캠핑장·휴양림·치유의숲 정보를 제공한다.
날씨 API 연동을 통한 날짜 기반 추천이 핵심 기능이다.

---

## 파일 구조

```
api/routers/outdoor/
├── __init__.py
├── camping.py      # /outdoor/camping, /outdoor/camping/{id}
├── forest.py       # /outdoor/forest
├── healing.py      # /outdoor/healing
└── recommend.py    # /outdoor/recommend
```

---

## 데이터 소스 상세

### 고캠핑 (한국관광공사 공공데이터)
- **Base URL**: `http://apis.data.go.kr/B551011/GoCamping/`
- **인증**: `TOUR_API_KEY` (TourAPI와 동일 키)
- **주요 API**:
  - `basedList` — 전체 캠핑장 목록
  - `imageList` — 캠핑장 이미지
  - `locationBasedList` — 위치 기반 검색

### 국립자연휴양림관리소 (공공데이터포털)
- **인증**: `DATA_GO_KR_API_KEY`
- **제공**: 전국 국립 휴양림 현황, 시설, 예약 가능 일정

### 산림청 산림복지서비스 (공공데이터포털)
- **인증**: `DATA_GO_KR_API_KEY`
- **제공**: 치유의숲, 산림욕장, 숲길 정보

---

## 캠핑장 타입 코드

```python
CAMPING_TYPES = {
    "일반야영장": "일반야영장",
    "자동차야영장": "자동차야영장",
    "글램핑": "글램핑",
    "카라반": "카라반",
    "캠핑트레일러": "캠핑트레일러"
}
```

---

## 엔드포인트 상세

### GET /api/v1/outdoor/camping
- **Query params**:
  - `region` (시도명)
  - `type` (`일반야영장`|`글램핑`|`카라반`|`자동차야영장`)
  - `pet` (bool, 반려동물 동반 가능)
  - `electric` (bool, 전기 사용 가능)
  - `indoor_pool` (bool, 실내수영장)
- **캐시**: 6시간
- **응답**:
```json
{
  "total": 48,
  "items": [
    {
      "id": "camp_001",
      "name": "OO캠핑장",
      "type": "글램핑",
      "region": "강원",
      "address": "강원도 춘천시 ...",
      "phone": "033-XXX-XXXX",
      "facilities": ["전기", "화장실", "샤워실", "매점"],
      "pet_allowed": true,
      "reservation_url": "https://...",
      "thumbnail": "https://...",
      "lat": 37.8,
      "lon": 127.7
    }
  ]
}
```

### GET /api/v1/outdoor/camping/{id}
- **캐시**: 6시간
- **로직**: 기본정보 + 이미지 목록 + 인근 날씨 (weather 그룹 캐시 활용)
- **응답 추가 필드**: `images`, `nearby_weather`

### GET /api/v1/outdoor/forest
- **Query params**: `region`, `reservation_available` (bool)
- **캐시**: 6시간
- **응답**:
```json
[
  {
    "name": "OO자연휴양림",
    "region": "경기",
    "address": "...",
    "facilities": ["숲속의집", "야영장", "숲길"],
    "reservation_url": "https://huyang.go.kr",
    "reservation_available": true,
    "fee": {"숲속의집": 70000, "야영장": 10000}
  }
]
```

### GET /api/v1/outdoor/healing
- **Query params**: `region`
- **캐시**: 12시간
- **응답**: `[{name, region, address, type, program, reservation_url}]`
  - `type`: `치유의숲`|`산림욕장`|`숲길`

### GET /api/v1/outdoor/recommend
- **Query params**: `date` (YYYY-MM-DD), `region` (선택), `type` (선택)
- **캐시**: 1시간
- **로직**:
  1. 대상 날짜 전국(또는 지역) 날씨 예보 조회 (weather 그룹 캐시)
  2. 강수확률 < 30% & 최고기온 15~28°C 지역 추출
  3. 해당 지역 캠핑장·휴양림 목록 반환
- **응답**:
```json
{
  "date": "2026-05-03",
  "weather_summary": "맑음, 강원/경기 북부 최적",
  "recommended": [
    {"type": "camping", "name": "OO캠핑장", "region": "강원", "weather": "맑음 23°C"}
  ]
}
```

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| 날씨 API 조회 실패 (recommend) | 날씨 없이 지역 기반만 추천 + 경고 |
| 결과 0건 | 200 + `items: []` |
| id 없음 | 404 |

---

## 구현 순서

1. `camping.py` — 고캠핑 목록·필터
2. `camping.py` — 상세 + 날씨 연동
3. `forest.py` — 국립휴양림
4. `healing.py` — 치유의숲·산림욕장
5. `recommend.py` — 날씨 기반 추천

---

## 의존성
- `requests` (기존)
- weather 그룹 캐시 (내부 호출)
- 환경변수: `TOUR_API_KEY`, `DATA_GO_KR_API_KEY`
