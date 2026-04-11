"""
대체 데이터 수집기 — 뉴스 감성 점수 (NewsAPI).

수집 항목:
  - 글로벌 경제/시장 뉴스 헤드라인 감성 점수 (일별 평균)
  - 연준(Fed) 관련 뉴스 감성 점수 (일별 평균)

컬럼명 규칙: sent_ 접두사
  sent_news_global : 글로벌 경제 뉴스 감성 (-1 ~ 1)
  sent_news_fed    : 연준 관련 뉴스 감성 (-1 ~ 1)

주의:
  - 원문/헤드라인 직접 저장 금지 (NewsAPI 이용약관 — 원문 재배포 불가)
  - 감성 점수(float)만 캐싱
  - NEWS_API_KEY 없으면 빈 DataFrame 반환
  - 무료 플랜: 최근 1개월 데이터만 조회 가능, 하루 100건 제한
"""
from __future__ import annotations

import datetime as dt
from typing import Iterator

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache
from config import NEWS_API_KEY

log = get_logger("global.alt")

# 감성 분석 쿼리 정의
_QUERIES = {
    "global": "stock market economy recession inflation",
    "fed": "Federal Reserve interest rate monetary policy",
}


def _vader_score(text: str) -> float:
    """
    VADER 감성 분석기로 복합 감성 점수 반환 (-1 ~ 1).
    vaderSentiment 없으면 0.0 반환.
    """
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        return float(analyzer.polarity_scores(text)["compound"])
    except ImportError:
        log.warning("vaderSentiment 패키지 없음 — pip install vaderSentiment")
        return 0.0


def _fetch_articles(
    query: str,
    from_date: str,
    to_date: str,
    page_size: int = 100,
) -> Iterator[str]:
    """
    NewsAPI get_everything으로 헤드라인+설명 텍스트 스트리밍.
    원문은 저장하지 않고 텍스트만 yield.
    """
    try:
        from newsapi import NewsApiClient
    except ImportError:
        log.warning("newsapi-python 패키지 없음 — pip install newsapi-python")
        return

    client = NewsApiClient(api_key=NEWS_API_KEY)

    try:
        resp = client.get_everything(
            q=query,
            from_param=from_date,
            to=to_date,
            language="en",
            sort_by="publishedAt",
            page_size=min(page_size, 100),
        )
    except Exception as e:
        log.warning("NewsAPI 요청 실패 (query=%r): %s", query, e)
        return

    articles = resp.get("articles", [])
    log.debug("NewsAPI: query=%r, %d건 수신 (%s ~ %s)", query, len(articles), from_date, to_date)

    for art in articles:
        title = art.get("title") or ""
        desc = art.get("description") or ""
        text = f"{title}. {desc}".strip()
        if text and text != ".":
            yield text


def _scores_by_date(
    query: str,
    from_date: str,
    to_date: str,
) -> pd.Series:
    """
    날짜별 감성 점수 평균 Series 반환.
    publishedAt 기준으로 그룹핑.
    """
    try:
        from newsapi import NewsApiClient
    except ImportError:
        return pd.Series(dtype=float)

    client = NewsApiClient(api_key=NEWS_API_KEY)

    try:
        resp = client.get_everything(
            q=query,
            from_param=from_date,
            to=to_date,
            language="en",
            sort_by="publishedAt",
            page_size=100,
        )
    except Exception as e:
        log.warning("NewsAPI 요청 실패 (query=%r): %s", query, e)
        return pd.Series(dtype=float)

    articles = resp.get("articles", [])
    if not articles:
        return pd.Series(dtype=float)

    records = []
    for art in articles:
        published = art.get("publishedAt", "")
        title = art.get("title") or ""
        desc = art.get("description") or ""
        text = f"{title}. {desc}".strip()

        if not published or not text or text == ".":
            continue

        try:
            date_key = pd.Timestamp(published).tz_convert(None).normalize()
        except Exception:
            try:
                date_key = pd.Timestamp(published).normalize()
            except Exception:
                continue

        score = _vader_score(text)
        records.append({"date": date_key, "score": score})

    if not records:
        return pd.Series(dtype=float)

    df_rec = pd.DataFrame(records)
    series = df_rec.groupby("date")["score"].mean()
    series.index = pd.DatetimeIndex(series.index)
    series.index.name = "date"
    return series


def get_news_sentiment(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    뉴스 감성 점수 수집.

    무료 NewsAPI 플랜 제약:
      - 최근 30일 데이터만 조회 가능
      - start가 30일 이전이면 최근 30일로 자동 조정

    Args:
        start    : 수집 시작일 'YYYY-MM-DD'
        end      : 수집 종료일 'YYYY-MM-DD', 기본값 오늘
        use_cache: True면 캐시 우선 사용
    Returns:
        DatetimeIndex DataFrame, 컬럼:
          sent_news_global, sent_news_fed
        API 키 없거나 실패 시 빈 DataFrame
    """
    if not NEWS_API_KEY:
        log.warning("NEWS_API_KEY 없음 — 빈 DataFrame 반환")
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")

    # 무료 플랜: 최근 30일 제한
    cutoff = (pd.Timestamp.today() - pd.Timedelta(days=29)).strftime("%Y-%m-%d")
    effective_start = max(start, cutoff)
    if effective_start != start:
        log.info(
            "NewsAPI 무료 플랜 제한: start=%s → %s (최근 30일)",
            start, effective_start,
        )

    cache_key = f"news_sentiment_{effective_start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("캐시 히트: %s", cache_key)
            return cached

    log.info("NewsAPI 감성 수집 시작: %s ~ %s", effective_start, end)

    result_frames: dict[str, pd.Series] = {}

    for col_suffix, query in _QUERIES.items():
        col_name = f"sent_news_{col_suffix}"
        s = _scores_by_date(query, effective_start, end)
        if not s.empty:
            s.name = col_name
            result_frames[col_name] = s
            log.info("NewsAPI %s: %d일치 감성 점수 수집", col_suffix, len(s))
        else:
            log.warning("NewsAPI %s: 감성 데이터 없음", col_suffix)

    if not result_frames:
        log.warning("NewsAPI: 수집된 데이터 없음")
        return pd.DataFrame()

    df = pd.concat(result_frames.values(), axis=1)
    df.sort_index(inplace=True)
    df = df.loc[effective_start:end]

    if df.empty:
        return pd.DataFrame()

    log.info("NewsAPI 감성 수집 완료: %d행 × %d컬럼", len(df), len(df.columns))

    if use_cache:
        save_cache(cache_key, df)

    return df
