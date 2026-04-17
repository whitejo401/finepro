"""crypto_intel/dev — 코인 GitHub 개발 활동 엔드포인트."""
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from api.core.cache import cache
from api.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

TTL_ACTIVITY = 3600   # 1시간
TTL_RELEASES = 10800  # 3시간
TTL_RANKING  = 10800  # 3시간

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
GITHUB_API = "https://api.github.com"


def _cg_get(path: str, params: dict | None = None) -> dict | list:
    import requests
    headers = {}
    api_key = os.getenv("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    resp = requests.get(f"{COINGECKO_BASE}{path}", params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _gh_get(path: str, params: dict | None = None) -> dict | list:
    import requests
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(f"{GITHUB_API}{path}", params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _extract_github_repo(coin_data: dict) -> str | None:
    """CoinGecko 코인 데이터에서 GitHub 레포 URL 추출."""
    repos = (coin_data.get("links") or {}).get("repos_url", {}).get("github", [])
    for url in repos:
        if url and "github.com" in url:
            return url.rstrip("/")
    return None


def _parse_owner_repo(github_url: str) -> tuple[str, str] | None:
    """'https://github.com/owner/repo' → (owner, repo)."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)", github_url)
    if m:
        return m.group(1), m.group(2)
    return None


def _calc_pulse(dev_data: dict) -> float:
    """개발 건강도 점수 0~100 산출."""
    commit4w  = dev_data.get("commit_activity_4_weeks") or 0
    closed    = dev_data.get("closed_issues") or 0
    total     = dev_data.get("total_issues") or 1
    last_push = dev_data.get("last_push_utc")

    commit_score      = min(commit4w / 100, 1.0) * 40
    contributor_score = min((dev_data.get("contributors_count") or 0) / 20, 1.0) * 30
    issue_score       = (closed / total) * 20

    freshness = 0.0
    if last_push:
        try:
            dt = datetime.fromisoformat(last_push.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days <= 7:
                freshness = 1.0
            elif age_days <= 30:
                freshness = 0.5
        except Exception:
            pass
    freshness_score = freshness * 10

    return round(commit_score + contributor_score + issue_score + freshness_score, 1)


@router.get("/{coin_id}/activity")
def dev_activity(
    coin_id: str = Path(description="CoinGecko 코인 ID (예: bitcoin)"),
):
    """개발 활동 요약 — 커밋수·기여자·PR·이슈·스타·포크."""
    cache_key = f"crypto_intel:dev:{coin_id}:activity"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        coin = _cg_get(f"/coins/{coin_id}", params={
            "localization": False, "tickers": False,
            "market_data": False, "community_data": False,
            "developer_data": True, "sparkline": False,
        })
        dd = coin.get("developer_data") or {}
        github_url = _extract_github_repo(coin)

        # GitHub API로 기여자 수 보완
        contributors_count = None
        last_push = None
        if github_url:
            parsed = _parse_owner_repo(github_url)
            if parsed:
                try:
                    repo_info = _gh_get(f"/repos/{parsed[0]}/{parsed[1]}")
                    last_push = repo_info.get("pushed_at")
                    # 기여자 수: 첫 페이지 count (최대 30명, 전체는 유료)
                    contribs = _gh_get(f"/repos/{parsed[0]}/{parsed[1]}/contributors",
                                       params={"per_page": 1, "anon": False})
                    if isinstance(contribs, list):
                        contributors_count = len(contribs)
                except Exception as e:
                    logger.debug("GitHub 기여자 조회 실패: %s", e)

        dev_data = {
            "coin_id": coin_id,
            "github_url": github_url,
            "forks": dd.get("forks"),
            "stars": dd.get("stars"),
            "subscribers": dd.get("subscribers"),
            "total_issues": dd.get("total_issues"),
            "closed_issues": dd.get("closed_issues"),
            "pull_requests_merged": dd.get("pull_requests_merged"),
            "pull_request_contributors": dd.get("pull_request_contributors"),
            "commit_activity_4_weeks": dd.get("commit_activity_4_weeks"),
            "code_additions_4w": (dd.get("code_additions_deletions_4_weeks") or {}).get("additions"),
            "code_deletions_4w": (dd.get("code_additions_deletions_4_weeks") or {}).get("deletions"),
            "contributors_count": contributors_count,
            "last_push_utc": last_push,
        }
        dev_data["pulse"] = _calc_pulse(dev_data)
        resp = ok(dev_data)
    except Exception as e:
        logger.error("dev_activity error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_ACTIVITY)
    return resp


@router.get("/{coin_id}/commits")
def dev_commits(
    coin_id: str = Path(description="CoinGecko 코인 ID"),
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(30, ge=1, le=100),
):
    """최근 커밋 로그 — 날짜·메시지·작성자."""
    cache_key = f"crypto_intel:dev:{coin_id}:commits:{days}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        coin = _cg_get(f"/coins/{coin_id}", params={
            "localization": False, "tickers": False,
            "market_data": False, "community_data": False,
            "developer_data": False, "sparkline": False,
        })
        github_url = _extract_github_repo(coin)
        if not github_url:
            raise HTTPException(status_code=404, detail=f"{coin_id} — GitHub 레포 없음")

        parsed = _parse_owner_repo(github_url)
        if not parsed:
            raise HTTPException(status_code=404, detail="GitHub URL 파싱 실패")

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        raw_commits = _gh_get(
            f"/repos/{parsed[0]}/{parsed[1]}/commits",
            params={"since": since, "per_page": limit},
        )
        commits = [
            {
                "sha": c["sha"][:7],
                "date": (c.get("commit") or {}).get("author", {}).get("date"),
                "message": ((c.get("commit") or {}).get("message") or "").split("\n")[0][:120],
                "author": (c.get("commit") or {}).get("author", {}).get("name"),
                "url": (c.get("html_url")),
            }
            for c in (raw_commits if isinstance(raw_commits, list) else [])
        ]
        resp = ok(commits, meta={
            "coin_id": coin_id,
            "repo": f"{parsed[0]}/{parsed[1]}",
            "days": days,
            "count": len(commits),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("dev_commits error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_ACTIVITY)
    return resp


@router.get("/{coin_id}/releases")
def dev_releases(
    coin_id: str = Path(description="CoinGecko 코인 ID"),
    limit: int = Query(10, ge=1, le=30),
):
    """최근 릴리즈·버전 이력 — 날짜·태그·변경요약."""
    cache_key = f"crypto_intel:dev:{coin_id}:releases:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        coin = _cg_get(f"/coins/{coin_id}", params={
            "localization": False, "tickers": False,
            "market_data": False, "community_data": False,
            "developer_data": False, "sparkline": False,
        })
        github_url = _extract_github_repo(coin)
        if not github_url:
            raise HTTPException(status_code=404, detail=f"{coin_id} — GitHub 레포 없음")

        parsed = _parse_owner_repo(github_url)
        if not parsed:
            raise HTTPException(status_code=404, detail="GitHub URL 파싱 실패")

        raw = _gh_get(f"/repos/{parsed[0]}/{parsed[1]}/releases", params={"per_page": limit})
        releases = [
            {
                "tag": r.get("tag_name"),
                "name": r.get("name"),
                "published_at": r.get("published_at"),
                "prerelease": r.get("prerelease"),
                "body_summary": (r.get("body") or "")[:300],
                "url": r.get("html_url"),
            }
            for r in (raw if isinstance(raw, list) else [])
        ]
        resp = ok(releases, meta={
            "coin_id": coin_id,
            "repo": f"{parsed[0]}/{parsed[1]}",
            "count": len(releases),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("dev_releases error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_RELEASES)
    return resp


@router.get("/ranking/activity")
def dev_ranking(
    sector: str = Query("layer-1", description="CoinGecko 카테고리 ID"),
    limit: int = Query(20, ge=5, le=50),
):
    """섹터별 개발 활동 상위 코인 순위 (4주 커밋수 기준)."""
    cache_key = f"crypto_intel:dev:ranking:{sector}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        # 섹터 상위 코인 목록 (시총 기준)
        coins = _cg_get("/coins/markets", params={
            "vs_currency": "usd",
            "category": sector,
            "order": "market_cap_desc",
            "per_page": min(limit * 2, 50),
            "page": 1,
            "sparkline": False,
        })

        results = []
        for coin in (coins if isinstance(coins, list) else []):
            cid = coin["id"]
            try:
                detail = _cg_get(f"/coins/{cid}", params={
                    "localization": False, "tickers": False,
                    "market_data": False, "community_data": False,
                    "developer_data": True, "sparkline": False,
                })
                dd = detail.get("developer_data") or {}
                commit4w = dd.get("commit_activity_4_weeks") or 0
                results.append({
                    "rank": None,
                    "coin_id": cid,
                    "symbol": coin["symbol"].upper(),
                    "name": coin["name"],
                    "commit_activity_4_weeks": commit4w,
                    "stars": dd.get("stars"),
                    "forks": dd.get("forks"),
                    "pull_requests_merged": dd.get("pull_requests_merged"),
                    "market_cap": coin.get("market_cap"),
                })
            except Exception:
                continue

        results.sort(key=lambda x: x["commit_activity_4_weeks"], reverse=True)
        for i, r in enumerate(results[:limit], 1):
            r["rank"] = i

        resp = ok(results[:limit], meta={"sector": sector, "count": len(results[:limit])})
    except Exception as e:
        logger.error("dev_ranking error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_RANKING)
    return resp


@router.get("/{coin_id}/pulse")
def dev_pulse(
    coin_id: str = Path(description="CoinGecko 코인 ID"),
):
    """개발 건강도 점수 0~100 (커밋빈도·기여자다양성·이슈해결률·최신성)."""
    cache_key = f"crypto_intel:dev:{coin_id}:pulse"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        # activity 엔드포인트 재활용
        act_cached = cache.get(f"crypto_intel:dev:{coin_id}:activity")
        if act_cached:
            dev_data = act_cached["data"]
        else:
            coin = _cg_get(f"/coins/{coin_id}", params={
                "localization": False, "tickers": False,
                "market_data": False, "community_data": False,
                "developer_data": True, "sparkline": False,
            })
            dd = coin.get("developer_data") or {}
            github_url = _extract_github_repo(coin)
            last_push = None
            contributors_count = None
            if github_url:
                parsed = _parse_owner_repo(github_url)
                if parsed:
                    try:
                        repo_info = _gh_get(f"/repos/{parsed[0]}/{parsed[1]}")
                        last_push = repo_info.get("pushed_at")
                    except Exception:
                        pass
            dev_data = {
                "commit_activity_4_weeks": dd.get("commit_activity_4_weeks") or 0,
                "closed_issues": dd.get("closed_issues") or 0,
                "total_issues": dd.get("total_issues") or 1,
                "contributors_count": contributors_count,
                "last_push_utc": last_push,
            }

        pulse = _calc_pulse(dev_data)

        # 점수 해석
        if pulse >= 80:
            grade, label = "A", "매우 활발"
        elif pulse >= 60:
            grade, label = "B", "활발"
        elif pulse >= 40:
            grade, label = "C", "보통"
        elif pulse >= 20:
            grade, label = "D", "저조"
        else:
            grade, label = "F", "비활성"

        resp = ok({
            "coin_id": coin_id,
            "pulse": pulse,
            "grade": grade,
            "label": label,
            "breakdown": {
                "commit_score": min((dev_data.get("commit_activity_4_weeks") or 0) / 100, 1.0) * 40,
                "contributor_score": min((dev_data.get("contributors_count") or 0) / 20, 1.0) * 30,
                "issue_score": ((dev_data.get("closed_issues") or 0) / max(dev_data.get("total_issues") or 1, 1)) * 20,
                "freshness_score": pulse - (
                    min((dev_data.get("commit_activity_4_weeks") or 0) / 100, 1.0) * 40 +
                    min((dev_data.get("contributors_count") or 0) / 20, 1.0) * 30 +
                    ((dev_data.get("closed_issues") or 0) / max(dev_data.get("total_issues") or 1, 1)) * 20
                ),
            },
        })
    except Exception as e:
        logger.error("dev_pulse error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    cache.set(cache_key, resp, TTL_ACTIVITY)
    return resp
