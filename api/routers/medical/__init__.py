"""medical 라우터 그룹 — 병원·약국·응급실·AED·의약품·건강검진."""
from fastapi import APIRouter

from . import emergency, pharmacy, hospital, drug, checkup

router = APIRouter()
router.include_router(emergency.router, prefix="",           tags=["medical:emergency"])
router.include_router(pharmacy.router,  prefix="/pharmacy",  tags=["medical:pharmacy"])
router.include_router(hospital.router,  prefix="/hospital",  tags=["medical:hospital"])
router.include_router(drug.router,      prefix="/drug",      tags=["medical:drug"])
router.include_router(checkup.router,   prefix="/checkup",   tags=["medical:checkup"])
