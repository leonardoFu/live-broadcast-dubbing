"""
VAD-based audio segmenter using GStreamer level element.

Per spec 023-vad-audio-segmentation:
- State machine that tracks silence duration and manages segment emission
- Detects silence boundaries (RMS < threshold for configured duration)
- Enforces min/max duration constraints
- Handles memory limits and forced emissions
- Provides metrics accessors for Prometheus instrumentation
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from media_service.config.segmentation_config import SegmentationConfig

logger = logging.getLogger(__name__)


class VADState(Enum):
    """VAD state machine states."""

    ACCUMULATING = "accumulating"  # Collecting audio, no silence detected
    IN_SILENCE = "in_silence"  # Silence threshold crossed, tracking duration


@dataclass
class VADAudioSegmenter:
    """VAD-based audio segmenter using GStreamer level element.

    State machine that:
    1. Accumulates audio buffers continuously
    2. Monitors RMS levels from level element messages
    3. Detects silence boundaries (RMS < threshold for configured duration)
    4. Emits segments at natural speech boundaries
    5. Enforces min/max duration constraints
    6. Handles memory limits and forced emissions

    Thread Safety:
        Methods are called from GStreamer callback thread.
        Segment emission callback should be thread-safe.

    Attributes:
        config: VAD configuration parameters
        on_segment_ready: Callback when segment should be emitted
        _state: Current VAD state (ACCUMULATING or IN_SILENCE)
        _accumulator: Audio data buffer
        _t0_ns: PTS of first buffer in current segment
        _duration_ns: Accumulated duration in nanoseconds
        _silence_start_ns: Timestamp when silence began (None if not in silence)
        _last_level_time_ns: Timestamp of last level message (for timeout detection)
        _consecutive_invalid_rms: Counter for invalid RMS value detection
    """

    config: SegmentationConfig
    on_segment_ready: Callable[[bytes, int, int, str], None]  # (data, t0_ns, duration_ns, trigger)

    # State tracking
    _state: VADState = field(default=VADState.ACCUMULATING, init=False)
    _accumulator: bytearray = field(default_factory=bytearray, init=False)
    _t0_ns: int = field(default=0, init=False)
    _duration_ns: int = field(default=0, init=False)
    _silence_start_ns: int | None = field(default=None, init=False)
    _last_level_time_ns: int = field(default=0, init=False)
    _consecutive_invalid_rms: int = field(default=0, init=False)

    # Metrics tracking
    _silence_detections: int = field(default=0, init=False)
    _forced_emissions: int = field(default=0, init=False)
    _min_duration_violations: int = field(default=0, init=False)
    _memory_limit_emissions: int = field(default=0, init=False)

    # Debug logging counter (to reduce log spam)
    _level_message_count: int = field(default=0, init=False)

    def on_audio_buffer(
        self,
        data: bytes,
        pts_ns: int,
        duration_ns: int,
    ) -> None:
        """Process incoming audio buffer.

        Accumulates buffer data and checks duration constraints.
        Called from GStreamer appsink callback thread.

        Args:
            data: Audio buffer data (AAC/ADTS format)
            pts_ns: Buffer presentation timestamp
            duration_ns: Buffer duration
        """
        # Capture t0 from first buffer
        if len(self._accumulator) == 0:
            self._t0_ns = pts_ns

        # Accumulate data
        self._accumulator.extend(data)
        self._duration_ns += duration_ns

        # Check memory limit
        if len(self._accumulator) >= self.config.memory_limit_bytes:
            logger.info(
                f"Memory limit reached: {len(self._accumulator)} bytes >= "
                f"{self.config.memory_limit_bytes} bytes"
            )
            self._memory_limit_emissions += 1
            self._emit_segment(trigger="memory_limit")
            return

        # Check max duration (forced emission)
        if self._duration_ns >= self.config.max_segment_duration_ns:
            logger.info(
                f"Max duration reached: {self._duration_ns / 1e9:.2f}s >= "
                f"{self.config.max_segment_duration_s}s"
            )
            self._forced_emissions += 1
            self._emit_segment(trigger="max_duration")

    def on_level_message(
        self,
        rms_db: float,
        timestamp_ns: int,
    ) -> None:
        """Process level element message with RMS value.

        Updates silence state based on RMS threshold.
        Called from GStreamer bus message handler.

        Args:
            rms_db: Peak RMS across all channels in dB
            timestamp_ns: Message timestamp (running time)
        """
        self._last_level_time_ns = timestamp_ns

        # Validate RMS range
        if not self._validate_rms(rms_db):
            return

        # Reset invalid counter on valid value
        self._consecutive_invalid_rms = 0
        self._level_message_count += 1

        is_silence = rms_db < self.config.silence_threshold_db

        # Log RMS level once per second (every 10 messages at 100ms interval)
        # This helps debug audio quality issues without spamming logs
        if self._level_message_count % 10 == 0:
            logger.info(
                f"🎤 VAD RMS: {rms_db:.1f} dB | threshold: {self.config.silence_threshold_db:.1f} dB | "
                f"{'SILENCE' if is_silence else 'SPEECH'} | state: {self._state.value} | "
                f"accum: {self._duration_ns / 1e9:.1f}s/{self.config.max_segment_duration_s}s"
            )

        if is_silence:
            self._handle_silence(timestamp_ns)
        else:
            self._handle_speech()

    def _validate_rms(self, rms_db: float) -> bool:
        """Validate RMS value is within expected range.

        Args:
            rms_db: RMS value in dB

        Returns:
            True if valid, False if invalid

        Raises:
            RuntimeError: If 10+ consecutive invalid values (pipeline malfunction)
        """
        if rms_db > 0.0 or rms_db < -100.0:
            self._consecutive_invalid_rms += 1
            logger.warning(
                f"Invalid RMS value: {rms_db} dB (expected -100 to 0 dB). "
                f"Consecutive invalid: {self._consecutive_invalid_rms}"
            )
            # Log warning for invalid value
            if self._consecutive_invalid_rms >= 10:
                raise RuntimeError(
                    f"Pipeline malfunction: 10+ consecutive invalid RMS values. "
                    f"Last value: {rms_db} dB (expected -100 to 0 dB)"
                )
            return False
        return True

    def _handle_silence(self, timestamp_ns: int) -> None:
        """Handle silence detection state transition."""
        if self._state == VADState.ACCUMULATING:
            # Start tracking silence
            self._state = VADState.IN_SILENCE
            self._silence_start_ns = timestamp_ns
            logger.debug(f"Silence detected at {timestamp_ns / 1e9:.2f}s")

        elif self._state == VADState.IN_SILENCE:
            # Check if silence duration threshold met
            if self._silence_start_ns is not None:
                silence_duration_ns = timestamp_ns - self._silence_start_ns
                if silence_duration_ns >= self.config.silence_duration_ns:
                    # Check minimum segment duration
                    if self._duration_ns >= self.config.min_segment_duration_ns:
                        logger.info(
                            f"Silence boundary detected after {silence_duration_ns / 1e9:.2f}s "
                            f"of silence, segment duration: {self._duration_ns / 1e9:.2f}s"
                        )
                        self._silence_detections += 1
                        self._emit_segment(trigger="silence")
                    else:
                        # Buffer short segment (min duration violation)
                        logger.debug(
                            f"Min duration violation: {self._duration_ns / 1e9:.2f}s < "
                            f"{self.config.min_segment_duration_s}s"
                        )
                        self._min_duration_violations += 1
                        # Stay in silence state, continue buffering

    def _handle_speech(self) -> None:
        """Handle speech detection (exit silence state)."""
        if self._state == VADState.IN_SILENCE:
            logger.debug("Speech resumed, resetting silence tracking")
            self._state = VADState.ACCUMULATING
            self._silence_start_ns = None

    def _emit_segment(self, trigger: str) -> None:
        """Emit accumulated audio as segment.

        Args:
            trigger: Emission trigger ("silence", "max_duration", "memory_limit", "eos")
        """
        if len(self._accumulator) == 0:
            logger.debug(f"No data to emit for trigger: {trigger}")
            return

        # Copy data and reset accumulator
        data = bytes(self._accumulator)
        t0_ns = self._t0_ns
        duration_ns = self._duration_ns

        logger.info(
            f"Emitting segment: trigger={trigger}, t0={t0_ns / 1e9:.2f}s, "
            f"duration={duration_ns / 1e9:.2f}s, size={len(data)} bytes"
        )

        self._reset_accumulator()

        # Invoke callback with trigger type
        self.on_segment_ready(data, t0_ns, duration_ns, trigger)

    def _reset_accumulator(self) -> None:
        """Reset accumulator state for new segment."""
        self._accumulator = bytearray()
        self._t0_ns = 0
        self._duration_ns = 0
        self._state = VADState.ACCUMULATING
        self._silence_start_ns = None

    def flush(self) -> None:
        """Flush remaining audio on EOS.

        Emits segment if duration >= minimum, otherwise discards.
        """
        if len(self._accumulator) == 0:
            logger.debug("Flush called with empty accumulator")
            return

        if self._duration_ns >= self.config.min_segment_duration_ns:
            logger.info(
                f"Flushing segment on EOS: {self._duration_ns / 1e9:.2f}s "
                f"(>= min {self.config.min_segment_duration_s}s)"
            )
            self._emit_segment(trigger="eos")
        else:
            # Discard short segment
            logger.info(
                f"Discarding short segment on EOS: {self._duration_ns / 1e9:.2f}s "
                f"(< min {self.config.min_segment_duration_s}s)"
            )
            self._reset_accumulator()

    def check_level_timeout(self, current_time_ns: int) -> None:
        """Check for level message timeout (pipeline malfunction).

        Args:
            current_time_ns: Current time in nanoseconds

        Raises:
            RuntimeError: If no level messages for 5 seconds
        """
        if self._last_level_time_ns == 0:
            return  # No messages received yet

        timeout_ns = 5_000_000_000  # 5 seconds
        if current_time_ns - self._last_level_time_ns > timeout_ns:
            raise RuntimeError(
                "Pipeline malfunction: No level messages received for 5 seconds. "
                "Check GStreamer pipeline and level element configuration."
            )

    # Metrics accessors
    @property
    def silence_detections(self) -> int:
        """Count of silence-triggered emissions."""
        return self._silence_detections

    @property
    def forced_emissions(self) -> int:
        """Count of max-duration forced emissions."""
        return self._forced_emissions

    @property
    def min_duration_violations(self) -> int:
        """Count of min-duration violations (buffered short segments)."""
        return self._min_duration_violations

    @property
    def memory_limit_emissions(self) -> int:
        """Count of memory-limit triggered emissions."""
        return self._memory_limit_emissions

    @property
    def accumulated_duration_ns(self) -> int:
        """Current accumulated duration in nanoseconds."""
        return self._duration_ns

    @property
    def accumulated_bytes(self) -> int:
        """Current accumulated data size in bytes."""
        return len(self._accumulator)
