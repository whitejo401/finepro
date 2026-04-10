# Claude Code 최적 활용 매뉴얼

## 1. 핵심 개념 이해

### 하네스(Harness)란?
에이전트의 입력·출력·도구 접근을 체계적으로 제어하는 설정 시스템.
모델 자체를 바꾸는 것보다 **하네스 최적화**가 더 큰 성능 향상을 가져온다.

6가지 레버:
| 레버 | 파일/위치 | 역할 |
|------|----------|------|
| 시스템 프롬프트 | `CLAUDE.md` | 행동 지침, 프로젝트 컨텍스트 주입 |
| 서브에이전트 | `.claude/agents/*.md` | 특화 작업 위임, 컨텍스트 절약 |
| 훅(Hooks) | `settings.json` | 도구 호출 전후 자동 실행 |
| 스킬(Skills) | `.claude/skills/` | 반복 워크플로우 정의 |
| MCP 서버 | `settings.json` | 외부 도구 연결 |
| 백프레셔 | 플랜 승인, 리뷰 | 검증 게이트 |

### CLAUDE.md vs AGENTS.md
- **CLAUDE.md**: Claude Code 전용. 세션 시작 시 자동으로 시스템 프롬프트에 주입됨
- **AGENTS.md**: Codex, Cursor 등 다른 AI 에이전트 시스템에서 사용하는 동일 개념의 파일
- Claude Code에서는 `CLAUDE.md`를 사용한다

### 멀티 에이전트 아키텍처
```
사용자
  ↓
메인 Claude (오케스트레이터)
  ├── Plan 에이전트 → 설계 계획 반환
  ├── Explore 에이전트 → 리서치 결과 반환
  ├── code-reviewer 에이전트 → 리뷰 결과 반환
  └── [프로젝트 전용 에이전트들]
       ├── data-collector → 수집 코드 작성
       ├── quant-analyst → 분석 코드 작성
       └── macro-researcher → 매크로 분석 반환
```
각 서브에이전트는 **독립된 컨텍스트 윈도우**에서 실행 → 메인 컨텍스트 절약

---

## 2. 설치된 파일 구조

```
C:\Users\sence\.claude\                  ← 글로벌 (모든 프로젝트)
├── CLAUDE.md                            ← 전역 행동 지침
├── settings.json                        ← hooks, 권한 설정
└── agents\
    ├── planner.md                       ← 설계 계획 전문
    ├── researcher.md (Explore)          ← 리서치/탐색 전문
    ├── code-reviewer.md                 ← 코드 리뷰 전문
    └── security-reviewer.md             ← 보안 감사 전문

D:\prosrc\AI\fine\                       ← 이 프로젝트
├── CLAUDE.md                            ← 프로젝트 지침 (데이터 소스 목록 포함)
├── .env.example                         ← API 키 템플릿
└── .claude\
    └── agents\
        ├── data-collector.md            ← 금융 데이터 수집 전문
        ├── quant-analyst.md             ← 퀀트 분석 전문
        └── macro-researcher.md          ← 글로벌 매크로 분석 전문
```

---

## 3. 서브에이전트 사용법

### 자동 라우팅
Claude가 작업 내용에 맞는 에이전트를 자동으로 선택한다.

### 명시적 호출
```
/plan [작업 설명]          → Plan 에이전트 호출
@Explore [검색할 내용]     → Explore 에이전트 호출
```

또는 자연어로:
```
"이 기능 구현 전에 Plan 에이전트로 설계 검토해줘"
"code-reviewer로 방금 작성한 코드 리뷰해줘"
"macro-researcher로 오늘 CPI 발표가 시장에 어떤 영향 줄지 분석해줘"
```

### 서브에이전트 파일 구조
```markdown
---
name: 에이전트이름
description: 언제 이 에이전트를 사용하는지 (자동 라우팅에 사용됨)
model: claude-haiku-4-5-20251001  # 선택사항. 간단한 작업엔 Haiku로 절약
tools:                             # 선택사항. 없으면 모든 도구 허용
  - Read
  - Grep
---

시스템 프롬프트 내용
```

**모델 선택 기준:**
- `claude-haiku-4-5-20251001`: 탐색, 검색, 단순 분류 (빠르고 저렴)
- `claude-sonnet-4-6` (기본값): 대부분의 작업
- `claude-opus-4-6`: 복잡한 설계, 어려운 분석

---

## 4. CLAUDE.md 작성 가이드

### 핵심 원칙
- **60줄 이하 유지** (너무 길면 오히려 성능 저하)
- LLM이 자동 생성한 내용 금지 (직접 작성만)
- 실패가 발생한 후에만 규칙 추가 (선제적 규칙 남발 금지)
- 조건부 규칙 최소화

### 계층 구조
```
~/.claude/CLAUDE.md          ← 항상 로드 (전역)
프로젝트/CLAUDE.md           ← 해당 프로젝트에서 추가 로드
프로젝트/src/CLAUDE.md       ← 해당 디렉토리에서 추가 로드 (선택)
```

