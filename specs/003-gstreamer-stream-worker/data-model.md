# Data Model: Stream Worker Implementation

**Feature**: Stream Worker Implementation
**Date**: 2025-12-28
**Related**: [spec.md](./spec.md), [plan.md](./plan.md)

## Overview

This document defines the data structures used by the stream worker for audio processing, STS integration, and pipeline management.

## Core Data Structures

### VideoSegment

Video segment written to disk as MP4 file (H.264 codec-copy).

```python
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

@dataclass
class VideoSegment:
    """Video segment metadata for disk-based storage.

    Video is stored as MP4 file with H.264 codec-copied from source.
    No transcoding occurs - original video quality preserved.

    Attributes:
        fragment_id: Unique identifier for this segment (UUID v4).
        stream_id: Identifier of the source stream.
        batch_number: Sequential number within the stream (0-indexed).
        t0_ns: PTS of the first frame in nanoseconds (GStreamer clock).
        duration_ns: Duration of the segment in nanoseconds.
        file_path: Path to MP4 file on disk.
        file_size: Size of MP4 file in bytes.

    Invariants:
        - duration_ns should be ~6_000_000_000 (6 seconds) +/- 100ms
        - file_path points to valid MP4 with H.264 video track
    """
    fragment_id: str
    stream_id: str
    batch_number: int
    t0_ns: int
    duration_ns: int
    file_path: Path
    file_size: int = 0

    @classmethod
    def create(
        cls,
        stream_id: str,
        batch_number: int,
        t0_ns: int,
        duration_ns: int,
        segment_dir: Path,
    ) -> "VideoSegment":
        """Factory method to create a VideoSegment with auto-generated fragment_id."""
        fragment_id = str(uuid4())
        file_path = segment_dir / stream_id / f"{batch_number:06d}_video.mp4"
        return cls(
            fragment_id=fragment_id,
            stream_id=stream_id,
            batch_number=batch_number,
            t0_ns=t0_ns,
            duration_ns=duration_ns,
            file_path=file_path,
        )

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.duration_ns / 1_000_000_000

    @property
    def exists(self) -> bool:
        """Check if segment file exists on disk."""
        return self.file_path.exists()
```

### AudioSegment

Audio segment written to disk as M4A file (AAC codec-copy).

```python
@dataclass
class AudioSegment:
    """Audio segment metadata for disk-based storage and STS transport.

    Audio is stored as M4A file (AAC in MP4 container) codec-copied from source.
    No PCM conversion - AAC preserved for efficient STS transport.

    Attributes:
        fragment_id: Unique identifier for this segment (UUID v4).
        stream_id: Identifier of the source stream.
        batch_number: Sequential number within the stream (0-indexed).
        t0_ns: PTS of the first sample in nanoseconds (GStreamer clock).
        duration_ns: Duration of the segment in nanoseconds.
        file_path: Path to M4A file on disk.
        file_size: Size of M4A file in bytes.
        dubbed_file_path: Path to dubbed M4A file (after STS processing).
        is_dubbed: Whether STS processing completed successfully.

    Invariants:
        - duration_ns should be ~6_000_000_000 (6 seconds) +/- 100ms
        - file_path points to valid M4A with AAC audio track
    """
    fragment_id: str
    stream_id: str
    batch_number: int
    t0_ns: int
    duration_ns: int
    file_path: Path
    file_size: int = 0
    dubbed_file_path: Path | None = None
    is_dubbed: bool = False

    @classmethod
    def create(
        cls,
        stream_id: str,
        batch_number: int,
        t0_ns: int,
        duration_ns: int,
        segment_dir: Path,
    ) -> "AudioSegment":
        """Factory method to create an AudioSegment with auto-generated fragment_id."""
        fragment_id = str(uuid4())
        file_path = segment_dir / stream_id / f"{batch_number:06d}_audio.m4a"
        return cls(
            fragment_id=fragment_id,
            stream_id=stream_id,
            batch_number=batch_number,
            t0_ns=t0_ns,
            duration_ns=duration_ns,
            file_path=file_path,
        )

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.duration_ns / 1_000_000_000

    @property
    def exists(self) -> bool:
        """Check if segment file exists on disk."""
        return self.file_path.exists()

    def get_m4a_data(self) -> bytes:
        """Read M4A data from file for STS transport."""
        if not self.exists:
            return b""
        return self.file_path.read_bytes()

    def set_dubbed(self, dubbed_path: Path) -> None:
        """Mark segment as dubbed with path to dubbed file."""
        self.dubbed_file_path = dubbed_path
        self.is_dubbed = True

    @property
    def output_file_path(self) -> Path:
        """Get file path to use for output (dubbed or original)."""
        if self.is_dubbed and self.dubbed_file_path:
            return self.dubbed_file_path
        return self.file_path
```

