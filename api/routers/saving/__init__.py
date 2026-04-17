"""saving 라우터 그룹 — 예금·적금·ISA·연금저축·ETF·추천."""
from fastapi import APIRouter

from . import deposit, pension, etf, recommend

router = APIRouter()
router.include_router(deposit.router,   prefix="",         tags=["saving:deposit"])
router.include_router(pension.router,   prefix="",         tags=["saving:pension"])
router.include_router(etf.router,       prefix="/etf",     tags=["saving:etf"])
router.include_router(recommend.router, prefix="",         tags=["saving:recommend"])
