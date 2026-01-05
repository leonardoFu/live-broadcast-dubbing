"""
Hook event receiver API endpoints.

Receives POST requests from MediaMTX hooks when streams become ready/not-ready.
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from media_service.models.events import HookEvent, NotReadyEvent, ReadyEvent
from media_service.worker.worker_runner import WorkerConfig

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ready", status_code=status.HTTP_200_OK)
async def handle_ready_event(event: HookEvent, request: Request) -> JSONResponse:
    """
    Handle stream ready event from MediaMTX.

    This endpoint is called by MediaMTX when a stream becomes available.
    Creates and starts a worker for the stream.

    Args:
        event: Hook event payload with path, query, sourceType, sourceId
        request: FastAPI request object (for accessing app state)

    Returns:
        JSONResponse with success status

    Raises:
        HTTPException: If event validation fails or worker startup fails
    """
    try:
        # Convert to ReadyEvent for type safety
        ready_event = ReadyEvent(**event.model_dump())

        # Extract stream metadata
        stream_id = ready_event.extract_stream_id()
        direction = ready_event.extract_direction()

        # Log structured event with correlation fields
        logger.info(
            "Stream ready event received",
            extra={
                "event_type": "ready",
                "path": ready_event.path,
                "stream_id": stream_id,
                "direction": direction,
                "source_type": ready_event.source_type,
                "source_id": ready_event.source_id,
                "query": ready_event.query,
                "correlation_id": ready_event.correlation_id,
                "timestamp": ready_event.timestamp.isoformat(),
            },
        )

        # Only process input streams (direction=="in")
        if direction != "in":
            logger.debug(
                f"Skipping worker creation for non-input stream: "
                f"{stream_id} (direction={direction})"
            )
            return JSONResponse(
                {
                    "status": "skipped",
                    "message": "Non-input stream, worker not created",
                    "stream_id": stream_id,
                    "direction": direction,
                }
            )

        # Get WorkerManager from app state
        worker_manager = request.app.state.worker_manager

        # Create worker configuration
        mediamtx_host = os.getenv("MEDIAMTX_HOST", "mediamtx")
        sts_url = os.getenv("STS_SERVICE_URL", "http://localhost:3000")
        segment_dir = Path(os.getenv("WORKER_SEGMENT_DIR", "/tmp/segments"))

        config = WorkerConfig(
            stream_id=stream_id,
            rtmp_input_url=f"rtmp://{mediamtx_host}:1935/live/{stream_id}/in",
            rtmp_url=f"rtmp://{mediamtx_host}:1935/live/{stream_id}/out",
            sts_url=sts_url,
            segment_dir=segment_dir / stream_id,
            source_language=os.getenv("WORKER_SOURCE_LANGUAGE", "en"),
            target_language=os.getenv("WORKER_TARGET_LANGUAGE", "zh"),
        )

        # Start worker (idempotent - safe to call multiple times)
        await worker_manager.start_worker(stream_id, config)

        logger.info(
            f"Worker started for stream {stream_id}",
            extra={
                "stream_id": stream_id,
                "correlation_id": ready_event.correlation_id,
            },
        )

        return JSONResponse(
            {
                "status": "worker_started",
                "message": "Worker created and started successfully",
                "stream_id": stream_id,
                "correlation_id": ready_event.correlation_id,
            }
        )

    except ValueError as e:
        logger.error(f"Invalid hook event: {e}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error processing ready event")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post("/not-ready", status_code=status.HTTP_200_OK)
async def handle_not_ready_event(event: HookEvent, request: Request) -> JSONResponse:
    """
    Handle stream not-ready event from MediaMTX.

    This endpoint is called by MediaMTX when a stream becomes unavailable.
    Stops and cleans up the worker for the stream.

    Args:
        event: Hook event payload with path, query, sourceType, sourceId
        request: FastAPI request object (for accessing app state)

    Returns:
        JSONResponse with success status

    Raises:
        HTTPException: If event validation fails
    """
    try:
        # Convert to NotReadyEvent for type safety
        not_ready_event = NotReadyEvent(**event.model_dump())

        # Extract stream metadata
        stream_id = not_ready_event.extract_stream_id()
        direction = not_ready_event.extract_direction()

        # Log structured event with correlation fields
        logger.info(
            "Stream not-ready event received",
            extra={
                "event_type": "not-ready",
                "path": not_ready_event.path,
                "stream_id": stream_id,
                "direction": direction,
                "source_type": not_ready_event.source_type,
                "source_id": not_ready_event.source_id,
                "query": not_ready_event.query,
                "correlation_id": not_ready_event.correlation_id,
                "timestamp": not_ready_event.timestamp.isoformat(),
            },
        )

        # Only process input streams (direction=="in")
        if direction != "in":
            logger.debug(
                f"Skipping worker cleanup for non-input stream: {stream_id} (direction={direction})"
            )
            return JSONResponse(
                {
                    "status": "skipped",
                    "message": "Non-input stream, no worker to stop",
                    "stream_id": stream_id,
                    "direction": direction,
                }
            )

        # Get WorkerManager from app state
        worker_manager = request.app.state.worker_manager

        # Stop worker (idempotent - safe to call even if worker doesn't exist)
        await worker_manager.stop_worker(stream_id)

        logger.info(
            f"Worker stopped for stream {stream_id}",
            extra={
                "stream_id": stream_id,
                "correlation_id": not_ready_event.correlation_id,
            },
        )

        return JSONResponse(
            {
                "status": "worker_stopped",
                "message": "Worker stopped successfully",
                "stream_id": stream_id,
                "correlation_id": not_ready_event.correlation_id,
            }
        )

    except ValueError as e:
        logger.error(f"Invalid hook event: {e}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error processing not-ready event")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
