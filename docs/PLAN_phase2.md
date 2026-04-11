# Phase 2 세부 기획안

> 대상: D-2 (연준·금리 감성), D-3 (암호화폐 스냅샷), W-3 (크립토 vs 전통자산), W-4 (KOSPI 3각 관계), M-3 (경기 사이클 좌표)
> 신규 차트 함수 2개(plot_gauge, plot_regime_path) 추가 후 리포트 빌더 3개 추가.

---

## 1. 변경 대상 파일 및 작업 범위

| 파일 | 작업 | 콘텐츠 |
|------|------|--------|
| `visualization/charts.py` | `plot_gauge()` 추가 | D-2, D-3 게이지 |
| `visualization/charts.py` | `plot_regime_path()` 추가 | M-3 PMI-CPI 사분면 |
| `visualization/report.py` | `build_d2_report()` 추가 | D-2 연준·금리 감성 |
| `visualization/report.py` | `build_d3_report()` 추가 | D-3 암호화폐 스냅샷 |
| `visualization/report.py` | `build_w3_report()` 추가 | W-3 크립토 vs 전통자산 |
| `visualization/report.py` | `build_w4_report()` 추가 | W-4 KOSPI 3각 관계 |
| `visualization/report.py` | `build_m3_report()` 추가 | M-3 경기 사이클 좌표 |
| `main.py` | `--mode` choices 확장 | d2/d3/w3/w4/m3 추가 |

---

## 2. 신규 차트 함수 시그니처

### 2-1. `plot_gauge()`

```python
def plot_gauge(
    value: float,                  # 0 ~ 100 사이 값
    title: str,
    low_label: str = "극공포",
    high_label: str = "극탐욕",
    thresholds: list[tuple[float, str]] | None = None,
    # 기본: [(20,"공포"),(40,"중립 하"), (60,"중립 상"), (80,"탐욕")]
) -> go.Figure:
    """
    0~100 반원형 게이지 차트.

    구간 색상:
      0~20   → #e74c3c (극공포/매우 부정)
      20~40  → #e67e22 (공포/부정)
      40~60  → #f1c40f (중립)
      60~80  → #2ecc71 (탐욕/긍정)
      80~100 → #27ae60 (극탐욕/매우 긍정)

    사용처:
      - D-2: 뉴스 감성 점수 (-1~1 → 0~100 변환)
      - D-3: BTC 도미넌스 (0~100 직접 사용)
      - Phase 4: 공포-탐욕 지수

    Returns: go.Figure (indicator gauge)
    """
```

변환 규칙:
- 감성 점수 (-1~1) → `(score + 1) / 2 * 100` → 0~100
- 도미넌스 (%) → 직접 사용

---

### 2-2. `plot_regime_path()`

```python
def plot_regime_path(
    pmi_series: pd.Series,
    cpi_series: pd.Series,
    lookback_months: int = 12,
    title: str = "미국 경기 사이클 좌표 (PMI-CPI)",
) -> go.Figure:
    """
    PMI-CPI 2차원 사분면 플롯 + 최근 N개월 이동 경로.

    사분면 배경:
      우상단 (PMI↑ CPI↑): overheat  → 주황 배경
      좌상단 (PMI↓ CPI↑): stagflation → 빨강 배경
      좌하단 (PMI↓ CPI↓): deflation  → 파랑 배경
      우하단 (PMI↑ CPI↓): reflation  → 초록 배경

    이동 경로:
      - 최근 lookback_months 개월의 (PMI_zscore, CPI_zscore) 좌표
      - 오래된 점: 회색 작은 원
      - 최신 점: 큰 원 + 국면명 텍스트 레이블
      - 경로: 점선 화살표

    축:
      x축: PMI Z-Score (변화율 기준)
      y축: CPI Z-Score (변화율 기준)
      중심선: x=0, y=0 (PMI/CPI 방향 전환점)

    Returns: go.Figure
    """
```

