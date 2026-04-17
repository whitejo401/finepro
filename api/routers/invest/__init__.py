"""invest 라우터 그룹 — 국내 주식·ETF·펀드 투자 정보."""
from fastapi import APIRouter

from . import stock, etf, fund

router = APIRouter()
router.include_router(stock.router, prefix="/stock", tags=["invest:stock"])
router.include_router(etf.router,   prefix="/etf",   tags=["invest:etf"])
router.include_router(fund.router,  prefix="/fund",  tags=["invest:fund"])
