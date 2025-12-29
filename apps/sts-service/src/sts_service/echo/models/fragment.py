"""Pydantic models for audio fragment payloads.

Implements fragment:data, fragment:processed, fragment:ack, and backpressure
messages as defined in spec 016 (WebSocket Audio Fragment Protocol).
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AudioData(BaseModel):
    """Audio data within a fragment.

    Matches spec 016 section 5.1 audio field structure.
    Uses M4A (AAC in MP4 container) as the default audio format.
    """

    format: str = Field(
        default="m4a",
        description="Audio format identifier (m4a = AAC audio in MP4 container)",
    )
    sample_rate_hz: int = Field(
        ge=8000,
        le=96000,
        description="Sample rate in Hz (embedded in M4A container)",
    )
    channels: int = Field(
        ge=1,
        le=2,
        description="Number of audio channels (1=mono, 2=stereo, embedded in M4A)",
    )
    duration_ms: int = Field(
        ge=0,
        le=60000,
        description="Fragment duration in milliseconds",
    )
    data_base64: str = Field(
        description="Base64-encoded M4A audio data",
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


class FragmentMetadata(BaseModel):
    """Optional metadata for a fragment.

    Matches spec 016 section 5.1 metadata field structure.
    """

    pts_ns: int | None = Field(
        default=None,
        description="Presentation timestamp in nanoseconds",
    )
    source_pts_ns: int | None = Field(
        default=None,
        description="Original input PTS in nanoseconds",
    )

    model_config = {"extra": "allow"}


class FragmentDataPayload(BaseModel):
    """Inbound fragment:data event payload.

    Matches spec 016 section 5.1 fragment:data structure.
    """

    fragment_id: str = Field(
        description="Unique fragment ID (UUID)",
    )
    stream_id: str = Field(
        description="Stream identifier",
    )
    sequence_number: int = Field(
        ge=0,
        description="Monotonic sequence number (0-based)",
    )
    timestamp: int = Field(
        description="Unix timestamp in milliseconds",
    )
    audio: AudioData
    metadata: FragmentMetadata | None = None


class StageTimings(BaseModel):
    """Per-stage timing breakdown for processing.

    Echo service uses mock values (all zeros or small values).
    """

    asr_ms: int = Field(default=0, ge=0)
    translation_ms: int = Field(default=0, ge=0)
    tts_ms: int = Field(default=0, ge=0)


class ProcessingMetadata(BaseModel):
    """Metadata about processing.

    Echo service uses mock model names.
    """

    asr_model: str = Field(default="echo-mock")
    translation_model: str = Field(default="echo-mock")
    tts_model: str = Field(default="echo-mock")
    gpu_utilization: float | None = None


class ProcessingError(BaseModel):
    """Error details for failed/partial processing.

    Matches spec 016 section 5.2 error field structure.
    """

    code: str = Field(
        description="Error code from spec 016 section 8.1",
    )
    message: str = Field(
        description="Human-readable error description",
    )
    stage: Literal["asr", "translation", "tts"] | None = Field(
        default=None,
        description="Processing stage that failed",
    )
    retryable: bool = Field(default=False)


class FragmentProcessedPayload(BaseModel):
    """Outbound fragment:processed event payload.

    Matches spec 016 section 5.2 fragment:processed structure.
    """

    fragment_id: str
    stream_id: str
    sequence_number: int = Field(ge=0)
    status: Literal["success", "partial", "failed"]

    # Audio result (present if status != failed)
    dubbed_audio: AudioData | None = None

    # Intermediate results (echo service uses mock values)
    transcript: str | None = None
    translated_text: str | None = None

    # Timing
    processing_time_ms: int = Field(ge=0)
    stage_timings: StageTimings | None = None

    # Error (present if status == failed or partial)
    error: ProcessingError | None = None

    # Metadata
    metadata: ProcessingMetadata | None = None


class FragmentAckPayload(BaseModel):
    """Fragment acknowledgment payload.

    Used for both:
    - STS -> Worker: Immediate ack after receiving fragment (status: queued/processing)
    - Worker -> STS: Confirm receipt of processed fragment (status: received/applied)
    """

    fragment_id: str
    status: Literal["queued", "processing", "received", "applied"]
    timestamp: int | None = None
    queue_position: int | None = None
    estimated_completion_ms: int | None = None


class BackpressurePayload(BaseModel):
    """Backpressure event payload.

    Matches spec 016 section 5.2 backpressure structure.
    """

    stream_id: str
    severity: Literal["low", "medium", "high"] = Field(
        description="Backpressure severity level",
    )
    current_inflight: int = Field(
        ge=0,
        description="Current in-flight fragment count",
    )
    queue_depth: int = Field(
        ge=0,
        description="Current queue depth",
    )
    action: Literal["slow_down", "pause", "none"] = Field(
        description="Recommended worker action",
    )
    recommended_delay_ms: int | None = Field(
        default=None,
        description="Suggested delay before next fragment",
    )
