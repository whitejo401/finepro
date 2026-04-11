"""
visualization/disclaimer.py

법적 면책 문구 모음. 리포트 HTML, 블로그 게시물 등에서 재사용한다.

근거 법령:
- 자본시장과 금융투자업에 관한 법률(자본시장법) 제17조, 제37조, 제178조
- 정보통신망 이용촉진 및 정보보호 등에 관한 법률
"""

# ── 한국어 전문 면책 문구 ────────────────────────────────────────────────────

DISCLAIMER_KO_FULL = """
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
"""

# ── 한국어 간략 면책 문구 (블로그 게시물 본문 하단 등) ─────────────────────

DISCLAIMER_KO_SHORT = (
    "본 콘텐츠는 투자 권유가 아닌 데이터 분석 참고 자료입니다. "
    "과거 성과는 미래 수익을 보장하지 않으며, "
    "투자 결과에 대한 책임은 전적으로 투자자 본인에게 있습니다. "
    "금융투자상품 투자 시 원금 손실이 발생할 수 있습니다."
)

# ── 영어 면책 문구 (영문 블로그/국제 독자용) ───────────────────────────────

DISCLAIMER_EN_FULL = """
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
"""

DISCLAIMER_EN_SHORT = (
    "For informational purposes only. Not investment advice. "
    "Past performance does not guarantee future results. "
    "All investments involve risk of loss."
)


def get_html_disclaimer(lang: str = "ko", length: str = "full") -> str:
    """
    HTML 면책 문구 반환.

    Args:
        lang:   'ko' | 'en'
        length: 'full' | 'short'
    Returns:
        HTML 문자열
    """
    mapping = {
        ("ko", "full"):  DISCLAIMER_KO_FULL,
        ("ko", "short"): f"<p>{DISCLAIMER_KO_SHORT}</p>",
        ("en", "full"):  DISCLAIMER_EN_FULL,
        ("en", "short"): f"<p>{DISCLAIMER_EN_SHORT}</p>",
    }
    return mapping.get((lang, length), DISCLAIMER_KO_FULL)


def get_text_disclaimer(lang: str = "ko") -> str:
    """마크다운/텍스트용 면책 문구 (HTML 태그 없음)."""
    if lang == "en":
        return (
            "DISCLAIMER: For informational purposes only. Not investment advice. "
            "Past performance does not guarantee future results. "
            "Investing involves risk of loss of principal."
        )
    return (
        "【면책 고지】 본 콘텐츠는 투자 권유가 아닌 데이터 분석 참고 자료입니다. "
        "과거 성과는 미래 수익을 보장하지 않으며, 금융투자상품 투자 시 원금 손실이 발생할 수 있습니다. "
        "투자 결과에 대한 책임은 전적으로 투자자 본인에게 있습니다."
    )
