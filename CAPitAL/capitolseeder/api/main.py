from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from capitolseeder.config import get_settings
from capitolseeder.db.session import init_db
import asyncio
import logging
from capitolseeder.api.routers import (
    trades,
    politicians,
    clusters,
    conflicts,
    violations,
    simulate,
    alerts,
    websocket
)
from capitolseeder.ingestion.live_feed import sync_live_congress_trades

logger = logging.getLogger("capitolseeder.background")
settings = get_settings()

async def background_live_feed_worker():
    """
    Periodically checks the live congressional disclosures stream and broadcasts updates.
    Runs every 45 seconds in the background.
    """
    logger.info("Starting background congressional live feed worker (interval: 45s)...")
    # Wait a few seconds after startup before initial sync
    await asyncio.sleep(5)
    while True:
        try:
            logger.info("Executing periodic live feed synchronization...")
            count = await sync_live_congress_trades(limit=100)
            if count > 0:
                logger.info(f"Background worker ingested {count} new congressional disclosure(s).")
        except asyncio.CancelledError:
            logger.info("Background live feed worker cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in background live feed worker: {e}")
        
        await asyncio.sleep(45)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and WAL mode on startup
    await init_db()
    # Spawn real-time live feed synchronization background worker
    worker_task = asyncio.create_task(background_live_feed_worker())
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="CAPitAL API",
    description="CAPitAL — Institutional Congressional Financial Intelligence Platform",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 Routers
app.include_router(websocket.router, prefix="/api/v1")
app.include_router(trades.router, prefix="/api/v1")
app.include_router(politicians.router, prefix="/api/v1")
app.include_router(clusters.router, prefix="/api/v1")
app.include_router(conflicts.router, prefix="/api/v1")
app.include_router(violations.router, prefix="/api/v1")
app.include_router(simulate.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")


# Mount static files
static_dir = settings.base_dir / "capitolseeder" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"status": "online", "message": "CAPitAL API is running. Access /docs for API documentation."}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "CAPitAL"}
