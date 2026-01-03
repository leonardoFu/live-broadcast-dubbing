"""Unit tests for BackpressureTracker.

Tests backpressure monitoring and flow control.
These tests MUST be written FIRST and MUST FAIL before implementation (TDD).

Task IDs: T073-T076
"""

import pytest

from sts_service.full.models.backpressure import (
    BackpressureAction,
    BackpressureSeverity,
    BackpressureState,
)
from sts_service.full.backpressure_tracker import BackpressureTracker


# -----------------------------------------------------------------------------
# T073: Backpressure tracker - low severity
# -----------------------------------------------------------------------------


class TestBackpressureLowSeverity:
    """Tests for T073: Backpressure tracker - low severity."""

    def test_low_severity_with_zero_inflight(self):
        """Zero in-flight fragments results in low severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.LOW
        assert state.action == BackpressureAction.NONE
        assert state.current_inflight == 0

    def test_low_severity_with_one_inflight(self):
        """One in-flight fragment results in low severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act
        tracker.increment()
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.LOW
        assert state.action == BackpressureAction.NONE
        assert state.current_inflight == 1

    def test_low_severity_at_threshold(self):
        """In-flight at low threshold (3) results in low severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 3 in-flight
        for _ in range(3):
            tracker.increment()
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.LOW
        assert state.action == BackpressureAction.NONE
        assert state.current_inflight == 3

    def test_low_severity_no_recommended_delay(self):
        """Low severity has no recommended delay."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )
        tracker.increment()

        # Act
        state = tracker.get_state()

        # Assert
        assert state.recommended_delay_ms is None or state.recommended_delay_ms == 0


# -----------------------------------------------------------------------------
# T074: Backpressure tracker - medium severity
# -----------------------------------------------------------------------------


class TestBackpressureMediumSeverity:
    """Tests for T074: Backpressure tracker - medium severity."""

    def test_medium_severity_at_four_inflight(self):
        """Four in-flight fragments results in medium severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 4 in-flight
        for _ in range(4):
            tracker.increment()
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.MEDIUM
        assert state.action == BackpressureAction.SLOW_DOWN
        assert state.current_inflight == 4

    def test_medium_severity_at_five_inflight(self):
        """Five in-flight fragments results in medium severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 5 in-flight
        for _ in range(5):
            tracker.increment()
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.MEDIUM
        assert state.action == BackpressureAction.SLOW_DOWN
        assert state.current_inflight == 5

    def test_medium_severity_at_six_inflight(self):
        """Six in-flight fragments results in medium severity (at threshold)."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 6 in-flight
        for _ in range(6):
            tracker.increment()
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.MEDIUM
        assert state.action == BackpressureAction.SLOW_DOWN
        assert state.current_inflight == 6

    def test_medium_severity_has_recommended_delay(self):
        """Medium severity has recommended delay of 500ms."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )
        for _ in range(5):
            tracker.increment()

        # Act
        state = tracker.get_state()

        # Assert
        assert state.recommended_delay_ms == 500


# -----------------------------------------------------------------------------
# T075: Backpressure tracker - high severity
# -----------------------------------------------------------------------------


class TestBackpressureHighSeverity:
    """Tests for T075: Backpressure tracker - high severity."""

    def test_high_severity_at_seven_inflight(self):
        """Seven in-flight fragments results in high severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 7 in-flight
        for _ in range(7):
            tracker.increment()
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.HIGH
        assert state.action == BackpressureAction.PAUSE
        assert state.current_inflight == 7

    def test_high_severity_at_nine_inflight(self):
        """Nine in-flight fragments results in high severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 9 in-flight
        for _ in range(9):
            tracker.increment()
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.HIGH
        assert state.action == BackpressureAction.PAUSE
        assert state.current_inflight == 9

    def test_high_severity_at_ten_inflight(self):
        """Ten in-flight fragments (max before critical) results in high severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 10 in-flight
        for _ in range(10):
            tracker.increment()
        state = tracker.get_state()

        # Assert
        assert state.severity == BackpressureSeverity.HIGH
        assert state.action == BackpressureAction.PAUSE
        assert state.current_inflight == 10
        # Should not reject yet
        assert tracker.should_reject() is False

    def test_high_severity_has_recommended_delay(self):
        """High severity has recommended delay of 2000ms."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )
        for _ in range(9):
            tracker.increment()

        # Act
        state = tracker.get_state()

        # Assert
        assert state.recommended_delay_ms == 2000


# -----------------------------------------------------------------------------
# T076: Backpressure tracker - critical rejection
# -----------------------------------------------------------------------------


