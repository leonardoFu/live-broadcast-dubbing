"""Pydantic models for Full STS Service.

Defines typed input/output contracts for Socket.IO events and pipeline processing.
Based on specs/021-full-sts-service/spec.md and contracts/*.json.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class PipelineStage(str, Enum):
    """Processing pipeline stages."""

    ASR = "asr"
    TRANSLATION = "translation"
    TTS = "tts"


class ProcessingStatus(str, Enum):
    """Fragment processing status."""

    SUCCESS = "success"  # All stages completed successfully
    PARTIAL = "partial"  # Completed with warnings (e.g., clamped speed ratio)
    FAILED = "failed"  # Processing failed at one or more stages


class StreamState(str, Enum):
    """Stream lifecycle states."""

    INITIALIZING = "initializing"  # stream:init received, setting up
    READY = "ready"  # stream:ready sent, accepting fragments
    PAUSED = "paused"  # stream:pause received, not accepting new fragments
    ENDING = "ending"  # stream:end received, draining in-flight fragments
    COMPLETED = "completed"  # stream:complete sent, session terminated


class BackpressureSeverity(str, Enum):
    """Backpressure severity levels."""

    LOW = "low"  # Normal operation (1-3 in-flight)
    MEDIUM = "medium"  # Slow down recommended (4-6 in-flight)
    HIGH = "high"  # Pause recommended (7-10 in-flight)


class BackpressureAction(str, Enum):
    """Recommended worker actions for backpressure."""

    NONE = "none"  # No action needed
    SLOW_DOWN = "slow_down"  # Increase delay between fragments
    PAUSE = "pause"  # Stop sending fragments


class AckStatus(str, Enum):
    """Fragment acknowledgment status."""

    QUEUED = "queued"  # Fragment queued for processing
    PROCESSING = "processing"  # Fragment being processed
    RECEIVED = "received"  # Worker confirmed receipt
    APPLIED = "applied"  # Worker applied dubbed audio


# -----------------------------------------------------------------------------
# Audio Data Models
# -----------------------------------------------------------------------------


class AudioData(BaseModel):
    """Audio data within a fragment.

    Matches spec 021 fragment-schema.json audio_data definition.
    """

    format: str = Field(
        default="m4a",
        description="Audio format identifier (m4a for input, pcm_s16le for dubbed output)",
    )
    sample_rate_hz: int = Field(
        ge=8000,
        le=96000,
        description="Sample rate in Hz",
    )
    channels: int = Field(
        ge=1,
        le=2,
        description="Number of audio channels (1=mono, 2=stereo)",
    )
    duration_ms: int = Field(
        ge=0,
        le=60000,
        description="Fragment duration in milliseconds",
    )
    data_base64: str = Field(
        description="Base64-encoded audio data",
    )

    @field_validator("data_base64")
    @classmethod
    def validate_base64_size(cls, v: str) -> str:
        """Validate that base64 data doesn't exceed 10MB when decoded."""
        # Base64 encoding increases size by ~33%, so 10MB decoded = ~13.3MB encoded
        max_base64_size = 10 * 1024 * 1024 * 4 // 3 + 4  # Account for padding
        if len(v) > max_base64_size:
            raise ValueError("Audio data exceeds 10MB limit")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "m4a",
                "sample_rate_hz": 48000,
                "channels": 1,
                "duration_ms": 6000,
                "data_base64": "AQIDBAU=",
            }
        }
    )


# -----------------------------------------------------------------------------
# Fragment Event Models
# -----------------------------------------------------------------------------


class FragmentMetadata(BaseModel):
    """Optional metadata for a fragment."""

    pts_ns: int | None = Field(
        default=None,
        description="Presentation timestamp in nanoseconds",
    )
    source_pts_ns: int | None = Field(
        default=None,
        description="Original input PTS in nanoseconds",
    )

    model_config = ConfigDict(extra="allow")


