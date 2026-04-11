# Phase 1 세부 기획안

> 대상: D-1 (글로벌 시황 브리핑), W-2 (매크로 국면), M-1 (월간 종합 리포트), M-4 (백테스팅 성과)
> 기존 모듈 조합으로 구현 가능한 항목. 신규 파일 없이 기존 파일에 함수/섹션 추가.

---

## 1. 변경 대상 파일 및 작업 범위

| 파일 | 작업 | 비고 |
|------|------|------|
| `visualization/charts.py` | `plot_daily_returns()` 추가 | D-1 자산 등락 바 차트 |
| `visualization/charts.py` | `plot_regime_timeline()` 추가 | W-2 국면 타임라인 컬러 바 |
| `visualization/report.py` | `build_daily_report()` 신규 함수 | D-1 전용 HTML 리포트 |
| `visualization/report.py` | `build_weekly_report()` 신규 함수 | W-2 전용 HTML 리포트 |
| `visualization/report.py` | `build_report()` 섹션 보강 | M-1 기존 함수에 국면 타임라인 + 백테스팅 섹션 개선 |

> M-1, M-4는 기존 `build_report()` 내부에 이미 섹션이 있음.
> 개선 범위: 국면 섹션에 타임라인 차트 추가, 백테스팅 섹션 지표 표시 개선.

---

## 2. 신규 함수 시그니처

### 2-1. `charts.py` — `plot_daily_returns()`

```python
def plot_daily_returns(
    master: pd.DataFrame,
    date: str | None = None,          # None이면 마지막 영업일
    cols: list[str] | None = None,    # None이면 _DAILY_COLS 기본값
) -> go.Figure:
    """
    지정 날짜의 전일 대비 등락률 수평 바 차트.

    - 양수: 초록(#2ecc71), 음수: 빨강(#e74c3c)
    - 막대 우측에 등락률 텍스트 표시
    - VIX는 별도 주석 카드로 표시

    Returns: go.Figure
    """
```

기본 대상 컬럼 (`_DAILY_COLS`):
```python
_DAILY_COLS = [
    "us_sp500_close", "us_nasdaq_close", "kr_kospi_close",
    "cmd_wti_close", "cmd_gold_close", "fx_krw_usd_close",
    "crypto_btc_close", "crypto_eth_close",
]
```

입력/출력 스펙:
- 입력: master DataFrame (DatetimeIndex), date 문자열 'YYYY-MM-DD'
- 출력: go.Figure (수평 막대 차트)
- 엣지케이스: date 해당일 데이터 없으면 직전 유효일 사용; 컬럼 없으면 skip

---

### 2-2. `charts.py` — `plot_regime_timeline()`

```python
def plot_regime_timeline(
    regime_series: pd.Series,          # classify_regime() 반환값
    title: str = "매크로 국면 타임라인",
) -> go.Figure:
    """
    국면 히스토리를 컬러 바(gantt-style) 로 표시.

    국면 색상:
      reflation   → #2ecc71 (초록)
      overheat    → #e67e22 (주황)
      stagflation → #e74c3c (빨강)
      deflation   → #3498db (파랑)

    Returns: go.Figure
    """
```

구현 방식: `go.Bar` 또는 `go.Scatter`의 fill 방식으로 구간별 색상 표시.
Gantt 방식: 국면 연속 구간을 `go.Scatter` shapes로 그림.

입력/출력 스펙:
- 입력: pd.Series (index=DatetimeIndex, values=국면명 문자열)
- 출력: go.Figure
- 엣지케이스: NaN 구간은 회색 처리; 전체 NaN이면 빈 Figure

---

### 2-3. `report.py` — `build_daily_report()`

```python
def build_daily_report(
    master: pd.DataFrame,
    date: str | None = None,
    output_path: str | None = None,
) -> str:
    """
    D-1 일간 시황 브리핑 HTML 리포트.

    포함 섹션:
      1. 헤더 카드: 날짜, 현재 국면, VIX 레벨
      2. 자산별 등락률 바 차트 (plot_daily_returns)
      3. 주요 거시 지표 현황 테이블 (금리, 스프레드 수준값)

    Returns: 저장 경로(str)
    """
```

출력 파일명: `reports/daily/daily_{date}.html`

---

### 2-4. `report.py` — `build_weekly_report()`

```python
def build_weekly_report(
    master: pd.DataFrame,
    week_end: str | None = None,       # None이면 마지막 영업일 포함 주
    output_path: str | None = None,
) -> str:
    """
    W-2 매크로 국면 주간 리포트 HTML.

    포함 섹션:
      1. 현재 국면 강조 카드
      2. 12개월 국면 타임라인 (plot_regime_timeline)
      3. 국면별 권장 자산 테이블

    Returns: 저장 경로(str)
    """
```

출력 파일명: `reports/weekly/weekly_{week_end}.html`

---

## 3. `build_report()` 개선 범위 (M-1, M-4)

기존 섹션 3 (매크로 국면): 텍스트+테이블 → **`plot_regime_timeline()` 차트 추가**
기존 섹션 4 (백테스팅): 성과 지표 HTML 포맷 개선 (테이블로 정리)

변경 없는 것: 섹션 1(상관 히트맵), 섹션 2(누적 수익률)

---

## 4. 구현 순서

```
Step 1: charts.py — plot_daily_returns() 구현 + 단위 테스트
Step 2: charts.py — plot_regime_timeline() 구현 + 단위 테스트
Step 3: report.py — build_daily_report() 구현
Step 4: report.py — build_weekly_report() 구현
Step 5: report.py — build_report() 국면 섹션에 타임라인 차트 연동
Step 6: main.py — --mode 인자 추가 (daily / weekly / monthly)
Step 7: 전체 파이프라인 실행 테스트
```

---

## 5. main.py 변경 사항

```python
parser.add_argument(
    "--mode",
    choices=["daily", "weekly", "monthly", "all"],
    default="all",
    help="생성할 리포트 종류",
)
```

- `daily`  → `build_daily_report(master)`
- `weekly` → `build_weekly_report(master)`
- `monthly`/`all` → `build_report(master)` (기존)

---

## 6. 엣지케이스 정리

| 상황 | 처리 방법 |
|------|----------|
| 요청 날짜에 시장 데이터 없음 | 직전 유효 거래일 데이터 사용 |
| 전일 데이터 없어 pct_change 계산 불가 | 해당 자산 skip, 로그 경고 |
| 국면 분류 NaN 구간 | 회색으로 표시, "데이터 부족" 주석 |
| master에 pmi/cpi 컬럼 없음 | 국면 섹션 전체 skip |
| reports/daily/ 디렉토리 없음 | 자동 mkdir |
