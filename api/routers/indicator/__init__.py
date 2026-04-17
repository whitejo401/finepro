"""indicator 라우터 그룹 — 거시경제 지표 통합."""
from fastapi import APIRouter

from . import inflation, growth, employment, trade, pmi, money, dashboard, calendar

router = APIRouter()
router.include_router(inflation.router)
router.include_router(growth.router)
router.include_router(employment.router)
router.include_router(trade.router)
router.include_router(pmi.router)
router.include_router(money.router)
router.include_router(dashboard.router)
router.include_router(calendar.router)
