"""card 라우터 그룹 — 카드 검색·비교·이벤트·추천."""
from fastapi import APIRouter

from . import search, compare, event, recommend

router = APIRouter()
router.include_router(search.router,    prefix="",  tags=["card:search"])
router.include_router(compare.router,   prefix="",  tags=["card:compare"])
router.include_router(event.router,     prefix="",  tags=["card:event"])
router.include_router(recommend.router, prefix="",  tags=["card:recommend"])