### 좋은 CLAUDE.md 예시
```markdown
# 프로젝트명

## 기술 스택
- Python 3.10, FastAPI, PostgreSQL

## 실행 방법
- 테스트: `pytest tests/`
- 서버: `uvicorn main:app --reload`

## 규칙
- DB 직접 접근 금지, 반드시 Repository 계층 통해서
- 환경 변수는 config.py의 Settings 클래스로만 접근
```

---

## 5. Hooks 설정

현재 설정된 훅 (`~/.claude/settings.json`):

### PreToolUse - Bash 안전 검사
위험한 명령어(`rm -rf`, `git push --force` 등) 포함 시 자동 차단.

### 훅 추가 방법
`~/.claude/settings.json`의 `hooks` 섹션에 추가:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python -c \"import sys,json; d=json.load(sys.stdin); print(f'파일 저장됨: {d.get(\\\"tool_input\\\",{}).get(\\\"file_path\\\",\\\"\\\")}')\""
          }
        ]
      }
    ]
  }
}
```

### 훅 이벤트 종류
| 이벤트 | 타이밍 | 용도 |
|--------|--------|------|
| PreToolUse | 도구 호출 직전 | 검증, 차단 (exit 2로 차단) |
| PostToolUse | 도구 호출 직후 | 로깅, 후처리 |
| Stop | 에이전트 중지 시 | 세션 요약 저장 |
| Notification | 알림 발생 시 | 외부 알림 연동 |

---

## 6. 효율적 작업 패턴

### 패턴 1: 계획 먼저, 구현 나중
```
나쁜 방법: "로그인 기능 만들어줘" → 즉시 코드 작성
좋은 방법: "/plan 로그인 기능 구현" → 계획 검토 → 승인 → 구현
```

### 패턴 2: 병렬 서브에이전트
독립적인 작업은 동시에 처리:
```
"pykrx 수집기와 yfinance 수집기를 동시에 만들어줘"
→ Claude가 두 서브에이전트를 병렬로 실행
```

### 패턴 3: 컨텍스트 절약
```
나쁜 방법: 메인 세션에서 모든 파일 읽고 분석
좋은 방법: "Explore 에이전트로 data/raw 폴더 구조 파악해줘"
           → 서브에이전트가 탐색, 요약만 반환
```

### 패턴 4: 계약형 프롬프트 (브런치 글 핵심)
```
나쁜 방법: "FRED 데이터 수집 코드 짜줘"
좋은 방법: "
  목표: fredapi로 미국 CPI, 금리, M2 수집
  제약: .env에서 API 키 로드, 캐싱 지원, DataFrame 반환
  역할: 시니어 Python 개발자로서 production-ready 코드 작성
  반론: 이 설계에서 문제가 될 수 있는 부분도 함께 알려줘
"
```

### 패턴 5: 반복 심화
한 번의 대화로 끝내지 말고 단계적으로:
```
1단계: "pykrx 기본 수집기 작성"
2단계: "에러 케이스 추가해줘"
3단계: "code-reviewer로 검토해줘"
4단계: "지적된 문제 수정해줘"
```

---

## 7. 이 프로젝트 전용 워크플로우

### 데이터 수집 작업 시
```
1. data-collector 에이전트로 수집기 코드 작성
2. code-reviewer로 코드 검토
3. security-reviewer로 API 키 노출 여부 확인
```

### 분석 작업 시
```
1. macro-researcher로 관련 매크로 환경 파악
2. quant-analyst로 분석 코드 작성
3. Explore 에이전트로 기존 코드 파악 후 통합
```

### 새 데이터 소스 추가 시
```
1. /plan으로 설계 검토
2. data-collector로 수집기 구현
3. CLAUDE.md의 데이터 소스 목록 업데이트
```

---

## 8. 새 프로젝트에 적용하는 방법

글로벌 에이전트(planner, researcher, code-reviewer, security-reviewer)는
**모든 프로젝트에서 자동으로 사용 가능**하다.

새 프로젝트에서 추가로 할 일:
```bash
# 1. 프로젝트 루트에 CLAUDE.md 생성
# 2. 프로젝트 전용 에이전트 필요 시:
mkdir .claude/agents
# 3. 에이전트 파일 생성 (위 구조 참고)
```

프로젝트 CLAUDE.md에 포함할 것:
- 기술 스택
- 테스트/실행 명령어
- 프로젝트 특화 규칙 (디렉토리 구조, 네이밍 컨벤션)
- 핵심 도메인 지식 (이 프로젝트의 경우 데이터 소스 목록)

---

## 9. 참고 자료

- [Claude Code 공식 서브에이전트 문서](https://code.claude.com/docs/en/sub-agents)
- [Everything Claude Code (GitHub)](https://github.com/affaan-m/everything-claude-code)
- [Harness Engineering 가이드](https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents)
- [멀티 에이전트 코딩 패턴](https://news.hada.io/topic?id=28303)