### StsConfig

Configuration for STS Service API request.

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class StsConfig:
    """Configuration for STS processing.

    Attributes:
        source_language: Language code of the input audio (e.g., "en-US").
        target_language: Language code for dubbing output (e.g., "es-ES").
        voice_id: TTS voice identifier (provider-specific).
        preserve_style: Whether to attempt style preservation (emotion, pace).
        background_mode: How to handle background audio.
    """
    source_language: str = "en-US"
    target_language: str = "es-ES"
    voice_id: str = "default"
    preserve_style: bool = True
    background_mode: Literal["remove", "preserve", "lower"] = "lower"
```

### StsSegmentEvent

Socket.io event payload for sending audio segment to STS service.

```python
from dataclasses import dataclass, field
import base64

@dataclass
class StsSegmentEvent:
    """Socket.io 'audio:segment' event payload for STS Service.

    Audio is sent as M4A file data via Socket.io binary event.
    The STS service processes the segment and responds with 'audio:dubbed' event.

    Attributes:
        fragment_id: UUID from AudioSegment for correlation.
        stream_id: Stream identifier for routing/logging.
        sequence_number: Segment sequence number for ordering.
        m4a_data: M4A audio data (AAC in MP4 container).
        config: STS processing configuration.
        timeout_ms: Maximum processing time before timeout.

    Socket.io Event:
        Event name: 'audio:segment'
        Payload: Binary M4A data + JSON metadata
    """
    fragment_id: str
    stream_id: str
    sequence_number: int
    m4a_data: bytes  # M4A file data
    config: StsConfig = field(default_factory=StsConfig)
    timeout_ms: int = 8000

    @classmethod
    def from_segment(cls, segment: "AudioSegment", config: StsConfig | None = None) -> "StsSegmentEvent":
        """Create StsSegmentEvent from AudioSegment."""
        return cls(
            fragment_id=segment.fragment_id,
            stream_id=segment.stream_id,
            sequence_number=segment.batch_number,
            m4a_data=segment.get_m4a_data(),
            config=config or StsConfig(),
        )

    def to_socketio_payload(self) -> tuple[dict, bytes]:
        """Convert to Socket.io payload (metadata + binary).

        Returns:
            Tuple of (metadata dict, binary M4A data) for socketio.emit().
        """
        metadata = {
            "fragment_id": self.fragment_id,
            "stream_id": self.stream_id,
            "sequence_number": self.sequence_number,
            "config": {
                "source_language": self.config.source_language,
                "target_language": self.config.target_language,
                "voice_id": self.config.voice_id,
                "preserve_style": self.config.preserve_style,
                "background_mode": self.config.background_mode,
            },
            "timeout_ms": self.timeout_ms,
        }
        return metadata, self.m4a_data
```

### StsDubbedEvent

Socket.io event payload received from STS service with dubbed audio.

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class StsDubbedEvent:
    """Socket.io 'audio:dubbed' event payload from STS Service.

    Dubbed audio is received as M4A format (AAC in MP4 container).
    Written to disk for remuxing with corresponding video segment.

    Attributes:
        fragment_id: Matching request UUID for correlation.
        status: Processing result status.
        dubbed_m4a_data: M4A dubbed audio data (AAC in MP4 container).
        transcript: ASR transcript of original audio (optional, for debugging).
        translation: Translated text (optional, for debugging).
        processing_time_ms: Server-side processing time.
        error_message: Error description if status is "error".

    Socket.io Event:
        Event name: 'audio:dubbed'
        Payload: Binary M4A data + JSON metadata
    """
    fragment_id: str
    status: Literal["success", "error", "timeout"]
    dubbed_m4a_data: bytes = b""  # M4A audio data
    transcript: str = ""
    translation: str = ""
    processing_time_ms: int = 0
    error_message: str = ""

    @property
    def is_success(self) -> bool:
        """Check if response indicates successful processing."""
        return self.status == "success" and len(self.dubbed_m4a_data) > 0

    @classmethod
    def from_socketio_payload(cls, metadata: dict, audio_data: bytes) -> "StsDubbedEvent":
        """Create StsDubbedEvent from Socket.io payload."""
        return cls(
            fragment_id=metadata["fragment_id"],
            status=metadata.get("status", "success"),
            dubbed_m4a_data=audio_data,
            transcript=metadata.get("transcript", ""),
            translation=metadata.get("translation", ""),
            processing_time_ms=metadata.get("processing_time_ms", 0),
            error_message=metadata.get("error_message", ""),
        )

    def save_to_file(self, file_path: "Path") -> None:
        """Save dubbed M4A data to file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(self.dubbed_m4a_data)
```

