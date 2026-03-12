"""
AI Judge Backend - Main Application Entry Point
Connects React frontend to NLP scorer, AI advisor, and Mistral 7B judge model.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import debate, judgment, advisor
from services.message_queue import rabbitmq_manager
from workers.judgment_worker import JudgmentWorker
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

worker_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    global worker_task

    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("🚀  Starting AI Judge Backend…")

    # Connect to RabbitMQ
    await rabbitmq_manager.connect()

    # Start background judgment worker
    worker = JudgmentWorker()
    worker_task = asyncio.create_task(worker.start())
    logger.info("✅  Judgment worker started")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("🛑  Shutting down…")
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    await rabbitmq_manager.disconnect()
    logger.info("👋  Shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Judge API",
    description="Backend orchestrating AI Advisor, NLP scorer and Mistral 7B judge model.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (allow React dev server + production) ────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(debate.router,    prefix="/debate",   tags=["Debate"])
app.include_router(judgment.router,  prefix="/judgment", tags=["Judgment"])
app.include_router(advisor.router,   prefix="/advisor",  tags=["Advisor"])


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "queue": await rabbitmq_manager.health(),
    }