class FragmentDataPayload(BaseModel):
    """Inbound fragment:data event payload from worker.

    Matches spec 021 fragment-schema.json fragment_data definition.
    """

    fragment_id: str = Field(
        description="Unique fragment ID (UUID)",
        min_length=1,
    )
    stream_id: str = Field(
        description="Stream identifier",
        min_length=1,
    )
    sequence_number: int = Field(
        ge=0,
        description="Monotonic sequence number (0-based)",
    )
    timestamp: int = Field(
        ge=0,
        description="Unix timestamp in milliseconds",
    )
    audio: AudioData
    metadata: FragmentMetadata | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
                "stream_id": "stream-abc-123",
                "sequence_number": 0,
                "timestamp": 1704067200000,
                "audio": {
                    "format": "m4a",
                    "sample_rate_hz": 48000,
                    "channels": 1,
                    "duration_ms": 6000,
                    "data_base64": "AQIDBAU=",
                },
            }
        }
    )


class FragmentAckPayload(BaseModel):
    """Fragment acknowledgment payload.

    Matches spec 021 fragment-schema.json fragment_ack definition.
    """

    fragment_id: str = Field(
        min_length=1,
        description="Fragment ID being acknowledged",
    )
    status: AckStatus = Field(
        description="Acknowledgment status",
    )
    timestamp: int = Field(
        ge=0,
        description="Acknowledgment timestamp in milliseconds",
    )
    queue_position: int | None = Field(
        default=None,
        ge=0,
        description="Position in processing queue",
    )
    estimated_completion_ms: int | None = Field(
        default=None,
        ge=0,
        description="Estimated time until processing completes",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "timestamp": 1704067200000,
            }
        }
    )


class StageTiming(BaseModel):
    """Per-stage timing breakdown for processing.

    Matches spec 021 fragment-schema.json stage_timings definition.
    """

    asr_ms: int = Field(default=0, ge=0, description="ASR processing time in ms")
    translation_ms: int = Field(default=0, ge=0, description="Translation time in ms")
    tts_ms: int = Field(default=0, ge=0, description="TTS synthesis time in ms")

    @property
    def total_ms(self) -> int:
        """Total pipeline processing time."""
        return self.asr_ms + self.translation_ms + self.tts_ms


class ProcessingError(BaseModel):
    """Error details for failed/partial processing.

    Matches spec 021 fragment-schema.json processing_error definition.
    """

    stage: PipelineStage = Field(
        description="Pipeline stage where error occurred",
    )
    code: str = Field(
        description="Error code (e.g., TIMEOUT, RATE_LIMIT_EXCEEDED)",
    )
    message: str = Field(
        description="Human-readable error description",
    )
    retryable: bool = Field(
        default=False,
        description="Whether the error is transient and retryable",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stage": "asr",
                "code": "TIMEOUT",
                "message": "ASR processing timed out after 5000ms",
                "retryable": True,
            }
        }
    )


class DurationMetadata(BaseModel):
    """Duration matching metadata for A/V sync.

    Matches spec 021 fragment-schema.json duration_metadata definition.
    """

    original_duration_ms: int = Field(
        ge=0,
        description="Original fragment duration in ms",
    )
    dubbed_duration_ms: int = Field(
        ge=0,
        description="Dubbed audio duration in ms",
    )
    duration_variance_percent: float = Field(
        ge=0,
        description="Variance between original and dubbed duration as percentage",
    )
    speed_ratio: float = Field(
        ge=0.5,
        le=2.0,
        description="Speed ratio applied for duration matching",
    )


