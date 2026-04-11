# 블로그 게시 가이드

이 프로젝트의 분석 결과물을 광고수익 블로그에 게시할 때 따라야 할 원칙과 체크리스트.

---

## 핵심 원칙

```
수집 → 분석 → [게시 가능한 것만 선별] → 블로그
                       ↑
              "분석 결과물"만 게시
              원시 데이터 게시 금지
```

이 프로젝트의 아웃풋(상관관계 히트맵, 국면 분류, 팩터 점수, 백테스팅 수익률)은
모두 가공된 분석 결과물이므로 **모든 API 무료 플랜 기준으로도 광고수익 블로그 게시 가능**하다.

---

## 게시 가능 / 불가 체크리스트

### ✅ 게시 가능한 콘텐츠

| 콘텐츠 | 설명 |
|-------|------|
| 상관관계 히트맵 | 자산 간 Spearman 상관계수 시각화 |
| 매크로 국면 차트 | PMI·CPI 기반 reflation/overheat/stagflation/deflation 분류 |
| 팩터 점수 추이 | PER·PBR·ROE 기반 저평가 점수 시리즈 |
| 백테스팅 수익률 | 전략 vs 벤치마크 누적 수익률 비교 |
| 감성 지수 | Reddit/뉴스 기반 자체 계산 심리 점수 (원문 아닌 수치) |
| 리스크 지표 | MDD, 샤프 비율, 변동성 등 파생 지표 |
| 국면별 자산 성과 표 | "과열 국면 평균 수익률: WTI +3.2%, KOSPI -0.8%" 형태 |
| 가격 차트 + 신호 오버레이 | 시장 가격 위에 매수/매도 신호, 국면 색상 표시 |

### ❌ 게시 금지 콘텐츠

| 콘텐츠 | 이유 |
|-------|------|
| 원시 가격 테이블 (종가 CSV 형태) | API 데이터 재배포에 해당 |
| 뉴스 헤드라인·기사 원문 | NewsAPI 약관 + 언론사 저작권 |
| Reddit 게시물 원문/스크린샷 대량 게시 | Reddit 저작권 및 약관 |
| "삼성전자 오늘 종가 XXX원" 단순 시세 나열 | KRX 데이터 직접 재배포 |
| API 응답 JSON/CSV 그대로 첨부 | 모든 API 공통 금지 |

---

## 리포트 생성 → 블로그 게시 워크플로우

```
1. python main.py 실행
        ↓
2. reports/report_YYYY-MM-DD.html 생성
        ↓
3. 아래 게시 전 체크리스트 확인
        ↓
4. 출처 표기 확인 후 블로그 게시
```

### 게시 전 체크리스트

- [ ] 원시 가격 테이블이 HTML에 포함되어 있지 않은가
- [ ] 차트 제목이 "분석 지표"임을 명확히 나타내는가 (예: "수익률 비교" O, "종가 데이터" X)
- [ ] 출처 표기(footer)가 있는가
- [ ] 투자 면책 문구가 있는가
- [ ] 특정 종목 매수/매도 추천 형태가 아닌가 (자본시장법 무인가 투자 조언 금지)

---

## 출처 표기 템플릿

블로그 게시물 하단 또는 차트 캡션에 사용:

**간략형:**
```
데이터 출처: DART, ECOS, FRED, Yahoo Finance | 본 내용은 투자 조언이 아닙니다.
```

**상세형:**
```
데이터 출처
- 국내 주식·재무: 금융감독원 전자공시시스템(DART), 한국거래소
- 국내 거시: 한국은행 경제통계시스템(ECOS)
- 글로벌 시장: Yahoo Finance
- 미국 거시: Federal Reserve Bank of St. Louis (FRED)
- 에너지: U.S. Energy Information Administration (EIA)

본 분석은 공개 데이터를 가공한 참고 자료이며 투자 조언이 아닙니다.
투자 결과에 대한 책임은 전적으로 투자자 본인에게 있습니다.
```

---

## 분석 결과물로 전환하는 원칙

원시 데이터를 그대로 게시하는 대신, 아래와 같이 변환한다.

| 원시 데이터 (게시 금지) | 분석 결과물 (게시 가능) |
|--------------------|-------------------|
| 삼성전자 일별 종가 테이블 | 삼성전자 12개월 모멘텀 점수 추이 |
| BTC/USD 가격 시계열 | BTC-KOSPI 60일 Rolling 상관계수 |
| CPI 원시 수치 | CPI 변화율 기반 국면 분류 차트 |
| Reddit 게시물 원문 | r/wallstreetbets 주간 감성 지수 (0~100) |
| 뉴스 헤드라인 목록 | 뉴스 감성 스코어 7일 이동평균 |

---

## 블로그 게시용 면책 문구 전문

블로그 게시물 하단에 아래 중 하나를 복사·붙여넣기 한다.
`visualization/disclaimer.py`의 `get_html_disclaimer()` / `get_text_disclaimer()`로 자동 삽입도 가능하다.

### 한국어 전문 (HTML, 리포트/블로그 본문)

