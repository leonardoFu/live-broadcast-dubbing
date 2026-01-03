"""Fragment processing handlers for Full STS Service.

Handles fragment:data event and emits fragment:ack and fragment:processed
as defined in spec 021.
"""

import asyncio
import logging
import time
from typing import Any

from pydantic import ValidationError

from sts_service.full.backpressure_tracker import BackpressureTracker
from sts_service.full.models.asset import AssetStatus
from sts_service.full.models.error import ErrorResponse
from sts_service.full.models.fragment import AckStatus, FragmentAck, FragmentData, FragmentResult, ProcessingStatus
from sts_service.full.models.stream import StreamState
from sts_service.full.observability.metrics import decrement_inflight, increment_inflight
from sts_service.full.session import SessionStore, StreamSession

logger = logging.getLogger(__name__)


async def handle_fragment_data(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
    backpressure_tracker: BackpressureTracker,
) -> None:
    """Handle fragment:data event.

    Validates fragment data, emits immediate fragment:ack, enqueues for processing.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The fragment:data payload.
        session_store: Session store instance.
        backpressure_tracker: Backpressure tracker instance.
    """
    try:
        # Validate payload
        fragment_data = FragmentData(**data)

        session = await session_store.get_by_sid(sid)
        if session is None:
            error = ErrorResponse(
                code="STREAM_NOT_FOUND",
                message="Stream session not found",
                severity="error",
                retryable=False,
                stream_id=fragment_data.stream_id,
            )
            await sio.emit("error", error.model_dump(), to=sid)
            return

        # Check if session can accept fragments
        if not session.can_accept_fragments():
            error = ErrorResponse(
                code="STREAM_PAUSED" if session.state == StreamState.PAUSED else "STREAM_NOT_READY",
                message=f"Stream is not accepting fragments (state={session.state.value})",
                severity="warning",
                retryable=True,
                stream_id=fragment_data.stream_id,
            )
            await sio.emit("error", error.model_dump(), to=sid)
            return

        # Check backpressure - reject if critical
        if backpressure_tracker and backpressure_tracker.should_reject_fragment(session.stream_id):
            error = ErrorResponse(
                code="BACKPRESSURE_EXCEEDED",
                message=f"Too many in-flight fragments ({session.inflight_count}), rejecting new request",
                severity="error",
                retryable=True,
                stream_id=fragment_data.stream_id,
            )
            await sio.emit("error", error.model_dump(), to=sid)
            return
        # Simple backpressure check using session count when tracker not available
        elif not backpressure_tracker and session.inflight_count > 10:
            error = ErrorResponse(
                code="BACKPRESSURE_EXCEEDED",
                message=f"Too many in-flight fragments ({session.inflight_count}), rejecting new request",
                severity="error",
                retryable=True,
                stream_id=fragment_data.stream_id,
            )
            await sio.emit("error", error.model_dump(), to=sid)
            return

        # Emit immediate fragment:ack
        ack = FragmentAck(
            fragment_id=fragment_data.fragment_id,
            status=AckStatus.QUEUED,
            timestamp=int(time.time() * 1000),
        )
        await sio.emit("fragment:ack", ack.model_dump(), to=sid)
        # CRITICAL: Force event loop to process the emit in ASGI mode
        await sio.sleep(0)

        # Increment in-flight count and track metrics
        session.increment_inflight()
        if backpressure_tracker:
            backpressure_tracker.increment_inflight(session.stream_id)
        increment_inflight(session.stream_id)  # Track in-flight fragments

        # Check backpressure state and emit event if needed
        if backpressure_tracker:
            bp_state = backpressure_tracker.get_backpressure_state(session.stream_id)
            if bp_state.severity != "none":
                await sio.emit("backpressure", bp_state.model_dump(), to=sid)
                logger.warning(
                    f"Backpressure {bp_state.severity}: stream_id={session.stream_id}, "
                    f"inflight={bp_state.current_inflight}, action={bp_state.action}"
                )

        # Process fragment asynchronously
        asyncio.create_task(
            _process_fragment_async(
                sio=sio,
                sid=sid,
                fragment_data=fragment_data,
                session=session,
                backpressure_tracker=backpressure_tracker,
            )
        )

        logger.debug(
            f"Fragment queued: fragment_id={fragment_data.fragment_id}, "
            f"seq={fragment_data.sequence_number}, stream_id={fragment_data.stream_id}"
        )

    except ValidationError as e:
        logger.warning(f"Invalid fragment:data payload: {e}")

        error = ErrorResponse(
            code="MALFORMED_DATA",
            message=f"Invalid fragment:data payload: {str(e)}",
            severity="error",
            retryable=False,
            stream_id=data.get("stream_id"),
        )

        await sio.emit("error", error.model_dump(), to=sid)

    except Exception as e:
        logger.exception(f"Error handling fragment:data: {e}")

        error = ErrorResponse(
            code="PROCESSING_ERROR",
            message=f"Failed to process fragment: {str(e)}",
            severity="error",
            retryable=True,
            stream_id=data.get("stream_id"),
        )

        await sio.emit("error", error.model_dump(), to=sid)


