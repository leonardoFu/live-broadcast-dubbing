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


class TestAvSyncStatePtsAdjustments:
    """Tests for AvSyncState PTS adjustments (T019)."""

    def test_default_offset_is_6_seconds(self) -> None:
        """Test default av_offset_ns is 6 seconds."""
        sync = AvSyncState()

        assert sync.av_offset_ns == 6_000_000_000  # 6 seconds in nanoseconds
        assert sync.av_offset_ms == 6000.0

    def test_adjust_video_pts(self) -> None:
        """Test video PTS is increased by offset."""
        sync = AvSyncState(av_offset_ns=6_000_000_000)

        original_pts = 1_000_000_000  # 1 second
        adjusted = sync.adjust_video_pts(original_pts)

        assert adjusted == 7_000_000_000  # 1s + 6s offset

    def test_adjust_audio_pts(self) -> None:
        """Test audio PTS is increased by offset."""
        sync = AvSyncState(av_offset_ns=6_000_000_000)

        original_pts = 2_000_000_000  # 2 seconds
        adjusted = sync.adjust_audio_pts(original_pts)

        assert adjusted == 8_000_000_000  # 2s + 6s offset

    def test_configurable_offset(self) -> None:
        """Test custom offset is respected."""
        sync = AvSyncState(av_offset_ns=3_000_000_000)  # 3 seconds

        video_pts = sync.adjust_video_pts(1_000_000_000)
        audio_pts = sync.adjust_audio_pts(1_000_000_000)

        assert video_pts == 4_000_000_000  # 1s + 3s
        assert audio_pts == 4_000_000_000  # 1s + 3s


class TestAvSyncStateDriftDetection:
    """Tests for AvSyncState drift detection (T019)."""

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

    def test_needs_correction_above_threshold(self) -> None:
        """Test needs_correction returns True when delta > threshold."""
        sync = AvSyncState(drift_threshold_ns=120_000_000)  # 120ms threshold

        sync.update_sync_state(
            video_pts=5_000_000_000,
            audio_pts=5_200_000_000,  # 200ms delta (above 120ms)
        )

        assert sync.needs_correction() is True

    def test_needs_correction_below_threshold(self) -> None:
        """Test needs_correction returns False when delta < threshold."""
        sync = AvSyncState(drift_threshold_ns=120_000_000)

        sync.update_sync_state(
            video_pts=5_000_000_000,
            audio_pts=5_050_000_000,  # 50ms delta (below 120ms)
        )

        assert sync.needs_correction() is False

    def test_needs_correction_at_threshold(self) -> None:
        """Test needs_correction at exactly threshold."""
        sync = AvSyncState(drift_threshold_ns=120_000_000)

        sync.update_sync_state(
            video_pts=5_000_000_000,
            audio_pts=5_120_000_000,  # Exactly 120ms
        )

        # At threshold, no correction needed (must exceed)
        assert sync.needs_correction() is False


class TestAvSyncStateSlewCorrection:
    """Tests for AvSyncState slew correction."""

    def test_apply_slew_correction_positive(self) -> None:
        """Test slew correction increases offset when video ahead."""
        sync = AvSyncState(av_offset_ns=6_000_000_000, slew_rate_ns=10_000_000)

        # Video ahead of audio
        sync.video_pts_last = 5_100_000_000
        sync.audio_pts_last = 5_000_000_000

        adjustment = sync.apply_slew_correction()

        assert adjustment == 10_000_000  # Positive adjustment
        assert sync.av_offset_ns == 6_010_000_000

    def test_apply_slew_correction_negative(self) -> None:
        """Test slew correction decreases offset when audio ahead."""
        sync = AvSyncState(av_offset_ns=6_000_000_000, slew_rate_ns=10_000_000)

        # Audio ahead of video
        sync.video_pts_last = 5_000_000_000
        sync.audio_pts_last = 5_100_000_000

        adjustment = sync.apply_slew_correction()

        assert adjustment == -10_000_000  # Negative adjustment
        assert sync.av_offset_ns == 5_990_000_000

    def test_apply_slew_correction_clamped_to_rate(self) -> None:
        """Test slew correction is clamped to max slew rate."""
        sync = AvSyncState(av_offset_ns=6_000_000_000, slew_rate_ns=10_000_000)

        # Try to apply larger adjustment
        adjustment = sync.apply_slew_correction(amount_ns=100_000_000)

        # Should be clamped to slew_rate_ns
        assert adjustment == 10_000_000
        assert sync.av_offset_ns == 6_010_000_000

    def test_apply_slew_correction_with_specific_amount(self) -> None:
        """Test slew correction with specific amount within rate."""
        sync = AvSyncState(av_offset_ns=6_000_000_000, slew_rate_ns=10_000_000)

        adjustment = sync.apply_slew_correction(amount_ns=5_000_000)

        assert adjustment == 5_000_000
        assert sync.av_offset_ns == 6_005_000_000

    def test_reset(self) -> None:
        """Test reset clears sync state."""
        sync = AvSyncState(av_offset_ns=6_000_000_000)

        sync.update_sync_state(5_000_000_000, 5_100_000_000)
        assert sync.video_pts_last != 0

        sync.reset()

        assert sync.video_pts_last == 0
        assert sync.audio_pts_last == 0
        assert sync.sync_delta_ns == 0
        # Offset should not be reset
        assert sync.av_offset_ns == 6_000_000_000
