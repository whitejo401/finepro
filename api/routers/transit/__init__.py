"""transit 라우터 그룹 — 열차·버스·고속도로·지하철·비교."""
from fastapi import APIRouter

from . import train, bus, highway, subway, compare

router = APIRouter()
router.include_router(train.router,   prefix="/train",   tags=["transit:train"])
router.include_router(bus.router,     prefix="/bus",     tags=["transit:bus"])
router.include_router(highway.router, prefix="/highway", tags=["transit:highway"])
router.include_router(subway.router,  prefix="/subway",  tags=["transit:subway"])
router.include_router(compare.router, prefix="",         tags=["transit:compare"])