class FragmentProcessedPayload(BaseModel):
    """Outbound fragment:processed event payload.

    Matches spec 021 fragment-schema.json fragment_processed definition.
    """

    fragment_id: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    sequence_number: int = Field(ge=0)
    status: ProcessingStatus

    # Audio result (present if status != failed)
    dubbed_audio: AudioData | None = None

    # Intermediate results (for debugging/logging)
    transcript: str | None = None
    translated_text: str | None = None

    # Timing
    processing_time_ms: int = Field(ge=0)
    stage_timings: StageTiming | None = None

    # Error (present if status == failed or partial)
    error: ProcessingError | None = None

    # Metadata
    metadata: DurationMetadata | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
                "stream_id": "stream-abc-123",
                "sequence_number": 0,
                "status": "success",
                "dubbed_audio": {
                    "format": "pcm_s16le",
                    "sample_rate_hz": 48000,
                    "channels": 1,
                    "duration_ms": 6050,
                    "data_base64": "AQIDBAU=",
                },
                "transcript": "Hello, welcome to the game.",
                "translated_text": "Hola, bienvenido al juego.",
                "processing_time_ms": 4500,
                "stage_timings": {
                    "asr_ms": 1200,
                    "translation_ms": 150,
                    "tts_ms": 3100,
                },
            }
        }
    )


# -----------------------------------------------------------------------------
# Stream Event Models
# -----------------------------------------------------------------------------


class StreamConfig(BaseModel):
    """Stream configuration from worker.

    Matches spec 021 stream-schema.json stream_config definition.
    """

    source_language: str = Field(
        default="en",
        min_length=2,
        max_length=10,
        description="Source language code (e.g., 'en')",
    )
    target_language: str = Field(
        default="es",
        min_length=2,
        max_length=10,
        description="Target language code (e.g., 'es')",
    )
    voice_profile: str = Field(
        default="default",
        min_length=1,
        description="TTS voice identifier from voices.json",
    )
    chunk_duration_ms: int = Field(
        default=6000,
        ge=100,
        le=10000,
        description="Expected fragment duration in milliseconds",
    )
    sample_rate_hz: int = Field(
        default=48000,
        ge=8000,
        le=96000,
        description="Audio sample rate in Hz",
    )
    channels: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Audio channels (1=mono, 2=stereo)",
    )
    format: str = Field(
        default="m4a",
        description="Audio format identifier",
    )
    domain_hints: list[str] | None = Field(
        default=None,
        description="Optional domain hints for vocabulary priming",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_language": "en",
                "target_language": "es",
                "voice_profile": "spanish_male_1",
                "chunk_duration_ms": 6000,
                "sample_rate_hz": 48000,
                "channels": 1,
                "format": "m4a",
                "domain_hints": ["sports", "general"],
            }
        }
    )


class StreamInitPayload(BaseModel):
    """stream:init event payload from worker.

    Matches spec 021 stream-schema.json stream_init definition.
    """

    stream_id: str = Field(min_length=1, description="Unique stream identifier")
    worker_id: str = Field(min_length=1, description="Worker instance identifier")
    config: StreamConfig
    max_inflight: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max concurrent fragments in flight",
    )
    timeout_ms: int = Field(
        default=8000,
        ge=1000,
        le=30000,
        description="Per-fragment timeout in milliseconds",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc-123",
                "worker_id": "worker-001",
                "config": {
                    "source_language": "en",
                    "target_language": "es",
                    "voice_profile": "spanish_male_1",
                    "chunk_duration_ms": 6000,
                    "sample_rate_hz": 48000,
                    "channels": 1,
                    "format": "m4a",
                },
            }
        }
    )


class StreamReadyPayload(BaseModel):
    """stream:ready event payload from STS service.

    Matches spec 021 stream-schema.json stream_ready definition.
    """

    stream_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1, description="Server-assigned session ID")
    max_inflight: int = Field(
        ge=1,
        le=10,
        description="Confirmed max concurrent fragments",
    )
    capabilities: list[str] = Field(
        default_factory=lambda: ["asr", "translation", "tts", "duration_matching"],
        description="Server capabilities",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc-123",
                "session_id": "session-xyz-789",
                "max_inflight": 3,
                "capabilities": ["asr", "translation", "tts", "duration_matching"],
            }
        }
    )


class StreamPausePayload(BaseModel):
    """stream:pause event payload.

    Matches spec 021 stream-schema.json stream_pause definition.
    """

    stream_id: str = Field(min_length=1)
    reason: str | None = Field(
        default=None,
        description="Optional reason for pause (e.g., 'backpressure')",
    )


