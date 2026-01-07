# Implementation Plan: VAD-Based Audio Segmentation

**Feature**: Dynamic VAD-Based Audio Segmentation
**Spec**: [specs/022-vad-audio-segmentation/spec.md](./spec.md)
**Created**: 2026-01-06
**Status**: Draft

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Design](#component-design)
3. [Data Flow](#data-flow)
4. [Implementation Approach](#implementation-approach)
5. [GStreamer Pipeline Integration](#gstreamer-pipeline-integration)
6. [Configuration Management](#configuration-management)
7. [Metrics and Observability](#metrics-and-observability)
8. [Testing Strategy](#testing-strategy)
9. [Risk Analysis](#risk-analysis)
10. [Rollout Plan](#rollout-plan)

---

## Architecture Overview

### High-Level Design

The VAD-based audio segmentation system replaces fixed 6-second segments with dynamic segmentation based on speech boundaries. The core innovation is using GStreamer's native `level` element for real-time RMS monitoring to detect silence periods.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Input Pipeline                                │
│  RTMP → flvdemux → [video: H.264] → appsink (unchanged)            │
│                    [audio: AAC]   → level → aacparse → appsink      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ↓ (audio buffers + level messages)
┌─────────────────────────────────────────────────────────────────────┐
│                      VADAudioSegmenter                               │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Level Message Handler                                          │ │
│  │  - Parse RMS levels from GStreamer bus messages                │ │
│  │  - Detect silence: RMS < -40dB for 1 second                    │ │
│  │  - Emit silence_boundary event                                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Buffer Accumulator (extends SegmentBuffer)                     │ │
│  │  - Accumulate audio buffers with PTS tracking                  │ │
│  │  - On silence_boundary: emit segment if >= 1s                  │ │
│  │  - On max_duration (15s): force emit segment                   │ │
│  │  - On min_duration violation: continue buffering               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│  NOTE: No fallback - level element REQUIRED (fatal error if missing) │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ↓ (AudioSegment, variable duration)
┌─────────────────────────────────────────────────────────────────────┐
│                   Existing Pipeline (unchanged)                      │
│  AudioSegmentWriter → STS Client → A/V Sync → Output Pipeline       │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Design Decisions**:

1. **GStreamer `level` Element**: Use native GStreamer element for RMS monitoring instead of custom DSP code. This provides:
   - Hardware-accelerated audio analysis where available
   - Proven stability and performance
   - Automatic handling of various audio formats
   - Integration with GStreamer message bus

2. **Extend SegmentBuffer**: Wrap/extend existing `SegmentBuffer` class rather than replace it:
   - Preserve API compatibility for video path (unchanged)
   - Maintain existing PTS tracking logic
   - Reuse flush/reset mechanisms
   - Minimize changes to `WorkerRunner`

3. **Configuration-First**: All VAD parameters configurable via environment variables:
   - Enables tuning for different content types without code changes
   - Supports A/B testing and gradual rollout
   - Allows per-stream customization in future iterations

4. **Fail-Fast Design**: No fallback - level element is required:
   - Clear error if GStreamer `gst-plugins-good` not installed
   - Forces proper deployment configuration
   - Avoids silent degradation that masks problems

---

## Component Design

### 1. VADAudioSegmenter

**Purpose**: Orchestrates VAD-based segmentation using GStreamer `level` element and extends `SegmentBuffer` for audio.

**Location**: `apps/media-service/src/media_service/buffer/vad_audio_segmenter.py`

**Interface**:
```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from media_service.buffer.segment_buffer import BufferAccumulator
from media_service.models.segments import AudioSegment


class SegmentTrigger(Enum):
    """Reason for segment emission."""
    SILENCE_DETECTED = "silence_detected"
    MAX_DURATION_REACHED = "max_duration_reached"
    EOS_FLUSH = "eos_flush"


@dataclass
class VADConfig:
    """VAD configuration parameters.

    Attributes:
        enabled: Whether VAD is enabled (always True - required)
        silence_threshold_db: RMS level threshold for silence detection (e.g., -40.0)
        silence_duration_ms: Duration audio must be below threshold (e.g., 1000)
        min_segment_duration_ns: Minimum segment duration (e.g., 1_000_000_000 = 1s)
        max_segment_duration_ns: Maximum segment duration (e.g., 15_000_000_000 = 15s)
    """
    enabled: bool = True
    silence_threshold_db: float = -40.0
    silence_duration_ms: int = 1000
    min_segment_duration_ns: int = 1_000_000_000  # 1 second
    max_segment_duration_ns: int = 15_000_000_000  # 15 seconds


class VADAudioSegmenter:
    """VAD-based audio segmentation using GStreamer level element.

    Monitors RMS levels from GStreamer level element and emits segments
    at natural speech boundaries (silence detection) instead of fixed intervals.

    Attributes:
        stream_id: Stream identifier
        config: VAD configuration
        _accumulator: Buffer accumulator for audio data
        _audio_batch_number: Current batch number
        _silence_start_ns: Timestamp when current silence period started
        _is_in_silence: Whether currently in silence period
        # No fallback mode - level element is required
    """

    def __init__(
        self,
        stream_id: str,
        segment_dir: Path,
        config: VADConfig,
    ) -> None:
        """Initialize VAD audio segmenter.

        Args:
            stream_id: Stream identifier
            segment_dir: Base directory for segment storage
            config: VAD configuration parameters
        """
        ...

    def push_audio(
        self,
        buffer_data: bytes,
        pts_ns: int,
        duration_ns: int,
    ) -> tuple[AudioSegment | None, bytes]:
        """Push audio buffer and return segment if ready.

        Args:
            buffer_data: Raw audio buffer data (AAC)
            pts_ns: Buffer presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds

        Returns:
            Tuple of (AudioSegment, accumulated_data) if segment ready,
            (None, empty bytes) otherwise
        """
        ...

    def handle_level_message(
        self,
        rms_db: float,
        timestamp_ns: int,
    ) -> tuple[AudioSegment | None, bytes]:
        """Handle RMS level message from GStreamer level element.

        Detects silence boundaries and triggers segment emission.

        Args:
            rms_db: RMS level in decibels
            timestamp_ns: Message timestamp in nanoseconds

        Returns:
            Tuple of (AudioSegment, accumulated_data) if silence boundary detected,
            (None, empty bytes) otherwise
        """
        ...

    def flush_audio(self) -> tuple[AudioSegment | None, bytes]:
        """Flush remaining audio as partial segment (EOS).

        Returns:
            Tuple of (AudioSegment, data) if valid partial (>= 1s),
            (None, empty bytes) if too short or no data
        """
        ...

    # No enable_fallback_mode() - level element is required, fatal error if missing
```

**Key Methods**:
- `push_audio()`: Same signature as `SegmentBuffer.push_audio()` for API compatibility
- `handle_level_message()`: Process RMS messages from GStreamer bus
- `flush_audio()`: EOS handling with 1s minimum duration check

**State Management**:
- `_silence_start_ns`: Tracks when silence period begins
- `_is_in_silence`: Boolean flag for current silence state

---

### 2. SegmentationConfig

**Purpose**: Centralized configuration management for VAD parameters.

**Location**: `apps/media-service/src/media_service/config/segmentation.py` (new module)

**Interface**:
```python
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SegmentationConfig:
    """Centralized segmentation configuration.

    Loads VAD parameters from environment variables with sensible defaults.

    Environment Variables:
        VAD_ENABLED: Enable VAD segmentation (default: true)
        VAD_SILENCE_THRESHOLD_DB: Silence RMS threshold in dB (default: -40.0)
        VAD_SILENCE_DURATION_MS: Silence duration in milliseconds (default: 1000)
        VAD_MIN_SEGMENT_DURATION_MS: Minimum segment duration (default: 1000 = 1s)
        VAD_MAX_SEGMENT_DURATION_MS: Maximum segment duration (default: 15000 = 15s)
    """

    vad_enabled: bool
    silence_threshold_db: float
    silence_duration_ms: int
    min_segment_duration_ns: int
    max_segment_duration_ns: int

    @classmethod
    def from_env(cls) -> SegmentationConfig:
        """Load configuration from environment variables.

        Returns:
            SegmentationConfig instance with loaded parameters
        """
        vad_enabled = os.getenv("VAD_ENABLED", "true").lower() == "true"
        silence_threshold_db = float(os.getenv("VAD_SILENCE_THRESHOLD_DB", "-40.0"))
        silence_duration_ms = int(os.getenv("VAD_SILENCE_DURATION_MS", "1000"))
        min_segment_duration_ms = int(os.getenv("VAD_MIN_SEGMENT_DURATION_MS", "1000"))
        max_segment_duration_ms = int(os.getenv("VAD_MAX_SEGMENT_DURATION_MS", "15000"))

        # Convert milliseconds to nanoseconds for internal use
        min_segment_duration_ns = min_segment_duration_ms * 1_000_000
        max_segment_duration_ns = max_segment_duration_ms * 1_000_000

        return cls(
            vad_enabled=vad_enabled,
            silence_threshold_db=silence_threshold_db,
            silence_duration_ms=silence_duration_ms,
            min_segment_duration_ns=min_segment_duration_ns,
            max_segment_duration_ns=max_segment_duration_ns,
        )

    def validate(self) -> None:
        """Validate configuration parameters.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.silence_threshold_db > 0:
            raise ValueError(f"Silence threshold must be negative dB: {self.silence_threshold_db}")

        if self.silence_duration_ms < 100:
            raise ValueError(f"Silence duration too short: {self.silence_duration_ms}ms (min 100ms)")

        if self.min_segment_duration_ns < 500_000_000:
            raise ValueError(f"Min segment duration too short: {self.min_segment_duration_ns}ns (min 500ms)")

        if self.max_segment_duration_ns < self.min_segment_duration_ns:
            raise ValueError("Max segment duration must be >= min segment duration")
```

**Design Rationale**:
- Environment variables allow configuration without code changes
- Validation ensures sane parameter ranges
- Millisecond → nanosecond conversion handled internally
- Defaults tuned for broadcast audio (-40dB, 1s silence, 1s-15s segments)

---

### 3. VADMetrics

**Purpose**: Prometheus metrics for VAD observability.

**Location**: Extend `apps/media-service/src/media_service/metrics/prometheus.py`

**New Metrics**:
```python
# Add to WorkerMetrics class:

# VAD-specific metrics (class-level singletons)
_vad_segments_total: ClassVar[Counter | None] = None
_vad_silence_detections_total: ClassVar[Counter | None] = None
_vad_forced_emissions_total: ClassVar[Counter | None] = None
_vad_segment_duration_seconds: ClassVar[Histogram | None] = None
_vad_min_duration_violations_total: ClassVar[Counter | None] = None

# In _ensure_metrics_initialized():

cls._vad_segments_total = Counter(
    f"{prefix}_vad_segments_total",
    "Total segments emitted via VAD",
    ["stream_id", "trigger"],  # trigger: silence_detected|max_duration_reached|eos_flush
)

cls._vad_silence_detections_total = Counter(
    f"{prefix}_vad_silence_detections_total",
    "Total silence boundaries detected",
    ["stream_id"],
)

cls._vad_forced_emissions_total = Counter(
    f"{prefix}_vad_forced_emissions_total",
    "Total segments forcibly emitted at max duration",
    ["stream_id"],
)

cls._vad_segment_duration_seconds = Histogram(
    f"{prefix}_vad_segment_duration_seconds",
    "VAD segment duration distribution",
    ["stream_id"],
    buckets=[0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0],
)

cls._vad_min_duration_violations_total = Counter(
    f"{prefix}_vad_min_duration_violations_total",
    "Segments buffered due to min duration violation",
    ["stream_id"],
)

# Accessor methods:

def record_vad_segment(self, trigger: str, duration_seconds: float) -> None:
    """Record VAD segment emission.

    Args:
        trigger: "silence_detected", "max_duration_reached", or "eos_flush"
        duration_seconds: Segment duration in seconds
    """
    self._vad_segments_total.labels(
        stream_id=self.stream_id,
        trigger=trigger,
    ).inc()

    self._vad_segment_duration_seconds.labels(
        stream_id=self.stream_id,
    ).observe(duration_seconds)

def record_vad_silence_detection(self) -> None:
    """Record silence boundary detection."""
    self._vad_silence_detections_total.labels(stream_id=self.stream_id).inc()

def record_vad_forced_emission(self) -> None:
    """Record forced emission at max duration."""
    self._vad_forced_emissions_total.labels(stream_id=self.stream_id).inc()

def record_vad_min_duration_violation(self) -> None:
    """Record min duration violation (segment buffered)."""
    self._vad_min_duration_violations_total.labels(stream_id=self.stream_id).inc()
```

**Metrics Purpose**:
- `vad_segments_total`: Track segmentation triggers (silence vs forced vs EOS)
- `vad_segment_duration_seconds`: Histogram shows natural distribution (expect peak 3-5s)
- `vad_forced_emissions_total`: Alert if too many forced emissions (indicates continuous speech)
- `vad_min_duration_violations_total`: Track min duration guard activations (rapid speech)

---

## Data Flow

### Normal Operation (VAD Enabled)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. GStreamer Input Pipeline                                             │
│                                                                          │
│    rtmpsrc → flvdemux → aacparse → level → appsink                      │
│                                       │                                  │
│                                       ├─→ Audio buffers (callback)      │
│                                       └─→ Level messages (bus)          │
└─────────────────────────────────────────────────────────────────────────┘
                    │                             │
                    │ (audio buffers)             │ (level messages)
                    ↓                             ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. WorkerRunner (orchestration)                                         │
│                                                                          │
│    _on_audio_buffer()               _on_bus_message()                   │
│         │                                  │                             │
│         ↓                                  ↓                             │
│    vad_segmenter.push_audio()     vad_segmenter.handle_level_message()  │
│         │                                  │                             │
│         └──────────────┬───────────────────┘                             │
│                        ↓                                                 │
│               VADAudioSegmenter                                          │
│               ┌────────────────┐                                         │
│               │ Accumulate     │                                         │
│               │ buffers        │                                         │
│               └────────────────┘                                         │
│                        │                                                 │
│               ┌────────┴────────┐                                        │
│               │  Check triggers │                                        │
│               │  - Silence 1s?  │                                        │
│               │  - Duration 15s?│                                        │
│               └────────┬────────┘                                        │
│                        │                                                 │
│                   YES  │  NO                                             │
│                   ┌────┴─────┐                                           │
│                   ↓          ↓                                           │
│             Emit segment   Continue buffering                            │
│             (AudioSegment, bytes)                                        │
└─────────────────────────────────────────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. Downstream Processing (unchanged)                                    │
│                                                                          │
│    AudioSegmentWriter → STS Client → A/V Sync → Output Pipeline         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Timing Points

1. **Buffer Arrival**: Audio buffers arrive at ~23ms intervals (AAC frame duration at 48kHz)
2. **Level Messages**: GStreamer `level` element emits messages every 100ms (configurable via `interval` property)
3. **Silence Detection**: After 1s of consecutive RMS < -40dB readings (10 messages @ 100ms interval)
4. **Segment Emission**: Triggered by silence boundary or max duration (15s)

**Note**: No fallback mode - level element is REQUIRED. Fatal error if unavailable.

---

## Implementation Approach

### Phase 1: Core VAD Implementation

**Goal**: Implement VADAudioSegmenter with GStreamer level element integration.

**Tasks**:

1. **Create VADAudioSegmenter class** (`apps/media-service/src/media_service/buffer/vad_audio_segmenter.py`)
   - Implement `__init__()` with VADConfig parameter
   - Implement `push_audio()` with buffer accumulation
   - Implement `handle_level_message()` for silence detection
   - Implement `flush_audio()` for EOS handling
   - Add unit tests for each method

2. **Create SegmentationConfig module** (`apps/media-service/src/media_service/config/segmentation.py`)
   - Implement `from_env()` class method
   - Implement `validate()` method
   - Add unit tests for configuration loading and validation

3. **Extend WorkerMetrics** (`apps/media-service/src/media_service/metrics/prometheus.py`)
   - Add VAD metrics (gauges, counters, histograms)
   - Add accessor methods
   - Update tests for new metrics

**Success Criteria**:
- All unit tests pass (80%+ coverage)
- VADAudioSegmenter can be instantiated with configuration
- Silence detection logic validated with synthetic audio patterns

---

### Phase 2: GStreamer Pipeline Integration

**Goal**: Integrate `level` element into InputPipeline and wire up message handling.

**Tasks**:

1. **Modify InputPipeline** (`apps/media-service/src/media_service/pipeline/input.py`)
   - Add `level` element to audio branch after aacparse
   - Configure level properties: `interval=100000000` (100ms), `message=True`
   - Set up bus watch for level messages
   - Extract RMS values from message structure
   - Pass RMS data to callback or store for polling

2. **Update WorkerRunner** (`apps/media-service/src/media_service/worker/worker_runner.py`)
   - Replace `SegmentBuffer` with `VADAudioSegmenter` for audio path
   - Keep `SegmentBuffer` for video path (unchanged)
   - Add `_on_bus_message()` handler for level messages
   - Call `vad_segmenter.handle_level_message()` when level messages arrive
   - Let level element initialization failures propagate as fatal errors

**GStreamer Pipeline Changes**:

**Before (Fixed 6s)**:
```
rtmpsrc → flvdemux → aacparse → appsink
```

**After (VAD)**:
```
rtmpsrc → flvdemux → aacparse → level → appsink
                                  │
                                  └─→ level messages (bus)
```

**Level Element Configuration**:
```python
level = Gst.ElementFactory.make("level", "audio_level")
level.set_property("interval", 100000000)  # 100ms in nanoseconds
level.set_property("message", True)  # Enable bus messages
```

**Success Criteria**:
- Level element successfully added to pipeline
- Level messages received on bus every 100ms
- RMS values correctly extracted and passed to VADAudioSegmenter
- Pipeline fails fast if level element unavailable (requires gst-plugins-good)
- Integration tests confirm variable-length segments emitted

---

### Phase 3: Metrics and Observability

**Goal**: Enable production monitoring and debugging.

**Tasks**:

1. **Implement metrics recording** in VADAudioSegmenter
   - Call `metrics.record_vad_segment()` on emission
   - Call `metrics.record_vad_silence_detection()` on boundary
   - Call `metrics.record_vad_forced_emission()` on max duration
   - Call `metrics.record_vad_min_duration_violation()` when buffering short segments

2. **Add structured logging**
   - Log segment emissions with trigger reason and duration
   - Log silence detections with RMS level and timestamp
   - Log errors with detailed context
   - Include stream_id and batch_number in all logs

**Example Log Output**:
```
INFO  [stream=live123] VAD segment emitted: batch=42, duration=3.2s, trigger=silence_detected, rms=-45.3dB
INFO  [stream=live123] Silence boundary detected: rms=-42.1dB, duration=1.05s
WARN  [stream=live123] VAD forced emission: batch=43, duration=15.0s (max duration reached)
ERROR [stream=live123] VAD initialization failed: level element unavailable - check gst-plugins-good installation
```

**Success Criteria**:
- All VAD events logged with context
- Prometheus metrics exposed on `/metrics` endpoint
- Metrics show correct counts during test runs

---

### Phase 4: Configuration and Tuning

**Goal**: Enable operators to tune VAD parameters for different content types.

**Tasks**:

1. **Document configuration parameters** (README or spec)
   - `VAD_ENABLED`: Enable/disable VAD (default: true)
   - `VAD_SILENCE_THRESHOLD_DB`: RMS threshold (default: -40.0)
   - `VAD_SILENCE_DURATION_MS`: Silence duration (default: 1000)
   - `VAD_MIN_SEGMENT_DURATION_MS`: Min segment (default: 1000)
   - `VAD_MAX_SEGMENT_DURATION_MS`: Max segment (default: 15000)

2. **Create tuning guide** for common scenarios:
   - **Studio speech** (clean audio): `-50dB threshold, 800ms silence`
   - **Live broadcast** (ambient noise): `-40dB threshold, 1000ms silence`
   - **Noisy environments** (crowd noise): `-35dB threshold, 1200ms silence`
   - **Multi-speaker** (overlapping speech): `-40dB threshold, 1500ms silence`

3. **Add configuration validation**
   - Prevent invalid ranges (e.g., threshold > 0dB, min > max)
   - Log warnings for unusual configurations
   - Document recommended ranges

**Success Criteria**:
- Configuration loaded from environment variables
- Invalid configurations rejected with clear error messages
- Tuning guide covers common use cases
- Operators can adjust parameters without code changes

---

## GStreamer Pipeline Integration

### Adding the `level` Element

The `level` element calculates RMS (Root Mean Square) and peak audio levels and emits messages on the GStreamer bus.

**Element Properties**:
```python
level.set_property("interval", 100000000)  # 100ms interval (nanoseconds)
level.set_property("message", True)        # Enable bus messages
level.set_property("peak-ttl", 0)          # Disable peak decay (we only use RMS)
level.set_property("peak-falloff", 0)      # Disable peak falloff
```

**Pipeline Integration** (in `InputPipeline.build()`):

```python
# Audio branch with level element
audio_parse = Gst.ElementFactory.make("aacparse", "audio_parse")
audio_level = Gst.ElementFactory.make("level", "audio_level")
audio_sink = Gst.ElementFactory.make("appsink", "audio_sink")

if not audio_level:
    raise RuntimeError(
        "Failed to create level element - VAD requires gst-plugins-good. "
        "Install with: apt-get install gstreamer1.0-plugins-good"
    )
else:
    # Configure level element
    audio_level.set_property("interval", 100000000)  # 100ms
    audio_level.set_property("message", True)

    # Add and link: aacparse → level → appsink
    self._pipeline.add(audio_parse, audio_level, audio_sink)
    audio_parse.link(audio_level)
    audio_level.link(audio_sink)

# Set up bus watch for level messages
bus = self._pipeline.get_bus()
bus.add_signal_watch()
bus.connect("message::element", self._on_level_message)
```

**Message Parsing** (in `InputPipeline._on_level_message()`):

```python
def _on_level_message(self, bus: Gst.Bus, message: Gst.Message) -> None:
    """Handle level element messages from bus.

    Args:
        bus: GStreamer bus
        message: Element message
    """
    if message.get_structure() is None:
        return

    structure_name = message.get_structure().get_name()
    if structure_name != "level":
        return

    # Extract RMS values (in dB)
    # Level element provides separate RMS per channel, we use channel 0
    rms_list = message.get_structure().get_value("rms")
    if not rms_list or len(rms_list) == 0:
        return

    rms_db = rms_list[0]  # Use first channel
    timestamp_ns = message.timestamp

    # Pass to VAD handler (set during initialization)
    if self._on_level_callback:
        self._on_level_callback(rms_db, timestamp_ns)
```

**Callback Wiring** (in `WorkerRunner._build_pipelines()`):

```python
self.input_pipeline = InputPipeline(
    rtmp_url=self.config.rtmp_input_url,
    on_video_buffer=self._on_video_buffer,
    on_audio_buffer=self._on_audio_buffer,
    on_level_message=self._on_level_message,  # NEW
)

# Handler in WorkerRunner
def _on_level_message(self, rms_db: float, timestamp_ns: int) -> None:
    """Handle RMS level message from input pipeline.

    Args:
        rms_db: RMS level in decibels
        timestamp_ns: Message timestamp
    """
    segment, segment_data = self.vad_segmenter.handle_level_message(
        rms_db, timestamp_ns
    )

    if segment is not None:
        # Segment ready due to silence boundary
        self._audio_queue.put_nowait((segment, segment_data))
```

### Level Element Error Handling

**Initialization Failure** (FATAL):
```python
audio_level = Gst.ElementFactory.make("level", "audio_level")
if not audio_level:
    raise RuntimeError(
        "Failed to create level element - VAD requires gst-plugins-good. "
        "Install with: apt-get install gstreamer1.0-plugins-good"
    )
# No fallback - level element is required
```

**Note**: No fallback mode. If level element is unavailable, the service fails to start.
This ensures proper deployment configuration and avoids silent degradation.

---

## Configuration Management

### Environment Variables

```bash
# Enable/disable VAD
VAD_ENABLED=true                        # true|false (default: true)

# Silence detection parameters
VAD_SILENCE_THRESHOLD_DB=-40.0          # RMS threshold in dB (default: -40.0)
VAD_SILENCE_DURATION_MS=1000            # Silence duration in ms (default: 1000)

# Segment duration guards
VAD_MIN_SEGMENT_DURATION_MS=1000        # Min duration in ms (default: 1000 = 1s)
VAD_MAX_SEGMENT_DURATION_MS=15000       # Max duration in ms (default: 15000 = 15s)
```

### Loading Configuration

```python
# In WorkerRunner.__init__()
from media_service.config.segmentation import SegmentationConfig

self.segmentation_config = SegmentationConfig.from_env()
self.segmentation_config.validate()

# Pass to VADAudioSegmenter
self.vad_segmenter = VADAudioSegmenter(
    stream_id=self.config.stream_id,
    segment_dir=self.config.segment_dir,
    config=VADConfig(
        enabled=self.segmentation_config.vad_enabled,
        silence_threshold_db=self.segmentation_config.silence_threshold_db,
        silence_duration_ms=self.segmentation_config.silence_duration_ms,
        min_segment_duration_ns=self.segmentation_config.min_segment_duration_ns,
        max_segment_duration_ns=self.segmentation_config.max_segment_duration_ns,
    ),
)
```

### Tuning Guide

**Content Type: Studio Speech (Clean Audio)**
```bash
VAD_SILENCE_THRESHOLD_DB=-50.0    # Lower threshold for quieter noise floor
VAD_SILENCE_DURATION_MS=800       # Shorter silence detection
VAD_MIN_SEGMENT_DURATION_MS=1000
VAD_MAX_SEGMENT_DURATION_MS=12000 # Shorter max for tighter segmentation
```

**Content Type: Live Broadcast (Ambient Noise)**
```bash
VAD_SILENCE_THRESHOLD_DB=-40.0    # Default (handles typical broadcast noise)
VAD_SILENCE_DURATION_MS=1000      # Default
VAD_MIN_SEGMENT_DURATION_MS=1000
VAD_MAX_SEGMENT_DURATION_MS=15000
```

**Content Type: Noisy Environment (Crowd, Music)**
```bash
VAD_SILENCE_THRESHOLD_DB=-35.0    # Higher threshold (noisier floor)
VAD_SILENCE_DURATION_MS=1200      # Longer silence to avoid false positives
VAD_MIN_SEGMENT_DURATION_MS=1500  # Longer min to reduce short fragments
VAD_MAX_SEGMENT_DURATION_MS=15000
```

**Content Type: Multi-Speaker (Panel Discussion)**
```bash
VAD_SILENCE_THRESHOLD_DB=-40.0
VAD_SILENCE_DURATION_MS=1500      # Longer to detect speaker transitions
VAD_MIN_SEGMENT_DURATION_MS=1000
VAD_MAX_SEGMENT_DURATION_MS=15000
```

---

## Metrics and Observability

### Prometheus Metrics

**Counters** (cumulative):
- `media_service_worker_vad_segments_total{stream_id, trigger}`: Total segments emitted
  - `trigger=silence_detected`: Natural speech boundaries
  - `trigger=max_duration_reached`: Forced at 15s
  - `trigger=eos_flush`: End-of-stream partial
- `media_service_worker_vad_silence_detections_total{stream_id}`: Silence boundaries detected
- `media_service_worker_vad_forced_emissions_total{stream_id}`: Segments forced at max duration
- `media_service_worker_vad_min_duration_violations_total{stream_id}`: Segments buffered due to < 1s

**Histograms** (distributions):
- `media_service_worker_vad_segment_duration_seconds{stream_id}`: Segment duration distribution
  - Buckets: [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0]
  - Expected peak: 3-5s for natural speech

### Alerting Queries

**High Forced Emission Rate** (warning):
```promql
# Alert if > 30% of segments are forced at max duration (indicates continuous speech)
rate(media_service_worker_vad_forced_emissions_total[5m])
/
rate(media_service_worker_vad_segments_total[5m]) > 0.3
```

**Low Silence Detection Rate** (warning):
```promql
# Alert if silence detection rate < 10 per minute (may indicate noisy audio)
rate(media_service_worker_vad_silence_detections_total[1m]) < 10
```

## Testing Strategy

### Unit Tests

**Location**: `apps/media-service/tests/unit/buffer/`

**Test Cases for VADAudioSegmenter**:

1. **test_vad_silence_detection_triggers_emission**
   - Push buffers with normal speech (RMS > -40dB)
   - Send level message with RMS = -42dB for 1s
   - Assert segment emitted with trigger=SILENCE_DETECTED

2. **test_vad_max_duration_forces_emission**
   - Push buffers continuously for 15s without silence
   - Assert segment forcibly emitted at 15s with trigger=MAX_DURATION_REACHED

3. **test_vad_min_duration_violation_buffers_segment**
   - Push buffers totaling 0.7s
   - Send silence boundary
   - Assert NO segment emitted (buffered)
   - Push another 0.5s of buffers
   - Assert segment emitted with 1.2s duration

4. **test_vad_pts_tracking_accurate**
   - Push multiple buffers with known PTS
   - Emit segment
   - Assert segment.t0_ns matches first buffer PTS
   - Assert segment.duration_ns matches accumulated duration

6. **test_vad_eos_flush_discards_short_partials**
   - Push buffers totaling 0.8s
   - Call flush_audio()
   - Assert None returned (< 1s minimum)

7. **test_vad_eos_flush_emits_valid_partials**
   - Push buffers totaling 1.5s
   - Call flush_audio()
   - Assert segment emitted with 1.5s duration

**Test Cases for SegmentationConfig**:

1. **test_config_from_env_defaults**
   - Clear environment variables
   - Load config
   - Assert default values (-40dB, 1s, 1s-15s range)

2. **test_config_from_env_custom**
   - Set environment variables
   - Load config
   - Assert custom values loaded

3. **test_config_validation_rejects_invalid_threshold**
   - Set threshold = 10.0 (positive)
   - Assert validate() raises ValueError

4. **test_config_validation_rejects_invalid_duration**
   - Set min_duration > max_duration
   - Assert validate() raises ValueError

### Integration Tests

**Location**: `apps/media-service/tests/integration/buffer/`

**Test Cases**:

1. **test_vad_integration_with_real_audio**
   - Use test audio file with known speech pattern (3s speech, 1s silence, 2s speech)
   - Run through InputPipeline → VADAudioSegmenter
   - Assert 2 segments emitted with durations ~3s and ~2s

2. **test_vad_integration_level_element_failure_fatal**
   - Mock level element to return None (init failure)
   - Build pipeline
   - Assert RuntimeError raised with message about gst-plugins-good
   - Assert pipeline does NOT start

3. **test_vad_integration_with_mediamtx**
   - Start MediaMTX with test stream (Docker)
   - Start WorkerRunner with VAD enabled
   - Publish test audio with silence patterns
   - Assert variable-length segments written to disk
   - Assert vad_enabled metric = 1

### E2E Tests

**Location**: `tests/e2e/`

**Test Cases**:

1. **test_e2e_vad_full_pipeline**
   - Start full E2E stack (MediaMTX, media-service, STS)
   - Publish test stream with speech + silence patterns
   - Assert variable-length audio fragments sent to STS
   - Assert A/V sync maintained (delta < 120ms)
   - Assert output stream plays correctly

2. **test_e2e_vad_metrics_exposed**
   - Start E2E stack with VAD enabled
   - Query /metrics endpoint
   - Assert vad_segments_total > 0
   - Assert vad_segment_duration_seconds histogram populated

### Test Data

**Create Test Fixtures** (`tests/fixtures/audio/`):

1. **speech_with_silence.aac**
   - 3 seconds speech (RMS -30dB)
   - 1 second silence (RMS -50dB)
   - 2 seconds speech (RMS -30dB)
   - Total: 6 seconds

2. **continuous_speech.aac**
   - 20 seconds continuous speech (no pauses)
   - Used to test max duration guard

3. **rapid_speech.aac**
   - Rapid utterances: 0.8s speech, 0.5s pause, 0.7s speech, 0.4s pause
   - Used to test min duration accumulation

---

## Risk Analysis

### Risk 1: GStreamer `level` Element Not Available

**Probability**: Low
**Impact**: High (VAD cannot function)

**Mitigation**:
- Check for element availability during initialization
- Raise fatal RuntimeError if unavailable (fail-fast design)
- Clear error message with installation instructions
- Document `gst-plugins-good` as required dependency
- Add health check to deployment (verify level element before start)

**Detection**:
- Unit test: `test_level_element_raises_on_failure`
- Service fails to start if level element unavailable (no metrics needed)

---

### Risk 2: Audio Format Incompatibility

**Probability**: Medium
**Impact**: Medium (VAD fails for specific streams)

**Mitigation**:
- Test with common AAC variants (ADTS, MP4, raw)
- Log level element errors with details
- Fatal error if audio format incompatible (fail-fast design)
- Document supported audio formats in deployment docs
- Validate stream format before processing

**Detection**:
- Integration test with various AAC formats
- Service logs clear error message with format details

---

### Risk 3: RMS Threshold Too Sensitive (False Positives)

**Probability**: Medium
**Impact**: Low (too many short segments)

**Mitigation**:
- Use conservative default (-40dB) tuned for broadcast audio
- Make threshold configurable per environment
- Provide tuning guide for different content types
- Monitor `vad_segment_duration_seconds` histogram for unusual patterns
- Min duration guard prevents very short segments (<1s)

**Detection**:
- Metric: `vad_segment_duration_seconds` (check for peak < 1s)
- Metric: `vad_min_duration_violations_total` (high rate indicates over-sensitivity)

---

### Risk 4: RMS Threshold Not Sensitive Enough (Missed Boundaries)

**Probability**: Medium
**Impact**: Medium (long segments, degraded translation quality)

**Mitigation**:
- Max duration guard forcibly emits at 15s
- Monitor forced emission rate
- Alert if > 30% of segments hit max duration
- Provide tuning guide to lower threshold for cleaner audio

**Detection**:
- Metric: `vad_forced_emissions_total` / `vad_segments_total` ratio
- Alert: `ratio > 0.3` indicates continuous speech or insensitive threshold

---

### Risk 5: A/V Sync Breaks with Variable Audio Segments

**Probability**: Low
**Impact**: Critical (dubbing unusable)

**Mitigation**:
- Preserve existing PTS tracking in AudioSegment model (no changes needed)
- A/V sync manager already handles variable durations (uses duration_ns)
- Extensive integration tests for A/V sync with variable segments
- Monitor `av_sync_delta_ms` metric (alert if > 120ms)

**Detection**:
- E2E test: `test_av_sync_with_vad_segments` (verify delta < 120ms)
- Metric: `media_service_worker_av_sync_delta_ms`

---

### Risk 6: Performance Degradation from Level Processing

**Probability**: Low
**Impact**: Low (slight latency increase)

**Mitigation**:
- Level element is hardware-accelerated where available
- 100ms message interval reduces message volume
- Level processing happens asynchronously on GStreamer bus
- Monitor processing latency in tests

**Detection**:
- Performance test: measure segment emission latency (target < 50ms overhead)
- E2E test: verify total pipeline latency unchanged

---

### Risk 7: Configuration Errors Break Pipeline

**Probability**: Medium
**Impact**: Medium (pipeline fails to start)

**Mitigation**:
- Validate configuration on load (SegmentationConfig.validate())
- Reject invalid ranges with clear error messages
- Provide sensible defaults
- Document recommended ranges
- Unit tests for all validation paths

**Detection**:
- Unit test: `test_config_validation_*` suite
- Production: startup validation fails fast before accepting traffic

---

## Rollout Plan

### Phase 1: Development and Testing (Week 1-2)

**Goals**:
- Implement core VAD logic
- Add unit and integration tests
- Validate with synthetic audio

**Tasks**:
1. Create VADAudioSegmenter class with unit tests
2. Create SegmentationConfig with validation
3. Extend WorkerMetrics with VAD metrics
4. Integration test with test audio fixtures
5. Code review and iteration

**Success Criteria**:
- All unit tests pass (80%+ coverage)
- Integration tests confirm variable segments
- Code review approved

---

### Phase 2: GStreamer Integration (Week 3)

**Goals**:
- Integrate level element into pipeline
- E2E testing with real streams
- Performance validation

**Tasks**:
1. Modify InputPipeline to add level element
2. Update WorkerRunner with VAD segmenter
3. E2E test with MediaMTX + STS
4. Performance testing (latency, memory)
5. Fix any integration issues

**Success Criteria**:
- E2E tests pass with VAD enabled
- A/V sync maintained (< 120ms delta)
- No memory leaks over 10-minute test
- Latency overhead < 50ms

---

### Phase 3: Canary Deployment (Week 4)

**Goals**:
- Deploy to staging environment
- Monitor real-world performance
- Tune default parameters

**Tasks**:
1. Deploy to staging with VAD enabled
2. Run 24-hour soak test with live streams
3. Monitor metrics (segment duration, A/V sync, forced emissions)
4. Tune default threshold if needed
5. Document tuning parameters

**Success Criteria**:
- No errors or restarts in 24 hours (VAD stable)
- Segment duration distribution shows peak 3-5s
- A/V sync delta < 120ms for 95% of segments
- Translation quality subjectively improved (manual review)

---

### Phase 4: Production Rollout (Week 5)

**Goals**:
- Gradual rollout to production
- Monitor health and performance
- Enable for all streams

**Strategy**:
1. **10% Traffic** (Day 1-2):
   - Enable VAD for 10% of streams via feature flag
   - Monitor metrics closely
   - Compare translation quality vs fixed segmentation

2. **50% Traffic** (Day 3-4):
   - Increase to 50% if no issues
   - Validate metrics at scale
   - Tune thresholds for specific content types

3. **100% Traffic** (Day 5-7):
   - Enable for all streams
   - Monitor for 3 days
   - Document operational playbook

**Rollback Plan**:
- Revert to previous Docker image tag (pre-VAD version)
- Restart services
- No runtime config toggle (fail-fast design)

**Success Criteria**:
- No increase in error rates
- A/V sync maintained at scale
- Translation quality improved (20% reduction in mid-phrase splits)
- Operator feedback positive

---

### Phase 5: Documentation and Cleanup (Week 6)

**Goals**:
- Complete documentation
- Remove any deprecated code
- Finalize operational playbook

**Tasks**:
1. Update deployment documentation with VAD requirements
2. Remove any legacy fixed-segmentation code paths
3. Document tuning parameters for different content types
4. Create operational playbook for VAD troubleshooting

**Success Criteria**:
- VAD is the only segmentation mode (no legacy code)
- Documentation complete and up-to-date
- Operations team trained on VAD configuration

---

## Appendix

### Related Specs

- [003-gstreamer-stream-worker](../003-gstreamer-stream-worker/spec.md) - GStreamer pipeline architecture
- [017-echo-sts-service](../017-echo-sts-service/spec.md) - STS fragment protocol
- [018-e2e-stream-handler-tests](../018-e2e-stream-handler-tests/spec.md) - E2E testing framework

### References

- [GStreamer level element documentation](https://gstreamer.freedesktop.org/documentation/level/index.html)
- [Voice Activity Detection (VAD) overview](https://en.wikipedia.org/wiki/Voice_activity_detection)
- [RMS (Root Mean Square) calculation](https://en.wikipedia.org/wiki/Root_mean_square)
- [Prometheus histogram best practices](https://prometheus.io/docs/practices/histograms/)

### Open Questions

1. **Q**: Should we support per-stream VAD configuration overrides?
   **A**: Deferred to future iteration. Use global config for MVP, add per-stream overrides if needed.

2. **Q**: Should we expose raw RMS levels as metrics for debugging?
   **A**: No for MVP (too high cardinality). Add debug logging instead.

3. **Q**: Should we implement more sophisticated VAD (spectral analysis, ML-based)?
   **A**: No for MVP. RMS-based VAD is sufficient for most speech. Evaluate after production deployment.

4. **Q**: How do we handle music-only streams (no speech)?
   **A**: Max duration guard (15s) ensures segments are emitted. Operators can disable VAD for music streams via `VAD_ENABLED=false`.

---

**End of Implementation Plan**
