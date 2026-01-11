# Data Model: VAD Audio Segmentation

**Feature**: 023-vad-audio-segmentation
**Date**: 2026-01-09

## Entities

### SegmentationConfig

Pydantic configuration model for VAD parameters loaded from environment variables.

```python
from pydantic import Field
from pydantic_settings import BaseSettings


class SegmentationConfig(BaseSettings):
    """VAD segmentation configuration from environment variables.

    All parameters are global (not per-stream) for MVP.

    Attributes:
        silence_threshold_db: RMS level below which audio is considered silence.
            Default -50 dB works for typical broadcast content.
        silence_duration_s: Duration of silence required to trigger segment boundary.
            Default 1.0 second provides natural speech boundary detection.
        min_segment_duration_s: Minimum segment duration before emission.
            Default 1.0 second prevents fragments too short for translation.
        max_segment_duration_s: Maximum segment duration before forced emission.
            Default 15.0 seconds prevents memory buildup during continuous speech.
        level_interval_ns: Interval for level element RMS measurements.
            Default 100ms (100,000,000 ns) balances responsiveness and CPU.
        memory_limit_bytes: Maximum accumulator memory per stream.
            Default 10MB (~60s of 16kHz PCM) prevents unbounded growth.
    """

    silence_threshold_db: float = Field(
        default=-50.0,
        ge=-100.0,
        le=0.0,
        description="RMS threshold in dB below which audio is silence",
    )
    silence_duration_s: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Duration of silence to trigger segment boundary",
    )
    min_segment_duration_s: float = Field(
        default=1.0,
        ge=0.5,
        le=5.0,
        description="Minimum segment duration before emission",
    )
    max_segment_duration_s: float = Field(
        default=15.0,
        ge=5.0,
        le=60.0,
        description="Maximum segment duration before forced emission",
    )
    level_interval_ns: int = Field(
        default=100_000_000,
        ge=50_000_000,
        le=500_000_000,
        description="Level element measurement interval in nanoseconds",
    )
    memory_limit_bytes: int = Field(
        default=10_485_760,  # 10 MB
        ge=1_048_576,  # 1 MB minimum
        le=104_857_600,  # 100 MB maximum
        description="Maximum audio accumulator memory per stream",
    )

    model_config = {
        "env_prefix": "VAD_",
        "case_sensitive": False,
    }

    @property
    def silence_duration_ns(self) -> int:
        """Silence duration in nanoseconds."""
        return int(self.silence_duration_s * 1_000_000_000)

    @property
    def min_segment_duration_ns(self) -> int:
        """Minimum segment duration in nanoseconds."""
        return int(self.min_segment_duration_s * 1_000_000_000)

    @property
    def max_segment_duration_ns(self) -> int:
        """Maximum segment duration in nanoseconds."""
        return int(self.max_segment_duration_s * 1_000_000_000)
```

**Environment Variables**:
| Variable | Default | Description |
|----------|---------|-------------|
| `VAD_SILENCE_THRESHOLD_DB` | -50.0 | RMS level (dB) below which audio is silence |
| `VAD_SILENCE_DURATION_S` | 1.0 | Seconds of silence to trigger boundary |
| `VAD_MIN_SEGMENT_DURATION_S` | 1.0 | Minimum segment duration in seconds |
| `VAD_MAX_SEGMENT_DURATION_S` | 15.0 | Maximum segment duration in seconds |
| `VAD_LEVEL_INTERVAL_NS` | 100000000 | Level element interval (100ms) |
| `VAD_MEMORY_LIMIT_BYTES` | 10485760 | Max accumulator memory (10MB) |

---

### VADAudioSegmenter

State machine class managing audio accumulation, silence tracking, and segment emission.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from media_service.config.segmentation_config import SegmentationConfig
from media_service.models.segments import AudioSegment