### CircuitBreaker

State machine for STS failure protection.

```python
from dataclasses import dataclass, field
from typing import Literal
import time

CircuitState = Literal["closed", "half_open", "open"]

@dataclass
class CircuitBreaker:
    """Circuit breaker for STS Service protection.

    States:
        - closed: Normal operation, requests pass through.
        - open: Requests blocked, using fallback (original audio).
        - half_open: Testing recovery with probe requests.

    Transitions:
        closed -> open: After failure_threshold consecutive failures.
        open -> half_open: After cooldown_seconds elapsed.
        half_open -> closed: On successful probe.
        half_open -> open: On failed probe.

    Attributes:
        state: Current circuit state.
        failure_count: Consecutive failure count (reset on success).
        last_failure_time: Timestamp of last failure (for cooldown).
        cooldown_seconds: Time before open -> half_open transition.
        failure_threshold: Failures required to open circuit.
    """
    state: CircuitState = "closed"
    failure_count: int = 0
    last_failure_time: float = 0.0
    cooldown_seconds: float = 30.0
    failure_threshold: int = 5

    # Metrics
    total_failures: int = field(default=0, init=False)
    total_fallbacks: int = field(default=0, init=False)

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
        """Record a successful request."""
        if self.state == "half_open":
            self.state = "closed"
        self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
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
```

### AvSyncState

A/V synchronization state tracking.

```python
from dataclasses import dataclass

@dataclass
class AvSyncState:
    """A/V synchronization state.

    Manages PTS offsets for video and audio to maintain synchronization
    despite asynchronous STS processing latency.

    Attributes:
        av_offset_ns: Base offset applied to both video and audio output PTS.
        video_pts_last: Last video PTS pushed to output (for drift detection).
        audio_pts_last: Last audio PTS pushed to output (for drift detection).
        sync_delta_ns: Current measured delta between video and audio.
        drift_threshold_ns: Threshold for triggering drift correction.

    The av_offset_ns creates a buffering window that allows STS processing
    to complete before the corresponding video frame needs to be output.
    Default is 6 seconds for lower latency while accommodating STS processing.
    """
    av_offset_ns: int = 6_000_000_000  # 6 seconds default
    video_pts_last: int = 0
    audio_pts_last: int = 0
    sync_delta_ns: int = 0
    drift_threshold_ns: int = 120_000_000  # 120ms

    @property
    def sync_delta_ms(self) -> float:
        """Current sync delta in milliseconds."""
        return self.sync_delta_ns / 1_000_000

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
            original_pts: Original audio PTS (t0_ns from PcmChunk).

        Returns:
            Adjusted PTS for output pipeline.
        """
        return original_pts + self.av_offset_ns

    def update_sync_state(self, video_pts: int, audio_pts: int) -> None:
        """Update sync state after pushing frames.

        Args:
            video_pts: Last video PTS pushed to output.
            audio_pts: Last audio PTS pushed to output.
        """
        self.video_pts_last = video_pts
        self.audio_pts_last = audio_pts
        self.sync_delta_ns = abs(video_pts - audio_pts)

    def needs_correction(self) -> bool:
        """Check if drift correction is needed."""
        return self.sync_delta_ns > self.drift_threshold_ns
```

### WorkerMetrics

Prometheus metrics container.

