from fastapi import APIRouter
from . import central, education

router = APIRouter()
router.include_router(central.router,   prefix="/central")
router.include_router(education.router, prefix="/education")