class VADState(Enum):
    """VAD state machine states."""
    ACCUMULATING = "accumulating"  # Collecting audio, no silence detected
    IN_SILENCE = "in_silence"      # Silence threshold crossed, tracking duration


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
    on_segment_ready: Callable[[bytes, int, int], None]  # (data, t0_ns, duration_ns)

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
            self._memory_limit_emissions += 1
            self._emit_segment(trigger="memory_limit")
            return

        # Check max duration (forced emission)
        if self._duration_ns >= self.config.max_segment_duration_ns:
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

        is_silence = rms_db < self.config.silence_threshold_db

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

        elif self._state == VADState.IN_SILENCE:
            # Check if silence duration threshold met
            silence_duration_ns = timestamp_ns - self._silence_start_ns
            if silence_duration_ns >= self.config.silence_duration_ns:
                # Check minimum segment duration
                if self._duration_ns >= self.config.min_segment_duration_ns:
                    self._silence_detections += 1
                    self._emit_segment(trigger="silence")
                else:
                    # Buffer short segment (min duration violation)
                    self._min_duration_violations += 1
                    # Stay in silence state, continue buffering

    def _handle_speech(self) -> None:
        """Handle speech detection (exit silence state)."""
        if self._state == VADState.IN_SILENCE:
            self._state = VADState.ACCUMULATING
            self._silence_start_ns = None

    def _emit_segment(self, trigger: str) -> None:
        """Emit accumulated audio as segment.

        Args:
            trigger: Emission trigger ("silence", "max_duration", "memory_limit", "eos")
        """
        if len(self._accumulator) == 0:
            return

        # Copy data and reset accumulator
        data = bytes(self._accumulator)
        t0_ns = self._t0_ns
        duration_ns = self._duration_ns

        self._reset_accumulator()

        # Invoke callback
        self.on_segment_ready(data, t0_ns, duration_ns)

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
            return

        if self._duration_ns >= self.config.min_segment_duration_ns:
            self._emit_segment(trigger="eos")
        else:
            # Discard short segment
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
```

---

### LevelMessageExtractor

Utility class for extracting RMS values from GStreamer level messages.

```python
from typing import Protocol

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


class LevelMessageExtractor:
    """Extract RMS values from GStreamer level element messages.

    Handles the complexities of GValue/GValueArray extraction
    from GStreamer message structures.
    """

    @staticmethod
    def extract_peak_rms_db(structure: Gst.Structure) -> float | None:
        """Extract peak RMS value across all channels.

        Args:
            structure: GStreamer message structure from level element

        Returns:
            Peak RMS value in dB, or None if extraction fails
        """
        success, value_array = structure.get_array("rms")
        if not success or value_array is None:
            return None

        if value_array.n_values == 0:
            return None

        rms_values = []
        for i in range(value_array.n_values):
            gvalue = value_array.get_nth(i)
            if gvalue is not None:
                rms_values.append(gvalue.get_double())

        if not rms_values:
            return None

        return max(rms_values)

    @staticmethod
    def extract_timestamp_ns(structure: Gst.Structure) -> int:
        """Extract running time timestamp from level message.

        Args:
            structure: GStreamer message structure

        Returns:
            Running time in nanoseconds, or 0 if not available
        """
        success, value = structure.get_uint64("running-time")
        if success:
            return value
        return 0

    @staticmethod
    def is_level_message(message: Gst.Message) -> bool:
        """Check if message is from level element.

        Args:
            message: GStreamer bus message

        Returns:
            True if message is a level measurement
        """
        if message.type != Gst.MessageType.ELEMENT:
            return False

        structure = message.get_structure()
        if structure is None:
            return False

        return structure.get_name() == "level"
```

---

### VADMetrics

VAD-specific Prometheus metrics (extension to existing WorkerMetrics).

```python
from prometheus_client import Counter, Gauge, Histogram


# New metrics to add to WorkerMetrics class
class VADMetrics:
    """VAD-specific Prometheus metrics.

    These metrics extend the existing WorkerMetrics with
    VAD segmentation observability.
    """

    # Segment emission counter with trigger label
    vad_segments_total: Counter
    # Metric: vad_segments_total{stream_id="...", trigger="silence|max_duration|memory_limit|eos"}

    # Segment duration histogram
    vad_segment_duration_seconds: Histogram
    # Metric: vad_segment_duration_seconds{stream_id="..."}
    # Buckets: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15] seconds

    # Silence detection counter
    vad_silence_detections_total: Counter
    # Metric: vad_silence_detections_total{stream_id="..."}

    # Forced emission counter (max duration reached)
    vad_forced_emissions_total: Counter
    # Metric: vad_forced_emissions_total{stream_id="..."}

    # Min duration violation counter
    vad_min_duration_violations_total: Counter
    # Metric: vad_min_duration_violations_total{stream_id="..."}

    # Memory limit emission counter
    vad_memory_limit_emissions_total: Counter
    # Metric: vad_memory_limit_emissions_total{stream_id="..."}

    # Current accumulator state gauges
    vad_accumulator_duration_seconds: Gauge
    # Metric: vad_accumulator_duration_seconds{stream_id="..."}

    vad_accumulator_bytes: Gauge
    # Metric: vad_accumulator_bytes{stream_id="..."}
