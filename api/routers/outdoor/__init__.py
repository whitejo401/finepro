"""outdoor 라우터 그룹 — 캠핑장·자연휴양림·치유의숲·날씨 기반 추천."""
from fastapi import APIRouter

from . import camping, forest, recommend

router = APIRouter()
router.include_router(camping.router,   prefix="/camping",   tags=["outdoor:camping"])
router.include_router(forest.router,    prefix="",           tags=["outdoor:forest"])
router.include_router(recommend.router, prefix="",           tags=["outdoor:recommend"])
