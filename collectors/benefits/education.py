"""교육 혜택 수집기 — 평생교육바우처, 국가장학금, 직업훈련."""
import os
import logging
import requests

log = logging.getLogger(__name__)


def get_lifelong_edu_voucher(
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    """평생교육바우처 지원 정보 조회 (공공데이터포털).

    Returns:
        바우처 지원 프로그램 리스트
    """
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        log.warning("DATA_GO_KR_API_KEY 미설정")
        return []

    url = "https://apis.data.go.kr/B553077/lifelongEduVoucher/getLifelongEduVoucherList"
    params = {
        "serviceKey": api_key,
        "pageNo":     page,
        "numOfRows":  page_size,
        "returnType": "json",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        items = body.get("body", {}).get("items", {}).get("item", [])
        return items if isinstance(items, list) else [items]
    except Exception as e:
        log.error("평생교육바우처 수집 실패: %s", e)
        return []


def get_scholarship_info(
    university_name: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    """국가장학금 정보 조회 (한국장학재단 공공데이터).

    Args:
        university_name: 대학명 필터 (선택)
        page: 페이지 번호
        page_size: 페이지당 결과 수

    Returns:
        장학금 정보 리스트
    """
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        log.warning("DATA_GO_KR_API_KEY 미설정")
        return []

    url = "https://apis.data.go.kr/B190021/kftScholInfo/getScholarshipList"
    params = {
        "serviceKey": api_key,
        "pageNo":     page,
        "numOfRows":  page_size,
        "returnType": "json",
    }
    if university_name:
        params["univNm"] = university_name

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        items = body.get("body", {}).get("items", {}).get("item", [])
        return items if isinstance(items, list) else [items]
    except Exception as e:
        log.error("국가장학금 수집 실패: %s", e)
        return []


def get_vocational_training(
    region: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    """국민내일배움카드 직업훈련 과정 조회 (HRD-Net).

    Args:
        region: 지역명 (서울, 경기, 부산 등)
        keyword: 훈련과정명 검색어
        page: 페이지 번호
        page_size: 페이지당 결과 수

    Returns:
        직업훈련 과정 리스트
    """
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        log.warning("DATA_GO_KR_API_KEY 미설정")
        return []

    url = "https://www.work24.go.kr/cm/c/d/CMCD-500.do"
    params = {
        "authKey":    api_key,
        "returnType": "JSON",
        "pageNum":    page,
        "pageSize":   page_size,
        "outType":    "1",
        "srchTraProcessNm": keyword or "",
        "srchTraArea1":     region or "",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        return body.get("srchList", [])
    except Exception as e:
        log.error("직업훈련 수집 실패: %s", e)
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = get_lifelong_edu_voucher(page_size=3)
    for r in results:
        print(r)
