"""Stream lifecycle handlers for Full STS Service.

Handles stream:init, stream:pause, stream:resume, stream:end events
as defined in spec 021.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from sts_service.asr.factory import create_asr_component
from sts_service.asr.models import ASRConfig
from sts_service.full.models.error import ErrorResponse
from sts_service.full.models.stream import (
    ServerCapabilities,
    StreamCompletePayload,
    StreamInitPayload,
    StreamReadyPayload,
    StreamState,
    StreamStatistics,
)
from sts_service.full.observability.metrics import (
    decrement_active_sessions,
    increment_active_sessions,
)
from sts_service.full.pipeline import PipelineCoordinator
from sts_service.full.session import SessionStore, StreamSession
from sts_service.translation.factory import create_translation_component
from sts_service.translation.models import TranslationConfig
from sts_service.tts.factory import create_tts_component
from sts_service.tts.models import TTSConfig

logger = logging.getLogger(__name__)


def load_voices_config() -> dict[str, Any]:
    """Load voice profiles from voices.json.

    Returns:
        Dictionary of voice profiles.

    Raises:
        FileNotFoundError: If voices.json not found.
    """
    voices_path = Path("apps/sts-service/configs/voices.json")
    if not voices_path.exists():
        # Fallback to relative path
        voices_path = Path("configs/voices.json")

    if not voices_path.exists():
        logger.warning("voices.json not found, using default voice only")
        return {"default": {"model": "tts_models/en/vctk/vits", "speaker": "p225"}}

    with open(voices_path) as f:
        return json.load(f)


async def handle_stream_init(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle stream:init event.

    Validates the initialization payload, creates a session, initializes
    ASR/Translation/TTS modules, and responds with stream:ready or an error.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The stream:init payload.
        session_store: Session store instance.
    """
    try:
        # Validate payload
        payload = StreamInitPayload(**data)

        # Load and validate voice profile
        voices_config = load_voices_config()
        if payload.config.voice_profile not in voices_config:
            error = ErrorResponse(
                code="INVALID_VOICE_PROFILE",
                message=f"Voice profile '{payload.config.voice_profile}' not found in voices.json",
                severity="error",
                retryable=False,
                stream_id=payload.stream_id,
            )
            await sio.emit("error", error.model_dump(), to=sid)
            return

        # Create session
        session = await session_store.create(
            sid=sid,
            stream_id=payload.stream_id,
            worker_id=payload.worker_id,
        )

        # Apply configuration from payload
        session.source_language = payload.config.source_language
        session.target_language = payload.config.target_language
        session.voice_profile = payload.config.voice_profile
        session.chunk_duration_ms = payload.config.chunk_duration_ms
        session.sample_rate_hz = payload.config.sample_rate_hz
        session.channels = payload.config.channels
        session.format = payload.config.format
        session.domain_hints = payload.config.domain_hints
        session.max_inflight = payload.max_inflight
        session.timeout_ms = payload.timeout_ms

        # Initialize pipeline components
        # Create ASR component
        asr_config = ASRConfig(
            model_size=os.getenv("ASR_MODEL_SIZE", "tiny"),
            device=os.getenv("ASR_DEVICE", "cpu"),
            compute_type="int8",
            language=session.source_language,
        )
        asr = create_asr_component(config=asr_config, mock=False)

        # Create Translation component
        translation_config = TranslationConfig(
            source_language=session.source_language,
            target_language=session.target_language,
        )
        translation = create_translation_component(config=translation_config, mock=False)

        # Create TTS component (uses TTS_PROVIDER env var, defaults to elevenlabs)
        voice_config_dict = voices_config[session.voice_profile]
        tts_config = TTSConfig(
            model_name=voice_config_dict.get("model", "tts_models/en/vctk/vits"),
            speaker=voice_config_dict.get("speaker"),
            language=session.target_language,
            device=os.getenv("TTS_DEVICE", "cpu"),
        )
        tts = create_tts_component(config=tts_config)  # Provider from TTS_PROVIDER env var

        # Initialize pipeline coordinator with components
        enable_artifact_logging = os.getenv("ENABLE_ARTIFACT_LOGGING", "true").lower() == "true"
        pipeline = PipelineCoordinator(
            asr=asr,
            translation=translation,
            tts=tts,
            enable_artifact_logging=enable_artifact_logging,
        )
        session.pipeline_coordinator = pipeline

        # Transition to ready state
        session.transition_to(StreamState.READY)

        # Track active session
        increment_active_sessions()

        # Build response
        response = StreamReadyPayload(
            stream_id=payload.stream_id,
            session_id=session.session_id,
            max_inflight=payload.max_inflight,
            capabilities=ServerCapabilities(
                batch_processing=False,
                async_delivery=True,
            ),
        )

        # Emit stream:ready
        await sio.emit(
            "stream:ready",
            response.model_dump(),
            to=sid,
        )
        # CRITICAL: Force event loop to process the emit in ASGI mode
        await sio.sleep(0)

        logger.info(
            f"Stream initialized: stream_id={payload.stream_id}, "
            f"session_id={session.session_id}, voice_profile={session.voice_profile}, sid={sid}"
        )

    except ValidationError as e:
        # Invalid configuration
        logger.warning(f"Invalid stream:init payload: {e}")

        error = ErrorResponse(
            code="INVALID_CONFIG",
            message=f"Invalid stream:init configuration: {str(e)}",
            severity="error",
            retryable=False,
            stream_id=data.get("stream_id"),
        )

        await sio.emit("error", error.model_dump(), to=sid)

    except Exception as e:
        # Unexpected error
        logger.exception(f"Error handling stream:init: {e}")

        error = ErrorResponse(
            code="INVALID_CONFIG",
            message=f"Failed to initialize stream: {str(e)}",
            severity="error",
            retryable=False,
            stream_id=data.get("stream_id"),
        )

        await sio.emit("error", error.model_dump(), to=sid)


