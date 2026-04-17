# PLAN — index (글로벌 주요 지수)

## 개요
yfinance·FRED·CBOE 등 이미 사용 중인 소스를 재활용해 글로벌 지수 전용 라우터를 구성한다.
finance 그룹이 파이프라인 결과 제공에 집중하는 반면, index는 실시간 지수 조회·비교·분석에 특화된다.

---

## 파일 구조

```
api/routers/index/
├── __init__.py
├── equity.py       # /index/snapshot, /us, /asia, /europe
├── dollar.py       # /index/dollar
├── volatility.py   # /index/vix
├── sector.py       # /index/sector
├── bond.py         # /index/bond
├── commodity.py    # /index/commodity
└── analysis.py     # /index/history/{symbol}, /index/correlation
```

---

## 심볼 정의

```python
SYMBOLS = {
    "us":        ["^GSPC", "^IXIC", "^DJI", "^RUT"],
    "korea":     ["^KS11", "^KQ11", "^KRX300"],
    "asia":      ["^N225", "^HSI", "000001.SS", "^TWII", "^STI"],
    "europe":    ["^GDAXI", "^FTSE", "^FCHI", "^STOXX50E"],
    "emerging":  ["EEM", "^BVSP", "^NSEI"],
    "dollar":    ["DX-Y.NYB"],          # DXY
    "vix":       ["^VIX", "^VIX9D", "^VIX3M", "^VVIX"],
    "sector":    ["XLK","XLE","XLF","XLV","XLI","XLU","XLY","XLP","XLB","XLRE"],
    "bond":      ["^TNX", "^IRX", "^TYX"],   # 10Y, 2Y, 30Y
    "commodity": ["GC=F","CL=F","HG=F","^BCOM"],
}
```

---

## 엔드포인트 상세

### GET /api/v1/index/snapshot
- **설명**: 전체 주요 지수 현재가·등락률 한눈에
- **캐시**: 5분
- **로직**: SYMBOLS 전체 yfinance `.info` 또는 `.history(period="2d")` 호출 → 전일 종가 대비 등락률 계산
- **응답**:
```json
{
  "status": "ok",
  "timestamp": "2026-04-15T09:00:00Z",
  "data": {
    "us":      [{"symbol":"^GSPC","name":"S&P 500","price":5200.1,"change_pct":0.43}],
    "korea":   [...],
    "asia":    [...],
    "europe":  [...],
    "dollar":  {"symbol":"DX-Y.NYB","price":104.2,"change_pct":-0.21},
    "vix":     {"symbol":"^VIX","price":18.3,"change_pct":-3.1}
  }
}
```

### GET /api/v1/index/dollar
- **캐시**: 10분
- **소스**: yfinance DX-Y.NYB + FRED DTWEXBGS (무역가중달러)
- **응답 추가 필드**: 구성통화 비중 (EUR 57.6%, JPY 13.6%, GBP 11.9%, CAD 9.1%, SEK 4.2%, CHF 3.6%)
- **에러**: FRED 키 없으면 yfinance DXY만 반환

### GET /api/v1/index/vix
- **캐시**: 5분
- **추가 계산**: VIX 레벨 해석 자동 태깅
  - `< 15` → "저변동성 (안도)"
  - `15~25` → "보통"
  - `25~35` → "불안"
  - `> 35` → "공황"
- **응답 추가 필드**: `term_structure` (VIX9D vs VIX vs VIX3M 콘탱고/백워데이션)

### GET /api/v1/index/sector
- **캐시**: 10분
- **소스**: XLK·XLE·XLF 등 섹터 ETF yfinance
- **응답**: 섹터별 `{name, etf, price, change_pct, ytd_pct}` 배열 (change_pct 내림차순 정렬)

### GET /api/v1/index/bond
- **캐시**: 10분
- **추가 계산**:
  - `spread_10y2y = TNX - IRX` (장단기 스프레드)
  - 역전 여부 플래그: `inverted: true/false`

### GET /api/v1/index/history/{symbol}
- **Path param**: `symbol` (URL 인코딩 필요 — `^GSPC` → `%5EGSPC`)
- **Query param**: `days` (기본 90, 최대 365)
- **캐시**: 10분
- **응답**: `[{date, open, high, low, close, volume}]`

### GET /api/v1/index/correlation
- **캐시**: 1시간
- **로직**: 최근 60일 일봉 수익률 기준 Pearson 상관계수 행렬
- **대상 심볼**: S&P500, 나스닥, KOSPI, 니케이, DXY, VIX, 금, WTI, BTC
- **응답**: 대칭 행렬 JSON

---

## 에러 케이스

| 케이스 | 처리 |
|--------|------|
| yfinance 응답 없음 (장 마감 후) | 직전 캐시값 반환 + `stale: true` 플래그 |
| 심볼 잘못됨 | 422 + "지원하지 않는 심볼" |
| FRED 키 없음 | FRED 데이터 제외하고 yfinance만 반환 |

---

## 구현 순서

1. `equity.py` — snapshot, us, asia, europe
2. `bond.py` — 장단기 스프레드 포함
3. `volatility.py` — VIX 레벨 태깅
4. `sector.py`
5. `dollar.py` — FRED 연동
6. `commodity.py`
7. `analysis.py` — history, correlation

---

## 의존성
- `yfinance` (기존)
- `fredapi` (기존)
- `pandas` (기존)
- 기존 `collectors/global_/market.py` 로직 재활용 가능
