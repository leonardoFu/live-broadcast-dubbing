"""
Socket.IO client for STS (Speech-to-Speech) Service communication.

Implements the WebSocket Audio Fragment Protocol per spec 017.

Per spec 003:
- Socket.IO async client with event handlers
- stream:init / stream:ready handshake
- fragment:data submission with M4A audio
- fragment:ack and fragment:processed reception
- Backpressure handling
- Reconnection with exponential backoff
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import socketio

from media_service.models.segments import AudioSegment
from media_service.sts.models import (
    BackpressurePayload,
    FragmentDataPayload,
    FragmentProcessedPayload,
    StreamConfig,
)

logger = logging.getLogger(__name__)

# Type aliases
FragmentProcessedCallback = Callable[[FragmentProcessedPayload], Coroutine[Any, Any, None]]
BackpressureCallback = Callable[[BackpressurePayload], Coroutine[Any, Any, None]]
ErrorCallback = Callable[[str, str, bool], Coroutine[Any, Any, None]]


class StsSocketIOClient:
    """Socket.IO client for STS Service communication.

    Manages connection to STS Service and implements the WebSocket Audio
    Fragment Protocol for real-time audio dubbing.

    Attributes:
        server_url: STS Service WebSocket URL
        namespace: Socket.IO namespace (default /sts)
        stream_id: Current stream identifier
        max_inflight: Maximum concurrent in-flight fragments
        session_id: STS session ID (assigned by server)
    """

    def __init__(
        self,
        server_url: str,
        namespace: str = "/",
        reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
    ) -> None:
        """Initialize STS Socket.IO client.

        Args:
            server_url: STS Service URL (e.g., "http://sts-service:8000")
            namespace: Socket.IO namespace (default /sts)
            reconnect_attempts: Max reconnection attempts
            reconnect_delay: Initial reconnect delay in seconds
        """
        self.server_url = server_url
        self.namespace = namespace
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self.stream_id: str | None = None
        self.session_id: str | None = None
        self.max_inflight: int = 3

        self._sio: socketio.AsyncClient | None = None
        self._connected = False
        self._stream_ready = False
        self._ready_event = asyncio.Event()
        self._sequence_number = 0

        # Callbacks
        self._on_fragment_processed: FragmentProcessedCallback | None = None
        self._on_backpressure: BackpressureCallback | None = None
        self._on_error: ErrorCallback | None = None

    async def connect(self) -> bool:
        """Connect to STS Service.

        Creates Socket.IO client and establishes connection.

        Returns:
            True if connection succeeded

        Raises:
            ConnectionError: If connection fails after retries
        """
        self._sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=self.reconnect_attempts,
            reconnection_delay=self.reconnect_delay,
            reconnection_delay_max=30.0,
        )

        # Register event handlers
        self._register_handlers()

        try:
            await self._sio.connect(
                self.server_url,
                namespaces=[self.namespace],
                transports=["websocket"],
            )
            self._connected = True
            logger.info(f"Connected to STS Service at {self.server_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to STS Service: {e}")
            raise ConnectionError(f"Failed to connect to STS Service: {e}")

    def _register_handlers(self) -> None:
        """Register Socket.IO event handlers."""
        if self._sio is None:
            return

        @self._sio.on("connect", namespace=self.namespace)
        async def on_connect() -> None:
            logger.info("Socket.IO connected")
            self._connected = True

        @self._sio.on("disconnect", namespace=self.namespace)
        async def on_disconnect() -> None:
            logger.warning("Socket.IO disconnected")
            self._connected = False
            self._stream_ready = False

        @self._sio.on("stream:ready", namespace=self.namespace)
        async def on_stream_ready(data: dict) -> None:
            await self._handle_stream_ready(data)

        @self._sio.on("fragment:ack", namespace=self.namespace)
        async def on_fragment_ack(data: dict) -> None:
            await self._handle_fragment_ack(data)

        @self._sio.on("fragment:processed", namespace=self.namespace)
        async def on_fragment_processed(data: dict) -> None:
            await self._handle_fragment_processed(data)

        @self._sio.on("backpressure", namespace=self.namespace)
        async def on_backpressure(data: dict) -> None:
            await self._handle_backpressure(data)

        @self._sio.on("error", namespace=self.namespace)
        async def on_error(data: dict) -> None:
            await self._handle_error(data)

    async def _handle_stream_ready(self, data: dict) -> None:
        """Handle stream:ready event from server.

        Args:
            data: Response data containing session_id, max_inflight
        """
        self.session_id = data.get("session_id")
        self.max_inflight = data.get("max_inflight", 3)

        logger.info(
            f"Stream ready: session_id={self.session_id}, "
            f"max_inflight={self.max_inflight}"
        )

        self._stream_ready = True
        self._ready_event.set()

    async def _handle_fragment_ack(self, data: dict) -> None:
        """Handle fragment:ack event from server.

        Args:
            data: Ack data with fragment_id, status, queue_position
        """
        fragment_id = data.get("fragment_id")
        status = data.get("status")
        queue_pos = data.get("queue_position", 0)

        logger.debug(f"Fragment ack: id={fragment_id}, status={status}, pos={queue_pos}")

    async def _handle_fragment_processed(self, data: dict) -> None:
        """Handle fragment:processed event from server.

        Args:
            data: Processing result with dubbed audio or error
        """
        payload = FragmentProcessedPayload.from_dict(data)

        logger.info(
            f"Fragment processed: id={payload.fragment_id}, "
            f"status={payload.status}, "
            f"processing_time={payload.processing_time_ms}ms"
        )

        if self._on_fragment_processed:
            await self._on_fragment_processed(payload)

    async def _handle_backpressure(self, data: dict) -> None:
        """Handle backpressure event from server.

        Args:
            data: Backpressure info with severity and recommended action
        """
        payload = BackpressurePayload.from_dict(data)

        logger.warning(
            f"Backpressure: severity={payload.severity}, "
            f"action={payload.action}, "
            f"inflight={payload.current_inflight}"
        )

        if self._on_backpressure:
            await self._on_backpressure(payload)

    async def _handle_error(self, data: dict) -> None:
        """Handle error event from server.

        Args:
            data: Error info with code, message, retryable flag
        """
        error_code = data.get("code", "UNKNOWN")
        error_message = data.get("message", "Unknown error")
        retryable = data.get("retryable", False)

        logger.error(f"STS error: code={error_code}, message={error_message}")

        if self._on_error:
            await self._on_error(error_code, error_message, retryable)

    async def init_stream(
        self,
        stream_id: str,
        config: StreamConfig,
        timeout: float = 10.0,
    ) -> bool:
        """Initialize stream with STS Service.

        Sends stream:init event and waits for stream:ready response.

        Args:
            stream_id: Stream identifier
            config: Stream configuration
            timeout: Timeout waiting for ready response

        Returns:
            True if stream initialized successfully

        Raises:
            ConnectionError: If not connected
            TimeoutError: If ready response not received in time
        """
        if not self._connected or self._sio is None:
            raise ConnectionError("Not connected to STS Service")

        self.stream_id = stream_id
        self._ready_event.clear()
        self._sequence_number = 0

        # Send stream:init
        await self._sio.emit(
            "stream:init",
            {
                "stream_id": stream_id,
                "worker_id": f"worker-{stream_id}",  # Worker ID based on stream ID
                "config": config.to_dict(),
            },
            namespace=self.namespace,
        )

        logger.info(f"Stream init sent: stream_id={stream_id}")

        # Wait for stream:ready
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for stream:ready (stream_id={stream_id})")
            raise TimeoutError("Stream init timeout - no stream:ready received")

    async def send_fragment(
        self,
        segment: AudioSegment,
    ) -> str:
        """Send audio fragment to STS Service.

        Creates fragment:data payload from AudioSegment and emits to server.

        Args:
            segment: AudioSegment with M4A file to send

        Returns:
            fragment_id for tracking

        Raises:
            ConnectionError: If not connected or stream not ready
            FileNotFoundError: If segment file doesn't exist
        """
        if not self._connected or self._sio is None:
            raise ConnectionError("Not connected to STS Service")

        if not self._stream_ready:
            raise ConnectionError("Stream not ready - call init_stream() first")

        if not segment.exists:
            raise FileNotFoundError(f"Segment file not found: {segment.file_path}")

        # Create payload
        payload = FragmentDataPayload.from_segment(
            segment=segment,
            sequence_number=self._sequence_number,
        )

        # Send fragment:data
        await self._sio.emit(
            "fragment:data",
            payload.to_dict(),
            namespace=self.namespace,
        )

        logger.info(
            f"Fragment sent: id={payload.fragment_id}, "
            f"seq={self._sequence_number}, "
            f"duration={segment.duration_ms}ms"
        )

        self._sequence_number += 1
        return payload.fragment_id

    async def end_stream(self) -> None:
        """Signal end of stream to STS Service.

        Sends stream:end event to signal no more fragments.
        """
        if not self._connected or self._sio is None:
            return

        if self.stream_id is None:
            return

        await self._sio.emit(
            "stream:end",
            {"stream_id": self.stream_id},
            namespace=self.namespace,
        )

        logger.info(f"Stream end sent: stream_id={self.stream_id}")

        self._stream_ready = False
        self.stream_id = None

    async def disconnect(self) -> None:
        """Disconnect from STS Service."""
        if self._sio is not None:
            await self._sio.disconnect()
            self._sio = None

        self._connected = False
        self._stream_ready = False
        logger.info("Disconnected from STS Service")

    def set_fragment_processed_callback(
        self,
        callback: FragmentProcessedCallback,
    ) -> None:
        """Set callback for fragment:processed events.

        Args:
            callback: Async function receiving FragmentProcessedPayload
        """
        self._on_fragment_processed = callback

    def set_backpressure_callback(
        self,
        callback: BackpressureCallback,
    ) -> None:
        """Set callback for backpressure events.

        Args:
            callback: Async function receiving BackpressurePayload
        """
        self._on_backpressure = callback

    def set_error_callback(
        self,
        callback: ErrorCallback,
    ) -> None:
        """Set callback for error events.

        Args:
            callback: Async function receiving (code, message, retryable)
        """
        self._on_error = callback

    @property
    def is_connected(self) -> bool:
        """Check if connected to STS Service."""
        return self._connected

    @property
    def is_stream_ready(self) -> bool:
        """Check if stream is initialized and ready."""
        return self._stream_ready

    @property
    def current_sequence_number(self) -> int:
        """Get current sequence number (next to be sent)."""
        return self._sequence_number
