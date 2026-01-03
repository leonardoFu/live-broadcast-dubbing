"""Fragment processing handlers for Echo STS Service.

Handles fragment:data and fragment:ack events, implementing the core
echo functionality and in-order delivery.
"""

import asyncio
import logging
import time
from typing import Any

from pydantic import ValidationError

from sts_service.echo.config import BackpressureConfig, get_config
from sts_service.echo.models.error import ErrorPayload
from sts_service.echo.models.fragment import (
    AudioData,
    BackpressurePayload,
    FragmentAckPayload,
    FragmentDataPayload,
    FragmentProcessedPayload,
    ProcessingError,
    ProcessingMetadata,
    StageTimings,
)
from sts_service.echo.session import SessionStore, StreamSession

logger = logging.getLogger(__name__)

# Maximum fragment size (10MB decoded from base64)
MAX_FRAGMENT_SIZE = 10 * 1024 * 1024
MAX_BASE64_SIZE = MAX_FRAGMENT_SIZE * 4 // 3 + 4


async def handle_fragment_data(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle fragment:data event.

    Processes an audio fragment by echoing it back with mock metadata.
    Implements in-order delivery via the session's pending buffer.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The fragment:data payload.
        session_store: Session store instance.
    """
    logger.info(f"📨 Received fragment:data: fragment_id={data.get('fragment_id')}, sid={sid}")
    start_time = time.monotonic()

    # Get session
    session = await session_store.get_by_sid(sid)
    if session is None:
        error = ErrorPayload.from_error_code(
            code="STREAM_NOT_FOUND",
            stream_id=data.get("stream_id"),
            fragment_id=data.get("fragment_id"),
        )
        await sio.emit("error", error.model_dump(), to=sid, namespace="/sts")
        return

    # Check if session can accept fragments
    if not session.can_accept_fragments():
        error = ErrorPayload.from_error_code(
            code="STREAM_NOT_FOUND",
            message=f"Stream is in {session.state} state, cannot accept fragments",
            stream_id=session.stream_id,
            fragment_id=data.get("fragment_id"),
        )
        await sio.emit("error", error.model_dump(), to=sid, namespace="/sts")
        return

    # Check fragment size before validation
    audio_data = data.get("audio", {})
    data_base64 = audio_data.get("data_base64", "")
    if len(data_base64) > MAX_BASE64_SIZE:
        error = ErrorPayload.from_error_code(
            code="FRAGMENT_TOO_LARGE",
            stream_id=session.stream_id,
            fragment_id=data.get("fragment_id"),
        )
        await sio.emit("error", error.model_dump(), to=sid, namespace="/sts")
        return

    try:
        # Validate payload
        payload = FragmentDataPayload(**data)
    except ValidationError as e:
        error = ErrorPayload(
            code="INVALID_CONFIG",
            message=f"Invalid fragment:data payload: {str(e)}",
            severity="error",
            retryable=False,
            stream_id=data.get("stream_id"),
            fragment_id=data.get("fragment_id"),
        )
        await sio.emit("error", error.model_dump(), to=sid, namespace="/sts")
        return

    # Track in-flight
    session.increment_inflight()

    # Send immediate ack
    ack = FragmentAckPayload(
        fragment_id=payload.fragment_id,
        status="queued",
        queue_position=session.inflight_count - 1,
    )
    await sio.emit("fragment:ack", ack.model_dump(), to=sid, namespace="/sts")

    # Check backpressure
    await _check_and_emit_backpressure(sio, sid, session)

    # Apply processing delay if configured
    if session.processing_delay_ms > 0:
        await asyncio.sleep(session.processing_delay_ms / 1000.0)

    # Check for error simulation
    error_result = _check_error_simulation(session, payload)

    # Calculate processing time
    processing_time_ms = int((time.monotonic() - start_time) * 1000)

    # Build response
    if error_result:
        # Return failed fragment
        response = FragmentProcessedPayload(
            fragment_id=payload.fragment_id,
            stream_id=payload.stream_id,
            sequence_number=payload.sequence_number,
            status="failed",
            processing_time_ms=processing_time_ms,
            error=error_result,
            stage_timings=StageTimings(asr_ms=0, translation_ms=0, tts_ms=0),
        )
        session.statistics.record_fragment("failed", processing_time_ms)
    else:
        # Echo the audio back (success)
        response = FragmentProcessedPayload(
            fragment_id=payload.fragment_id,
            stream_id=payload.stream_id,
            sequence_number=payload.sequence_number,
            status="success",
            dubbed_audio=AudioData(
                format=payload.audio.format,
                sample_rate_hz=payload.audio.sample_rate_hz,
                channels=payload.audio.channels,
                duration_ms=payload.audio.duration_ms,
                data_base64=payload.audio.data_base64,  # Echo original audio
            ),
            transcript=f"[ECHO] Original audio (seq={payload.sequence_number})",
            translated_text=f"[ECHO] Audio original (seq={payload.sequence_number})",
            processing_time_ms=processing_time_ms,
            stage_timings=StageTimings(
                asr_ms=processing_time_ms // 3,
                translation_ms=processing_time_ms // 3,
                tts_ms=processing_time_ms // 3,
            ),
            metadata=ProcessingMetadata(
                asr_model="echo-mock",
                translation_model="echo-mock",
                tts_model="echo-mock",
            ),
        )
        session.statistics.record_fragment("success", processing_time_ms)

    # Add to pending buffer for in-order delivery
    session.add_pending_fragment(payload.sequence_number, response)

    # Emit fragments that can be delivered in order
    # Note: inflight_count is decremented when worker sends fragment:ack,
    # not here, to ensure end-to-end acknowledgment tracking
    fragments_to_emit = session.get_fragments_to_emit()
    for fragment in fragments_to_emit:
        logger.info(f"📤 Emitting fragment:processed: fragment_id={fragment.fragment_id}, sid={sid}")
        await sio.emit("fragment:processed", fragment.model_dump(), to=sid, namespace="/sts")

    # Check if stream should complete
    if session.is_complete():
        logger.info(f"All fragments processed: stream_id={session.stream_id}, sid={sid}")


async def handle_fragment_ack(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle fragment:ack event from worker.

    Worker sends this to acknowledge receipt of fragment:processed.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The fragment:ack payload.
        session_store: Session store instance.
    """
    session = await session_store.get_by_sid(sid)
    if session is None:
        return  # Silently ignore ack for unknown session

    # Worker acknowledged receipt - decrement inflight count
    fragment_id = data.get("fragment_id")
    status = data.get("status")

    # Decrement in-flight count for end-to-end acknowledgment
    session.decrement_inflight()

    logger.debug(
        f"Fragment ack received: fragment_id={fragment_id}, "
        f"status={status}, inflight={session.inflight_count}, sid={sid}"
    )


def _check_error_simulation(
    session: StreamSession,
    payload: FragmentDataPayload,
) -> ProcessingError | None:
    """Check if error simulation should trigger for this fragment.

    Args:
        session: The stream session.
        payload: The fragment payload.

    Returns:
        ProcessingError if simulation should trigger, None otherwise.
    """
    if session.error_simulation is None:
        return None

    rule = session.error_simulation.find_matching_rule(
        sequence_number=payload.sequence_number,
        fragment_id=payload.fragment_id,
        fragment_count=session.fragment_count,
    )

    if rule is None:
        return None

    logger.info(
        f"Error simulation triggered: fragment_id={payload.fragment_id}, "
        f"sequence={payload.sequence_number}, error_code={rule.error_code}"
    )

    return ProcessingError(
        code=rule.error_code,
        message=rule.error_message,
        stage=rule.stage,
        retryable=rule.retryable,
    )


async def _check_and_emit_backpressure(
    sio: Any,
    sid: str,
    session: StreamSession,
) -> None:
    """Check backpressure state and emit event if needed.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        session: The stream session.
    """
    if not session.backpressure_enabled:
        return

    config = get_config()
    bp_config = BackpressureConfig.from_echo_config(config)

    # Calculate current load percentage
    if session.max_inflight == 0:
        return

    load_pct = session.inflight_count / session.max_inflight

    # Determine severity and action
    severity: str
    action: str
    recommended_delay_ms: int | None = None

    if load_pct >= bp_config.threshold_high:
        severity = "high"
        action = "pause"
        recommended_delay_ms = 1000
    elif load_pct >= bp_config.threshold_medium:
        severity = "medium"
        action = "slow_down"
        recommended_delay_ms = 500
    elif load_pct >= bp_config.threshold_low:
        severity = "low"
        action = "none"
    else:
        # Below threshold - check if we need to clear backpressure
        if session.backpressure_active:
            severity = "low"
            action = "none"
            session.backpressure_active = False
            # Emit clear event
            bp_payload = BackpressurePayload(
                stream_id=session.stream_id,
                severity=severity,
                current_inflight=session.inflight_count,
                queue_depth=len(session.pending_fragments),
                action=action,
            )
            await sio.emit("backpressure", bp_payload.model_dump(), to=sid, namespace="/sts")
        return

    # Emit backpressure event
    bp_payload = BackpressurePayload(
        stream_id=session.stream_id,
        severity=severity,
        current_inflight=session.inflight_count,
        queue_depth=len(session.pending_fragments),
        action=action,
        recommended_delay_ms=recommended_delay_ms,
    )

    session.backpressure_active = True
    await sio.emit("backpressure", bp_payload.model_dump(), to=sid, namespace="/sts")

    logger.debug(
        f"Backpressure emitted: stream_id={session.stream_id}, severity={severity}, action={action}"
    )


def register_fragment_handlers(
    sio: Any,
    session_store: SessionStore,
) -> None:
    """Register fragment event handlers on /sts namespace.

    Args:
        sio: Socket.IO server instance.
        session_store: Session store instance.
    """

    @sio.on("fragment:data", namespace="/sts")
    async def on_fragment_data(sid: str, data: dict[str, Any]) -> None:
        await handle_fragment_data(sio, sid, data, session_store)

    @sio.on("fragment:ack", namespace="/sts")
    async def on_fragment_ack(sid: str, data: dict[str, Any]) -> None:
        await handle_fragment_ack(sio, sid, data, session_store)
