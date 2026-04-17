# PLAN — game (인기 게임 정보·스탯 계산·쿠폰·이벤트)

## 개요
넥슨·Riot·크래프톤·Neople·펄어비스·Devsisters(비공식) API를 연동해
전적 조회·스탯 계산·쿠폰·이벤트를 통합 제공한다.

---

## 파일 구조

```
api/routers/game/
├── __init__.py
├── lol.py          # /game/lol/*
├── valorant.py     # /game/valorant/*
├── pubg.py         # /game/pubg/*
├── maple.py        # /game/maple/*
├── fc.py           # /game/fc/*
├── dnf.py          # /game/dnf/*
├── cookierun.py    # /game/cookierun/*, /game/ovensmash/*, /game/devsisters/*
├── coupon.py       # /game/coupon
└── event.py        # /game/event, /game/maintenance
```

---

## 데이터 소스 상세

### Riot Games API
- **Base URL**: `https://kr.api.riotgames.com/`
- **인증**: `RIOT_API_KEY` (헤더 `X-Riot-Token`)
- **Rate limit**: 20 req/s, 100 req/2min (개발키), 프로덕션 키는 별도

### 넥슨 Open API
- **Base URL**: `https://open.api.nexon.com/`
- **인증**: `NEXON_API_KEY` (헤더 `x-nxopen-api-key`)
- **지원 게임**: 메이플스토리, FC온라인, 던전앤파이터, 바람의나라, 서든어택 등

### 크래프톤 PUBG API
- **Base URL**: `https://api.pubg.com/shards/kakao/`
- **인증**: `PUBG_API_KEY` (Bearer Token)

### Neople API (던전앤파이터)
- **Base URL**: `https://api.neople.co.kr/df/`
- **인증**: `NEOPLE_API_KEY` (쿼리 파라미터)

### 펄어비스 API (검은사막)
- **Base URL**: `https://api.blackdesertonline.com/`
- **인증**: `BDO_API_KEY`

### Devsisters (쿠키런·오븐스매시)
- 공식 API 없음 → 비공식 커뮤니티 API (`api.crlkd.me`) + 공식 뉴스 RSS 파싱

### 게임사 이벤트·쿠폰 RSS
- 넥슨 공지: `https://maplestory.nexon.com/news/notice` RSS
- Riot 공지: `https://www.leagueoflegends.com/ko-kr/news/` RSS
- 크래프톤 공지: RSS 파싱
- Devsisters: `https://www.devsisters.com/ko/news/` RSS

---

## 엔드포인트 상세

### GET /api/v1/game/lol/summoner/{name}
- **캐시**: 5분
- **로직**:
  1. `summoner-v4` → puuid 획득
  2. `league-v4` → 티어·LP·승률
  3. `champion-mastery-v4` → 주요 챔피언 숙련도
- **응답**: `{name, tier, lp, win_rate, most_champions: [{name, mastery}]}`

### GET /api/v1/game/lol/match/{name}
- **Query params**: `count` (기본 20, 최대 50)
- **캐시**: 5분
- **로직**: `match-v5` 최근 매치 목록 → 상세 병렬 조회
- **응답**: `[{champion, role, win, kills, deaths, assists, cs, damage, duration_min}]`

### GET /api/v1/game/lol/calc/dps
- **Query params**: `champion`, `build` (아이템 쉼표 구분)
- **캐시**: 없음 (계산 엔드포인트)
- **로직**: 정적 챔피언·아이템 데이터 (Riot Data Dragon) 기반 DPS 계산
  - `dps = (ad + ap * ratio) * (1 + crit * 0.75) * attack_speed`
- **응답**: `{champion, build, dps, burst_dmg, effective_hp}`

### GET /api/v1/game/lol/meta/tier
- **캐시**: 30분
- **소스**: Riot Data Dragon (정적) + 외부 메타 API (op.gg API 대신 자체 집계 불가 → 정적 업데이트)
- **Note**: 패치 주기(2주)마다 수동 갱신 필요. 자동화 어려움 명시

### GET /api/v1/game/maple/character/{name}
- **캐시**: 10분
- **로직**: 넥슨 API `character/basic` → `character/stat` → `character/equipment` 순차 호출
- **응답**: `{name, class, level, world, stats: {str, dex, int, luk, damage_pct, boss_damage_pct, crit_rate}}`

### GET /api/v1/game/maple/calc/damage
- **Query params**: `atk`, `damage_pct`, `boss_pct`, `final_dmg_pct`, `crit_rate`, `crit_dmg`
- **캐시**: 없음
- **로직**:
  ```
  avg_dmg = atk × (1 + damage_pct/100) × (1 + boss_pct/100) × (1 + final_dmg_pct/100)
  avg_crit = avg_dmg × (1 + crit_rate/100 × crit_dmg/100)
  ```
