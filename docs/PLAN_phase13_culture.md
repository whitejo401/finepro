# PLAN — culture (문화행사·축제)

## 개요
한국관광공사 TourAPI·KOPIS·문화공공데이터광장을 연동해 전국 축제·공연·전시 정보를 제공한다.
지역·기간·테마 필터와 "이번 주 인기 행사" 집계가 핵심이다.

---

## 파일 구조

```
api/routers/culture/
├── __init__.py
├── festival.py     # /culture/events/festival
├── performance.py  # /culture/events/performance
├── exhibition.py   # /culture/events/exhibition
└── trending.py     # /culture/events, /culture/events/trending
```

---

## 데이터 소스 상세

### 한국관광공사 TourAPI 4.0
- **Base URL**: `http://apis.data.go.kr/B551011/KorService1/`
- **인증**: `TOUR_API_KEY`
- **주요 operation**:
  - `searchFestival1` — 축제·행사 목록 (날짜·지역 필터)
  - `detailCommon1` — 상세정보
  - `detailImage1` — 이미지

### KOPIS (공연예술통합전산망)
- **Base URL**: `http://kopis.or.kr/openApi/restful/`
- **인증**: `KOPIS_API_KEY`
- **주요 API**:
  - `pblprfr` — 공연 목록 (장르·지역·날짜 필터)
  - `pblprfr/{pfId}` — 공연 상세
  - `prfplc` — 공연장 정보

### 문화공공데이터광장
- **Base URL**: `https://www.culture.go.kr/data/openapi/`
- **인증**: `CULTURE_API_KEY`
- **제공**: 전시·박물관·미술관 행사

---

## 지역 코드 매핑

```python
REGION_MAP = {
    "서울": "1", "인천": "2", "대전": "3", "대구": "4",
    "광주": "5", "부산": "6", "울산": "7", "세종": "8",
    "경기": "31", "강원": "32", "충북": "33", "충남": "34",
    "경북": "35", "경남": "36", "전북": "37", "전남": "38", "제주": "39"
}
```

---

## 엔드포인트 상세

### GET /api/v1/culture/events
- **Query params**: `region`, `month` (YYYYMM), `keyword`
- **캐시**: 1시간
- **로직**: TourAPI `searchFestival1` + KOPIS `pblprfr` 병렬 호출 → 날짜순 병합
- **응답**: 통합 행사 목록 `[{id, title, type, region, start_date, end_date, venue, thumbnail, source}]`

### GET /api/v1/culture/events/festival
- **Query params**: `region`, `month`, `theme` (선택: `음식`|`음악`|`전통`|`빛`|`꽃`)
- **캐시**: 1시간
- **소스**: TourAPI `searchFestival1` (contentTypeId=15)
- **응답**:
```json
[
  {
    "id": "tour_123",
    "title": "진해 군항제",
    "region": "경남",
    "venue": "경상남도 창원시",
    "start_date": "2026-04-01",
    "end_date": "2026-04-10",
    "description": "...",
    "thumbnail": "http://...",
    "lat": 35.15,
    "lon": 128.69,
    "source": "TourAPI"
  }
]
```

### GET /api/v1/culture/events/performance
- **Query params**:
  - `region`
  - `genre` (`뮤지컬`|`연극`|`클래식`|`무용`|`국악`|`대중음악`)
  - `price_max` (최대 가격, 0이면 무료만)
  - `start_date`, `end_date`
- **캐시**: 30분
- **소스**: KOPIS `pblprfr`
- **응답**: `[{id, title, genre, venue, price_range, start_date, end_date, poster_url, ticket_url}]`

### GET /api/v1/culture/events/exhibition
- **Query params**: `region`, `type` (`박물관`|`미술관`|`전시`)
- **캐시**: 3시간
- **소스**: 문화공공데이터광장
- **응답**: `[{title, venue, region, start_date, end_date, admission, url}]`

### GET /api/v1/culture/events/trending
- **캐시**: 1시간
- **로직**: 이번 주 진행 중인 행사 전체 → 조회수·좋아요 데이터 없으므로 날씨(맑음) + 주말 + 대도시 가중치로 스코어링
- **응답**: Top10 `[{rank, title, type, region, score_reason}]`

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| 결과 0건 | 200 + `items: []` |
| TourAPI 일일 호출 한도 초과 | KOPIS 데이터만 반환 + 경고 헤더 |
| 날짜 형식 오류 | 422 "YYYYMM 형식" |

---

## 구현 순서

1. `festival.py` — TourAPI 축제 연동
2. `performance.py` — KOPIS 공연 연동
3. `exhibition.py` — 문화광장 전시 연동
4. `trending.py` — 통합 목록 + 트렌딩 스코어링

---

## 의존성
- `requests` (기존)
- 환경변수: `TOUR_API_KEY`, `KOPIS_API_KEY`, `CULTURE_API_KEY`
