"""
Unit tests for StsCircuitBreaker class.

Tests T066-T073 from tasks.md - validating circuit breaker behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from media_service.models.segments import AudioSegment
from media_service.sts.circuit_breaker import StsCircuitBreaker
from media_service.sts.models import FragmentProcessedPayload, ProcessingError


class TestStsCircuitBreakerInit:
    """Tests for StsCircuitBreaker initialization."""

    def test_default_values(self) -> None:
        """Test default circuit breaker values."""
        breaker = StsCircuitBreaker()

        assert breaker.is_closed is True
        assert breaker.is_open is False
        assert breaker.is_half_open is False
        assert breaker.failure_count == 0
        assert breaker.state == "closed"

    def test_custom_threshold(self) -> None:
        """Test custom failure threshold."""
        breaker = StsCircuitBreaker(failure_threshold=10)

        assert breaker.breaker.failure_threshold == 10


class TestStsCircuitBreakerShouldSend:
    """Tests for should_send decision making."""

    def test_should_send_when_closed(self) -> None:
        """Test should_send returns True when closed."""
        breaker = StsCircuitBreaker()

        assert breaker.should_send() is True

    def test_should_not_send_when_open(self) -> None:
        """Test should_send returns False when open."""
        breaker = StsCircuitBreaker(failure_threshold=3, cooldown_seconds=1000)

        # Trip the breaker
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open is True
        assert breaker.should_send() is False


class TestStsCircuitBreakerRecording:
    """Tests for success/failure recording."""

    def test_record_success_resets_count(self) -> None:
        """Test record_success resets failure count."""
        breaker = StsCircuitBreaker()

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2

        breaker.record_success()

        assert breaker.failure_count == 0

    def test_record_failure_increments_count(self) -> None:
        """Test record_failure increments count."""
        breaker = StsCircuitBreaker()

        breaker.record_failure()
        assert breaker.failure_count == 1

        breaker.record_failure()
        assert breaker.failure_count == 2

    def test_record_failure_with_error(self) -> None:
        """Test record_failure with ProcessingError."""
        breaker = StsCircuitBreaker()

        error = ProcessingError(code="TIMEOUT", message="Timeout", retryable=True)
        breaker.record_failure(error)

        assert breaker.failure_count == 1

    def test_record_timeout(self) -> None:
        """Test record_timeout increments count."""
        breaker = StsCircuitBreaker()

        breaker.record_timeout()

        assert breaker.failure_count == 1

    def test_non_retryable_error_does_not_increment(self) -> None:
        """Test non-retryable errors don't increment count."""
        breaker = StsCircuitBreaker()

        error = ProcessingError(code="INVALID_CONFIG", message="Bad config", retryable=False)
        breaker.record_failure(error)

        assert breaker.failure_count == 0


class TestStsCircuitBreakerHandleResponse:
    """Tests for handle_response method."""

    def test_handle_success_response(self) -> None:
        """Test handling successful response."""
        breaker = StsCircuitBreaker()
        breaker.record_failure()  # Add a failure

        response = FragmentProcessedPayload(
            fragment_id="frag-1",
            stream_id="stream-1",
            sequence_number=0,
            status="success",
            dubbed_audio=MagicMock(),
        )

        result = breaker.handle_response(response)

        assert result is True
        assert breaker.failure_count == 0

    def test_handle_failed_response(self) -> None:
        """Test handling failed response."""
        breaker = StsCircuitBreaker()

        response = FragmentProcessedPayload(
            fragment_id="frag-1",
            stream_id="stream-1",
            sequence_number=0,
            status="failed",
            error=ProcessingError(code="TIMEOUT", message="Timeout", retryable=True),
        )

        result = breaker.handle_response(response)

        assert result is False
        assert breaker.failure_count == 1

    def test_handle_partial_response(self) -> None:
        """Test handling partial response."""
        breaker = StsCircuitBreaker()

        response = FragmentProcessedPayload(
            fragment_id="frag-1",
            stream_id="stream-1",
            sequence_number=0,
            status="partial",
        )

        result = breaker.handle_response(response)

        assert result is True  # Partial is acceptable


class TestStsCircuitBreakerExecuteWithFallback:
    """Tests for execute_with_fallback method."""

    @pytest.mark.asyncio
    async def test_execute_when_closed(self) -> None:
        """Test execution when circuit is closed."""
        breaker = StsCircuitBreaker()

        mock_segment = MagicMock(spec=AudioSegment)
        mock_send = AsyncMock(return_value="frag-123")

        result = await breaker.execute_with_fallback(mock_segment, mock_send)

        assert result == "frag-123"
        mock_send.assert_called_once_with(mock_segment)

    @pytest.mark.asyncio
    async def test_execute_uses_fallback_when_open(self) -> None:
        """Test fallback is used when circuit is open."""
        breaker = StsCircuitBreaker(failure_threshold=1, cooldown_seconds=1000)
        breaker.record_failure()  # Open the circuit

        mock_segment = MagicMock(spec=AudioSegment)
        mock_segment.fragment_id = "frag-test-123"  # Set the fragment_id attribute
        mock_send = AsyncMock(return_value="frag-123")
        mock_fallback = AsyncMock()

        breaker.set_fallback_callback(mock_fallback)

        result = await breaker.execute_with_fallback(mock_segment, mock_send)

        assert result is None
        mock_send.assert_not_called()
        mock_fallback.assert_called_once_with(mock_segment)


class TestStsCircuitBreakerMetrics:
    """Tests for circuit breaker metrics."""

    def test_state_value(self) -> None:
        """Test state_value property."""
        breaker = StsCircuitBreaker(failure_threshold=1, cooldown_seconds=0)

        # Closed = 0
        assert breaker.state_value == 0

        # Open = 2
        breaker.record_failure()
        assert breaker.state_value == 2

        # Half open = 1 (after cooldown)
        breaker.breaker._check_cooldown()
        assert breaker.state_value == 1

    def test_total_failures(self) -> None:
        """Test total_failures counter."""
        breaker = StsCircuitBreaker()

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()  # Resets failure_count but not total
        breaker.record_failure()

        assert breaker.total_failures == 3

    def test_reset(self) -> None:
        """Test reset clears state."""
        breaker = StsCircuitBreaker(failure_threshold=1, cooldown_seconds=1000)

        breaker.record_failure()
        assert breaker.is_open is True

        breaker.reset()

        assert breaker.is_closed is True
        assert breaker.failure_count == 0
