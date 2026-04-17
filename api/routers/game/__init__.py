"""game 라우터 그룹 — LoL·메이플·PUBG·FC·DNF·쿠키런·쿠폰·이벤트."""
from fastapi import APIRouter

from . import lol, maple, pubg, fc, dnf, cookierun, coupon, event

router = APIRouter()
router.include_router(lol.router,        prefix="/lol",        tags=["game:lol"])
router.include_router(maple.router,      prefix="/maple",      tags=["game:maple"])
router.include_router(pubg.router,       prefix="/pubg",       tags=["game:pubg"])
router.include_router(fc.router,         prefix="/fc",         tags=["game:fc"])
router.include_router(dnf.router,        prefix="/dnf",        tags=["game:dnf"])
router.include_router(cookierun.router,  prefix="/cookierun",  tags=["game:cookierun"])
router.include_router(coupon.router,     prefix="/coupon",     tags=["game:coupon"])
router.include_router(event.router,      prefix="/event",      tags=["game:event"])