class StreamResumePayload(BaseModel):
    """stream:resume event payload.

    Matches spec 021 stream-schema.json stream_resume definition.
    """

    stream_id: str = Field(min_length=1)


class StreamEndPayload(BaseModel):
    """stream:end event payload.

    Matches spec 021 stream-schema.json stream_end definition.
    """

    stream_id: str = Field(min_length=1)
    reason: str | None = Field(
        default=None,
        description="Optional reason for ending (e.g., 'source_ended')",
    )


class ErrorBreakdown(BaseModel):
    """Error breakdown by stage and code."""

    by_stage: dict[str, int] = Field(
        default_factory=dict,
        description="Error count by pipeline stage",
    )
    by_code: dict[str, int] = Field(
        default_factory=dict,
        description="Error count by error code",
    )


class StreamCompletePayload(BaseModel):
    """stream:complete event payload from STS service.

    Matches spec 021 stream-schema.json stream_complete definition.
    """

    stream_id: str = Field(min_length=1)
    total_fragments: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    avg_processing_time_ms: float = Field(ge=0)
    error_breakdown: ErrorBreakdown | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc-123",
                "total_fragments": 50,
                "success_count": 45,
                "failed_count": 5,
                "avg_processing_time_ms": 4500,
            }
        }
    )


# -----------------------------------------------------------------------------
# Backpressure Model
# -----------------------------------------------------------------------------


class BackpressurePayload(BaseModel):
    """Backpressure event payload.

    Matches spec 021 backpressure-schema.json backpressure definition.
    """

    stream_id: str = Field(min_length=1)
    severity: BackpressureSeverity
    action: BackpressureAction
    current_inflight: int = Field(ge=0)
    max_inflight: int = Field(ge=1, le=10)
    threshold_exceeded: Literal["low", "medium", "high"] | None = None
    recommended_delay_ms: int | None = Field(
        default=None,
        ge=0,
        description="Suggested delay before next fragment submission",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc-123",
                "severity": "medium",
                "action": "slow_down",
                "current_inflight": 5,
                "max_inflight": 3,
                "threshold_exceeded": "medium",
                "recommended_delay_ms": 500,
            }
        }
    )


# -----------------------------------------------------------------------------
# Error Response Model
# -----------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Error response payload.

    Matches spec 021 error-schema.json error_response definition.
    """

    code: str = Field(description="Error code identifier")
    message: str = Field(min_length=1, description="Human-readable error description")
    retryable: bool = Field(description="Whether the error is transient and retryable")
    stage: PipelineStage | None = Field(
        default=None,
        description="Pipeline stage where error occurred (optional)",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "STREAM_NOT_FOUND",
                "message": "Stream stream-abc-123 not found",
                "retryable": False,
            }
        }
    )


# -----------------------------------------------------------------------------
# Session State Model
# -----------------------------------------------------------------------------


class SessionInfo(BaseModel):
    """Runtime session information for a stream.

    Tracks stream state, configuration, and statistics.
    """

    stream_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1)
    socket_id: str = Field(min_length=1, description="Socket.IO socket ID")

    # Configuration
    config: StreamConfig
    max_inflight: int = Field(default=3, ge=1, le=10)
    timeout_ms: int = Field(default=8000, ge=1000, le=30000)

    # State
    state: StreamState = Field(default=StreamState.INITIALIZING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)

    # Statistics (updated during processing)
    fragments_received: int = Field(default=0, ge=0)
    fragments_processed: int = Field(default=0, ge=0)
    fragments_failed: int = Field(default=0, ge=0)
    current_inflight: int = Field(default=0, ge=0)
    total_processing_time_ms: int = Field(default=0, ge=0)

    # In-flight tracking
    inflight_fragment_ids: set[str] = Field(default_factory=set)

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.utcnow()

    @property
    def avg_processing_time_ms(self) -> float:
        """Average processing time per fragment."""
        if self.fragments_processed == 0:
            return 0.0
        return self.total_processing_time_ms / self.fragments_processed

    model_config = ConfigDict(arbitrary_types_allowed=True)
