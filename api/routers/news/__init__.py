from fastapi import APIRouter
from . import headlines, geek

router = APIRouter()
router.include_router(headlines.router, prefix="/headlines")
router.include_router(geek.router,      prefix="/geek")