class TestBackpressureCriticalRejection:
    """Tests for T076: Backpressure tracker - critical rejection."""

    def test_should_reject_at_eleven_inflight(self):
        """Eleven in-flight fragments triggers rejection."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 11 in-flight
        for _ in range(11):
            tracker.increment()

        # Assert
        assert tracker.should_reject() is True

    def test_should_reject_above_eleven_inflight(self):
        """Any in-flight count above 10 triggers rejection."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add 15 in-flight
        for _ in range(15):
            tracker.increment()

        # Assert
        assert tracker.should_reject() is True
        assert tracker.current_inflight == 15

    def test_no_rejection_at_ten_inflight(self):
        """Ten in-flight fragments does NOT trigger rejection."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Add exactly 10 in-flight
        for _ in range(10):
            tracker.increment()

        # Assert
        assert tracker.should_reject() is False

    def test_rejection_returns_to_normal_after_decrement(self):
        """After decrement below threshold, rejection is cleared."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Add 12 in-flight (critical)
        for _ in range(12):
            tracker.increment()
        assert tracker.should_reject() is True

        # Act - Decrement back to 10
        tracker.decrement()
        tracker.decrement()

        # Assert - No longer rejecting
        assert tracker.current_inflight == 10
        assert tracker.should_reject() is False


# -----------------------------------------------------------------------------
# Additional BackpressureTracker tests
# -----------------------------------------------------------------------------


class TestBackpressureTrackerOperations:
    """Additional tests for BackpressureTracker operations."""

    def test_increment_increases_count(self):
        """increment() increases the in-flight count."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act
        tracker.increment()
        tracker.increment()

        # Assert
        assert tracker.current_inflight == 2

    def test_decrement_decreases_count(self):
        """decrement() decreases the in-flight count."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )
        tracker.increment()
        tracker.increment()
        tracker.increment()

        # Act
        tracker.decrement()

        # Assert
        assert tracker.current_inflight == 2

    def test_decrement_does_not_go_negative(self):
        """decrement() does not go below zero."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act - Decrement when already at 0
        tracker.decrement()

        # Assert
        assert tracker.current_inflight == 0

    def test_reset_clears_count(self):
        """reset() sets count back to zero."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )
        for _ in range(5):
            tracker.increment()

        # Act
        tracker.reset()

        # Assert
        assert tracker.current_inflight == 0

    def test_get_state_returns_backpressure_state(self):
        """get_state() returns a BackpressureState object."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Act
        state = tracker.get_state()

        # Assert
        assert isinstance(state, BackpressureState)
        assert state.stream_id == "stream-abc-123"
        assert state.max_inflight == 3

    def test_state_includes_threshold_exceeded_for_medium(self):
        """BackpressureState includes threshold_exceeded for medium severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )
        for _ in range(5):
            tracker.increment()

        # Act
        state = tracker.get_state()

        # Assert
        assert state.threshold_exceeded == "low"

    def test_state_includes_threshold_exceeded_for_high(self):
        """BackpressureState includes threshold_exceeded for high severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )
        for _ in range(8):
            tracker.increment()

        # Act
        state = tracker.get_state()

        # Assert
        assert state.threshold_exceeded == "medium"

    def test_custom_thresholds(self):
        """BackpressureTracker respects custom thresholds."""
        # Arrange - Custom thresholds: low_max=5, medium_max=10, high_max=15
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=5,
            low_max=5,
            medium_max=10,
            high_max=15,
        )

        # Act - Add 5 (should be low)
        for _ in range(5):
            tracker.increment()
        state_low = tracker.get_state()

        # Add 1 more (should be medium)
        tracker.increment()
        state_medium = tracker.get_state()

        # Assert
        assert state_low.severity == BackpressureSeverity.LOW
        assert state_medium.severity == BackpressureSeverity.MEDIUM


class TestBackpressureStateTransitions:
    """Tests for state transitions in BackpressureTracker."""

    def test_transition_low_to_medium(self):
        """Tracker transitions from low to medium severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Add 3 (low)
        for _ in range(3):
            tracker.increment()
        assert tracker.get_state().severity == BackpressureSeverity.LOW

        # Act - Add 1 more (medium)
        tracker.increment()

        # Assert
        assert tracker.get_state().severity == BackpressureSeverity.MEDIUM

    def test_transition_medium_to_high(self):
        """Tracker transitions from medium to high severity."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Add 6 (medium)
        for _ in range(6):
            tracker.increment()
        assert tracker.get_state().severity == BackpressureSeverity.MEDIUM

        # Act - Add 1 more (high)
        tracker.increment()

        # Assert
        assert tracker.get_state().severity == BackpressureSeverity.HIGH

    def test_transition_high_to_medium_on_decrement(self):
        """Tracker transitions from high to medium on decrement."""
        # Arrange
        tracker = BackpressureTracker(
            stream_id="stream-abc-123",
            max_inflight=3,
        )

        # Add 7 (high)
        for _ in range(7):
            tracker.increment()
        assert tracker.get_state().severity == BackpressureSeverity.HIGH

        # Act - Decrement to 6 (medium)
        tracker.decrement()

        # Assert
        assert tracker.get_state().severity == BackpressureSeverity.MEDIUM
