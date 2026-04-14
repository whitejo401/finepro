from fastapi import APIRouter
from . import market, signal, report

router = APIRouter()
router.include_router(market.router,  prefix="/market")
router.include_router(signal.router,  prefix="/signal")
router.include_router(report.router,  prefix="/report")