구현 방식:
- PMI, CPI 각각 `diff(6)` → Z-Score 정규화 → 좌표계
- `go.Scatter` mode="lines+markers"로 경로 표시
- `layout.shapes`로 4개 사분면 배경색 직사각형

---

## 3. 리포트 빌더 시그니처

### D-2: `build_d2_report()`

```python
def build_d2_report(master, date=None, output_path=None) -> str:
```
출력: `reports/daily/d2_sentiment_{date}.html`

포함 섹션:
1. 뉴스 감성 게이지 (global + fed 각각)
2. 감성 점수 7일 이동평균 라인 차트
3. 금리 현황 테이블 (rate_fed, rate_us10y, rate_us2y, rate_spread_10_2)

데이터 가용성 주의:
- `sent_news_global`, `sent_news_fed`: 최근 30일만 존재
- 30일치 라인 차트로 표시 (단기 트렌드)

---

### D-3: `build_d3_report()`

```python
def build_d3_report(master, date=None, output_path=None) -> str:
```
출력: `reports/daily/d3_crypto_{date}.html`

포함 섹션:
1. BTC 도미넌스 게이지
2. BTC/ETH 24h 등락률 (plot_daily_returns 재활용, crypto 컬럼만)
3. 시총 + BTC/ETH 가격 라인 차트 (최근 90일)

---

### W-3: `build_w3_report()`

```python
def build_w3_report(master, week_end=None, output_path=None) -> str:
```
출력: `reports/weekly/w3_crypto_corr_{date}.html`

포함 섹션:
1. BTC-S&P500 rolling 30일 Spearman 상관 (plot_rolling_correlation 재활용)
2. BTC-Gold rolling 30일 Spearman 상관
3. BTC-VIX rolling 30일 Spearman 상관
4. 현재 상관계수 요약 테이블

---

### W-4: `build_w4_report()`

```python
def build_w4_report(master, week_end=None, output_path=None) -> str:
```
출력: `reports/weekly/w4_kospi_triangle_{date}.html`

포함 섹션:
1. KOSPI-USD/KRW rolling 30일 상관
2. KOSPI-US10Y rolling 30일 상관
3. KRW-US10Y rolling 30일 상관
4. 산점도 3개 (각 쌍, 추세선 포함)

---

### M-3: `build_m3_report()`

```python
def build_m3_report(master, month_end=None, output_path=None) -> str:
```
출력: `reports/monthly/m3_cycle_{date}.html`

포함 섹션:
1. PMI-CPI 사분면 이동 경로 (plot_regime_path, 12개월)
2. 6개 거시 지표 Z-Score 레이더 차트
3. 현재 국면 + 권장 자산 카드

---

## 4. main.py --mode 확장

```python
choices=["daily", "weekly", "monthly", "all",
         "d1", "d2", "d3", "w2", "w3", "w4", "m1", "m3"]
```

`all` = d1 + d2 + d3 + w2 + w3 + w4 + m1 + m3 (Phase 2 완료 시)

---

## 5. 구현 순서

```
Step 1: charts.py — plot_gauge() 구현
Step 2: charts.py — plot_regime_path() 구현
Step 3: report.py — build_d2_report() 구현
Step 4: report.py — build_d3_report() 구현
Step 5: report.py — build_w3_report() 구현
Step 6: report.py — build_w4_report() 구현
Step 7: report.py — build_m3_report() 구현
Step 8: main.py --mode 확장
Step 9: 전체 테스트
```

---

## 6. 엣지케이스 정리

| 상황 | 처리 |
|------|------|
| sent_news_* 데이터 없음 (30일 이전 start) | 게이지 생략, 경고 텍스트 표시 |
| crypto 데이터 365일 미만 | rolling 상관 window 조정 (min 30일) |
| PMI/CPI Z-Score 계산 시 분산=0 | ZeroDivision 방지, 0으로 처리 |
| rolling 상관 데이터 부족 (< window) | 빈 Figure 반환, 섹션 skip |
| KOSPI 데이터 없음 (장 마감 후 pykrx) | W-4 섹션 skip + 경고 |
