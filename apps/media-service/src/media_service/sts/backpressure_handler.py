"""
Backpressure handler for STS client flow control.

Manages flow control based on backpressure signals from STS Service.

Per spec 003 and 017:
- Respond to backpressure severity levels (low, medium, high)
- Implement slow_down with recommended delay
- Implement pause/resume flow control
- Track backpressure state for metrics
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from media_service.sts.models import BackpressurePayload

logger = logging.getLogger(__name__)


@dataclass
class BackpressureState:
    """Current backpressure state.

    Attributes:
        is_paused: Whether sending is paused
        current_severity: Current backpressure severity
        delay_ms: Current delay to apply between sends
        total_slow_downs: Count of slow_down events received
        total_pauses: Count of pause events received
    """

    is_paused: bool = False
    current_severity: Literal["none", "low", "medium", "high"] = "none"
    delay_ms: int = 0
    total_slow_downs: int = 0
    total_pauses: int = 0


class BackpressureHandler:
    """Handles backpressure signals from STS Service.

    Implements flow control by:
    - Adding delays between fragment sends (slow_down)
    - Pausing fragment sends (pause)
    - Resuming normal operation (none action)

    Attributes:
        state: Current BackpressureState
        _resume_event: Event for pause/resume signaling
    """

    # Default delays for severity levels when server doesn't specify
    DEFAULT_DELAYS_MS = {
        "low": 100,
        "medium": 500,
        "high": 1000,
    }

    def __init__(self) -> None:
        """Initialize backpressure handler."""
        self.state = BackpressureState()
        self._resume_event = asyncio.Event()
        self._resume_event.set()  # Start in non-paused state

    async def handle(self, payload: BackpressurePayload) -> None:
        """Handle backpressure event from STS Service.

        Args:
            payload: BackpressurePayload with action and parameters
        """
        self.state.current_severity = payload.severity

        if payload.action == "slow_down":
            await self._handle_slow_down(payload)
        elif payload.action == "pause":
            await self._handle_pause()
        elif payload.action == "none":
            await self._handle_resume()
        else:
            logger.warning(f"Unknown backpressure action: {payload.action}")

    async def _handle_slow_down(self, payload: BackpressurePayload) -> None:
        """Handle slow_down action.

        Sets delay_ms based on recommended or default for severity.

        Args:
            payload: BackpressurePayload with recommended_delay_ms
        """
        if payload.recommended_delay_ms > 0:
            self.state.delay_ms = payload.recommended_delay_ms
        else:
            # Use default for severity
            self.state.delay_ms = self.DEFAULT_DELAYS_MS.get(
                payload.severity, self.DEFAULT_DELAYS_MS["medium"]
            )

        self.state.total_slow_downs += 1

        logger.info(
            f"Backpressure slow_down: severity={payload.severity}, "
            f"delay={self.state.delay_ms}ms"
        )

    async def _handle_pause(self) -> None:
        """Handle pause action.

        Blocks fragment sends until resume.
        """
        if self.state.is_paused:
            return

        self.state.is_paused = True
        self.state.total_pauses += 1
        self._resume_event.clear()

        logger.warning("Backpressure pause: fragment sending blocked")

    async def _handle_resume(self) -> None:
        """Handle resume (none action).

        Clears pause state and resets delay.
        """
        was_paused = self.state.is_paused

        self.state.is_paused = False
        self.state.delay_ms = 0
        self.state.current_severity = "none"
        self._resume_event.set()

        if was_paused:
            logger.info("Backpressure resume: fragment sending unblocked")
        else:
            logger.debug("Backpressure cleared")

    async def wait_if_paused(self, timeout: float | None = None) -> bool:
        """Wait if currently paused.

        Blocks until resume signal or timeout.

        Args:
            timeout: Max seconds to wait (None = infinite)

        Returns:
            True if resumed, False if timeout
        """
        if not self.state.is_paused:
            return True

        try:
            await asyncio.wait_for(
                self._resume_event.wait(),
                timeout=timeout,
            )
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Backpressure wait timeout after {timeout}s")
            return False

    async def apply_delay(self) -> None:
        """Apply current delay if slow_down is active.

        Sleeps for delay_ms if greater than 0.
        """
        if self.state.delay_ms > 0:
            await asyncio.sleep(self.state.delay_ms / 1000.0)

    async def wait_and_delay(self, timeout: float | None = 30.0) -> bool:
        """Wait for resume and apply delay.

        Combined helper for flow control before sending fragment.

        Args:
            timeout: Max seconds to wait for resume

        Returns:
            True if ready to send, False if timeout waiting for resume
        """
        # Wait for resume if paused
        if not await self.wait_if_paused(timeout):
            return False

        # Apply slow_down delay
        await self.apply_delay()

        return True

    def reset(self) -> None:
        """Reset backpressure state.

        Clears pause and delay, resets severity to none.
        """
        self.state.is_paused = False
        self.state.delay_ms = 0
        self.state.current_severity = "none"
        self._resume_event.set()

        logger.debug("Backpressure handler reset")

    @property
    def is_paused(self) -> bool:
        """Check if currently paused."""
        return self.state.is_paused

    @property
    def current_delay_ms(self) -> int:
        """Get current delay in milliseconds."""
        return self.state.delay_ms

    @property
    def total_slow_downs(self) -> int:
        """Total slow_down events received."""
        return self.state.total_slow_downs

    @property
    def total_pauses(self) -> int:
        """Total pause events received."""
        return self.state.total_pauses
