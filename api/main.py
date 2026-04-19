"""FastAPI 메인 앱 — 주제별 라우터 등록."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import finance, benefits, realestate, crypto, exchange, weather, news
from api.routers.index import router as index_router
from api.routers.indicator import router as indicator_router
from api.routers.invest import router as invest_router
from api.routers.crypto_intel import router as crypto_intel_router
from api.routers.kids import router as kids_router
from api.routers.culture import router as culture_router
from api.routers.outdoor import router as outdoor_router
from api.routers.travel import router as travel_router
from api.routers.price import router as price_router
from api.routers.medical import router as medical_router
from api.routers.seasonal import router as seasonal_router
from api.routers.saving import router as saving_router
from api.routers.game import router as game_router
from api.routers.transit import router as transit_router
from api.routers.card import router as card_router

app = FastAPI(
    title="Info API",
    description="금융·혜택·부동산·암호화폐·환율·날씨·뉴스 등 주제별 정보 API",
    version="1.0.0",
)

# CORS (Next.js 개발 서버 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영 시 실제 도메인으로 교체
    allow_methods=["GET"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(finance.router,    prefix="/api/v1/finance",    tags=["finance"])
app.include_router(benefits.router,   prefix="/api/v1/benefits",   tags=["benefits"])
app.include_router(realestate.router, prefix="/api/v1/realestate", tags=["realestate"])
app.include_router(crypto.router,     prefix="/api/v1/crypto",     tags=["crypto"])
app.include_router(exchange.router,   prefix="/api/v1/exchange",   tags=["exchange"])
app.include_router(weather.router,    prefix="/api/v1/weather",    tags=["weather"])
app.include_router(news.router,       prefix="/api/v1/news",       tags=["news"])
app.include_router(index_router,      prefix="/api/v1/index",      tags=["index"])
app.include_router(indicator_router,  prefix="/api/v1/indicator",  tags=["indicator"])
app.include_router(invest_router,        prefix="/api/v1/invest",        tags=["invest"])
app.include_router(crypto_intel_router, prefix="/api/v1/crypto_intel",  tags=["crypto_intel"])
app.include_router(kids_router,         prefix="/api/v1/kids",           tags=["kids"])
app.include_router(culture_router,      prefix="/api/v1/culture",        tags=["culture"])
app.include_router(outdoor_router,      prefix="/api/v1/outdoor",        tags=["outdoor"])
app.include_router(travel_router,       prefix="/api/v1/travel",         tags=["travel"])
app.include_router(price_router,        prefix="/api/v1/price",          tags=["price"])
app.include_router(medical_router,      prefix="/api/v1/medical",        tags=["medical"])
app.include_router(seasonal_router,     prefix="/api/v1/seasonal",       tags=["seasonal"])
app.include_router(saving_router,       prefix="/api/v1/saving",         tags=["saving"])
app.include_router(game_router,         prefix="/api/v1/game",           tags=["game"])
app.include_router(transit_router,      prefix="/api/v1/transit",        tags=["transit"])
app.include_router(card_router,         prefix="/api/v1/card",           tags=["card"])


@app.get("/api/v1/data/status", tags=["system"])
def data_status():
    """master 데이터 신선도 상태 확인."""
    from api.core.master import get_master_meta
    return get_master_meta()


@app.get("/api/v1/health", tags=["system"])
def health():
    """서비스 헬스체크."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "service": "Info API",
        "version": "1.0.0",
        "groups": [
            "/api/v1/finance",
            "/api/v1/benefits",
            "/api/v1/realestate",
            "/api/v1/crypto",
            "/api/v1/exchange",
            "/api/v1/weather",
            "/api/v1/news",
            "/api/v1/index",
            "/api/v1/indicator",
            "/api/v1/invest",
            "/api/v1/crypto_intel",
            "/api/v1/kids",
            "/api/v1/culture",
            "/api/v1/outdoor",
            "/api/v1/travel",
            "/api/v1/price",
            "/api/v1/medical",
            "/api/v1/seasonal",
            "/api/v1/saving",
            "/api/v1/game",
            "/api/v1/transit",
            "/api/v1/card",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
