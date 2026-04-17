# 프로젝트 현황 (세션 재개용)
> 세션 종료 시 항상 이 파일을 최신 상태로 갱신한다.
> 재개 시 이 파일만 읽으면 컨텍스트 복구 가능.

---

## 현재 단계

**Phase 13 — 신규 API 그룹 구현 진행 중**
마지막 작업일: 2026-04-17

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
| 🔨 구현중 | index | `api/routers/index/` — 파일 생성됨, main.py 연결 미확인 |
| 🔨 구현중 | indicator | `api/routers/indicator/` — 파일 생성됨, main.py 연결 미확인 |
| 🔨 구현중 | invest | `api/routers/invest/` — 파일 생성됨, main.py 연결 미확인 |
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
| ⬜ 미시작 | crypto_intel | 기획완료 (`PLANNING.md` — 섹터/기관보유/개발활동 13개 EP) |

---

## 미커밋 변경사항

```
M  PLANNING.md              — Phase13 crypto_intel 기획 추가
M  analysis/prediction.py
M  api/main.py
M  collectors/global_/macro.py
M  main.py
M  processors/merger.py
?? api/routers/index/
?? api/routers/indicator/
?? api/routers/invest/
?? docs/PLAN_phase13_*.md   — 14개
?? visualization/index.py
```

---

## 다음 할 일 (우선순위 순)

1. **index / indicator / invest 구현 완료 확인** — 파일은 있으나 `api/main.py` 라우터 등록 여부 미확인
2. **미커밋 파일 전체 커밋** — 위 변경사항 정리
3. **crypto_intel 구현** — `api/routers/crypto_intel/` 신규 (섹터·기관보유·개발활동)
4. 나머지 11개 그룹 순차 구현 (kids → culture → outdoor → ...)

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
