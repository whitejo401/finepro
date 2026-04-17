# 프로젝트 현황 (세션 재개용)
> 세션 종료 시 항상 이 파일을 최신 상태로 갱신한다.
> 재개 시 이 파일만 읽으면 컨텍스트 복구 가능.

---

## 현재 단계

**Phase 13 — 전체 완료**
마지막 작업일: 2026-04-17 (전체 23개 그룹, 152개 엔드포인트 구현 완료)

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
| ✅ 완료 | kids | `api/routers/kids/` — 5개 EP, main.py 등록 완료 |
| ✅ 완료 | culture | `api/routers/culture/` — 5개 EP, main.py 등록 완료 |
| ✅ 완료 | outdoor | `api/routers/outdoor/` — 5개 EP, main.py 등록 완료 |
| ✅ 완료 | travel | `api/routers/travel/` — 5개 EP, main.py 등록 완료 |
| ✅ 완료 | price | `api/routers/price/` — 5개 EP, main.py 등록 완료 |
| ✅ 완료 | medical | `api/routers/medical/` — 6개 EP, main.py 등록 완료 |
| ✅ 완료 | seasonal | `api/routers/seasonal/` — 6개 EP, main.py 등록 완료 |
| ✅ 완료 | saving | `api/routers/saving/` — 11개 EP, main.py 등록 완료 |
| ✅ 완료 | game | `api/routers/game/` — 21개 EP, main.py 등록 완료 |
| ✅ 완료 | transit | `api/routers/transit/` — 7개 EP, main.py 등록 완료 |
| ✅ 완료 | card | `api/routers/card/` — 6개 EP, main.py 등록 완료 |
| ✅ 완료 | crypto_intel | `api/routers/crypto_intel/` — 13개 EP, main.py 등록 완료 |

---

## 미커밋 변경사항

없음 (클린)

---

## 다음 할 일 (우선순위 순)

1. Phase 13 전 그룹 구현 완료. 다음 단계 기획 필요.

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