- **응답**: `{avg_dmg, avg_crit, min_dmg, max_dmg}`

### GET /api/v1/game/maple/calc/starforce
- **Query params**: `item` (장비명), `current_star`, `target_star`, `event` (bool, 30% 할인 이벤트)
- **캐시**: 없음
- **로직**: 스타포스 확률 테이블 기반 몬테카를로 시뮬레이션 (10,000회)
- **응답**: `{expected_cost, destruction_count, avg_attempts, p50_cost, p90_cost}`

### GET /api/v1/game/cookierun/cookie/{name}
- **캐시**: 6시간
- **소스**: `api.crlkd.me/cookies/{name}` (비공식)
- **응답**: `{name, rarity, type, skill, topping_recommendation}`

### GET /api/v1/game/ovensmash/character/{name}
- **캐시**: 6시간
- **소스**: 커뮤니티 위키 API
- **응답**: `{name, type, stats, skills, combo_tips}`

### GET /api/v1/game/devsisters/news
- **캐시**: 30분
- **소스**: Devsisters 공식 RSS
- **응답**: `[{game, title, date, type: 이벤트|쿠폰|업데이트|점검, url}]`

### GET /api/v1/game/coupon
- **Query params**: `game` (`maple`|`fc`|`pubg`|`lol`|`valorant`|`bdo`|`dnf`|`cookierun`|`ovensmash`)
- **캐시**: 10분
- **소스**: 각 게임사 공지 RSS + 인벤·루리웹 RSS 파싱
- **로직**: 쿠폰 코드 패턴 정규식 추출, 만료일 추정 (공지 날짜 + 30일 기본)
- **응답**: `[{code, game, source, issued_date, estimated_expiry, rewards}]`

### GET /api/v1/game/coupon/all
- **캐시**: 10분
- **응답**: 전 게임 쿠폰 통합, 만료 임박순 정렬

### GET /api/v1/game/event
- **Query params**: `game`
- **캐시**: 30분
- **소스**: 넥슨 API 이벤트 + 각 게임사 RSS
- **응답**: `[{title, game, start, end, rewards_summary, url}]`

### GET /api/v1/game/event/all
- **캐시**: 30분
- **응답**: 전 게임 이벤트 통합 캘린더, 시작일순

### GET /api/v1/game/event/ending
- **Query params**: `days` (기본 3)
- **캐시**: 30분
- **로직**: `end_date <= today + days` 필터
- **응답**: `[{title, game, end, remaining_days}]`

### GET /api/v1/game/maintenance
- **캐시**: 10분
- **소스**: 각 게임사 공지 RSS — 점검 키워드 필터
- **응답**: `[{game, title, start, end, is_ongoing, estimated_restore}]`

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| Riot API 키 한도 초과 | 429 + Retry-After |
| 넥슨 캐릭터 없음 | 404 "캐릭터를 찾을 수 없습니다" |
| 비공식 API (쿠키런) 응답 없음 | 503 + "커뮤니티 API 일시 불가" |
| RSS 파싱 실패 | 해당 소스 제외, 나머지 반환 |
| 스타포스 계산 item 없음 | 422 + 지원 장비 목록 |

---

## 구현 순서

1. `lol.py` — summoner, match (Riot API 기본)
2. `maple.py` — character 조회 (넥슨 API)
3. `maple.py` — damage, starforce 계산기
4. `lol.py` — dps 계산기
5. `pubg.py` — player 전적
6. `fc.py`, `dnf.py` — 넥슨 API 재활용
7. `coupon.py` — RSS 파싱
8. `event.py` — 이벤트 + 점검
9. `cookierun.py` — 비공식 API + Devsisters RSS

---

## 의존성
- `requests` (기존)
- `feedparser` (신규 — card 그룹과 공유)
- `numpy` (스타포스 몬테카를로)
- 환경변수: `RIOT_API_KEY`, `NEXON_API_KEY`, `PUBG_API_KEY`, `NEOPLE_API_KEY`, `BDO_API_KEY`

## 추가 환경변수 (.env에 추가 필요)
```
RIOT_API_KEY=
NEXON_API_KEY=
PUBG_API_KEY=
NEOPLE_API_KEY=
BDO_API_KEY=
KOPIS_API_KEY=
TOUR_API_KEY=
CULTURE_API_KEY=
LIBRARY_API_KEY=
EMUSEUM_API_KEY=
FINLIFE_API_KEY=
OPINET_API_KEY=
KAMIS_API_KEY=
KAMIS_CERT_KEY=
HIRA_API_KEY=
MFDS_API_KEY=
EX_API_KEY=
SEOUL_API_KEY=
ODSAY_API_KEY=
```
