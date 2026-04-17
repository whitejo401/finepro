"""travel 라우터 그룹 — 숙박·여행 할인 이벤트·패키지."""
from fastapi import APIRouter

from . import stay, discount, packages

router = APIRouter()
router.include_router(stay.router,     prefix="/stay",     tags=["travel:stay"])
router.include_router(discount.router, prefix="/discount", tags=["travel:discount"])
router.include_router(packages.router, prefix="/packages", tags=["travel:packages"])
