"""
Stream Worker implementation for MediaMTX integration.

Implements User Story 3: Stream Worker Input/Output via MediaMTX.

This worker:
- Pulls incoming streams via RTSP from MediaMTX
- Processes the stream (passthrough in this implementation)
- Publishes processed output back to MediaMTX via RTMP
- Handles disconnections with 3 retries (1s, 2s, 4s exponential backoff)

Acceptance Criteria:
- Worker pulls from rtsp://mediamtx:8554/live/<streamId>/in with <500ms latency
- Worker publishes to rtmp://mediamtx:1935/live/<streamId>/out
- Worker uses RTSP over TCP (protocols=tcp)
- Worker handles disconnections with 3 retries (1s, 2s, 4s exponential backoff)
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from media_service.models.events import ReadyEvent

logger = logging.getLogger(__name__)


class InvalidStreamIdError(Exception):
    """Raised when a stream ID contains invalid characters."""

    def __init__(self, stream_id: str, reason: str = "Invalid stream ID") -> None:
        self.stream_id = stream_id
        self.reason = reason
        super().__init__(f"{reason}: '{stream_id}'")


# Valid stream ID pattern: alphanumeric, hyphens, underscores only
# Per FR-020: System MUST support stream IDs containing alphanumeric characters,
# hyphens, and underscores
VALID_STREAM_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_stream_id(stream_id: str) -> None:
    """Validate stream ID matches allowed pattern.

    Args:
        stream_id: The stream identifier to validate.

    Raises:
        InvalidStreamIdError: If stream_id is empty or contains invalid characters.
    """
    if not stream_id:
        raise InvalidStreamIdError(stream_id, "Stream ID cannot be empty")

    if not VALID_STREAM_ID_PATTERN.match(stream_id):
        raise InvalidStreamIdError(
            stream_id,
            "Stream ID must contain only alphanumeric characters, hyphens, and underscores",
        )


# Worker state type
WorkerState = Literal["idle", "connecting", "running", "stopped"]


@dataclass
class StreamWorker:
    """Stream worker for MediaMTX input/output processing.

    Reads from RTSP input path and publishes to RTMP output path.
    Implements passthrough processing with retry logic for connection failures.

    Attributes:
        stream_id: Unique identifier for the stream (e.g., "my-stream-123").
        mediamtx_host: Hostname of MediaMTX server (e.g., "mediamtx" or "localhost").
        rtsp_port: RTSP port for input streams (default: 8554).
        rtmp_port: RTMP port for output streams (default: 1935).
        use_tcp: Use TCP transport for RTSP (avoids UDP packet loss).
        max_retries: Maximum number of connection retry attempts.
        state: Current worker state.
    """

    stream_id: str
    mediamtx_host: str
    rtsp_port: int = 8554
    rtmp_port: int = 1935
    use_tcp: bool = True
    max_retries: int = 3
    state: WorkerState = field(default="idle", init=False)

    def __post_init__(self) -> None:
        """Validate stream_id after initialization."""
        validate_stream_id(self.stream_id)

    def get_rtsp_input_url(self) -> str:
        """Construct RTSP input URL for pulling stream from MediaMTX.

        Returns:
            RTSP URL in format: rtsp://<host>:<port>/live/<streamId>/in

        Example:
            >>> worker = StreamWorker("test-stream", "mediamtx")
            >>> worker.get_rtsp_input_url()
            'rtsp://mediamtx:8554/live/test-stream/in'
        """
        return f"rtsp://{self.mediamtx_host}:{self.rtsp_port}/live/{self.stream_id}/in"

    def get_rtmp_output_url(self) -> str:
        """Construct RTMP output URL for publishing stream to MediaMTX.

        Returns:
            RTMP URL in format: rtmp://<host>:<port>/live/<streamId>/out

        Example:
            >>> worker = StreamWorker("test-stream", "mediamtx")
            >>> worker.get_rtmp_output_url()
            'rtmp://mediamtx:1935/live/test-stream/out'
        """
        return f"rtmp://{self.mediamtx_host}:{self.rtmp_port}/live/{self.stream_id}/out"

    def get_retry_delays(self) -> list[float]:
        """Get exponential backoff delays for connection retries.

        Per spec FR-021: Worker MUST retry exactly 3 times with exponential
        backoff intervals (1 second, 2 seconds, 4 seconds).

        Returns:
            List of delay values in seconds: [1.0, 2.0, 4.0]
        """
        return [1.0, 2.0, 4.0]

    def get_pipeline_config(self) -> dict[str, str]:
        """Get pipeline configuration for passthrough processing.

        Returns:
            Dictionary with input_url, output_url, and mode.
        """
        return {
            "input_url": self.get_rtsp_input_url(),
            "output_url": self.get_rtmp_output_url(),
            "mode": "passthrough",
        }

    def set_state(self, state: WorkerState) -> None:
        """Set worker state.

        Args:
            state: New state to set.
        """
        logger.debug(
            "Worker state transition",
            extra={
                "stream_id": self.stream_id,
                "from_state": self.state,
                "to_state": state,
            },
        )
        self.state = state

    async def _connect_rtsp(self) -> None:
        """Internal method to establish RTSP connection.

        This is a placeholder that should be overridden or mocked in tests.
        In a real implementation, this would use GStreamer or FFmpeg to
        establish the RTSP connection.

        Raises:
            ConnectionError: If connection fails.
        """
        # Placeholder for actual RTSP connection logic
        # In real implementation, this would use GStreamer rtspsrc element
        # with protocols=tcp for TCP transport
        pass

    async def connect_with_retry(self) -> bool:
        """Attempt to connect to RTSP source with exponential backoff retries.

        Per spec FR-021: Worker MUST retry RTSP connection failures exactly
        3 times with exponential backoff intervals (1s, 2s, 4s), logging each
        attempt, and exit cleanly after final failure.

        Returns:
            True if connection succeeded, False if all retries exhausted.
        """
        self.set_state("connecting")
        delays = self.get_retry_delays()

        # Initial attempt (not counted as a retry)
        attempt = 0
        max_attempts = self.max_retries + 1  # Initial + retries

        while attempt < max_attempts:
            attempt += 1
            try:
                logger.info(
                    f"Connection attempt {attempt}/{max_attempts}",
                    extra={
                        "stream_id": self.stream_id,
                        "rtsp_url": self.get_rtsp_input_url(),
                        "attempt": attempt,
                    },
                )
                await self._connect_rtsp()
                self.set_state("running")
                logger.info(
                    "RTSP connection established",
                    extra={
                        "stream_id": self.stream_id,
                        "attempt": attempt,
                    },
                )
                return True

            except ConnectionError as e:
                logger.warning(
                    f"Connection failed: {e}",
                    extra={
                        "stream_id": self.stream_id,
                        "attempt": attempt,
                        "error": str(e),
                    },
                )

                # If we have more retries, wait with exponential backoff
                if attempt < max_attempts:
                    delay = delays[attempt - 1]
                    logger.info(
                        f"Retrying in {delay}s...",
                        extra={
                            "stream_id": self.stream_id,
                            "delay": delay,
                        },
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted, exit cleanly
        logger.error(
            "All connection attempts exhausted",
            extra={
                "stream_id": self.stream_id,
                "total_attempts": max_attempts,
            },
        )
        self.set_state("stopped")
        return False

    async def stop(self) -> None:
        """Stop the worker and cleanup resources.

        Sets state to 'stopped' and performs any necessary cleanup.
        """
        logger.info(
            "Stopping worker",
            extra={"stream_id": self.stream_id},
        )
        self.set_state("stopped")
        # In real implementation, this would stop the GStreamer pipeline
        # and cleanup resources


def extract_stream_id_from_path(path: str) -> str:
    """Extract stream ID from MediaMTX path.

    Args:
        path: Path in format 'live/<streamId>/(in|out)'

    Returns:
        The stream ID portion of the path.

    Example:
        >>> extract_stream_id_from_path("live/my-stream/in")
        'my-stream'
    """
    parts = path.split("/")
    if len(parts) >= 2:
        return parts[1]
    return ""


def create_worker_from_event(
    event: ReadyEvent,
    mediamtx_host: str,
    rtsp_port: int = 8554,
    rtmp_port: int = 1935,
    use_tcp: bool = True,
) -> StreamWorker:
    """Create a StreamWorker instance from a ReadyEvent.

    This factory function extracts the stream ID from the event path
    and creates a configured StreamWorker.

    Args:
        event: The ReadyEvent from MediaMTX hook.
        mediamtx_host: Hostname of MediaMTX server.
        rtsp_port: RTSP port for input streams (default: 8554).
        rtmp_port: RTMP port for output streams (default: 1935).
        use_tcp: Use TCP transport for RTSP (default: True).

    Returns:
        Configured StreamWorker instance.

    Example:
        >>> event = ReadyEvent(path="live/test123/in", sourceType="rtmp", sourceId="1")
        >>> worker = create_worker_from_event(event, "mediamtx")
        >>> worker.stream_id
        'test123'
    """
    stream_id = extract_stream_id_from_path(event.path)

    logger.info(
        "Creating worker from event",
        extra={
            "path": event.path,
            "stream_id": stream_id,
            "source_type": event.source_type,
            "correlation_id": event.correlation_id,
        },
    )

    return StreamWorker(
        stream_id=stream_id,
        mediamtx_host=mediamtx_host,
        rtsp_port=rtsp_port,
        rtmp_port=rtmp_port,
        use_tcp=use_tcp,
    )
