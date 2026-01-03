"""Stream lifecycle models for Full STS Service.

Defines typed models for stream lifecycle events per spec 021:
- stream:init, stream:ready, stream:pause, stream:resume, stream:end, stream:complete.

Matches contracts/stream-schema.json.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StreamState(str, Enum):
    """Stream lifecycle states."""

    INITIALIZING = "initializing"  # stream:init received, setting up
    READY = "ready"  # stream:ready sent, accepting fragments
    PAUSED = "paused"  # stream:pause received, not accepting new fragments
    ENDING = "ending"  # stream:end received, draining in-flight fragments
    COMPLETED = "completed"  # stream:complete sent, session terminated


class StreamConfig(BaseModel):
    """Stream configuration from worker.

    Matches spec 021 stream-schema.json stream_config definition.
    """

    source_language: str = Field(
        default="en",
        min_length=2,
        max_length=10,
        description="Source language code (e.g., 'en', 'es', 'fr')",
    )
    target_language: str = Field(
        default="es",
        min_length=2,
        max_length=10,
        description="Target language code",
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
        description="Audio format identifier (m4a, pcm_s16le, wav)",
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


class StreamStatistics(BaseModel):
    """Statistics for a completed stream."""

    total_fragments: int = Field(ge=0, description="Total fragments processed")
    success_count: int = Field(ge=0, description="Successfully processed fragments")
    partial_count: int = Field(ge=0, description="Partially processed fragments")
    failed_count: int = Field(ge=0, description="Failed fragments")
    avg_processing_time_ms: float = Field(ge=0, description="Average processing time")
    p95_processing_time_ms: float = Field(ge=0, description="95th percentile processing time")
    total_audio_duration_ms: int = Field(default=0, ge=0, description="Total audio duration processed")

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_fragments == 0:
            return 0.0
        return (self.success_count / self.total_fragments) * 100

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_fragments": 50,
                "success_count": 45,
                "partial_count": 3,
                "failed_count": 2,
                "avg_processing_time_ms": 4500,
                "p95_processing_time_ms": 6200,
                "total_audio_duration_ms": 300000,
            }
        }
    )


# Event Payloads


class ServerCapabilities(BaseModel):
    """Server capabilities advertised in stream:ready."""

    batch_processing: bool = Field(
        default=False,
        description="Whether server supports batch fragment processing",
    )
    async_delivery: bool = Field(
        default=True,
        description="Whether server delivers results asynchronously (out of order)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_processing": False,
                "async_delivery": True,
            }
        }
    )


class StreamInitPayload(BaseModel):
    """Inbound stream:init event payload from worker.

    Matches spec 021 stream-schema.json stream_init definition.
    """

    stream_id: str = Field(min_length=1, description="Unique stream identifier")
    worker_id: str = Field(min_length=1, description="Worker instance identifier")
    config: StreamConfig
    max_inflight: int = Field(default=3, ge=1, le=10, description="Maximum concurrent fragments")
    timeout_ms: int = Field(default=8000, ge=1000, le=30000, description="Processing timeout in ms")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc-123",
                "worker_id": "worker-001",
                "config": {
                    "source_language": "en",
                    "target_language": "es",
                    "voice_profile": "spanish_male_1",
                },
                "max_inflight": 3,
                "timeout_ms": 8000,
            }
        }
    )


class StreamReadyPayload(BaseModel):
    """Outbound stream:ready event payload to worker.

    Matches spec 021 stream-schema.json stream_ready definition.
    """

    stream_id: str = Field(min_length=1, description="Stream identifier")
    session_id: str = Field(min_length=1, description="Server-assigned session ID")
    max_inflight: int = Field(ge=1, le=10, description="Confirmed max concurrent fragments")
    capabilities: ServerCapabilities

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc-123",
                "session_id": "session-xyz-789",
                "max_inflight": 3,
                "capabilities": {
                    "batch_processing": False,
                    "async_delivery": True,
                },
            }
        }
    )


class StreamCompletePayload(BaseModel):
    """Outbound stream:complete event payload to worker.

    Matches spec 021 stream-schema.json stream_complete definition.
    """

    stream_id: str = Field(min_length=1, description="Stream identifier")
    total_fragments: int = Field(ge=0, description="Total fragments processed")
    total_duration_ms: int = Field(ge=0, description="Total stream duration in milliseconds")
    statistics: StreamStatistics

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc-123",
                "total_fragments": 50,
                "total_duration_ms": 300000,
                "statistics": {
                    "total_fragments": 50,
                    "success_count": 45,
                    "partial_count": 3,
                    "failed_count": 2,
                    "avg_processing_time_ms": 4500,
                    "p95_processing_time_ms": 6200,
                },
            }
        }
    )