```

---

## State Transitions

### VADAudioSegmenter State Machine

```
                         +-------------------+
                         |   ACCUMULATING    |
                         | (collecting audio)|
                         +-------------------+
                                  |
                                  | RMS < threshold
                                  v
                         +-------------------+
                         |    IN_SILENCE     |
                         | (tracking silence)|
                         +-------------------+
                                  |
          +----------+-----------+-----------+----------+
          |          |           |           |          |
          v          v           v           v          v
     [Speech]   [Silence     [Max        [Memory    [EOS]
     detected   duration     duration    limit
               threshold    reached]    reached]
                 met]
          |          |           |           |          |
          v          v           v           v          v
     ACCUMULATING  EMIT if    EMIT       EMIT       EMIT if
     (reset        dur >=     segment    segment    dur >=
      silence)     min_dur                          min_dur
```

### Segment Emission Triggers

| Trigger | Condition | Action |
|---------|-----------|--------|
| `silence` | RMS < threshold for silence_duration_s AND duration >= min_segment_duration_s | Emit segment, reset state |
| `max_duration` | Accumulated duration >= max_segment_duration_s | Force emit, increment metric |
| `memory_limit` | Accumulated bytes >= memory_limit_bytes | Force emit, increment metric |
| `eos` | Stream ended | Emit if duration >= min_segment_duration_s, else discard |

---

## Relationships

```
SegmentationConfig (1) -----> (1) VADAudioSegmenter
       |                              |
       | configures                   | emits
       v                              v
   InputPipeline (1) <-----> (1) AudioSegment
       |                              |
       | produces                     | consumed by
       v                              v
  GStreamer level -----> WorkerRunner/SegmentBuffer
    element                      |
       |                         | updates
       | messages                v
       v                    VADMetrics (Prometheus)
  LevelMessageExtractor
```

---

## Validation Rules

### SegmentationConfig

| Field | Validation | Error Message |
|-------|------------|---------------|
| silence_threshold_db | -100.0 <= value <= 0.0 | "Threshold must be between -100 and 0 dB" |
| silence_duration_s | 0.1 <= value <= 5.0 | "Duration must be between 0.1 and 5.0 seconds" |
| min_segment_duration_s | 0.5 <= value <= 5.0 | "Min duration must be between 0.5 and 5.0 seconds" |
| max_segment_duration_s | 5.0 <= value <= 60.0 | "Max duration must be between 5.0 and 60.0 seconds" |
| level_interval_ns | 50ms <= value <= 500ms | "Interval must be between 50ms and 500ms" |
| memory_limit_bytes | 1MB <= value <= 100MB | "Memory limit must be between 1MB and 100MB" |

### VADAudioSegmenter

| Validation | Trigger | Action |
|------------|---------|--------|
| RMS value out of range | Invalid RMS from level element | Log warning, treat as speech |
| 10+ consecutive invalid RMS | Repeated invalid values | Raise RuntimeError |
| No level messages for 5s | Level element timeout | Raise RuntimeError |
| Segment < min duration on silence | Short segment detected | Buffer (don't emit), increment metric |

---

## File Locations

| Entity | File Path |
|--------|-----------|
| SegmentationConfig | `apps/media-service/src/media_service/config/segmentation_config.py` |
| VADAudioSegmenter | `apps/media-service/src/media_service/vad/vad_audio_segmenter.py` |
| LevelMessageExtractor | `apps/media-service/src/media_service/vad/level_message_extractor.py` |
| VADMetrics (extension) | `apps/media-service/src/media_service/metrics/prometheus.py` |
