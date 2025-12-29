# Data Model: Echo STS Service

**Feature**: 017-echo-sts-service
**Date**: 2025-12-28
**Status**: Draft

## Overview

This document defines the data entities for the Echo STS Service. All models are implemented as Pydantic v2 models for runtime validation and type safety.

---

## Entity: StreamSession

Represents an active streaming session with a connected worker.

### Definition

```python
from dataclasses import dataclass, field
from typing import Optional, Literal
from asyncio import Queue
from datetime import datetime
import uuid

SessionState = Literal["initializing", "active", "paused", "ending", "completed"]

@dataclass
class StreamSession:
    """Per-stream session state managed by the echo service."""

    # Identity
    sid: str                          # Socket.IO session ID
    stream_id: str                    # Client-provided stream ID
    worker_id: str                    # Client-provided worker ID
    session_id: str = field(          # Server-assigned session ID
        default_factory=lambda: str(uuid.uuid4())
    )

    # State
    state: SessionState = "initializing"
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Configuration (from stream:init)
    source_language: str = "en"
    target_language: str = "es"
    voice_profile: str = "default"
    chunk_duration_ms: int = 1000
    sample_rate_hz: int = 48000
    channels: int = 1
    format: str = "pcm_s16le"
    max_inflight: int = 3
    timeout_ms: int = 8000

    # Flow control
    inflight_count: int = 0
    next_sequence_to_emit: int = 0
    pending_fragments: dict = field(default_factory=dict)

    # Backpressure
    backpressure_enabled: bool = False
    backpressure_threshold: int = 5
    backpressure_active: bool = False

    # Error simulation
    error_simulation: Optional["ErrorSimulationConfig"] = None

    # Processing delay (for testing latency)
    processing_delay_ms: int = 0

    # Statistics
    statistics: "SessionStatistics" = field(
        default_factory=lambda: SessionStatistics()
    )

@dataclass
class SessionStatistics:
    """Statistics tracked per session."""
    total_fragments: int = 0
    success_count: int = 0
    partial_count: int = 0
    failed_count: int = 0
    total_processing_time_ms: int = 0

    @property
    def avg_processing_time_ms(self) -> float:
        if self.total_fragments == 0:
            return 0.0
        return self.total_processing_time_ms / self.total_fragments
```

### Relationships

- One StreamSession per Socket.IO connection
- Contains multiple pending Fragment records (in-flight)
- May have one ErrorSimulationConfig

### Validation Rules

- `stream_id`: Required, non-empty string
- `max_inflight`: Range 1-10
- `timeout_ms`: Range 1000-30000
- `sample_rate_hz`: Must be one of [16000, 22050, 44100, 48000]
- `channels`: Must be 1 or 2

### State Transitions

```
initializing -> active     (on stream:ready sent)
active -> paused           (on stream:pause received)
paused -> active           (on stream:resume received)
active -> ending           (on stream:end received)
paused -> ending           (on stream:end received)
ending -> completed        (when all in-flight fragments processed)
```

---

## Entity: Fragment

Represents an audio fragment in transit.

### Inbound: FragmentDataPayload

```python
from pydantic import BaseModel, Field
from typing import Optional, Any

class AudioData(BaseModel):
    """Audio data within a fragment."""
    format: str = Field(description="Audio format, e.g., pcm_s16le")
    sample_rate_hz: int = Field(ge=8000, le=96000, description="Sample rate in Hz")
    channels: int = Field(ge=1, le=2, description="Number of audio channels")
    duration_ms: int = Field(ge=0, le=60000, description="Fragment duration in ms")
    data_base64: str = Field(description="Base64-encoded audio data")

class FragmentMetadata(BaseModel):
    """Optional metadata for a fragment."""
    pts_ns: Optional[int] = Field(None, description="Presentation timestamp in nanoseconds")
    source_pts_ns: Optional[int] = Field(None, description="Original input PTS")
    # Allow additional metadata
    model_config = {"extra": "allow"}

class FragmentDataPayload(BaseModel):
    """Inbound fragment:data event payload (spec 016 section 5.1)."""
    fragment_id: str = Field(description="Unique fragment ID (UUID)")
    stream_id: str = Field(description="Stream identifier")
    sequence_number: int = Field(ge=0, description="Monotonic sequence number")
    timestamp: int = Field(description="Unix timestamp in milliseconds")
    audio: AudioData
    metadata: Optional[FragmentMetadata] = None
```

### Outbound: FragmentProcessedPayload

