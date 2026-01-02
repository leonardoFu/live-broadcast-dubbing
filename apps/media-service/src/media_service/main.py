"""
Stream Orchestration Service - FastAPI Application

This service receives MediaMTX hook events and manages stream worker lifecycle.
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import REGISTRY, generate_latest

from media_service.api import hooks
from media_service.orchestrator.worker_manager import WorkerManager

# Configure structured logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Initializes WorkerManager on startup and cleans up all workers on shutdown.
    """
    # Startup
    logger.info("Stream orchestration service starting...")

    # Initialize WorkerManager and attach to app state
    worker_manager = WorkerManager()
    app.state.worker_manager = worker_manager

    logger.info("WorkerManager initialized and ready to accept hook events")

    yield

    # Shutdown
    logger.info("Stream orchestration service shutting down...")

    # Cleanup all active workers
    await worker_manager.cleanup_all()

    logger.info("All workers cleaned up, shutdown complete")


app = FastAPI(
    title="Media Service API",
    description="Receives MediaMTX hook events and manages stream worker lifecycle",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(hooks.router, prefix="/v1/mediamtx/events", tags=["hooks"])


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    """Expose Prometheus metrics endpoint."""
    return PlainTextResponse(
        content=generate_latest(REGISTRY).decode("utf-8"),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "service": "media-service"})


@app.get("/")
async def root() -> JSONResponse:
    """Root endpoint."""
    return JSONResponse(
        {
            "service": "stream-orchestration",
            "version": "0.1.0",
            "status": "running",
        }
    )
