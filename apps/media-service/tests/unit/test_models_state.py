"""
Unit tests for CircuitBreaker and AvSyncState data models.

Tests T018 and T019 from tasks.md - validating state models.
"""

from __future__ import annotations

from unittest.mock import patch

from media_service.models.state import AvSyncState, CircuitBreaker


class TestCircuitBreakerStateTransitions:
    """Tests for CircuitBreaker state transitions (T018)."""

    def test_initial_state_is_closed(self) -> None:
        """Test that circuit breaker starts in closed state."""
        breaker = CircuitBreaker()

        assert breaker.state == "closed"
        assert breaker.is_closed() is True
        assert breaker.is_open() is False
        assert breaker.is_half_open() is False

    def test_opens_after_threshold_retryable_failures(self) -> None:
        """Test that breaker opens after failure_threshold retryable failures."""
        breaker = CircuitBreaker(failure_threshold=5)

        # Record 5 retryable failures (TIMEOUT is retryable)
        for _ in range(5):
            breaker.record_failure("TIMEOUT")

        assert breaker.state == "open"
        assert breaker.is_open() is True
        assert breaker.failure_count == 5

    def test_does_not_open_for_non_retryable_errors(self) -> None:
        """Test that non-retryable errors do not increment failure count."""
        breaker = CircuitBreaker(failure_threshold=5)

        # Record 10 non-retryable failures
        for _ in range(10):
            breaker.record_failure("INVALID_CONFIG")

        # Should still be closed
        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_mixed_errors_only_count_retryable(self) -> None:
        """Test that only retryable errors count toward threshold."""
        breaker = CircuitBreaker(failure_threshold=5)

        # Mix of retryable and non-retryable
        breaker.record_failure("TIMEOUT")  # Counts
        breaker.record_failure("INVALID_CONFIG")  # Does not count
        breaker.record_failure("MODEL_ERROR")  # Counts
        breaker.record_failure("INVALID_SEQUENCE")  # Does not count
        breaker.record_failure("GPU_OOM")  # Counts
        breaker.record_failure("STREAM_NOT_FOUND")  # Does not count
        breaker.record_failure("QUEUE_FULL")  # Counts

        assert breaker.failure_count == 4
        assert breaker.state == "closed"

        # One more retryable error should open it
        breaker.record_failure("RATE_LIMIT")  # Counts
        assert breaker.failure_count == 5
        assert breaker.state == "open"

    def test_transitions_to_half_open_after_cooldown(self) -> None:
        """Test that breaker transitions to half_open after cooldown."""
        breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=1.0)

        # Open the breaker
        for _ in range(5):
            breaker.record_failure("TIMEOUT")
        assert breaker.state == "open"

        # Mock time to simulate cooldown elapsed
        with patch("time.time") as mock_time:
            # Set initial failure time
            breaker.last_failure_time = 1000.0

            # Time has passed beyond cooldown
            mock_time.return_value = 1002.0  # 2 seconds later

            # Check should transition to half_open
            assert breaker.is_half_open() is True
            assert breaker.state == "half_open"

    def test_closes_on_successful_probe_in_half_open(self) -> None:
        """Test that successful probe in half_open closes the circuit."""
        breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=0)

        # Open the breaker
        for _ in range(5):
            breaker.record_failure("TIMEOUT")

        # Immediately transition to half_open (cooldown=0)
        breaker._check_cooldown()
        assert breaker.state == "half_open"

        # Record success
        breaker.record_success()

        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_reopens_on_failed_probe_in_half_open(self) -> None:
        """Test that failed probe in half_open reopens the circuit."""
        breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=0)

        # Open the breaker
        for _ in range(5):
            breaker.record_failure("TIMEOUT")

        # Transition to half_open
        breaker._check_cooldown()
        assert breaker.state == "half_open"

        # Record failure (probe failed)
        breaker.record_failure("TIMEOUT")

        assert breaker.state == "open"

    def test_success_resets_failure_count(self) -> None:
        """Test that success resets failure count."""
        breaker = CircuitBreaker(failure_threshold=5)

        # Record some failures
        breaker.record_failure("TIMEOUT")
        breaker.record_failure("TIMEOUT")
        assert breaker.failure_count == 2

        # Record success
        breaker.record_success()

        assert breaker.failure_count == 0
        assert breaker.state == "closed"


