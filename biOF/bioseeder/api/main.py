import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from bioseeder.config import get_settings
from bioseeder.database import init_db, get_db
from bioseeder.api.routes import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    await init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Institutional-grade biotech financial intelligence & catalyst scoring platform",
    lifespan=lifespan,
)

# CORS configuration: Wildcard origins cannot be paired with allow_credentials=True
allow_creds = "*" not in settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/api/v1/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {exc}"
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


# Static assets & Terminal UI mounting
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_terminal_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"Welcome to {settings.PROJECT_NAME} API. Visit /docs for API documentation."}
