from fastapi import APIRouter
from bioseeder.api.routes.catalysts import router as catalysts_router
from bioseeder.api.routes.screener import router as screener_router
from bioseeder.api.routes.companies import router as companies_router
from bioseeder.api.routes.live_feed import router as live_feed_router
from bioseeder.api.routes.seed import router as seed_router

api_router = APIRouter()
api_router.include_router(catalysts_router, tags=["Catalysts"])
api_router.include_router(screener_router, tags=["Screener"])
api_router.include_router(companies_router, tags=["Companies"])
api_router.include_router(live_feed_router, tags=["Live Feed"])
api_router.include_router(seed_router, tags=["Seed & Utilities"])

__all__ = ["api_router"]