class TestCircuitBreakerErrorClassification:
    """Tests for CircuitBreaker error classification."""

    def test_timeout_is_retryable(self) -> None:
        """Test TIMEOUT increments failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("TIMEOUT")
        assert breaker.failure_count == 1

    def test_model_error_is_retryable(self) -> None:
        """Test MODEL_ERROR increments failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("MODEL_ERROR")
        assert breaker.failure_count == 1

    def test_gpu_oom_is_retryable(self) -> None:
        """Test GPU_OOM increments failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("GPU_OOM")
        assert breaker.failure_count == 1

    def test_queue_full_is_retryable(self) -> None:
        """Test QUEUE_FULL increments failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("QUEUE_FULL")
        assert breaker.failure_count == 1

    def test_rate_limit_is_retryable(self) -> None:
        """Test RATE_LIMIT increments failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("RATE_LIMIT")
        assert breaker.failure_count == 1

    def test_invalid_config_is_not_retryable(self) -> None:
        """Test INVALID_CONFIG does not increment failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("INVALID_CONFIG")
        assert breaker.failure_count == 0

    def test_invalid_sequence_is_not_retryable(self) -> None:
        """Test INVALID_SEQUENCE does not increment failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("INVALID_SEQUENCE")
        assert breaker.failure_count == 0

    def test_stream_not_found_is_not_retryable(self) -> None:
        """Test STREAM_NOT_FOUND does not increment failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("STREAM_NOT_FOUND")
        assert breaker.failure_count == 0

    def test_fragment_too_large_is_not_retryable(self) -> None:
        """Test FRAGMENT_TOO_LARGE does not increment failure counter."""
        breaker = CircuitBreaker()
        breaker.record_failure("FRAGMENT_TOO_LARGE")
        assert breaker.failure_count == 0

    def test_unknown_error_treated_as_retryable(self) -> None:
        """Test unknown errors are treated as retryable for safety."""
        breaker = CircuitBreaker()
        breaker.record_failure("UNKNOWN_ERROR")
        assert breaker.failure_count == 1

    def test_none_error_code_treated_as_retryable(self) -> None:
        """Test None error code is treated as retryable."""
        breaker = CircuitBreaker()
        breaker.record_failure(None)
        assert breaker.failure_count == 1


