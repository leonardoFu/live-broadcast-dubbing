"""
Hook event receiver API endpoints.

Receives POST requests from MediaMTX hooks when streams become ready/not-ready.
"""

import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from media_service.models.events import HookEvent, NotReadyEvent, ReadyEvent

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ready", status_code=status.HTTP_200_OK)
async def handle_ready_event(event: HookEvent) -> JSONResponse:
    """
    Handle stream ready event from MediaMTX.

    This endpoint is called by MediaMTX when a stream becomes available.

    Args:
        event: Hook event payload with path, query, sourceType, sourceId

    Returns:
        JSONResponse with success status

    Raises:
        HTTPException: If event validation fails
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

        # TODO: Trigger worker lifecycle management (future implementation)
        # For now, just log the event

        return JSONResponse(
            {
                "status": "received",
                "message": "Ready event received",
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
async def handle_not_ready_event(event: HookEvent) -> JSONResponse:
    """
    Handle stream not-ready event from MediaMTX.

    This endpoint is called by MediaMTX when a stream becomes unavailable.

    Args:
        event: Hook event payload with path, query, sourceType, sourceId

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

        # TODO: Trigger worker lifecycle management (future implementation)
        # For now, just log the event

        return JSONResponse(
            {
                "status": "received",
                "message": "Not-ready event received",
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
