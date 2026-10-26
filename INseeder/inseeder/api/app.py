import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from inseeder.db.database import Database
from inseeder.execution.paper_broker import PaperBroker
from inseeder.execution.notifier import Notifier
from inseeder.collectors.sec_edgar import SecEdgarCollector
from inseeder.worker import IngestionWorker
from inseeder.api.routes import router

from typing import Optional
from inseeder.config import settings
from inseeder.execution.alpaca_broker import AlpacaBroker
from inseeder.execution.ibkr_broker import IBKRBroker

def create_app(
    db_path: Optional[str] = None,
    start_worker: bool = False,
    broker_name: Optional[str] = None
) -> FastAPI:
    """Application factory for INseeder API server."""
    active_db_path = db_path or settings.DB_PATH
    db = Database(db_path=active_db_path)

    # Broker selection and initialization
    brokers = {}
    paper_broker = PaperBroker(db=db)
    brokers["paper"] = paper_broker

    if settings.ALPACA_API_KEY and settings.ALPACA_API_SECRET:
        brokers["alpaca"] = AlpacaBroker(
            api_key=settings.ALPACA_API_KEY,
            api_secret=settings.ALPACA_API_SECRET,
            base_url=settings.ALPACA_BASE_URL,
            db=db
        )

    if settings.IBKR_ACCOUNT_ID:
        brokers["ibkr"] = IBKRBroker(
            base_url=settings.IBKR_BASE_URL,
            account_id=settings.IBKR_ACCOUNT_ID
        )

    active_broker = (broker_name or settings.DEFAULT_BROKER).lower()
    broker = brokers.get(active_broker, paper_broker)

    notifier = Notifier(
        telegram_token=settings.TELEGRAM_BOT_TOKEN,
        telegram_chat_id=settings.TELEGRAM_CHAT_ID,
        discord_webhook_url=settings.DISCORD_WEBHOOK_URL
    )
    collector = SecEdgarCollector(
        user_agent=settings.SEC_USER_AGENT,
        poll_interval_sec=settings.POLL_INTERVAL_SEC
    )
    worker = IngestionWorker(db=db, broker=broker, notifier=notifier, collector=collector, brokers=brokers)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await db.init_db()
        worker_task = None
        if start_worker:
            worker_task = asyncio.create_task(worker.start_loop(interval_sec=settings.POLL_INTERVAL_SEC))

        yield

        # Shutdown
        if worker_task:
            worker.stop()
            worker_task.cancel()
        await collector.close()
        await notifier.close()
        await db.close()

    app = FastAPI(
        title="INseeder API",
        description="US Equities Insider Trading Detection, Scoring, Alerting, and Copy-Trading System",
        version="0.1.0",
        lifespan=lifespan
    )

    app.state.db = db
    app.state.broker = broker
    app.state.brokers = brokers
    app.state.notifier = notifier
    app.state.collector = collector
    app.state.worker = worker

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    # Mount static files if web directory exists
    web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web")
    if os.path.exists(web_dir):
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return app

# Default instance for uvicorn run
app = create_app(start_worker=True)

