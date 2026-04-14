from fastapi import APIRouter
from . import forecast

router = APIRouter()
router.include_router(forecast.router, prefix="/forecast")