```html
<strong>【 법적 고지 및 면책 사항 】</strong><br><br>

<strong>1. 투자 권유 아님</strong><br>
본 콘텐츠는 자본시장과 금융투자업에 관한 법률(자본시장법)에 따른 투자자문업 등록을 하지 않은
개인이 작성한 것으로, 특정 금융투자상품의 매수·매도를 권유하거나 추천하는 내용이 아닙니다.
본 내용은 순수하게 공개 데이터를 분석한 참고 자료이며, 어떠한 투자 결정의 근거로도
사용할 수 없습니다.<br><br>

<strong>2. 과거 성과는 미래 수익을 보장하지 않음</strong><br>
본 리포트에 포함된 백테스팅 결과, 수익률, 전략 성과 등은 과거 데이터를 기반으로 한
시뮬레이션 결과입니다. 과거의 성과가 미래의 수익을 보장하지 않으며,
실제 거래에서는 시장 충격, 유동성, 세금, 수수료 등 추가 비용이 발생합니다.<br><br>

<strong>3. 정보의 정확성·완전성 보장 불가</strong><br>
본 분석에 사용된 데이터는 DART, ECOS, FRED, Yahoo Finance 등 공개 출처에서 수집되었으며,
데이터 지연, 오류, 누락이 있을 수 있습니다. 작성자는 정보의 정확성, 완전성,
최신성에 대해 어떠한 보증도 하지 않으며, 이로 인해 발생한 손해에 대해 책임을 지지 않습니다.<br><br>

<strong>4. 투자 손실 책임</strong><br>
금융투자상품 투자는 원금 손실이 발생할 수 있으며, 투자 결과에 대한 모든 책임은
전적으로 투자자 본인에게 있습니다. 본 콘텐츠를 참고한 투자로 인한 손실에 대해
작성자는 어떠한 법적·도의적 책임도 지지 않습니다.<br><br>

<strong>5. 세금 및 개인 상황 고려</strong><br>
투자에 따른 세금(양도소득세, 금융투자소득세 등) 및 개인별 재무 상황은 본 분석에
반영되어 있지 않습니다. 실제 투자 전 세무사, 금융전문가 등 전문가의 상담을 권고합니다.<br><br>

<strong>6. 데이터 출처</strong><br>
국내 주식·재무: 금융감독원 전자공시시스템(DART), 한국거래소 &nbsp;|&nbsp;
국내 거시: 한국은행 경제통계시스템(ECOS) &nbsp;|&nbsp;
글로벌 시장: Yahoo Finance &nbsp;|&nbsp;
미국 거시: Federal Reserve Bank of St. Louis (FRED) &nbsp;|&nbsp;
에너지: U.S. Energy Information Administration (EIA)
```

### 한국어 간략형 (텍스트/마크다운)

```
본 콘텐츠는 투자 권유가 아닌 데이터 분석 참고 자료입니다.
과거 성과는 미래 수익을 보장하지 않으며,
투자 결과에 대한 책임은 전적으로 투자자 본인에게 있습니다.
금융투자상품 투자 시 원금 손실이 발생할 수 있습니다.
```

### 영어 전문 (HTML, 영문 블로그/국제 독자)

```html
<strong>[LEGAL DISCLAIMER]</strong><br><br>

<strong>1. Not Investment Advice</strong><br>
This content is produced by an individual and does not constitute investment advice,
a solicitation, or a recommendation to buy or sell any financial instrument.
The author is not a registered investment advisor.<br><br>

<strong>2. Past Performance</strong><br>
All backtesting results and historical performance data shown are simulations based on
historical data. Past performance does not guarantee future results. Actual trading
results may differ materially due to market impact, liquidity constraints, taxes, and fees.<br><br>

<strong>3. No Warranty</strong><br>
Data is sourced from publicly available APIs (DART, ECOS, FRED, Yahoo Finance, EIA, etc.)
and may contain errors, delays, or omissions. The author makes no representations
regarding the accuracy, completeness, or timeliness of any information.<br><br>

<strong>4. Limitation of Liability</strong><br>
Investing in financial instruments involves risk of loss, including loss of principal.
The author accepts no liability for any losses arising from use of this content.<br><br>

<strong>5. Consult a Professional</strong><br>
Before making any investment decision, consult a qualified financial advisor,
tax professional, or other relevant expert.
```

---

## 자본시장법 관련 주의사항

분석 결과를 블로그에 게시할 때 **무인가 투자 자문업** 해당 여부에 주의한다.

| 행위 | 판단 |
|-----|------|
| "현재 매크로 국면은 리플레이션이며 주식에 유리한 환경" | ✅ 분석/정보 제공 |
| "KOSPI가 상승할 것으로 전망됩니다" | ⚠️ 전망 제시 — 면책 문구 필수 |
| "삼성전자 매수 추천, 목표가 80,000원" | ❌ 투자 자문업 해당 가능성 |
| "백테스팅 결과 이 전략의 과거 샤프비율은 1.2" | ✅ 과거 성과 데이터 제시 |

**핵심 기준**: 특정 종목의 매수/매도를 직접 권유하지 않고, 분석 방법론과 결과를 공유하는 형태로 게시한다.
