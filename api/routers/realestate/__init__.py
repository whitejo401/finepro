from fastapi import APIRouter
from . import apt

router = APIRouter()
router.include_router(apt.router, prefix="/apt")
