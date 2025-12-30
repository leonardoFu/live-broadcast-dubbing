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
    """A/V synchronization state.

    Manages PTS offsets for video and audio to maintain synchronization
    despite asynchronous STS processing latency.

    The av_offset_ns creates a buffering window that allows STS processing
    to complete before the corresponding video frame needs to be output.
    Default is 6 seconds for lower latency while accommodating STS processing.

    Attributes:
        av_offset_ns: Base offset applied to both video and audio output PTS.
        video_pts_last: Last video PTS pushed to output (for drift detection).
        audio_pts_last: Last audio PTS pushed to output (for drift detection).
        sync_delta_ns: Current measured delta between video and audio.
        drift_threshold_ns: Threshold for triggering drift correction.
        slew_rate_ns: Maximum adjustment per slew correction step.
    """

    av_offset_ns: int = 6_000_000_000  # 6 seconds default
    video_pts_last: int = 0
    audio_pts_last: int = 0
    sync_delta_ns: int = 0
    drift_threshold_ns: int = 120_000_000  # 120ms
    slew_rate_ns: int = 10_000_000  # 10ms per correction step

    @property
    def sync_delta_ms(self) -> float:
        """Current sync delta in milliseconds."""
        return self.sync_delta_ns / 1_000_000

    @property
    def av_offset_ms(self) -> float:
        """A/V offset in milliseconds."""
        return self.av_offset_ns / 1_000_000

    def adjust_video_pts(self, original_pts: int) -> int:
        """Adjust video PTS for output, applying offset.

        Args:
            original_pts: Original video PTS from input.

        Returns:
            Adjusted PTS for output pipeline.
        """
        return original_pts + self.av_offset_ns

    def adjust_audio_pts(self, original_pts: int) -> int:
        """Adjust audio PTS for output, applying offset.

        Args:
            original_pts: Original audio PTS (t0_ns from AudioSegment).

        Returns:
            Adjusted PTS for output pipeline.
        """
        return original_pts + self.av_offset_ns

    def update_sync_state(self, video_pts: int, audio_pts: int) -> None:
        """Update sync state after pushing frames.

        Calculates the current sync delta between video and audio.

        Args:
            video_pts: Last video PTS pushed to output.
            audio_pts: Last audio PTS pushed to output.
        """
        self.video_pts_last = video_pts
        self.audio_pts_last = audio_pts
        self.sync_delta_ns = abs(video_pts - audio_pts)

    def needs_correction(self) -> bool:
        """Check if drift correction is needed.

        Returns:
            True if sync delta exceeds drift threshold.
        """
        return self.sync_delta_ns > self.drift_threshold_ns

    def apply_slew_correction(self, amount_ns: int | None = None) -> int:
        """Apply gradual slew correction to the offset.

        Adjusts av_offset_ns gradually to correct drift without hard jumps.
        Per spec: use gradual slew, not hard jumps.

        Args:
            amount_ns: Amount to adjust (positive = increase offset).
                      If None, uses slew_rate_ns.

        Returns:
            The amount actually adjusted.
        """
        if amount_ns is None:
            # Determine direction based on whether video or audio is ahead
            if self.video_pts_last > self.audio_pts_last:
                # Video ahead, increase offset to delay video
                adjustment = self.slew_rate_ns
            else:
                # Audio ahead, decrease offset to delay audio
                adjustment = -self.slew_rate_ns
        else:
            # Clamp to max slew rate
            if abs(amount_ns) > self.slew_rate_ns:
                adjustment = self.slew_rate_ns if amount_ns > 0 else -self.slew_rate_ns
            else:
                adjustment = amount_ns

        self.av_offset_ns += adjustment
        return adjustment

    def reset(self) -> None:
        """Reset sync state to initial values."""
        self.video_pts_last = 0
        self.audio_pts_last = 0
        self.sync_delta_ns = 0
