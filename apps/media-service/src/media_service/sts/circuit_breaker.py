"""
Circuit breaker wrapper for STS client.

Wraps CircuitBreaker with STS-specific error classification and
fallback handling.

Per spec 003:
- Error classification (retryable vs non-retryable)
- Fallback to original audio when circuit is open
- Integration with metrics
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from media_service.models.segments import AudioSegment
from media_service.models.state import CircuitBreaker
from media_service.sts.models import FragmentProcessedPayload, ProcessingError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class StsCircuitBreaker:
    """Circuit breaker wrapper for STS client operations.

    Wraps the base CircuitBreaker with STS-specific behavior:
    - Classifies errors based on STS error codes
    - Provides fallback to original audio
    - Integrates with fragment tracking

    Attributes:
        breaker: Underlying CircuitBreaker instance
        _on_fallback: Callback when fallback is used
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
    ) -> None:
        """Initialize STS circuit breaker.

        Args:
            failure_threshold: Consecutive retryable failures to open circuit
            cooldown_seconds: Time before open -> half_open transition
        """
        self.breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
        )
        self._on_fallback: Callable[[AudioSegment], Coroutine[Any, Any, None]] | None = None

    def should_send(self) -> bool:
        """Check if fragment should be sent to STS.

        Returns:
            True if circuit allows request (closed or half_open probe)
        """
        return self.breaker.should_allow_request()

    def record_success(self) -> None:
        """Record successful STS processing.

        Resets failure count and closes circuit if in half_open state.
        """
        self.breaker.record_success()
        logger.debug(f"Circuit breaker: success recorded, state={self.breaker.state}")

    def record_failure(self, error: ProcessingError | None = None) -> None:
        """Record STS processing failure.

        Classifies error and updates breaker state accordingly.

        Args:
            error: ProcessingError from STS (if available)
        """
        error_code = error.code if error else None
        self.breaker.record_failure(error_code)

        logger.debug(
            f"Circuit breaker: failure recorded, "
            f"code={error_code}, "
            f"count={self.breaker.failure_count}, "
            f"state={self.breaker.state}"
        )

    def record_timeout(self) -> None:
        """Record STS timeout.

        Timeouts are treated as retryable failures.
        """
        self.breaker.record_failure("TIMEOUT")
        logger.debug(
            f"Circuit breaker: timeout recorded, "
            f"count={self.breaker.failure_count}, "
            f"state={self.breaker.state}"
        )

    def handle_response(self, response: FragmentProcessedPayload) -> bool:
        """Handle STS response and update circuit state.

        Args:
            response: FragmentProcessedPayload from STS

        Returns:
            True if processing was successful
        """
        if response.is_success:
            self.record_success()
            return True

        if response.is_failed and response.error:
            self.record_failure(response.error)

        return response.is_success or response.is_partial

    async def execute_with_fallback(
        self,
        segment: AudioSegment,
        send_func: Callable[[AudioSegment], Coroutine[Any, Any, str]],
    ) -> str | None:
        """Execute send operation with circuit breaker protection.

        If circuit is open, uses fallback (original audio).
        If circuit is closed/half_open, attempts send.

        Args:
            segment: AudioSegment to send
            send_func: Async function to send fragment, returns fragment_id

        Returns:
            fragment_id if sent, None if fallback used

        Raises:
            Exception: If send fails and needs to be handled
        """
        if not self.should_send():
            logger.info(
                f"Circuit open: using fallback for segment {segment.fragment_id}"
            )
            if self._on_fallback:
                await self._on_fallback(segment)
            return None

        # Attempt send
        return await send_func(segment)

    def set_fallback_callback(
        self,
        callback: Callable[[AudioSegment], Coroutine[Any, Any, None]],
    ) -> None:
        """Set callback for when fallback is used.

        Args:
            callback: Async function receiving AudioSegment for fallback handling
        """
        self._on_fallback = callback

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.breaker.is_closed()

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.breaker.is_open()

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half_open (probe mode)."""
        return self.breaker.is_half_open()

    @property
    def state(self) -> str:
        """Get current circuit state string."""
        return self.breaker.state

    @property
    def failure_count(self) -> int:
        """Get current consecutive failure count."""
        return self.breaker.failure_count

    @property
    def total_failures(self) -> int:
        """Get total failure count (for metrics)."""
        return self.breaker.total_failures

    @property
    def total_fallbacks(self) -> int:
        """Get total fallback count (for metrics)."""
        return self.breaker.total_fallbacks

    @property
    def state_value(self) -> int:
        """Get numeric state value for metrics (0=closed, 1=half_open, 2=open)."""
        return self.breaker.get_state_value()

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.breaker.state = "closed"
        self.breaker.failure_count = 0
        self.breaker.last_failure_time = 0.0
        logger.info("Circuit breaker reset to closed state")
