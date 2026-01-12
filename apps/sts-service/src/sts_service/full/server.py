"""Socket.IO server setup for Full STS Service.

Creates FastAPI app combined with Socket.IO AsyncServer per spec 021.
"""

import logging

import socketio
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from sts_service.full.handlers.fragment import register_fragment_handlers
from sts_service.full.handlers.lifecycle import register_lifecycle_handlers
from sts_service.full.handlers.stream import register_stream_handlers
from sts_service.full.session import SessionStore

logger = logging.getLogger(__name__)


def create_app() -> socketio.ASGIApp:
    """Create FastAPI + Socket.IO ASGI application.

    Returns:
        Combined ASGI app with FastAPI and Socket.IO.
    """
    # Create FastAPI app for HTTP endpoints
    fastapi_app = FastAPI(
        title="Full STS Service",
        description="Speech-to-speech dubbing service with ASR, Translation, and TTS",
        version="0.1.0",
    )

    # Add CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development (restrict in production)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @fastapi_app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "full-sts-service"}

    # Prometheus metrics endpoint
    @fastapi_app.get("/metrics")
    async def metrics_endpoint():
        """
        Prometheus metrics endpoint.

        Returns metrics in Prometheus text format including:
        - Fragment processing latency histograms
        - Stage timing histograms (ASR, Translation, TTS)
        - In-flight fragment count gauge
        - Error counters by stage and code
        - Active session count gauge
        - GPU utilization metrics (if available)
        """
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Create Socket.IO AsyncServer
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins="*",  # Allow all origins for development
        logger=False,  # Use our own logger
        engineio_logger=False,
        max_http_buffer_size=10 * 1024 * 1024,  # 10MB max message size
    )

    # Create session store and backpressure tracker
    session_store = SessionStore()
    # TODO: BackpressureTracker should be per-session, not global
    # For now, create a dummy instance - handlers create per-session trackers
    backpressure_tracker = None  # Handlers will manage their own trackers

    # Register event handlers
    register_lifecycle_handlers(sio, session_store)
    register_stream_handlers(sio, session_store)
    register_fragment_handlers(sio, session_store, backpressure_tracker)

    logger.info("Full STS Service handlers registered")

    # Combine FastAPI and Socket.IO into single ASGI app
    app = socketio.ASGIApp(
        socketio_server=sio,
        other_asgi_app=fastapi_app,
    )

    return app
