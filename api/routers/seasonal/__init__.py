"""seasonal 라우터 그룹 — 계절별 야외시설 개장 현황."""
from fastapi import APIRouter

from . import water, winter, now

router = APIRouter()
router.include_router(water.router,  prefix="", tags=["seasonal:water"])
router.include_router(winter.router, prefix="", tags=["seasonal:winter"])
router.include_router(now.router,    prefix="", tags=["seasonal:now"])