```python
from dataclasses import dataclass, field
from prometheus_client import Counter, Gauge, Histogram

@dataclass
class WorkerMetrics:
    """Prometheus metrics for stream worker.

    All metrics include a 'stream_id' label for per-stream monitoring.

    Counters:
        - audio_fragments_total: Total fragments processed
        - fallback_total: Fallback activations (circuit breaker)
        - gst_bus_errors_total: GStreamer pipeline errors

    Gauges:
        - inflight_fragments: Currently processing fragments
        - av_sync_delta_ms: Current A/V sync delta
        - sts_breaker_state: Circuit breaker state (0=closed, 1=half_open, 2=open)

    Histograms:
        - sts_rtt_ms: STS round-trip time distribution
    """
    # Counters
    audio_fragments_total: Counter = field(
        default_factory=lambda: Counter(
            "worker_audio_fragments_total",
            "Total audio fragments processed",
            ["stream_id"],
        )
    )
    fallback_total: Counter = field(
        default_factory=lambda: Counter(
            "worker_fallback_total",
            "Total fallback activations",
            ["stream_id"],
        )
    )
    gst_bus_errors_total: Counter = field(
        default_factory=lambda: Counter(
            "worker_gst_bus_errors_total",
            "GStreamer bus errors",
            ["stream_id", "error_type"],
        )
    )

    # Gauges
    inflight_fragments: Gauge = field(
        default_factory=lambda: Gauge(
            "worker_inflight_fragments",
            "Currently in-flight fragments",
            ["stream_id"],
        )
    )
    av_sync_delta_ms: Gauge = field(
        default_factory=lambda: Gauge(
            "worker_av_sync_delta_ms",
            "Current A/V sync delta in milliseconds",
            ["stream_id"],
        )
    )
    sts_breaker_state: Gauge = field(
        default_factory=lambda: Gauge(
            "worker_sts_breaker_state",
            "Circuit breaker state: 0=closed, 1=half_open, 2=open",
            ["stream_id"],
        )
    )

    # Histograms
    sts_rtt_ms: Histogram = field(
        default_factory=lambda: Histogram(
            "worker_sts_rtt_ms",
            "STS round-trip time in milliseconds",
            ["stream_id"],
            buckets=[50, 100, 250, 500, 1000, 2000, 4000, 8000],
        )
    )
```

## Type Aliases

```python
from typing import Callable, Awaitable

# GStreamer buffer callback signature
BufferCallback = Callable[[bytes, int], None]  # (data, pts_ns) -> None

# Async STS processor signature
StsProcessor = Callable[["PcmChunk"], Awaitable["StsResponse"]]

# Fallback audio provider signature
FallbackProvider = Callable[["PcmChunk"], bytes]  # Returns original PCM
```

## Enumerations

```python
from enum import Enum, auto

class WorkerMode(Enum):
    """Stream worker operating mode."""
    PASSTHROUGH = auto()  # No STS processing, audio passthrough
    ENABLED = auto()      # Full STS processing with dubbing
    FALLBACK = auto()     # STS failed, using original audio

class PipelineState(Enum):
    """GStreamer pipeline state."""
    NULL = auto()
    READY = auto()
    PAUSED = auto()
    PLAYING = auto()
    ERROR = auto()
```

## Validation Functions

```python
def validate_video_segment(segment: VideoSegment) -> list[str]:
    """Validate VideoSegment invariants.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    # Check duration is approximately 6 seconds (+/- 100ms)
    duration_ms = segment.duration_ns / 1_000_000
    if not (5900 <= duration_ms <= 6100):
        # Allow partial segments (minimum 1s)
        if duration_ms < 1000:
            errors.append(f"Duration {duration_ms}ms too short (minimum 1s)")

    # Check fragment_id is valid UUID
    try:
        from uuid import UUID
        UUID(segment.fragment_id)
    except ValueError:
        errors.append(f"Invalid fragment_id: {segment.fragment_id}")

    # Check file exists and is valid MP4
    if segment.exists:
        data = segment.file_path.read_bytes()
        if len(data) < 8 or b'ftyp' not in data[:12]:
            errors.append("Video file does not appear to be valid MP4 format")
    else:
        errors.append(f"Video file not found: {segment.file_path}")

    return errors


def validate_audio_segment(segment: AudioSegment) -> list[str]:
    """Validate AudioSegment invariants.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    # Check duration is approximately 6 seconds (+/- 100ms)
    duration_ms = segment.duration_ns / 1_000_000
    if not (5900 <= duration_ms <= 6100):
        # Allow partial segments (minimum 1s)
        if duration_ms < 1000:
            errors.append(f"Duration {duration_ms}ms too short (minimum 1s)")

    # Check fragment_id is valid UUID
    try:
        from uuid import UUID
        UUID(segment.fragment_id)
    except ValueError:
        errors.append(f"Invalid fragment_id: {segment.fragment_id}")

    # Check file exists and is valid M4A
    if segment.exists:
        data = segment.file_path.read_bytes()
        if len(data) < 8 or b'ftyp' not in data[:12]:
            errors.append("Audio file does not appear to be valid M4A format")
    else:
        errors.append(f"Audio file not found: {segment.file_path}")

    return errors
```

## JSON Schemas

See `contracts/sts-api.json` for complete OpenAPI/JSON Schema definitions of the STS API contract.
