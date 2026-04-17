# PLAN — transit (교통요금)

## 개요
코레일·고속버스·한국도로공사·서울 열린데이터·ODsay를 연동해 교통수단별 요금 조회 및 비교를 제공한다.
핵심 기능은 출발지→목적지 다중 교통수단 요금·시간 비교다.

---

## 파일 구조

```
api/routers/transit/
├── __init__.py
├── train.py        # /transit/train
├── bus.py          # /transit/bus
├── highway.py      # /transit/highway
├── subway.py       # /transit/subway
└── compare.py      # /transit/route/fare, /transit/compare
```

---

## 데이터 소스 상세

### 코레일 (공공데이터포털)
- **서비스명**: 한국철도공사 열차운행정보
- **인증**: `DATA_GO_KR_API_KEY`
- **제공**: 출발역·도착역·열차종류별 운임, 시간표

### 고속버스 (공공데이터포털)
- **서비스명**: 고속버스 운행정보
- **인증**: `DATA_GO_KR_API_KEY`
- **제공**: 출발지·도착지·등급별(우등·일반) 요금, 시간표

### 한국도로공사
- **Base URL**: `https://data.ex.co.kr/`
- **인증**: `EX_API_KEY`
- **제공**: 고속도로 구간별 통행료 (차종 1~5종)

### 서울 열린데이터광장
- **서비스**: 지하철·버스 요금 체계
- **인증**: `SEOUL_API_KEY`

### ODsay 대중교통 API
- **Base URL**: `https://api.odsay.com/v1/api/`
- **인증**: `ODSAY_API_KEY`
- **제공**: 전국 대중교통 환승 경로 + 요금 계산

---

## 엔드포인트 상세

### GET /api/v1/transit/train
- **Query params**: `from` (출발역명, 필수), `to` (도착역명, 필수), `date` (YYYYMMDD, 기본 오늘)
- **캐시**: 6시간
- **응답**:
```json
{
  "from": "서울",
  "to": "부산",
  "fares": [
    {"type": "KTX", "grade": "일반실", "price": 59800, "duration_min": 162},
    {"type": "KTX", "grade": "특실", "price": 83800, "duration_min": 162},
    {"type": "무궁화", "grade": "일반실", "price": 28600, "duration_min": 290}
  ]
}
```

### GET /api/v1/transit/bus
- **Query params**: `from`, `to`, `date`
- **캐시**: 6시간
- **응답**:
```json
{
  "from": "서울",
  "to": "강릉",
  "fares": [
    {"grade": "우등", "price": 20700, "duration_min": 140},
    {"grade": "일반", "price": 15400, "duration_min": 150}
  ],
  "terminals": {"departure": "동서울터미널", "arrival": "강릉시외버스터미널"}
}
```

### GET /api/v1/transit/highway
- **Query params**: `from` (출발IC), `to` (도착IC), `vehicle_type` (1~5, 기본 1=승용차)
- **캐시**: 24시간
- **응답**: `{from, to, toll_fee, distance_km, vehicle_type}`

### GET /api/v1/transit/subway
- **Query params**: `region` (`서울`|`부산`|`대구`|`광주`|`대전`, 기본 `서울`)
- **캐시**: 24시간
- **로직**: 정적 요금 테이블 (거리비례제) + 환승 할인 규칙
- **응답**:
```json
{
  "region": "서울",
  "base_fare": 1400,
  "distance_surcharge": [
    {"km_range": "0~10km", "fare": 1400},
    {"km_range": "10~50km", "fare": 1400, "per_5km": 100},
    {"km_range": "50km+", "fare": 1400, "per_8km": 100}
  ],
  "transfer_discount": "환승 시 기본요금 미중복 적용"
}
```

### GET /api/v1/transit/route/fare
- **Query params**: `from` (출발지명 또는 위경도), `to` (도착지명 또는 위경도)
- **캐시**: 10분
- **소스**: ODsay API `searchPubTransPathT`
- **응답**: 최적 경로 3가지 + 각 경로별 총 요금·소요시간·환승 횟수

### GET /api/v1/transit/compare
- **Query params**: `from`, `to`
- **캐시**: 6시간
- **로직**: train + bus + highway(자가용 유류비 계산) 동시 조회 후 병합
- **자가용 유류비 계산**: `거리(km) / 연비(기본 12km/L) × 유가(price 그룹 캐시 활용)`
- **응답**:
```json
{
  "from": "서울",
  "to": "부산",
  "comparison": [
    {"mode": "KTX", "price": 59800, "duration_min": 162, "co2_g": 18000},
    {"mode": "고속버스(우등)", "price": 20700, "duration_min": 280, "co2_g": 25000},
    {"mode": "자가용", "price": 52000, "duration_min": 270, "co2_g": 72000, "toll": 21700}
  ]
}
```

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| 출발지·도착지 미입력 | 422 |
| 역명·터미널명 매칭 실패 | 422 + "지원 역명 목록 참조" |
| ODsay 경로 없음 | 200 + `routes: []` |
| 도로공사 API 점검 | highway 제외하고 나머지만 반환 |

---

## 구현 순서

1. `train.py` — 코레일 연동
2. `bus.py` — 고속버스 연동
3. `highway.py` — 도로공사 연동
4. `subway.py` — 정적 테이블 (API 연동 불필요)
5. `compare.py` — 통합 비교 (1~4 완료 후)
6. `compare.py` — ODsay 경로 요금 추가

---

## 의존성
- `requests` (기존)
- 환경변수: `DATA_GO_KR_API_KEY`, `EX_API_KEY`, `SEOUL_API_KEY`, `ODSAY_API_KEY`
