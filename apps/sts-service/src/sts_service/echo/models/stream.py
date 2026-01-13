"""Pydantic models for stream lifecycle payloads.

Implements stream:init, stream:ready, stream:pause, stream:resume, stream:end,
and stream:complete messages as defined in spec 016.
"""

from pydantic import BaseModel, Field


class StreamConfigPayload(BaseModel):
    """Stream configuration from worker.

    Part of stream:init payload, matches spec 016 section 5.1.

    Updated for spec 021-fragment-length-30s:
    - chunk_duration_ms max increased from 6000 to 30000 (FR-004)
    """

    source_language: str = Field(
        default="zh",
        description="Source language code (e.g., 'zh')",
    )
    target_language: str = Field(
        default="en-us",
        description="Target language code (e.g., 'en-us')",
    )
    voice_profile: str = Field(
        default="default",
        description="TTS voice identifier",
    )
    chunk_duration_ms: int = Field(
        default=30000,  # spec 021: default changed from 1000 to 30000
        ge=100,
        le=30000,  # spec 021: max increased from 6000 to 30000 (FR-004)
        description="Expected fragment duration in milliseconds",
    )
    sample_rate_hz: int = Field(
        default=48000,
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
        description="Audio format identifier (m4a = AAC audio in MP4 container)",
    )


class StreamInitPayload(BaseModel):
    """stream:init event payload.

    Matches spec 016 section 5.1 stream:init structure.
    Sent by worker to initialize a streaming session.

    Updated for spec 021-fragment-length-30s:
    - timeout_ms default increased from 8000 to 60000 (FR-006)
    - timeout_ms max increased from 30000 to 120000 (FR-006)
    """

    stream_id: str = Field(
        description="Unique stream identifier",
    )
    worker_id: str = Field(
        description="Worker instance identifier",
    )
    config: StreamConfigPayload
    max_inflight: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max concurrent fragments in flight",
    )
    timeout_ms: int = Field(
        default=60000,  # spec 021: increased from 8000 to 60000 (FR-006)
        ge=1000,
        le=120000,  # spec 021: increased from 30000 to 120000 (FR-006)
        description="Per-fragment timeout in milliseconds",
    )


class ServerCapabilities(BaseModel):
    """Server capabilities advertised on stream:ready.

    Echo service does not batch, but supports async delivery.
    """

    batch_processing: bool = Field(
        default=False,
        description="Whether server supports batch processing",
    )
    async_delivery: bool = Field(
        default=True,
        description="Whether server supports async fragment delivery",
    )


class StreamReadyPayload(BaseModel):
    """stream:ready event payload.

    Matches spec 016 section 5.2 stream:ready structure.
    Sent by STS to confirm stream initialization.
    """

    stream_id: str
    session_id: str = Field(
        description="Server-assigned session ID",
    )
    max_inflight: int = Field(
        description="Confirmed max concurrent fragments",
    )
    capabilities: ServerCapabilities = Field(
        default_factory=ServerCapabilities,
    )


class StreamPausePayload(BaseModel):
    """stream:pause event payload.

    Matches spec 016 section 5.1 stream:pause structure.
    """

    stream_id: str
    reason: str | None = Field(
        default=None,
        description="Optional reason for pause (e.g., 'backpressure')",
    )


class StreamResumePayload(BaseModel):
    """stream:resume event payload.

    Matches spec 016 section 5.1 stream:resume structure.
    """

    stream_id: str


class StreamEndPayload(BaseModel):
    """stream:end event payload.

    Matches spec 016 section 5.1 stream:end structure.
    """

    stream_id: str
    reason: str | None = Field(
        default=None,
        description="Optional reason for ending (e.g., 'source_ended')",
    )


class StreamStatistics(BaseModel):
    """Statistics returned on stream completion.

    Matches spec 016 section 5.2 stream:complete statistics.
    """

    success_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    avg_processing_time_ms: float = Field(ge=0)
    p95_processing_time_ms: float = Field(ge=0)


class StreamCompletePayload(BaseModel):
    """stream:complete event payload.

    Matches spec 016 section 5.2 stream:complete structure.
    Sent by STS when all fragments are processed after stream:end.
    """

    stream_id: str
    total_fragments: int = Field(ge=0)
    total_duration_ms: int = Field(ge=0)
    statistics: StreamStatistics
