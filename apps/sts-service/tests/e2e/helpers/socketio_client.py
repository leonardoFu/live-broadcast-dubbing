"""Socket.IO client wrapper for E2E tests.

Provides a simplified interface for testing Full STS Service Socket.IO events.
Wraps python-socketio AsyncClient with test-friendly methods.

Usage:
    async with SocketIOClient("http://localhost:8000") as client:
        # Initialize stream
        ready_event = await client.send_stream_init(
            source_language="en",
            target_language="es",
        )
        assert ready_event["session_id"]

        # Send fragment
        ack_event = await client.send_fragment(fragment_data)
        assert ack_event["status"] == "queued"

        # Wait for processed result
        result = await client.wait_for_event("fragment:processed", timeout=10)
        assert result["status"] == "success"
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

import socketio

logger = logging.getLogger(__name__)


@dataclass
class EventCapture:
    """Captured Socket.IO event."""

    event_name: str
    data: Any
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class SocketIOClient:
    """Socket.IO client wrapper for E2E testing.

    Simplifies Socket.IO event handling for Full STS Service tests.

    Features:
    - Automatic event capture and storage
    - Helper methods for common operations (stream:init, fragment:data)
    - Event waiting with timeout and predicate filtering
    - Context manager support for automatic cleanup
    """

    def __init__(
        self,
        service_url: str,
        socketio_path: str = "/socket.io",
        auto_connect: bool = False,
    ) -> None:
        """Initialize Socket.IO client.

        Args:
            service_url: STS service URL (e.g., http://localhost:8000)
            socketio_path: Socket.IO endpoint path
            auto_connect: Automatically connect on init (default False)
        """
        self.service_url = service_url
        self.socketio_path = socketio_path
        self.client = socketio.AsyncClient(logger=False, engineio_logger=False)

        # Event storage
        self._events: list[EventCapture] = []
        self._events_by_type: dict[str, list[EventCapture]] = defaultdict(list)
        self._event_queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

        # Connection state
        self._connected = False

        # Setup event handlers
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup Socket.IO event handlers."""

        @self.client.event
        async def connect():
            """Handle Socket.IO connection."""
            self._connected = True
            logger.info(f"Socket.IO connected to {self.service_url}")

        @self.client.event
        async def disconnect():
            """Handle Socket.IO disconnection."""
            self._connected = False
            logger.info(f"Socket.IO disconnected from {self.service_url}")

        @self.client.event
        async def connect_error(data):
            """Handle Socket.IO connection error."""
            logger.error(f"Socket.IO connection error: {data}")

        # Wildcard handler to capture all events
        @self.client.on("*")
        async def catch_all(event_name: str, *args):
            """Capture all Socket.IO events."""
            # Skip internal events
            if event_name in ["connect", "disconnect", "connect_error"]:
                return

            data = args[0] if args else None
            await self._capture_event(event_name, data)

    async def _capture_event(self, event_name: str, data: Any) -> None:
        """Capture an event.

        Args:
            event_name: Event name
            data: Event data
        """
        capture = EventCapture(event_name=event_name, data=data)
        self._events.append(capture)
        self._events_by_type[event_name].append(capture)

        # Add to event queue for wait_for_event
        await self._event_queues[event_name].put(capture)

        logger.debug(f"Captured event: {event_name}")

    async def connect(self) -> None:
        """Connect to STS service.

        Raises:
            ConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("Already connected")
            return

        try:
            await self.client.connect(
                self.service_url,
                socketio_path=self.socketio_path,
            )
            # Wait a bit for connection to stabilize
            await asyncio.sleep(0.5)
            logger.info(f"Connected to {self.service_url}")
        except Exception as e:
            logger.error(f"Failed to connect to STS service: {e}")
            raise ConnectionError(f"Could not connect to {self.service_url}: {e}")

    async def disconnect(self) -> None:
        """Disconnect from STS service."""
        if self.client.connected:
            await self.client.disconnect()
            await asyncio.sleep(0.5)  # Allow cleanup
            logger.info("Disconnected")

    async def emit(self, event_name: str, data: Any) -> None:
        """Emit an event to STS service.

        Args:
            event_name: Event name
            data: Event data

        Raises:
            RuntimeError: If not connected
        """
        if not self.client.connected:
            raise RuntimeError("Not connected to STS service")

        await self.client.emit(event_name, data)
        logger.debug(f"Emitted event: {event_name}")

    async def send_stream_init(
        self,
        source_language: str = "en",
        target_language: str = "es",
        voice_profile: str = "default",
        chunk_duration_ms: int = 6000,
        sample_rate: int = 16000,
        channels: int = 1,
        format: str = "pcm_f32le",
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Send stream:init event and wait for stream:ready response.

        Args:
            source_language: Source language code (default "en")
            target_language: Target language code (default "es")
            voice_profile: Voice profile name (default "default")
            chunk_duration_ms: Expected chunk duration in ms (default 6000)
            sample_rate: Audio sample rate (default 16000)
            channels: Number of audio channels (default 1)
            format: Audio format (default "pcm_f32le")
            timeout: Timeout in seconds (default 10)

        Returns:
            stream:ready event data (session_id, max_inflight, capabilities)

        Raises:
            TimeoutError: If stream:ready not received within timeout
        """
        config = {
            "source_language": source_language,
            "target_language": target_language,
            "voice_profile": voice_profile,
            "chunk_duration_ms": chunk_duration_ms,
            "sample_rate": sample_rate,
            "channels": channels,
            "format": format,
        }

        await self.emit("stream:init", config)
        logger.info(f"Sent stream:init: {source_language}→{target_language}")

        # Wait for stream:ready
        ready_event = await self.wait_for_event("stream:ready", timeout=timeout)
        logger.info(f"Received stream:ready: {ready_event.data}")

        return ready_event.data

    async def send_fragment(
        self,
        fragment_data: dict[str, Any],
        wait_for_ack: bool = True,
        ack_timeout: float = 1.0,
    ) -> dict[str, Any] | None:
        """Send fragment:data event.

        Args:
            fragment_data: Fragment data payload
            wait_for_ack: Wait for fragment:ack response (default True)
            ack_timeout: Timeout for ack in seconds (default 1.0)

        Returns:
            fragment:ack event data if wait_for_ack=True, else None

        Raises:
            TimeoutError: If fragment:ack not received within timeout
        """
        fragment_id = fragment_data.get("fragment_id", "unknown")
        await self.emit("fragment:data", fragment_data)
        logger.debug(f"Sent fragment:data: {fragment_id}")

        if wait_for_ack:
            # Wait for ack with matching fragment_id
            ack_event = await self.wait_for_event(
                "fragment:ack",
                timeout=ack_timeout,
                predicate=lambda data: data.get("fragment_id") == fragment_id,
            )
            logger.debug(f"Received fragment:ack: {fragment_id}")
            return ack_event.data

        return None

    async def send_stream_pause(self) -> None:
        """Send stream:pause event."""
        await self.emit("stream:pause", {})
        logger.info("Sent stream:pause")

    async def send_stream_resume(self) -> None:
        """Send stream:resume event."""
        await self.emit("stream:resume", {})
        logger.info("Sent stream:resume")

    async def send_stream_end(
        self,
        wait_for_complete: bool = True,
        complete_timeout: float = 30.0,
    ) -> dict[str, Any] | None:
        """Send stream:end event.

        Args:
            wait_for_complete: Wait for stream:complete response (default True)
            complete_timeout: Timeout for complete in seconds (default 30.0)

        Returns:
            stream:complete event data if wait_for_complete=True, else None

        Raises:
            TimeoutError: If stream:complete not received within timeout
        """
        await self.emit("stream:end", {})
        logger.info("Sent stream:end")

        if wait_for_complete:
            complete_event = await self.wait_for_event(
                "stream:complete",
                timeout=complete_timeout,
            )
            logger.info(f"Received stream:complete: {complete_event.data}")
            return complete_event.data

        return None

    async def wait_for_event(
        self,
        event_name: str,
        timeout: float = 30.0,
        predicate: Callable[[Any], bool] | None = None,
    ) -> EventCapture:
        """Wait for a specific event.

        Args:
            event_name: Event name to wait for
            timeout: Timeout in seconds
            predicate: Optional predicate function to filter events (receives event.data)

        Returns:
            Captured event

        Raises:
            TimeoutError: If event not received within timeout
        """
        try:
            while True:
                event = await asyncio.wait_for(
                    self._event_queues[event_name].get(),
                    timeout=timeout,
                )

                # Check predicate if provided
                if predicate is None or predicate(event.data):
                    return event

                # Event didn't match predicate, keep waiting
                logger.debug(f"Event {event_name} didn't match predicate, waiting...")

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Timeout waiting for event '{event_name}' after {timeout}s"
            )

    async def wait_for_events(
        self,
        event_name: str,
        count: int,
        timeout: float = 30.0,
    ) -> list[EventCapture]:
        """Wait for multiple events of the same type.

        Args:
            event_name: Event name to wait for
            count: Number of events to collect
            timeout: Total timeout in seconds

        Returns:
            List of captured events

        Raises:
            TimeoutError: If all events not received within timeout
        """
        events = []
        start_time = asyncio.get_event_loop().time()

        while len(events) < count:
            remaining_timeout = timeout - (asyncio.get_event_loop().time() - start_time)
            if remaining_timeout <= 0:
                raise TimeoutError(
                    f"Timeout waiting for {count} '{event_name}' events "
                    f"(received {len(events)} after {timeout}s)"
                )

            try:
                event = await asyncio.wait_for(
                    self._event_queues[event_name].get(),
                    timeout=remaining_timeout,
                )
                events.append(event)
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Timeout waiting for {count} '{event_name}' events "
                    f"(received {len(events)} after {timeout}s)"
                )

        return events

    def get_events(self, event_name: str | None = None) -> list[EventCapture]:
        """Get captured events.

        Args:
            event_name: Optional event name filter

        Returns:
            List of captured events
        """
        if event_name:
            return list(self._events_by_type[event_name])
        return list(self._events)

    def clear_events(self) -> None:
        """Clear all captured events."""
        self._events.clear()
        self._events_by_type.clear()
        # Clear queues
        for queue in self._event_queues.values():
            while not queue.empty():
                queue.get_nowait()

    @property
    def connected(self) -> bool:
        """Check if connected to service."""
        return self._connected

    async def __aenter__(self) -> SocketIOClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
