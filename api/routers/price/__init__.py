"""price 라우터 그룹 — 유가·농산물·생필품·CPI."""
from fastapi import APIRouter

from . import fuel, grocery, consumer, cpi

router = APIRouter()
router.include_router(fuel.router,     prefix="/fuel",     tags=["price:fuel"])
router.include_router(grocery.router,  prefix="/grocery",  tags=["price:grocery"])
router.include_router(consumer.router, prefix="/consumer", tags=["price:consumer"])
router.include_router(cpi.router,      prefix="/cpi",      tags=["price:cpi"])
