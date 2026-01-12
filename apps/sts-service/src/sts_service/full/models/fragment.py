"""Fragment processing models for Full STS Service.

Defines typed models for fragment events per spec 021:
- fragment:data (inbound audio fragments)
- fragment:ack (acknowledgments)
- fragment:processed (processing results)

Matches contracts/fragment-schema.json.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProcessingStatus(str, Enum):
    """Fragment processing result status."""

    SUCCESS = "success"  # All stages completed successfully
    PARTIAL = "partial"  # Completed with warnings (e.g., clamped speed ratio)
    FAILED = "failed"  # Processing failed at one or more stages


class AckStatus(str, Enum):
    """Fragment acknowledgment status."""

    QUEUED = "queued"  # Fragment queued for processing
    PROCESSING = "processing"  # Fragment being processed
    RECEIVED = "received"  # Worker confirmed receipt
    APPLIED = "applied"  # Worker applied dubbed audio


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
        min_length=1,
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "asr_ms": 1200,
                "translation_ms": 150,
                "tts_ms": 3100,
            }
        }
    )


class DurationMetadata(BaseModel):
    """Duration matching metadata for A/V sync.

    Matches spec 021 fragment-schema.json duration_metadata definition.
    """

    original_duration_ms: int = Field(
        ge=0,
        description="Original fragment duration in milliseconds",
    )
    dubbed_duration_ms: int = Field(
        ge=0,
        description="Dubbed audio duration in milliseconds",
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

    @property
    def is_within_threshold(self) -> bool:
        """Check if duration variance is within 20% threshold."""
        return self.duration_variance_percent <= 20.0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "original_duration_ms": 6000,
                "dubbed_duration_ms": 6050,
                "duration_variance_percent": 0.83,
                "speed_ratio": 0.99,
            }
        }
    )


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


class FragmentData(BaseModel):
    """Inbound fragment:data event payload from worker.

    Matches spec 021 fragment-schema.json fragment_data definition.
    """

    fragment_id: str = Field(
        min_length=1,
        description="Unique fragment ID (UUID)",
    )
    stream_id: str = Field(
        min_length=1,
        description="Stream identifier",
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


class FragmentAck(BaseModel):
    """Fragment acknowledgment payload.

    Matches spec 021 fragment-schema.json fragment_ack definition.
    """

    fragment_id: str = Field(
        min_length=1,
        description="Fragment ID being acknowledged",
    )
    status: AckStatus
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


class ProcessingError(BaseModel):
    """Error details for failed/partial processing.

    Matches spec 021 fragment-schema.json processing_error definition.
    """

    stage: str = Field(
        description="Pipeline stage where error occurred (asr, translation, tts)",
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


class FragmentResult(BaseModel):
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

    # Duration metadata
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
