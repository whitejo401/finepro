"""GeekNews RSS 수집기 — IT 기술 뉴스 큐레이션 (API 키 불필요)."""
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

import requests

log = logging.getLogger(__name__)

_RSS_URL = "https://news.hada.io/rss/news"

# Atom 네임스페이스
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
}

# 카테고리 키워드 매핑 (제목 기준 자동 분류)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "AI/ML":     ["ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
                  "머신러닝", "딥러닝", "인공지능", "neural", "transformer", "diffusion"],
    "오픈소스":  ["open source", "opensource", "github", "linux", "apache",
                  "오픈소스", "오픈 소스", "rust", "golang", "python", "typescript"],
    "보안":      ["security", "hack", "vulnerability", "exploit", "ransomware",
                  "보안", "취약점", "해킹", "malware", "phishing", "zero-day"],
    "스타트업":  ["startup", "funding", "series", "ipo", "acquisition", "valuation",
                  "스타트업", "투자", "인수", "합병", "유니콘"],
    "클라우드":  ["cloud", "aws", "azure", "gcp", "kubernetes", "docker", "serverless",
                  "클라우드", "인프라"],
    "모바일/앱": ["ios", "android", "app store", "flutter", "react native",
                  "앱", "모바일"],
    "웹/프론트": ["react", "vue", "nextjs", "svelte", "css", "webassembly", "browser",
                  "프론트엔드", "웹"],
    "데이터":    ["database", "postgresql", "mysql", "redis", "kafka", "spark",
                  "데이터", "analytics", "bigquery"],
}

# 불용어 (트렌드 키워드 추출 시 제외)
_STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "with", "that", "this", "it", "be", "as", "by",
    "이", "그", "저", "에", "의", "을", "를", "은", "는", "도", "로", "가",
    "과", "와", "에서", "으로", "하다", "있다", "되다", "하고", "위해",
}


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []

    def handle_data(self, data):
        self._text.append(data)

    def get_text(self):
        return " ".join(self._text).strip()


def _strip_html(html: str) -> str:
    p = _HTMLStripper()
    p.feed(html)
    return p.get_text()


def fetch_feed(limit: int = 50) -> list[dict]:
    """GeekNews RSS 피드 파싱.

    Args:
        limit: 반환할 최대 기사 수

    Returns:
        [{title, link, published, author, summary, categories}, ...]
    """
    try:
        resp = requests.get(_RSS_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        log.error("GeekNews RSS 수집 실패: %s", e)
        return []

    entries = root.findall("atom:entry", _NS)
    results = []

    for entry in entries[:limit]:
        title_el   = entry.find("atom:title", _NS)
        link_el    = entry.find("atom:link", _NS)
        pub_el     = entry.find("atom:published", _NS)
        author_el  = entry.find("atom:author/atom:name", _NS)
        content_el = entry.find("atom:content", _NS)

        title   = title_el.text.strip()   if title_el   is not None else ""
        link    = link_el.get("href", "") if link_el    is not None else ""
        pub_raw = pub_el.text.strip()     if pub_el     is not None else ""
        author  = author_el.text.strip()  if author_el  is not None else ""
        summary = _strip_html(content_el.text or "") if content_el is not None else ""

        # 발행 시간 파싱
        published = None
        if pub_raw:
            try:
                published = datetime.fromisoformat(pub_raw).astimezone(timezone.utc).isoformat()
            except Exception:
                published = pub_raw

        categories = _classify(title)

        results.append({
            "title":      title,
            "link":       link,
            "published":  published,
            "author":     author,
            "summary":    summary[:300] if summary else "",
            "categories": categories,
        })

    return results


def get_trending_keywords(days: int = 7, top_n: int = 20) -> list[dict]:
    """최근 N일 기사 제목에서 트렌드 키워드 추출.

    Args:
        days: 최근 며칠 기사 분석 (피드에 있는 것 기준)
        top_n: 상위 N개 키워드

    Returns:
        [{"keyword": "AI", "count": 15}, ...]
    """
    articles = fetch_feed(limit=200)

    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    words: list[str] = []
    for art in articles:
        pub = art.get("published", "")
        if pub:
            try:
                pub_dt = datetime.fromisoformat(pub)
                if pub_dt < cutoff:
                    continue
            except Exception:
                pass

        title = art.get("title", "").lower()
        # 영문 단어 + 한글 단어 추출
        tokens = re.findall(r"[a-z][a-z0-9+#\-\.]{1,}", title) + \
                 re.findall(r"[가-힣]{2,}", title)
        words.extend([w for w in tokens if w not in _STOPWORDS and len(w) >= 2])

    counter = Counter(words)
    return [{"keyword": k, "count": v} for k, v in counter.most_common(top_n)]


def get_by_category(category: str, limit: int = 20) -> list[dict]:
    """카테고리별 기사 필터링.

    Args:
        category: CATEGORY_KEYWORDS의 키 (예: "AI/ML", "보안")
        limit: 최대 결과 수

    Returns:
        해당 카테고리에 속하는 기사 리스트
    """
    articles = fetch_feed(limit=200)
    return [a for a in articles if category in a.get("categories", [])][:limit]


def _classify(title: str) -> list[str]:
    """제목 기반 카테고리 자동 분류."""
    title_lower = title.lower()
    matched = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            matched.append(cat)
    return matched if matched else ["기타"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json
    articles = fetch_feed(limit=5)
    print(json.dumps(articles, ensure_ascii=False, indent=2))
    print("\n=== 트렌드 키워드 ===")
    print(get_trending_keywords(days=7, top_n=10))
