"""
대체 데이터 수집기.

수집 항목:
  - 뉴스 감성 점수 (NewsAPI)
  - Google Trends (pytrends)
  - GDELT 지정학 이벤트 평균 톤 (CSV)
  - EPU 경제정책 불확실성 지수 (CSV)

컬럼명 규칙
  sent_  : 뉴스/트렌드 감성
  trends_: Google Trends 검색량 (0~100 정규화)
  gdelt_ : GDELT 이벤트 지표
  epu_   : 경제정책 불확실성 지수

주의:
  - 원문/헤드라인 직접 저장 금지 (NewsAPI 이용약관 — 원문 재배포 불가)
  - 감성 점수(float)만 캐싱
  - NEWS_API_KEY 없으면 NewsAPI 섹션 빈 DataFrame 반환
  - 무료 플랜: 최근 1개월 데이터만 조회 가능, 하루 100건 제한
"""
from __future__ import annotations

import io
import time
from typing import Iterator

import pandas as pd

from collectors.base import get_logger, load_cache, save_cache
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
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


# ---------------------------------------------------------------------------
# Google Trends (pytrends)
# ---------------------------------------------------------------------------

_TRENDS_KEYWORDS: dict[str, str] = {
    "trends_bitcoin":    "bitcoin",
    "trends_recession":  "recession",
    "trends_inflation":  "inflation",
    "trends_stock_crash": "stock market crash",
}


def get_trends_dataset(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Google Trends 주간 검색량 지수 수집.

    pytrends 패키지 사용 (pip install pytrends). 키 불필요.
    무료 비공개 API — 과도한 요청 시 429 반환 가능.

    Returns:
        DatetimeIndex(주간) DataFrame, 컬럼: trends_bitcoin, trends_recession, ...
        각 값 0~100 (구글 상대 검색량)
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"trends_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    try:
        from pytrends.request import TrendReq  # type: ignore
    except ImportError:
        log.warning("pytrends 패키지 없음 — pip install pytrends")
        return pd.DataFrame()

    keywords = list(_TRENDS_KEYWORDS.values())
    col_map = {v: k for k, v in _TRENDS_KEYWORDS.items()}

    log.info("fetch Google Trends: %s (%s ~ %s)", keywords, start, end)

    # pytrends는 한 번에 최대 5개 키워드
    try:
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
        timeframe = f"{start[:10]} {end[:10]}"
        pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo="", gprop="")
        time.sleep(1)  # 속도 제한
        raw = pytrends.interest_over_time()
    except Exception as e:
        log.warning("Google Trends 요청 실패: %s", e)
        return pd.DataFrame()

    if raw.empty:
        log.warning("Google Trends: 빈 응답")
        return pd.DataFrame()

    # 'isPartial' 컬럼 제거
    if "isPartial" in raw.columns:
        raw = raw.drop(columns=["isPartial"])

    raw = raw.rename(columns=col_map)
    raw.index = pd.DatetimeIndex(raw.index)
    raw.index.name = "date"
    raw = raw.loc[start:end]

    if use_cache:
        save_cache(cache_key, raw)

    log.info("Google Trends: %d 행 × %d 컬럼", len(raw), len(raw.columns))
    return raw


# ---------------------------------------------------------------------------
# GDELT v2 — 지정학 이벤트 평균 톤
# ---------------------------------------------------------------------------

_GDELT_DOC_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
# GDELT timespan 최대 1년
_GDELT_MAX_DAYS = 365


