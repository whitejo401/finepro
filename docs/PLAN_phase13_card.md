# PLAN — card (카드 혜택)

## 개요
금융감독원 finlife API와 카드사 RSS를 통해 신용·체크카드 혜택 비교 및 추천을 제공한다.
지출 패턴 입력 → 최적 카드 조합 추천이 핵심 킬러 기능이다.

---

## 파일 구조

```
api/routers/card/
├── __init__.py
├── search.py       # /card/search, /card/{id}
├── compare.py      # /card/compare, /card/annual_fee
├── event.py        # /card/event
└── recommend.py    # /card/recommend
```

---

## 데이터 소스 상세

### 금융감독원 finlife
- **Base URL**: `https://finlife.fss.or.kr/finlifeapi/`
- **인증**: `FINLIFE_API_KEY`
- **API**: `creditCardSearch` — 신용카드 상품 목록·혜택·연회비

### 각 카드사 이벤트 RSS/공지
- 삼성카드, 신한카드, KB국민카드, 현대카드, 롯데카드, 우리카드, 하나카드
- 각 카드사 공식 사이트 이벤트 페이지 RSS 또는 HTML 파싱

---

## 카테고리 정의

```python
CARD_CATEGORIES = [
    "주유", "대형마트", "편의점", "카페", "음식점",
    "온라인쇼핑", "통신", "의료", "교통", "항공마일리지",
    "해외결제", "구독서비스", "백화점", "영화"
]
```

---

## 엔드포인트 상세

### GET /api/v1/card/search
- **Query params**:
  - `category` (혜택 카테고리, 선택)
  - `company` (카드사명, 선택)
  - `card_type` (`신용`|`체크`, 기본 `신용`)
  - `annual_fee_max` (최대 연회비 만원, 선택)
  - `sort` (`discount_rate`|`annual_fee`, 기본 `discount_rate`)
- **캐시**: 3시간
- **응답**:
```json
{
  "total": 28,
  "items": [
    {
      "id": "card_001",
      "name": "OO카드",
      "company": "신한카드",
      "card_type": "신용",
      "annual_fee": 15000,
      "top_benefits": [
        {"category": "주유", "discount_rate": 7, "monthly_limit": 6000}
      ],
      "min_spending": 300000
    }
  ]
}
```

### GET /api/v1/card/{id}
- **캐시**: 6시간
- **응답**:
```json
{
  "id": "card_001",
  "name": "OO카드",
  "company": "신한카드",
  "annual_fee": {"domestic": 15000, "international": 20000},
  "benefits": [
    {"category": "주유", "discount_rate": 7, "monthly_limit": 6000, "condition": "전월실적 30만원 이상"},
    {"category": "카페", "discount_rate": 5, "monthly_limit": 3000}
  ],
  "min_spending": 300000,
  "image_url": "...",
  "apply_url": "..."
}
```

### GET /api/v1/card/compare
- **Query params**: `ids` (쉼표 구분, 최대 4개)
- **캐시**: 6시간
- **응답**: 카드별 혜택을 카테고리 기준으로 정렬한 비교 테이블
```json
{
  "cards": ["OO카드", "XX카드"],
  "comparison": [
    {"category": "주유", "OO카드": 7, "XX카드": 5},
    {"category": "카페", "OO카드": 5, "XX카드": 10}
  ],
  "annual_fee": {"OO카드": 15000, "XX카드": 0},
  "min_spending": {"OO카드": 300000, "XX카드": 200000}
}
```

### GET /api/v1/card/annual_fee
- **Query params**: `benefit` (특정 혜택 필터, 선택)
- **캐시**: 6시간
- **로직**: 전체 카드 → 연간 혜택 총액 추정 / 연회비 → ROI 계산
- **응답**: ROI 내림차순 `[{name, annual_fee, estimated_benefit, roi}]`

### GET /api/v1/card/event
- **캐시**: 30분
- **소스**: 각 카드사 RSS 파싱 (feedparser 활용)
- **응답**:
```json
[
  {
    "company": "삼성카드",
    "title": "봄 쇼핑 캐시백 이벤트",
    "description": "4~5월 특정 가맹점 최대 10% 캐시백",
    "start": "2026-04-01",
    "end": "2026-05-31",
    "url": "..."
  }
]
```

### GET /api/v1/card/recommend
- **Query params**: `spend` (지출 패턴, 쿼리스트링 형식)
  - 예: `spend=주유:30,카페:10,마트:20` (단위: 만원/월)
- **캐시**: 1시간
- **로직**:
  1. 지출 패턴 파싱
  2. 카테고리별 최고 혜택 카드 매핑
  3. 전월실적 조건 충족 여부 체크 (총 지출 합산)
  4. 월간 예상 절감액 = Σ(지출 × 할인율) - 월 환산 연회비
  5. 단일 카드 최적해 + 2카드 조합 최적해 반환
- **응답**:
```json
{
  "monthly_spend_total": 600000,
  "best_single": {
    "card": "OO카드",
    "monthly_saving": 32000,
    "annual_saving": 384000,
    "annual_fee": 15000,
    "net_benefit": 369000
  },
  "best_combo": {
    "cards": ["주유특화카드", "카페특화카드"],
    "monthly_saving": 38000,
    "net_benefit": 441000
  }
}
```

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| spend 파싱 실패 | 422 "형식: spend=주유:30,카페:10" |
| ids 5개 이상 | 422 "최대 4개" |
| RSS 파싱 실패 (카드사 사이트 변경) | 해당 카드사 제외 후 나머지 반환 |
| finlife API 키 없음 | 503 |

---

## 구현 순서

1. `search.py` — finlife 카드 목록·상세
2. `compare.py` — 비교 테이블
3. `compare.py` — annual_fee ROI
4. `event.py` — RSS 파싱 (feedparser)
5. `recommend.py` — 단일 카드 추천
6. `recommend.py` — 2카드 조합 최적화

---

## 의존성
- `requests` (기존)
- `feedparser` (신규 설치 필요)
- 환경변수: `FINLIFE_API_KEY`
