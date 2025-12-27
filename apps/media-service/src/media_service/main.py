"""
Stream Orchestration Service - FastAPI Application

This service receives MediaMTX hook events and manages stream worker lifecycle.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from media_service.api import hooks

# Configure structured logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Stream orchestration service starting...")
    yield
    logger.info("Stream orchestration service shutting down...")


app = FastAPI(
    title="Media Service API",
    description="Receives MediaMTX hook events and manages stream worker lifecycle",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(hooks.router, prefix="/v1/mediamtx/events", tags=["hooks"])


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
