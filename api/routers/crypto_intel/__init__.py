"""crypto_intel 라우터 그룹 — 섹터·기관보유량·개발활동."""
from fastapi import APIRouter

from . import sector, institution, dev

router = APIRouter()
router.include_router(sector.router,      prefix="/sector",      tags=["crypto_intel:sector"])
router.include_router(institution.router, prefix="/institution", tags=["crypto_intel:institution"])
router.include_router(dev.router,         prefix="/dev",         tags=["crypto_intel:dev"])
