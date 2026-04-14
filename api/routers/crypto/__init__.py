from fastapi import APIRouter
from . import market

router = APIRouter()
router.include_router(market.router, prefix="/market")
