"""Backpressure Tracker for Full STS Service.

Tracks in-flight fragments and calculates backpressure state
to enable flow control between worker and STS service.

Task IDs: T085-T086
"""

from .models.backpressure import (
    RECOMMENDED_DELAYS_MS,
    BackpressureAction,
    BackpressureSeverity,
    BackpressureState,
    BackpressureThresholds,
)


class BackpressureTracker:
    """Tracks in-flight fragments and manages backpressure state.

    Thresholds (default configuration):
    - LOW: 1-3 in-flight fragments (normal operation)
    - MEDIUM: 4-6 in-flight fragments (slow down recommended)
    - HIGH: 7-10 in-flight fragments (pause recommended)
    - CRITICAL: 11+ in-flight fragments (reject new fragments)

    Features:
    - Track in-flight count with increment/decrement
    - Calculate severity and recommended action
    - Detect when fragments should be rejected
    - Configurable thresholds
    """

    # Critical threshold for rejection
    CRITICAL_THRESHOLD = 10

    def __init__(
        self,
        stream_id: str,
        max_inflight: int = 3,
        low_max: int = 3,
        medium_max: int = 6,
        high_max: int = 10,
    ):
        """Initialize the backpressure tracker.

        Args:
            stream_id: Stream identifier for this tracker
            max_inflight: Configured maximum in-flight limit
            low_max: Upper bound for low severity (default 3)
            medium_max: Upper bound for medium severity (default 6)
            high_max: Upper bound for high severity (default 10)
        """
        self._stream_id = stream_id
        self._max_inflight = max_inflight
        self._current_inflight = 0

        # Configure thresholds
        self._thresholds = BackpressureThresholds(
            low_max=low_max,
            medium_max=medium_max,
            high_max=high_max,
        )

    @property
    def stream_id(self) -> str:
        """Return the stream ID."""
        return self._stream_id

    @property
    def max_inflight(self) -> int:
        """Return the configured max in-flight limit."""
        return self._max_inflight

    @property
    def current_inflight(self) -> int:
        """Return the current in-flight count."""
        return self._current_inflight

    def increment(self) -> int:
        """Increment the in-flight count.

        Returns:
            New in-flight count
        """
        self._current_inflight += 1
        return self._current_inflight

    def decrement(self) -> int:
        """Decrement the in-flight count.

        Will not go below 0.

        Returns:
            New in-flight count
        """
        if self._current_inflight > 0:
            self._current_inflight -= 1
        return self._current_inflight

    def reset(self) -> None:
        """Reset the in-flight count to zero."""
        self._current_inflight = 0

    def should_reject(self) -> bool:
        """Check if new fragments should be rejected.

        Returns True when in-flight count exceeds critical threshold (>10).

        Returns:
            True if fragments should be rejected
        """
        return self._current_inflight > self.CRITICAL_THRESHOLD

    def get_state(self) -> BackpressureState:
        """Get the current backpressure state.

        Returns:
            BackpressureState with severity, action, and recommendations
        """
        severity = self._thresholds.get_severity(self._current_inflight)
        action = self._thresholds.get_action(severity)

        # Determine which threshold was exceeded
        threshold_exceeded = None
        if severity == BackpressureSeverity.MEDIUM:
            threshold_exceeded = "low"
        elif severity == BackpressureSeverity.HIGH:
            threshold_exceeded = "medium"

        # Get recommended delay
        recommended_delay = RECOMMENDED_DELAYS_MS.get(severity, 0)

        return BackpressureState(
            stream_id=self._stream_id,
            severity=severity,
            action=action,
            current_inflight=self._current_inflight,
            max_inflight=self._max_inflight,
            threshold_exceeded=threshold_exceeded,
            recommended_delay_ms=recommended_delay if recommended_delay > 0 else None,
        )

    def get_severity(self) -> BackpressureSeverity:
        """Get the current severity level.

        Returns:
            BackpressureSeverity enum value
        """
        return self._thresholds.get_severity(self._current_inflight)

    def get_action(self) -> BackpressureAction:
        """Get the recommended action for current state.

        Returns:
            BackpressureAction enum value
        """
        severity = self.get_severity()
        return self._thresholds.get_action(severity)

    def is_healthy(self) -> bool:
        """Check if backpressure is at healthy (low) levels.

        Returns:
            True if severity is LOW
        """
        return self.get_severity() == BackpressureSeverity.LOW

    def should_emit_event(self, previous_severity: BackpressureSeverity) -> bool:
        """Check if a backpressure event should be emitted.

        Events are emitted when severity changes.

        Args:
            previous_severity: The previous severity level

        Returns:
            True if severity has changed
        """
        current_severity = self.get_severity()
        return current_severity != previous_severity