```python
class ProcessingError(BaseModel):
    """Error details for failed/partial processing."""
    code: str = Field(description="Error code from spec 016 section 8.1")
    message: str = Field(description="Human-readable error description")
    stage: Optional[str] = Field(None, description="asr, translation, or tts")
    retryable: bool = Field(default=False)

class ProcessingMetadata(BaseModel):
    """Metadata about processing (echo service uses mock values)."""
    asr_model: str = "echo-mock"
    translation_model: str = "echo-mock"
    tts_model: str = "echo-mock"
    gpu_utilization: Optional[float] = None

class StageTimings(BaseModel):
    """Per-stage timing breakdown."""
    asr_ms: int = 0
    translation_ms: int = 0
    tts_ms: int = 0

class FragmentProcessedPayload(BaseModel):
    """Outbound fragment:processed event payload (spec 016 section 5.2)."""
    fragment_id: str
    stream_id: str
    sequence_number: int
    status: str = Field(description="success, partial, or failed")

    # Audio result (present if status != failed)
    dubbed_audio: Optional[AudioData] = None

    # Intermediate results
    transcript: Optional[str] = None
    translated_text: Optional[str] = None

    # Timing
    processing_time_ms: int = Field(ge=0)
    stage_timings: Optional[StageTimings] = None

    # Error (present if status == failed or partial)
    error: Optional[ProcessingError] = None

    # Metadata
    metadata: Optional[ProcessingMetadata] = None
```

### Validation Rules

- `fragment_id`: Must be valid UUID format
- `sequence_number`: Non-negative, gaps trigger INVALID_SEQUENCE error
- `audio.data_base64`: Max 10MB when decoded (FRAGMENT_TOO_LARGE error)
- `status`: Must be one of ["success", "partial", "failed"]

---

## Entity: ErrorSimulationConfig

Configures error simulation for testing.

### Definition

```python
from pydantic import BaseModel, Field
from typing import Literal, Union

class ErrorSimulationRule(BaseModel):
    """Single error simulation rule."""
    trigger: Literal["sequence_number", "fragment_id", "nth_fragment"] = Field(
        description="How to match fragments for error injection"
    )
    value: Union[int, str] = Field(
        description="Trigger value: sequence number, fragment ID, or N for nth fragment"
    )
    error_code: str = Field(
        description="Error code from spec 016: TIMEOUT, MODEL_ERROR, GPU_OOM, etc."
    )
    error_message: str = Field(
        default="Simulated error",
        description="Human-readable error message"
    )
    retryable: bool = Field(
        default=True,
        description="Whether the error is retryable"
    )
    stage: Optional[str] = Field(
        default=None,
        description="Processing stage that failed: asr, translation, tts"
    )

class ErrorSimulationConfig(BaseModel):
    """Error simulation configuration sent via config:error_simulation."""
    enabled: bool = Field(default=False, description="Enable error simulation")
    rules: list[ErrorSimulationRule] = Field(
        default_factory=list,
        description="List of error simulation rules"
    )
```

### Supported Error Codes (from spec 016)

| Code | Retryable | Description |
|------|-----------|-------------|
| AUTH_FAILED | No | Invalid API key (connection-level) |
| STREAM_NOT_FOUND | No | Unknown stream_id |
| INVALID_CONFIG | No | Invalid stream:init config |
| FRAGMENT_TOO_LARGE | No | Fragment exceeds 10MB |
| TIMEOUT | Yes | Processing timeout |
| MODEL_ERROR | Yes | ASR/MT/TTS model failure |
| GPU_OOM | Yes | Out of GPU memory |
| QUEUE_FULL | Yes | Processing queue full |
| INVALID_SEQUENCE | No | Sequence number gap |
| RATE_LIMIT | Yes | Too many requests |

---

## Entity: BackpressureState

Tracks backpressure state for flow control.

### Definition

```python
class BackpressurePayload(BaseModel):
    """Backpressure event payload (spec 016 section 5.2)."""
    stream_id: str
    severity: Literal["low", "medium", "high"] = Field(
        description="Backpressure severity level"
    )
    current_inflight: int = Field(ge=0, description="Current in-flight fragment count")
    queue_depth: int = Field(ge=0, description="Current queue depth")
    action: Literal["slow_down", "pause", "none"] = Field(
        description="Recommended worker action"
    )
    recommended_delay_ms: Optional[int] = Field(
        None,
        description="Suggested delay before next fragment"
    )
```

### Thresholds (configurable)

