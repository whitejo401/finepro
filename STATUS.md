# 프로젝트 현황 (세션 재개용)
> 세션 종료 시 항상 이 파일을 최신 상태로 갱신한다.
> 재개 시 이 파일만 읽으면 컨텍스트 복구 가능.

---

## 현재 단계

**Phase 13 — 신규 API 그룹 구현 진행 중**
마지막 작업일: 2026-04-17 (index·indicator·invest·crypto_intel 완료, kids 다음)

---

## API 그룹 전체 현황

| 상태 | 그룹 | 위치 |
|------|------|------|
| ✅ 완료 | finance | `api/routers/finance/` |
| ✅ 완료 | benefits | `api/routers/benefits/` |
| ✅ 완료 | realestate | `api/routers/realestate/` |
| ✅ 완료 | crypto | `api/routers/crypto/` |
| ✅ 완료 | exchange | `api/routers/exchange/` |
| ✅ 완료 | weather | `api/routers/weather/` |
| ✅ 완료 | news | `api/routers/news/` |
| ✅ 완료 | index | `api/routers/index/` — 11개 EP, main.py 등록 완료 |
| ✅ 완료 | indicator | `api/routers/indicator/` — 8개 EP, main.py 등록 완료 |
| ✅ 완료 | invest | `api/routers/invest/` — 8개 EP, main.py 등록 완료 |
| ⬜ 미시작 | kids | 기획완료 (`docs/PLAN_phase13_kids.md`) |
| ⬜ 미시작 | culture | 기획완료 (`docs/PLAN_phase13_culture.md`) |
| ⬜ 미시작 | outdoor | 기획완료 (`docs/PLAN_phase13_outdoor.md`) |
| ⬜ 미시작 | travel | 기획완료 (`docs/PLAN_phase13_travel.md`) |
| ⬜ 미시작 | price | 기획완료 (`docs/PLAN_phase13_price.md`) |
| ⬜ 미시작 | medical | 기획완료 (`docs/PLAN_phase13_medical.md`) |
| ⬜ 미시작 | seasonal | 기획완료 (`docs/PLAN_phase13_seasonal.md`) |
| ⬜ 미시작 | saving | 기획완료 (`docs/PLAN_phase13_saving.md`) |
| ⬜ 미시작 | game | 기획완료 (`docs/PLAN_phase13_game.md`) |
| ⬜ 미시작 | transit | 기획완료 (`docs/PLAN_phase13_transit.md`) |
| ⬜ 미시작 | card | 기획완료 (`docs/PLAN_phase13_card.md`) |
| ✅ 완료 | crypto_intel | `api/routers/crypto_intel/` — 13개 EP, main.py 등록 완료 |

---

## 미커밋 변경사항

없음 (클린)

---

## 다음 할 일 (우선순위 순)

1. 나머지 11개 그룹 순차 구현 (kids → culture → outdoor → travel → price → medical → seasonal → saving → game → transit → card)

---

## 핵심 파일 위치

| 파일 | 용도 |
|------|------|
| `PLANNING.md` | 전체 기획 (API 설계, 엔드포인트 스펙) |
| `api/main.py` | FastAPI 앱 진입점, 라우터 등록 |
| `api/core/cache.py` | 인메모리 TTL 캐시 |
| `api/core/response.py` | 공통 응답 포맷 |
| `.env` | API 키 (커밋 금지) |

---

## 추가 필요 API 키

| 키 | 용도 | 상태 |
|----|------|------|
| `GITHUB_TOKEN` | crypto_intel 개발활동 (없으면 60req/hr) | 미입력 |
