"""index 라우터 그룹 — 글로벌 주식·달러·변동성·섹터·채권·원자재·분석."""
from fastapi import APIRouter

from . import equity, dollar, volatility, sector, bond, commodity, analysis

router = APIRouter()
router.include_router(equity.router,     tags=["index:equity"])
router.include_router(dollar.router,     tags=["index:dollar"])
router.include_router(volatility.router, tags=["index:volatility"])
router.include_router(sector.router,     tags=["index:sector"])
router.include_router(bond.router,       tags=["index:bond"])
router.include_router(commodity.router,  tags=["index:commodity"])
router.include_router(analysis.router,   tags=["index:analysis"])
