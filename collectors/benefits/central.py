"""중앙정부 혜택/지원금 수집기 — 복지로 API, 정부24."""
import os
import logging
import requests

log = logging.getLogger(__name__)

_BASE_BOKJIRO = "https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do"
_BASE_GOV24 = "https://www.gov.kr/openapi/service/rest/G050H010/getLifeSvcList"
_DATA_GO_KR = "https://api.odcloud.kr/api"

# 복지로 서비스 분야 코드
CATEGORY_CODES = {
    "생활안정":    "001",
    "주거자립":    "002",
    "보건의료":    "003",
    "교육":        "004",
    "고용취업":    "005",
    "행정사법":    "006",
    "임신출산":    "007",
    "보육":        "008",
    "아동청소년":  "009",
    "노인":        "010",
    "장애인":      "011",
    "기타":        "012",
}


def get_welfare_services(
    category: str | None = None,
    life_stage: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    use_cache: bool = True,
) -> list[dict]:
    """복지로 복지서비스 목록 조회.

    Args:
        category: 서비스 분야 (CATEGORY_CODES 키)
        life_stage: 생애주기 (영유아|아동|청소년|청년|중장년|노인|장애인|임산부|다문화)
        keyword: 서비스명 검색어
        page: 페이지 번호 (1부터)
        page_size: 페이지당 결과 수 (최대 100)
        use_cache: 캐시 사용 여부

    Returns:
        복지서비스 정보 리스트
    """
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        log.warning("DATA_GO_KR_API_KEY 미설정 — 복지로 수집 불가")
        return []

    params = {
        "serviceKey": api_key,
        "pageNo":     page,
        "numOfRows":  page_size,
        "returnType": "json",
    }
    if category and category in CATEGORY_CODES:
        params["srchSrvPattnCd"] = CATEGORY_CODES[category]
    if life_stage:
        params["srchLftmCycCd"] = life_stage
    if keyword:
        params["srchWlfareInfoNm"] = keyword

    url = "https://apis.data.go.kr/B554287/NationalWelfareInformationsKr/NationalWelfarelistInfoSearch"

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        items = (
            body.get("body", {}).get("items", {}).get("item", [])
            if isinstance(body.get("body"), dict)
            else []
        )
        if isinstance(items, dict):
            items = [items]
        return items
    except Exception as e:
        log.error("복지서비스 수집 실패: %s", e)
        return []


def get_welfare_detail(service_id: str) -> dict | None:
    """복지서비스 상세 정보 조회.

    Args:
        service_id: 복지서비스 ID (WlfareInfoId)

    Returns:
        서비스 상세 정보 dict 또는 None
    """
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        log.warning("DATA_GO_KR_API_KEY 미설정")
        return None

    url = "https://apis.data.go.kr/B554287/NationalWelfareInformationsKr/NationalWelfaredetailedInfoSearch"
    params = {
        "serviceKey":  api_key,
        "wlfareInfoId": service_id,
        "returnType":  "json",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        return body.get("body", {}).get("items", {}).get("item")
    except Exception as e:
        log.error("복지서비스 상세 수집 실패 (%s): %s", service_id, e)
        return None


def get_gov24_services(
    life_stage: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    """정부24 생애주기별 서비스 조회.

    Args:
        life_stage: 생애주기 코드 (임신출산|영유아|아동|청소년|청년|중장년|노년|장애인)
        keyword: 서비스명 검색어
        page: 페이지 번호
        page_size: 페이지당 결과 수

    Returns:
        정부24 서비스 리스트
    """
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        log.warning("DATA_GO_KR_API_KEY 미설정 — 정부24 수집 불가")
        return []

    params = {
        "serviceKey": api_key,
        "pageNo":     page,
        "numOfRows":  page_size,
        "type":       "json",
    }
    if life_stage:
        params["lifeArray"] = life_stage
    if keyword:
        params["svcNm"] = keyword

    try:
        resp = requests.get(_BASE_GOV24, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        items = body.get("body", {}).get("items", [])
        return items if isinstance(items, list) else [items]
    except Exception as e:
        log.error("정부24 서비스 수집 실패: %s", e)
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = get_welfare_services(category="교육", page_size=5)
    for r in results:
        print(r.get("wlfareInfoNm", r))