async def handle_stream_pause(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle stream:pause event.

    Pauses the stream, preventing new fragments from being accepted.
    In-flight fragments will still complete.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The stream:pause payload.
        session_store: Session store instance.
    """
    stream_id = data.get("stream_id")
    reason = data.get("reason")

    session = await session_store.get_by_sid(sid)
    if session is None:
        error = ErrorResponse(
            code="STREAM_NOT_FOUND",
            message="Stream session not found",
            severity="error",
            retryable=False,
            stream_id=stream_id,
        )
        await sio.emit("error", error.model_dump(), to=sid)
        return

    if session.transition_to(StreamState.PAUSED):
        logger.info(f"Stream paused: stream_id={stream_id}, reason={reason}, sid={sid}")
    else:
        logger.warning(
            f"Cannot pause stream in state {session.state}: stream_id={stream_id}, sid={sid}"
        )


async def handle_stream_resume(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle stream:resume event.

    Resumes the stream, allowing new fragments to be accepted.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The stream:resume payload.
        session_store: Session store instance.
    """
    stream_id = data.get("stream_id")

    session = await session_store.get_by_sid(sid)
    if session is None:
        error = ErrorResponse(
            code="STREAM_NOT_FOUND",
            message="Stream session not found",
            severity="error",
            retryable=False,
            stream_id=stream_id,
        )
        await sio.emit("error", error.model_dump(), to=sid)
        return

    if session.transition_to(StreamState.READY):
        logger.info(f"Stream resumed: stream_id={stream_id}, sid={sid}")
    else:
        logger.warning(
            f"Cannot resume stream in state {session.state}: stream_id={stream_id}, sid={sid}"
        )


async def handle_stream_end(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle stream:end event.

    Marks the stream as ending, waits for in-flight fragments to complete,
    then sends stream:complete with statistics.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The stream:end payload.
        session_store: Session store instance.
    """
    stream_id = data.get("stream_id")
    reason = data.get("reason")

    session = await session_store.get_by_sid(sid)
    if session is None:
        error = ErrorResponse(
            code="STREAM_NOT_FOUND",
            message="Stream session not found",
            severity="error",
            retryable=False,
            stream_id=stream_id,
        )
        await sio.emit("error", error.model_dump(), to=sid)
        return

    # Mark stream as ending
    session.mark_stream_end()

    logger.info(
        f"Stream ending: stream_id={stream_id}, reason={reason}, "
        f"inflight={session.inflight_count}, sid={sid}"
    )

    # Wait for in-flight fragments to complete (with timeout)
    timeout = min(session.timeout_ms / 1000, 30)  # Max 30 seconds
    try:
        await asyncio.wait_for(
            _wait_for_inflight_fragments(session),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"Timeout waiting for in-flight fragments: stream_id={stream_id}, "
            f"remaining={session.inflight_count}"
        )

    # Send stream:complete
    await _send_stream_complete(sio, sid, session)


async def _wait_for_inflight_fragments(session: StreamSession) -> None:
    """Wait for all in-flight fragments to complete.

    Args:
        session: The stream session.
    """
    while session.inflight_count > 0:
        await asyncio.sleep(0.1)


async def _send_stream_complete(
    sio: Any,
    sid: str,
    session: StreamSession,
) -> None:
    """Send stream:complete and schedule auto-disconnect.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        session: The stream session.
    """
    # Build statistics
    stats = StreamStatistics(
        total_fragments=session.statistics.total_fragments,
        success_count=session.statistics.success_count,
        partial_count=session.statistics.partial_count,
        failed_count=session.statistics.failed_count,
        avg_processing_time_ms=session.statistics.avg_processing_time_ms,
        p95_processing_time_ms=session.statistics.p95_processing_time_ms,
    )

    # Build response
    response = StreamCompletePayload(
        stream_id=session.stream_id,
        total_fragments=session.statistics.total_fragments,
        total_duration_ms=session.duration_ms(),
        statistics=stats,
    )

    # Transition to completed
    session.transition_to(StreamState.COMPLETED)

    # Decrement active session counter
    decrement_active_sessions()

    # Emit stream:complete
    await sio.emit(
        "stream:complete",
        response.model_dump(),
        to=sid,
    )

    logger.info(
        f"Stream complete: stream_id={session.stream_id}, "
        f"total_fragments={session.statistics.total_fragments}, sid={sid}"
    )

    # Schedule auto-disconnect after 5 seconds
    asyncio.create_task(_auto_disconnect(sio, sid, delay_seconds=5))


async def _auto_disconnect(
    sio: Any,
    sid: str,
    delay_seconds: int,
) -> None:
    """Disconnect the client after a delay.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        delay_seconds: Delay before disconnect in seconds.
    """
    await asyncio.sleep(delay_seconds)

    try:
        await sio.disconnect(sid)
        logger.info(f"Auto-disconnected: sid={sid}")
    except Exception as e:
        # Client may have already disconnected
        logger.debug(f"Auto-disconnect failed (client may have left): {e}")


def register_stream_handlers(
    sio: Any,
    session_store: SessionStore,
) -> None:
    """Register stream lifecycle event handlers.

    Args:
        sio: Socket.IO server instance.
        session_store: Session store instance.
    """

    @sio.on("stream:init")
    async def on_stream_init(sid: str, data: dict[str, Any]) -> None:
        await handle_stream_init(sio, sid, data, session_store)

    @sio.on("stream:pause")
    async def on_stream_pause(sid: str, data: dict[str, Any]) -> None:
        await handle_stream_pause(sio, sid, data, session_store)

    @sio.on("stream:resume")
    async def on_stream_resume(sid: str, data: dict[str, Any]) -> None:
        await handle_stream_resume(sio, sid, data, session_store)

    @sio.on("stream:end")
    async def on_stream_end(sid: str, data: dict[str, Any]) -> None:
        await handle_stream_end(sio, sid, data, session_store)
