# Phase 4 세부 기획안

> 대상: M-5 (국면별 자산 성과), M-6 (공포-탐욕 지수)
> 신규 파일: analysis/sentiment.py, analysis/fear_greed.py

---

## 1. analysis/sentiment.py
- `calc_sentiment_ma(master, windows)` — 7/30일 이동평균
- `composite_sentiment_score(master)` — sent_news_global + sent_news_fed 가중 합산 → -1~1

## 2. analysis/fear_greed.py
- `calc_fear_greed_index(master)` — 5개 지표 Z-Score 가중 합산 → 0~100
  - alt_vix_close (역방향, 공포 ↑ → 점수 ↓)
  - rate_hy_spread (역방향)
  - sent_news_global (정방향)
  - crypto_btc_dominance (정방향, 위험선호 ↑)
  - rate_spread_10_2 (정방향)

## 3. 신규 리포트
- `build_m5_report(master)` → `reports/monthly/m5_regime_perf_{date}.html`
- `build_m6_report(master)` → `reports/monthly/m6_fear_greed_{date}.html`
