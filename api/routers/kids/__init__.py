"""kids 라우터 그룹 — 어린이·학생 무료 체험 행사."""
from fastapi import APIRouter

from . import events, museum, performance, library

router = APIRouter()
router.include_router(events.router,      prefix="/events",             tags=["kids:events"])
router.include_router(museum.router,      prefix="/events/museum",      tags=["kids:museum"])
router.include_router(performance.router, prefix="/events/performance",  tags=["kids:performance"])
router.include_router(library.router,     prefix="/events/library",     tags=["kids:library"])