| Severity | Threshold (% of max_inflight) | Action |
|----------|------------------------------|--------|
| low | 50% | none |
| medium | 70% | slow_down |
| high | 90% | pause |

---

## Entity: StreamEvents

Stream lifecycle event payloads.

### stream:init (Worker -> STS)

```python
class StreamConfigPayload(BaseModel):
    """Stream configuration from worker."""
    source_language: str = Field(default="en", description="Source language code")
    target_language: str = Field(default="es", description="Target language code")
    voice_profile: str = Field(default="default", description="TTS voice identifier")
    chunk_duration_ms: int = Field(default=1000, ge=100, le=5000)
    sample_rate_hz: int = Field(default=48000)
    channels: int = Field(default=1, ge=1, le=2)
    format: str = Field(default="pcm_s16le")

class StreamInitPayload(BaseModel):
    """stream:init event payload (spec 016 section 5.1)."""
    stream_id: str = Field(description="Unique stream identifier")
    worker_id: str = Field(description="Worker instance identifier")
    config: StreamConfigPayload
    max_inflight: int = Field(default=3, ge=1, le=10)
    timeout_ms: int = Field(default=8000, ge=1000, le=30000)
```

### stream:ready (STS -> Worker)

```python
class ServerCapabilities(BaseModel):
    """Server capabilities advertised on stream:ready."""
    batch_processing: bool = False  # Echo service doesn't batch
    async_delivery: bool = True

class StreamReadyPayload(BaseModel):
    """stream:ready event payload (spec 016 section 5.2)."""
    stream_id: str
    session_id: str = Field(description="Server-assigned session ID")
    max_inflight: int = Field(description="Confirmed max concurrent fragments")
    capabilities: ServerCapabilities
```

### stream:complete (STS -> Worker)

```python
class StreamStatistics(BaseModel):
    """Statistics returned on stream completion."""
    success_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    avg_processing_time_ms: float = Field(ge=0)
    p95_processing_time_ms: float = Field(ge=0)

class StreamCompletePayload(BaseModel):
    """stream:complete event payload (spec 016 section 5.2)."""
    stream_id: str
    total_fragments: int = Field(ge=0)
    total_duration_ms: int = Field(ge=0)
    statistics: StreamStatistics
```

---

## Entity: ErrorPayload

General error event payload.

```python
class ErrorPayload(BaseModel):
    """error event payload (spec 016 section 5.2)."""
    error_id: Optional[str] = Field(None, description="Unique error identifier")
    stream_id: Optional[str] = None
    fragment_id: Optional[str] = None
    code: str = Field(description="Error code from spec 016 section 8.1")
    message: str = Field(description="Human-readable description")
    severity: Literal["warning", "error", "fatal"] = Field(default="error")
    retryable: bool = Field(default=False)
    metadata: Optional[dict] = None
```

---

## Session Store

In-memory session management.

```python
from typing import Optional

class SessionStore:
    """Thread-safe in-memory session store."""

    def __init__(self):
        self._sessions: dict[str, StreamSession] = {}  # sid -> session
        self._stream_to_sid: dict[str, str] = {}       # stream_id -> sid

    async def create(self, sid: str, stream_id: str, worker_id: str) -> StreamSession:
        """Create a new session."""
        session = StreamSession(sid=sid, stream_id=stream_id, worker_id=worker_id)
        self._sessions[sid] = session
        self._stream_to_sid[stream_id] = sid
        return session

    async def get_by_sid(self, sid: str) -> Optional[StreamSession]:
        """Get session by Socket.IO session ID."""
        return self._sessions.get(sid)

    async def get_by_stream_id(self, stream_id: str) -> Optional[StreamSession]:
        """Get session by stream ID."""
        sid = self._stream_to_sid.get(stream_id)
        return self._sessions.get(sid) if sid else None

    async def delete(self, sid: str) -> None:
        """Delete session."""
        session = self._sessions.pop(sid, None)
        if session:
            self._stream_to_sid.pop(session.stream_id, None)

    def count(self) -> int:
        """Return number of active sessions."""
        return len(self._sessions)
```

---

## Summary

| Entity | Purpose | Storage |
|--------|---------|---------|
| StreamSession | Per-connection state | In-memory dict |
| Fragment (Data/Processed) | Audio fragment payloads | Transient |
| ErrorSimulationConfig | Test error injection | Per-session |
| BackpressureState | Flow control | Per-session |
| StreamEvents | Lifecycle payloads | Transient |
| ErrorPayload | Error responses | Transient |
| SessionStore | Session management | In-memory singleton |