def get_gdelt_tone(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    GDELT v2 DOC API — 경제 뉴스 일별 평균 감성 톤 수집.

    GDELT 무료 API — 키 불필요.
    15분 단위 데이터를 일별 평균으로 리샘플링.
    최대 1년 이전 데이터까지 조회 가능.

    Returns:
        DatetimeIndex(일별) DataFrame, 컬럼: gdelt_tone (평균 감성)
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    # GDELT는 최근 365일만 지원 — 범위 조정
    cutoff = (pd.Timestamp.today() - pd.Timedelta(days=_GDELT_MAX_DAYS - 1)).strftime("%Y-%m-%d")
    effective_start = max(start, cutoff)
    if effective_start != start:
        log.info("GDELT 기간 조정: %s → %s (최대 365일)", start, effective_start)

    # end도 cutoff 이전이면 수집 범위 없음
    if end < cutoff:
        log.info("GDELT: 요청 범위 전체(%s ~ %s)가 365일 제한 이전 — 스킵", start, end)
        return pd.DataFrame()

    cache_key = f"gdelt_tone_{effective_start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    days_diff = (pd.Timestamp(end) - pd.Timestamp(effective_start)).days + 1
    if days_diff <= 30:
        timespan = f"{days_diff}days"
    elif days_diff <= 90:
        timespan = "3months"
    elif days_diff <= 180:
        timespan = "6months"
    else:
        timespan = "1year"

    params = {
        "query": "economy stock market inflation recession",
        "mode": "timelinetone",
        "format": "csv",
        "timespan": timespan,
    }

    log.info("fetch GDELT tone: timespan=%s (%s ~ %s)", timespan, effective_start, end)
    try:
        import requests
        resp = requests.get(_GDELT_DOC_BASE, params=params, timeout=60)
        resp.raise_for_status()
        text = resp.text.strip().lstrip("\ufeff")  # BOM 제거
    except Exception as e:
        log.warning("GDELT 요청 실패: %s", e)
        return pd.DataFrame()

    if not text:
        log.warning("GDELT: 빈 응답")
        return pd.DataFrame()

    try:
        df_raw = pd.read_csv(io.StringIO(text))
    except Exception as e:
        log.warning("GDELT CSV 파싱 실패: %s", e)
        return pd.DataFrame()

    # 형식: Date, Series, Value
    if "Date" not in df_raw.columns or "Value" not in df_raw.columns:
        log.warning("GDELT: 예상 외 컬럼 — %s", df_raw.columns.tolist())
        return pd.DataFrame()

    try:
        df_raw["date"] = pd.to_datetime(df_raw["Date"], errors="coerce")
        df_raw["value"] = pd.to_numeric(df_raw["Value"], errors="coerce")
        df_raw = df_raw.dropna(subset=["date", "value"])
        # 15분 → 일별 평균 리샘플링
        df_raw = df_raw.set_index("date")[["value"]]
        df_daily = df_raw.resample("D").mean()
        df_daily.columns = ["gdelt_tone"]
        df_daily = df_daily.dropna()
        df_daily.index.name = "date"
        df_daily.sort_index(inplace=True)
        df_daily = df_daily.loc[effective_start:end]
    except Exception as e:
        log.warning("GDELT 변환 실패: %s", e)
        return pd.DataFrame()

    if df_daily.empty:
        return pd.DataFrame()

    if use_cache:
        save_cache(cache_key, df_daily)

    log.info("GDELT tone: %d 행", len(df_daily))
    return df_daily


# ---------------------------------------------------------------------------
# EPU Index — 경제정책 불확실성 지수
# ---------------------------------------------------------------------------

_EPU_US_URL = "https://www.policyuncertainty.com/media/US_Policy_Uncertainty_Data.xlsx"
_EPU_GLOBAL_URL = "https://www.policyuncertainty.com/media/Global_Policy_Uncertainty_Data.xlsx"


def get_epu_index(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    EPU(경제정책 불확실성) 지수 수집.

    Baker, Bloom & Davis (policyuncertainty.com) 무료 공개 Excel 다운로드.
    키 불필요.

    Returns:
        DatetimeIndex(월말) DataFrame, 컬럼:
          epu_us    : 미국 EPU 지수
          epu_global: 글로벌 EPU 지수
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"epu_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    log.info("fetch EPU Index: %s ~ %s", start, end)
    frames: list[pd.DataFrame] = []

    for col_name, url in [("epu_us", _EPU_US_URL), ("epu_global", _EPU_GLOBAL_URL)]:
        try:
            import requests
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            raw = pd.read_excel(io.BytesIO(resp.content))
        except Exception as e:
            log.warning("EPU 다운로드 실패 (%s): %s", col_name, e)
            continue

        # 컬럼 탐색: Year, Month, 지수값
        year_col = next((c for c in raw.columns if "year" in str(c).lower()), None)
        month_col = next((c for c in raw.columns if "month" in str(c).lower()), None)
        # 지수 컬럼: 숫자형 중 Year/Month 아닌 것
        value_cols = [
            c for c in raw.columns
            if c not in [year_col, month_col]
            and pd.api.types.is_numeric_dtype(raw[c])
        ]

        if not year_col or not month_col or not value_cols:
            log.warning("EPU 컬럼 탐색 실패 (%s): %s", col_name, raw.columns.tolist())
            continue

        value_col = value_cols[0]
        try:
            df = raw[[year_col, month_col, value_col]].copy()
            df.columns = ["year", "month", col_name]
            df = df.dropna()
            df["date"] = pd.to_datetime(
                df["year"].astype(int).astype(str) + "-"
                + df["month"].astype(int).astype(str).str.zfill(2) + "-01"
            ) + pd.offsets.MonthEnd(0)
            df = df.set_index("date")[[col_name]]
            df.index.name = "date"
            df.sort_index(inplace=True)
            df = df.loc[start:end]
            if not df.empty:
                frames.append(df)
                log.info("EPU %s: %d 행", col_name, len(df))
        except Exception as e:
            log.warning("EPU 변환 실패 (%s): %s", col_name, e)

    if not frames:
        return pd.DataFrame()

    result = frames[0]
    for df in frames[1:]:
        result = result.join(df, how="outer")
    result.sort_index(inplace=True)

    if use_cache:
        save_cache(cache_key, result)

    return result


# ---------------------------------------------------------------------------
# Reddit 커뮤니티 감성 (praw)
# ---------------------------------------------------------------------------

_REDDIT_SUBS: list[str] = [
    "wallstreetbets",
    "investing",
    "stocks",
    "economics",
]

_REDDIT_LIMIT = 500  # 서브레딧당 최대 수집 게시글 수


def _get_reddit_client():
    """praw Reddit 인스턴스 반환. 키 없으면 None."""
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return None
    try:
        import praw  # type: ignore
        return praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
    except ImportError:
        log.warning("praw 패키지 없음 — pip install praw")
        return None


def get_reddit_sentiment(
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Reddit 커뮤니티 감성 점수 수집.

    praw로 주요 금융 서브레딧(wallstreetbets, investing, stocks, economics)의
    최근 게시글 제목에 VADER 감성 분석을 적용한 일별 복합 점수 반환.

    Reddit API는 서브레딧당 최근 ~1000개 게시글까지 직접 접근 가능.
    start가 수 개월 이전이면 해당 기간 데이터가 부족할 수 있음.

    REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET 필요.

    Returns:
        DatetimeIndex(일별) DataFrame, 컬럼:
          sent_reddit_compound  — 일별 가중 VADER compound 평균 (-1 ~ +1)
          sent_reddit_volume    — 일별 분석된 게시글 수
    """
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        log.warning("REDDIT_CLIENT_ID/SECRET 없음 — Reddit 감성 수집 스킵")
        return pd.DataFrame()

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    cache_key = f"reddit_sent_{start}_{end}"

    if use_cache:
        cached = load_cache(cache_key)
        if cached is not None:
            log.info("cache hit: %s", cache_key)
            return cached

    reddit = _get_reddit_client()
    if reddit is None:
        return pd.DataFrame()

    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
        analyzer = SentimentIntensityAnalyzer()
    except ImportError:
        log.warning("vaderSentiment 패키지 없음 — pip install vaderSentiment")
        return pd.DataFrame()

    start_ts = pd.Timestamp(start).timestamp()
    end_ts   = pd.Timestamp(end).timestamp() + 86_400  # end 당일 포함

    # 날짜별 집계용
    daily: dict[pd.Timestamp, list[float]] = {}

    for sub_name in _REDDIT_SUBS:
        log.info("Reddit fetch: r/%s (limit=%d)", sub_name, _REDDIT_LIMIT)
        try:
            subreddit = reddit.subreddit(sub_name)
            posts = subreddit.new(limit=_REDDIT_LIMIT)
            count = 0
            for post in posts:
                created = post.created_utc
                if created < start_ts or created > end_ts:
                    continue
                title = post.title or ""
                if not title.strip():
                    continue
                score = analyzer.polarity_scores(title)["compound"]
                date_key = pd.Timestamp(created, unit="s").normalize()
                daily.setdefault(date_key, []).append(score)
                count += 1
            log.info("Reddit r/%s: %d 게시글 수집", sub_name, count)
        except Exception as e:
            log.warning("Reddit r/%s 수집 실패: %s", sub_name, e)
        time.sleep(0.5)

    if not daily:
        log.warning("Reddit: 수집된 게시글 없음 (%s ~ %s)", start, end)
        return pd.DataFrame()

    records = []
    for date_key, scores in sorted(daily.items()):
        records.append({
            "date": date_key,
            "sent_reddit_compound": round(sum(scores) / len(scores), 4),
            "sent_reddit_volume":   len(scores),
        })

    df = pd.DataFrame(records).set_index("date")
    df.index = pd.DatetimeIndex(df.index)
    df.index.name = "date"
    df.sort_index(inplace=True)
    df = df.loc[start:end]

    if use_cache:
        save_cache(cache_key, df)

    log.info("Reddit 감성: %d 일치 수집", len(df))
    return df
