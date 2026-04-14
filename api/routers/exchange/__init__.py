from fastapi import APIRouter
from . import rates

router = APIRouter()
router.include_router(rates.router, prefix="/rates")