class TestCircuitBreakerRequestDecisions:
    """Tests for CircuitBreaker request decisions."""

    def test_should_allow_request_when_closed(self) -> None:
        """Test should_allow_request returns True when closed."""
        breaker = CircuitBreaker()

        assert breaker.should_allow_request() is True

    def test_should_allow_request_when_half_open(self) -> None:
        """Test should_allow_request returns True when half_open (probe)."""
        breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=0)

        # Open and then transition to half_open
        for _ in range(5):
            breaker.record_failure("TIMEOUT")
        breaker._check_cooldown()

        assert breaker.state == "half_open"
        assert breaker.should_allow_request() is True

    def test_should_not_allow_request_when_open(self) -> None:
        """Test should_allow_request returns False when open."""
        breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=1000)

        # Open the breaker
        for _ in range(5):
            breaker.record_failure("TIMEOUT")

        assert breaker.state == "open"
        assert breaker.should_allow_request() is False

    def test_fallback_counter_increments_when_open(self) -> None:
        """Test fallback counter increments when request denied."""
        breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=1000)

        # Open the breaker
        for _ in range(5):
            breaker.record_failure("TIMEOUT")

        initial_fallbacks = breaker.total_fallbacks

        # Try to make requests while open
        breaker.should_allow_request()
        breaker.should_allow_request()
        breaker.should_allow_request()

        assert breaker.total_fallbacks == initial_fallbacks + 3

    def test_get_state_value(self) -> None:
        """Test get_state_value returns correct numeric values."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0)

        # Closed = 0
        assert breaker.get_state_value() == 0

        # Open = 2
        breaker.record_failure("TIMEOUT")
        assert breaker.get_state_value() == 2

        # Half open = 1
        breaker._check_cooldown()
        assert breaker.get_state_value() == 1


class TestAvSyncStateBufferAndWait:
    """Tests for AvSyncState buffer-and-wait approach (spec 021).

    Per spec 021-fragment-length-30s:
    - av_offset_ns has been REMOVED (buffer-and-wait instead)
    - Video segments are buffered until dubbed audio arrives
    - Output PTS starts from 0 (re-encoded, not original stream PTS)
    """

    def test_av_sync_state_no_offset(self) -> None:
        """FR-013: AvSyncState should not have av_offset_ns (removed)."""
        sync = AvSyncState()
        # av_offset_ns should not exist or be 0 in buffer-and-wait approach
        assert not hasattr(sync, "av_offset_ns") or sync.av_offset_ns == 0

    def test_av_sync_state_tracks_pts(self) -> None:
        """Validate AvSyncState tracks video_pts_last and audio_pts_last."""
        sync = AvSyncState()
        sync.update_sync_state(video_pts=5_000_000_000, audio_pts=5_100_000_000)

        assert sync.video_pts_last == 5_000_000_000
        assert sync.audio_pts_last == 5_100_000_000

    def test_av_sync_state_calculates_delta(self) -> None:
        """Validate AvSyncState calculates sync_delta_ns correctly."""
        sync = AvSyncState()
        sync.update_sync_state(video_pts=5_000_000_000, audio_pts=5_100_000_000)

        assert sync.sync_delta_ns == 100_000_000  # 100ms delta
        assert sync.sync_delta_ms == 100.0

    def test_av_sync_state_no_adjust_methods(self) -> None:
        """Verify adjust_video_pts and adjust_audio_pts are removed."""
        sync = AvSyncState()
        # In buffer-and-wait, PTS adjustment methods should not exist
        assert not hasattr(sync, "adjust_video_pts")
        assert not hasattr(sync, "adjust_audio_pts")


class TestAvSyncStateSyncDelta:
    """Tests for AvSyncState sync delta tracking (spec 021 buffer-and-wait)."""

    def test_update_sync_state(self) -> None:
        """Test sync state is updated correctly."""
        sync = AvSyncState()

        sync.update_sync_state(
            video_pts=5_000_000_000,
            audio_pts=4_900_000_000,
        )

        assert sync.video_pts_last == 5_000_000_000
        assert sync.audio_pts_last == 4_900_000_000
        assert sync.sync_delta_ns == 100_000_000  # 100ms delta

    def test_sync_delta_metric(self) -> None:
        """Test sync_delta_ns updated correctly."""
        sync = AvSyncState()

        sync.update_sync_state(
            video_pts=5_000_000_000,
            audio_pts=5_150_000_000,  # 150ms ahead
        )

        assert sync.sync_delta_ns == 150_000_000
        assert sync.sync_delta_ms == 150.0

    def test_drift_threshold_for_logging(self) -> None:
        """Test drift_threshold_ns is 100ms (for logging only in buffer-and-wait)."""
        sync = AvSyncState()
        # In buffer-and-wait, drift_threshold_ns is for logging only (100ms)
        assert sync.drift_threshold_ns == 100_000_000  # 100ms

    def test_reset(self) -> None:
        """Test reset clears sync state."""
        sync = AvSyncState()

        sync.update_sync_state(5_000_000_000, 5_100_000_000)
        assert sync.video_pts_last != 0

        sync.reset()

        assert sync.video_pts_last == 0
        assert sync.audio_pts_last == 0
        assert sync.sync_delta_ns == 0

    def test_no_drift_correction_methods(self) -> None:
        """Verify needs_correction and apply_slew_correction are removed (spec 021)."""
        sync = AvSyncState()
        # In buffer-and-wait, drift correction methods should not exist
        assert not hasattr(sync, "needs_correction")
        assert not hasattr(sync, "apply_slew_correction")
        assert not hasattr(sync, "slew_rate_ns")
