# PLAN — medical (의료·보건)

## 개요
중앙응급의료센터·HIRA·식약처·건보공단 API를 연동해 병원·약국·응급실·의약품 정보를 제공한다.
응급실 실시간 현황과 심야 약국 조회가 핵심 킬러 기능이다.

---

## 파일 구조

```
api/routers/medical/
├── __init__.py
├── hospital.py     # /medical/hospital
├── pharmacy.py     # /medical/pharmacy
├── emergency.py    # /medical/emergency, /medical/aed
├── drug.py         # /medical/drug
└── checkup.py      # /medical/checkup
```

---

## 데이터 소스 상세

### 중앙응급의료센터 (E-GEN)
- **Base URL**: `https://www.data.go.kr/api/` (공공데이터포털)
- **서비스**: 응급의료기관 기본정보, 실시간 응급실 현황, 약국 정보, AED 위치
- **인증**: `DATA_GO_KR_API_KEY`

### 건강보험심사평가원 (HIRA)
- **Base URL**: `https://opendata.hira.or.kr/`
- **서비스**: 병원·의원 목록, 진료과목, 평가등급
- **인증**: `HIRA_API_KEY`

### 식품의약품안전처
- **Base URL**: `https://data.mfds.go.kr/`
- **서비스**: 의약품 허가정보, 성분, 부작용, 복약정보
- **인증**: `MFDS_API_KEY`

### 국민건강보험공단
- **Base URL**: `https://www.data.go.kr/api/`
- **서비스**: 건강검진 기관, 장기요양 시설
- **인증**: `DATA_GO_KR_API_KEY`

---

## 엔드포인트 상세

### GET /api/v1/medical/hospital
- **Query params**:
  - `region` (시도, 필수)
  - `dept` (진료과목명, 선택: `소아과`|`정형외과`|...)
  - `type` (`병원`|`의원`|`종합병원`, 선택)
  - `open_now` (bool, 현재 운영 중, 선택)
- **캐시**: 1시간
- **응답**:
```json
{
  "total": 142,
  "items": [
    {
      "name": "OO병원",
      "type": "종합병원",
      "address": "서울 강남구 ...",
      "phone": "02-XXX-XXXX",
      "depts": ["소아과", "내과"],
      "rating": "1등급",
      "lat": 37.123,
      "lon": 127.456
    }
  ]
}
```

### GET /api/v1/medical/pharmacy
- **Query params**: `lat`, `lon` (필수), `radius` (km, 기본 1.0), `open_now` (bool)
- **캐시**: 10분 (운영시간 변동 잦음)
- **로직**: 위경도 기준 반경 내 약국 → 거리순 정렬
- **응답**: `[{name, address, phone, distance_m, hours, open_now}]`

### GET /api/v1/medical/emergency
- **Query params**: `region` (시도, 필수)
- **캐시**: 5분 (실시간성 중요)
- **로직**: 응급실 현황 API → 병상 가용률 계산
- **응답**:
```json
{
  "items": [
    {
      "name": "OO대학병원 응급실",
      "address": "...",
      "phone": "02-XXX-XXXX",
      "er_beds_total": 30,
      "er_beds_available": 12,
      "wait_status": "보통",
      "is_open": true
    }
  ]
}
```
- **wait_status 기준**: 가용률 > 50% → "여유", 20~50% → "보통", < 20% → "혼잡"

### GET /api/v1/medical/aed
- **Query params**: `lat`, `lon` (필수), `radius` (km, 기본 0.5)
- **캐시**: 24시간 (위치 변동 거의 없음)
- **응답**: `[{name, address, location_detail, lat, lon, distance_m, available_hours}]`

### GET /api/v1/medical/drug
- **Query params**: `name` (의약품명, 필수)
- **캐시**: 24시간
- **로직**: 식약처 허가정보 검색 → 성분·효능·부작용·주의사항 파싱
- **응답**:
```json
{
  "name": "타이레놀",
  "ingredient": "아세트아미노펜 500mg",
  "category": "해열진통제",
  "company": "한국존슨앤드존슨",
  "efficacy": "...",
  "caution": "...",
  "approved_date": "1995-03-01"
}
```

### GET /api/v1/medical/checkup
- **Query params**: `region` (시도), `type` (`일반`|`암검진`|`구강`)
- **캐시**: 24시간
- **응답**: `[{name, address, phone, checkup_types, reservation_url}]`

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| lat/lon 없음 (pharmacy, aed) | 422 "위경도 필수" |
| region 없음 (hospital, emergency) | 422 "지역 필수" |
| 결과 0건 | 200 + `items: []` + `message: "해당 조건 결과 없음"` |
| 응급의료센터 API 지연 | 3초 timeout → 504 |

---

## 구현 순서

1. `emergency.py` — 실시간성 가장 중요, 먼저 구현
2. `pharmacy.py` — 위경도 기반 근처 약국
3. `hospital.py` — HIRA 연동
4. `aed.py` (emergency.py 내 라우터로 추가)
5. `drug.py` — 식약처 연동
6. `checkup.py`

---

## 의존성
- `requests` (기존)
- 환경변수: `DATA_GO_KR_API_KEY`, `HIRA_API_KEY`, `MFDS_API_KEY`
