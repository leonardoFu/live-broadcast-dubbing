"""
State models for circuit breaker and A/V synchronization.

Per spec 003:
- CircuitBreaker: Protects against STS Service failures
- AvSyncState: Maintains audio/video synchronization
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import ClassVar, Literal

# Type alias for circuit breaker state
CircuitState = Literal["closed", "half_open", "open"]


@dataclass
class CircuitBreaker:
    """Circuit breaker for STS Service protection.

    States:
        - closed: Normal operation, requests pass through.
        - open: Requests blocked, using fallback (original audio).
        - half_open: Testing recovery with probe requests.

    Transitions:
        closed -> open: After failure_threshold consecutive retryable failures.
        open -> half_open: After cooldown_seconds elapsed.
        half_open -> closed: On successful probe.
        half_open -> open: On failed probe.

    Error Classification:
        - Retryable errors (increment failure count): TIMEOUT, MODEL_ERROR,
          GPU_OOM, QUEUE_FULL, RATE_LIMIT
        - Non-retryable errors (DO NOT increment): STREAM_NOT_FOUND,
          INVALID_CONFIG, FRAGMENT_TOO_LARGE, INVALID_SEQUENCE

    Attributes:
        state: Current circuit state.
        failure_count: Consecutive retryable failure count (reset on success).
        last_failure_time: Timestamp of last failure (for cooldown).
        cooldown_seconds: Time before open -> half_open transition.
        failure_threshold: Failures required to open circuit.
        total_failures: Total failures recorded (for metrics).
        total_fallbacks: Total fallback activations (for metrics).
    """

    state: CircuitState = "closed"
    failure_count: int = 0
    last_failure_time: float = 0.0
    cooldown_seconds: float = 30.0
    failure_threshold: int = 5

    # Metrics counters
    total_failures: int = field(default=0, init=False)
    total_fallbacks: int = field(default=0, init=False)

    # Error classification constants
    RETRYABLE_ERRORS: ClassVar[set[str]] = {
        "TIMEOUT",
        "MODEL_ERROR",
        "GPU_OOM",
        "QUEUE_FULL",
        "RATE_LIMIT",
    }

    NON_RETRYABLE_ERRORS: ClassVar[set[str]] = {
        "STREAM_NOT_FOUND",
        "INVALID_CONFIG",
        "FRAGMENT_TOO_LARGE",
        "INVALID_SEQUENCE",
    }

    def is_closed(self) -> bool:
        """Check if circuit allows normal requests."""
        self._check_cooldown()
        return self.state == "closed"

    def is_open(self) -> bool:
        """Check if circuit is blocking requests."""
        self._check_cooldown()
        return self.state == "open"

    def is_half_open(self) -> bool:
        """Check if circuit is in probe mode."""
        self._check_cooldown()
        return self.state == "half_open"

    def should_allow_request(self) -> bool:
        """Determine if a request should proceed.

        Returns:
            True if request should proceed (closed or half_open probe).
            False if request should use fallback (open).
        """
        self._check_cooldown()

        if self.state == "closed":
            return True
        elif self.state == "half_open":
            return True  # Allow probe request
        else:  # open
            self.total_fallbacks += 1
            return False

    def record_success(self) -> None:
        """Record a successful request.

        Resets failure count and closes circuit if in half_open state.
        """
        if self.state == "half_open":
            self.state = "closed"
        self.failure_count = 0

    def record_failure(self, error_code: str | None = None) -> None:
        """Record a failed request.

        Only retryable errors increment the failure counter.
        Non-retryable errors are logged but do not affect breaker state.

        Args:
            error_code: Error code from STS service (optional).
                       If None, treated as retryable.
        """
        # Check if this is a retryable error
        is_retryable = True
        if error_code:
            if error_code in self.NON_RETRYABLE_ERRORS:
                is_retryable = False
            elif error_code not in self.RETRYABLE_ERRORS:
                # Unknown errors treated as retryable for safety
                is_retryable = True

        if not is_retryable:
            # Non-retryable errors do not increment failure count
            return

        # Record retryable failure
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = time.time()

        if self.state == "half_open":
            # Failed probe, go back to open
            self.state = "open"
        elif self.failure_count >= self.failure_threshold:
            self.state = "open"

    def _check_cooldown(self) -> None:
        """Check if cooldown has expired and transition to half_open."""
        if self.state == "open":
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.cooldown_seconds:
                self.state = "half_open"

    def get_state_value(self) -> int:
        """Get numeric state value for metrics.

        Returns:
            0 for closed, 1 for half_open, 2 for open.
        """
        if self.state == "closed":
            return 0
        elif self.state == "half_open":
            return 1
        else:  # open
            return 2


@dataclass
class AvSyncState:
    """A/V synchronization state (buffer-and-wait approach per spec 021).

    Updated for spec 021-fragment-length-30s:
    - REMOVED av_offset_ns (buffer-and-wait instead of offset)
    - REMOVED adjust_video_pts/adjust_audio_pts (PTS reset to 0)
    - REMOVED needs_correction/apply_slew_correction (no drift correction)
    - Video segments are buffered until dubbed audio arrives
    - Output is re-encoded with PTS starting from 0

    Attributes:
        video_pts_last: Last video PTS pushed to output (for sync delta logging).
        audio_pts_last: Last audio PTS pushed to output (for sync delta logging).
        sync_delta_ns: Current measured delta between video and audio.
        drift_threshold_ns: Threshold for logging warnings (100ms per spec 021).
    """

    # Buffer-and-wait: no av_offset_ns, PTS reset to 0
    av_offset_ns: int = 0  # DEPRECATED: kept for backward compat, always 0
    video_pts_last: int = 0
    audio_pts_last: int = 0
    sync_delta_ns: int = 0
    drift_threshold_ns: int = 100_000_000  # 100ms (for logging only, per spec 021)

    @property
    def sync_delta_ms(self) -> float:
        """Current sync delta in milliseconds."""
        return self.sync_delta_ns / 1_000_000

    def update_sync_state(self, video_pts: int, audio_pts: int) -> None:
        """Update sync state after pushing frames.

        Calculates the current sync delta between video and audio for logging.

        Args:
            video_pts: Last video PTS pushed to output.
            audio_pts: Last audio PTS pushed to output.
        """
        self.video_pts_last = video_pts
        self.audio_pts_last = audio_pts
        self.sync_delta_ns = abs(video_pts - audio_pts)

    def reset(self) -> None:
        """Reset sync state to initial values."""
        self.video_pts_last = 0
        self.audio_pts_last = 0
        self.sync_delta_ns = 0
