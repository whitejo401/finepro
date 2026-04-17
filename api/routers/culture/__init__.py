"""culture 라우터 그룹 — 문화행사·축제·공연·전시."""
from fastapi import APIRouter

from . import trending, festival, performance, exhibition

router = APIRouter()
router.include_router(trending.router,    prefix="/events",             tags=["culture:events"])
router.include_router(festival.router,    prefix="/events/festival",    tags=["culture:festival"])
router.include_router(performance.router, prefix="/events/performance", tags=["culture:performance"])
router.include_router(exhibition.router,  prefix="/events/exhibition",  tags=["culture:exhibition"])
