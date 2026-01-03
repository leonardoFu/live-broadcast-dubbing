"""Socket.IO Monitor for E2E Tests.

Provides event capture and monitoring for Socket.IO events emitted by
the STS service during E2E testing.

Main use cases:
- Capture fragment:processed events to verify dubbing occurred
- Wait for specific events with timeout
- Collect event history for validation
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import socketio

logger = logging.getLogger(__name__)


@dataclass
class EventCapture:
    """Captured Socket.IO event."""

    event_name: str
    data: Any
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class SocketIOMonitor:
    """Monitors Socket.IO events for E2E tests.

    Connects to STS service and captures events for validation.

    Usage:
        async with SocketIOMonitor("http://localhost:3000") as monitor:
            # Send fragment:data event
            await monitor.client.emit("fragment:data", {...})

            # Wait for response
            event = await monitor.wait_for_event("fragment:processed", timeout=20)
            assert event.data["dubbed_audio"] is not None
    """

    def __init__(
        self,
        sts_url: str,
        socketio_path: str = "/socket.io",
        namespace: str = "/sts",
    ) -> None:
        """Initialize Socket.IO monitor.

        Args:
            sts_url: STS service URL (e.g., http://localhost:3000)
            socketio_path: Socket.IO endpoint path
            namespace: Socket.IO namespace (default /sts)
        """
        self.sts_url = sts_url
        self.socketio_path = socketio_path
        self.namespace = namespace
        self.client = socketio.AsyncClient()

        # Event storage
        self._events: list[EventCapture] = []
        self._events_by_type: dict[str, list[EventCapture]] = defaultdict(list)
        self._event_queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

        # Setup event handlers
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup Socket.IO event handlers."""

        @self.client.on("connect", namespace=self.namespace)
        async def connect():
            """Handle Socket.IO connection."""
            logger.info(f"Socket.IO connected to {self.sts_url} (namespace={self.namespace})")

        @self.client.on("disconnect", namespace=self.namespace)
        async def disconnect():
            """Handle Socket.IO disconnection."""
            logger.info(f"Socket.IO disconnected from {self.sts_url}")

        @self.client.on("connect_error", namespace=self.namespace)
        async def connect_error(data):
            """Handle Socket.IO connection error."""
            logger.error(f"Socket.IO connection error: {data}")

        # Wildcard handler to capture all events
        @self.client.on("*", namespace=self.namespace)
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
        try:
            await self.client.connect(
                self.sts_url,
                socketio_path=self.socketio_path,
                namespaces=[self.namespace],
            )
            # Wait a bit for connection to stabilize
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to connect to STS service: {e}")
            raise ConnectionError(f"Could not connect to {self.sts_url}: {e}")

    async def disconnect(self) -> None:
        """Disconnect from STS service."""
        if self.client.connected:
            await self.client.disconnect()
            await asyncio.sleep(0.5)  # Allow cleanup

    async def emit(self, event_name: str, data: Any) -> None:
        """Emit an event to STS service.

        Args:
            event_name: Event name
            data: Event data
        """
        if not self.client.connected:
            raise RuntimeError("Not connected to STS service")

        await self.client.emit(event_name, data)
        logger.debug(f"Emitted event: {event_name}")

    async def wait_for_event(
        self,
        event_name: str,
        timeout: float = 30.0,
        predicate: callable | None = None,
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

    async def __aenter__(self) -> SocketIOMonitor:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
