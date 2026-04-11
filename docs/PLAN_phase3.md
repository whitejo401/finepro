# Phase 3 세부 기획안

> 대상: D-4 (KOSPI 예측), D-5 (미국→KOSPI 선행 분석), W-5 (예측 적중률 리뷰)
> 신규 파일: analysis/prediction.py
> 신규 리포트: build_d4_report, build_d5_report, build_w5_report

---

## 1. analysis/prediction.py 함수 목록

| 함수 | 설명 |
|------|------|
| `lag_correlation_rank(master, target, lag, top_n)` | shift(lag) 후 target과 상관 높은 컬럼 순위 반환 |
| `majority_vote_signal(master, feature_cols, target, lag)` | 상위 N 변수 부호 다수결 → +1/-1/0 |
| `rolling_logit_predict(master, feature_cols, target, window)` | 60일 롤링 LogisticRegression, 오늘 확률 반환 |
| `rolling_ols_gap(master, x_cols, target, window)` | OLS 갭 예측, R² 포함 |
| `save_prediction_log(date, pred_dir, actual)` | parquet 로그 저장 |
| `load_prediction_log(pred_dir)` | 로그 불러오기 + 누적 적중률 계산 |

---

## 2. 신규 리포트 함수

- `build_d4_report(master)` → `reports/daily/d4_kospi_pred_{date}.html`
- `build_d5_report(master)` → `reports/daily/d5_kospi_lead_{date}.html`
- `build_w5_report(master)` → `reports/weekly/w5_pred_accuracy_{date}.html`

---

## 3. 구현 시 주의사항

- lag=1: 미국 전일(T) → KOSPI 당일(T+1) — 룩어헤드 없음
- prediction_log: `data/processed/prediction_log.parquet`
- LogisticRegression: statsmodels Logit (계수 해석 가능)
- KOSPI 데이터 없을 시 yfinance kr_kospi_close 사용 (pykrx 대체)