async def _process_fragment_async(
    sio: Any,
    sid: str,
    fragment_data: FragmentData,
    session: StreamSession,
    backpressure_tracker: BackpressureTracker,
) -> None:
    """Process fragment asynchronously through pipeline.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        fragment_data: The fragment data to process.
        session: The stream session.
        backpressure_tracker: Backpressure tracker instance.
    """
    try:
        # Call pipeline coordinator
        if session.pipeline_coordinator is None:
            raise RuntimeError("Pipeline coordinator not initialized")

        result = await session.pipeline_coordinator.process_fragment(fragment_data, session)

        # Add to pending fragments for in-order emission
        session.add_pending_fragment(fragment_data.sequence_number, result)

        # Emit fragments in order
        fragments_to_emit = session.get_fragments_to_emit()
        for frag_result in fragments_to_emit:
            await emit_fragment_processed(
                sio=sio,
                sid=sid,
                fragment_result=frag_result,
                session=session,
                backpressure_tracker=backpressure_tracker,
            )

    except Exception as e:
        logger.exception(f"Error processing fragment {fragment_data.fragment_id}: {e}")

        # Create error result
        from sts_service.full.models.fragment import ProcessingError

        error_result = FragmentResult(
            fragment_id=fragment_data.fragment_id,
            stream_id=fragment_data.stream_id,
            sequence_number=fragment_data.sequence_number,
            status=ProcessingStatus.FAILED,
            processing_time_ms=0,
            error=ProcessingError(
                stage="pipeline",
                code="PROCESSING_ERROR",
                message=str(e),
                retryable=True,
            ),
        )

        # Add to pending and try to emit
        session.add_pending_fragment(fragment_data.sequence_number, error_result)
        fragments_to_emit = session.get_fragments_to_emit()
        for frag_result in fragments_to_emit:
            await emit_fragment_processed(
                sio=sio,
                sid=sid,
                fragment_result=frag_result,
                session=session,
                backpressure_tracker=backpressure_tracker,
            )


async def emit_fragment_processed(
    sio: Any,
    sid: str,
    fragment_result: FragmentResult,
    session: StreamSession,
    backpressure_tracker: BackpressureTracker,
) -> None:
    """Emit fragment:processed event and update statistics.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        fragment_result: The processed fragment result.
        session: The stream session.
        backpressure_tracker: Backpressure tracker instance.
    """
    # Emit fragment:processed
    await sio.emit(
        "fragment:processed",
        fragment_result.model_dump(),
        to=sid,
    )
    # CRITICAL: Force event loop to process the emit in ASGI mode
    await sio.sleep(0)

    # Decrement in-flight count and track metrics
    session.decrement_inflight()
    if backpressure_tracker:
        backpressure_tracker.decrement_inflight(session.stream_id)
    decrement_inflight(session.stream_id)  # Always decrement even if processing failed

    # Update statistics
    status_str = "success" if fragment_result.status == ProcessingStatus.SUCCESS else "failed"
    session.statistics.record_fragment(
        status=status_str,
        processing_time_ms=fragment_result.processing_time_ms,
    )

    # Check backpressure state again (may have dropped below threshold)
    if backpressure_tracker:
        bp_state = backpressure_tracker.get_backpressure_state(session.stream_id)
        if bp_state.severity == "none" and session.inflight_count < session.max_inflight:
            # Backpressure relieved
            logger.info(
                f"Backpressure relieved: stream_id={session.stream_id}, inflight={session.inflight_count}"
            )

    logger.debug(
        f"Fragment processed: fragment_id={fragment_result.fragment_id}, "
        f"status={fragment_result.status.value}, latency={fragment_result.processing_time_ms:.0f}ms"
    )


def register_fragment_handlers(
    sio: Any,
    session_store: SessionStore,
    backpressure_tracker: BackpressureTracker,
) -> None:
    """Register fragment event handlers.

    Args:
        sio: Socket.IO server instance.
        session_store: Session store instance.
        backpressure_tracker: Backpressure tracker instance.
    """

    @sio.on("fragment:data")
    async def on_fragment_data(sid: str, data: dict[str, Any]) -> None:
        await handle_fragment_data(sio, sid, data, session_store, backpressure_tracker)
