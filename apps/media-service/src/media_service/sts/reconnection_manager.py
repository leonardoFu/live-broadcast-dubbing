"""
Reconnection manager for STS Socket.IO client.

Handles disconnection recovery with exponential backoff.

Per spec 003:
- Exponential backoff with jitter
- Maximum retry attempts
- State restoration after reconnect
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for reconnect callback
ReconnectCallback = Callable[[], Coroutine[Any, Any, bool]]


@dataclass
class ReconnectionState:
    """Reconnection state tracking.

    Attributes:
        attempt: Current attempt number (0-based)
        connected: Whether currently connected
        last_disconnect_time: Timestamp of last disconnect
        total_reconnects: Total successful reconnections
        total_failures: Total failed reconnection attempts
    """

    attempt: int = 0
    connected: bool = False
    last_disconnect_time: float = 0.0
    total_reconnects: int = 0
    total_failures: int = 0


class ReconnectionManager:
    """Manages reconnection with exponential backoff.

    Implements exponential backoff with jitter for reconnection attempts.
    Integrates with StsSocketIOClient for automatic reconnection.

    Attributes:
        max_attempts: Maximum reconnection attempts (0 = unlimited)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Jitter factor (0.0-1.0)
        state: Current ReconnectionState
    """

    def __init__(
        self,
        max_attempts: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: float = 0.1,
    ) -> None:
        """Initialize reconnection manager.

        Args:
            max_attempts: Maximum reconnection attempts (0 = unlimited)
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            jitter: Jitter factor to add randomness (0.0-1.0)
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.jitter = jitter

        self.state = ReconnectionState()
        self._reconnect_callback: ReconnectCallback | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt with exponential backoff and jitter.

        Args:
            attempt: Attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: initial_delay * 2^attempt
        delay = self.initial_delay * (2**attempt)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter
        if self.jitter > 0:
            jitter_range = delay * self.jitter
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)

    def on_connected(self) -> None:
        """Called when connection is established.

        Resets attempt counter and updates state.
        """
        if not self.state.connected:
            self.state.total_reconnects += 1

        self.state.connected = True
        self.state.attempt = 0

        logger.info("Reconnection manager: connected")

    def on_disconnected(self) -> None:
        """Called when connection is lost.

        Updates state and triggers reconnection if configured.
        """
        import time

        self.state.connected = False
        self.state.last_disconnect_time = time.time()

        logger.warning("Reconnection manager: disconnected")

        # Start reconnection if callback is set
        if self._reconnect_callback and self._reconnect_task is None:
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Internal reconnection loop with exponential backoff."""
        self._stop_event.clear()

        while not self._stop_event.is_set():
            # Check max attempts
            if self.max_attempts > 0 and self.state.attempt >= self.max_attempts:
                logger.error(f"Max reconnection attempts reached ({self.max_attempts})")
                self.state.total_failures += 1
                break

            # Calculate and apply delay
            delay = self.calculate_delay(self.state.attempt)
            logger.info(f"Reconnecting in {delay:.2f}s (attempt {self.state.attempt + 1})")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=delay,
                )
                # Stop event was set
                break
            except asyncio.TimeoutError:
                # Delay elapsed, try to reconnect
                pass

            # Attempt reconnection
            self.state.attempt += 1

            try:
                if self._reconnect_callback:
                    success = await self._reconnect_callback()
                    if success:
                        self.on_connected()
                        break
                    else:
                        logger.warning(f"Reconnection attempt {self.state.attempt} failed")
            except Exception as e:
                logger.error(f"Reconnection error: {e}")

        self._reconnect_task = None

    async def trigger_reconnect(self) -> bool:
        """Manually trigger reconnection attempt.

        Returns:
            True if reconnection started, False if already reconnecting
        """
        if self._reconnect_task is not None:
            logger.debug("Reconnection already in progress")
            return False

        if self._reconnect_callback is None:
            logger.warning("No reconnect callback set")
            return False

        self.state.connected = False
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        return True

    def stop(self) -> None:
        """Stop any ongoing reconnection attempts."""
        self._stop_event.set()

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        self._reconnect_task = None
        logger.debug("Reconnection manager stopped")

    def set_reconnect_callback(self, callback: ReconnectCallback) -> None:
        """Set callback for reconnection attempts.

        Args:
            callback: Async function that returns True on successful reconnect
        """
        self._reconnect_callback = callback

    def reset(self) -> None:
        """Reset reconnection state.

        Stops any pending reconnection and resets attempt counter.
        """
        self.stop()
        self.state.attempt = 0
        self.state.connected = False
        logger.debug("Reconnection manager reset")

    @property
    def is_reconnecting(self) -> bool:
        """Check if reconnection is in progress."""
        return self._reconnect_task is not None and not self._reconnect_task.done()

    @property
    def current_attempt(self) -> int:
        """Current reconnection attempt number."""
        return self.state.attempt

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.state.connected
