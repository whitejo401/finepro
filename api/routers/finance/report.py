"""finance/report — 일간/주간/월간 리포트 메타 엔드포인트."""
import glob
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.core.cache import cache
from api.core.response import ok
from config import BASE_DIR

router = APIRouter()

REPORTS_DIR = BASE_DIR / "reports"


def _list_reports(prefix: str) -> list[dict]:
    pattern = str(REPORTS_DIR / f"{prefix}*.html")
    files = sorted(glob.glob(pattern), reverse=True)
    return [
        {"filename": os.path.basename(f), "path": f}
        for f in files[:30]
    ]


@router.get("/list")
def report_list(type: str = "daily"):
    """리포트 목록 반환. type: daily | weekly | monthly"""
    prefix_map = {"daily": "daily_", "weekly": "weekly_", "monthly": "monthly_"}
    prefix = prefix_map.get(type, "daily_")
    cached = cache.get(f"finance:report:list:{type}")
    if cached:
        return cached
    resp = ok(_list_reports(prefix), meta={"type": type})
    cache.set(f"finance:report:list:{type}", resp, 600)
    return resp


@router.get("/latest")
def report_latest(type: str = "daily"):
    """가장 최신 리포트 HTML 파일 반환."""
    prefix_map = {"daily": "daily_", "weekly": "weekly_", "monthly": "monthly_"}
    prefix = prefix_map.get(type, "daily_")
    files = sorted(glob.glob(str(REPORTS_DIR / f"{prefix}*.html")), reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="리포트 없음")
    return FileResponse(files[0], media_type="text/html")
