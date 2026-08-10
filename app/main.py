from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings
from app.api.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s", Settings().app_name)
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = Settings()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)

    from app.api.routes_ingestion import router as ingestion_router

    application.include_router(health_router)
    application.include_router(ingestion_router, prefix="/ingest", tags=["ingestion"])

    return application


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
