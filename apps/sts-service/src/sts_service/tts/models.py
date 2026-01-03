"""
Pydantic data models for the TTS component.

Defines typed input/output contracts for text-to-speech synthesis.
Based on specs/008-tts-module/data-model.md.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

# Import AssetIdentifiers from ASR module for lineage tracking
from sts_service.asr.models import AssetIdentifiers

from .errors import TTSError

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class AudioFormat(str, Enum):
    """Supported audio formats for synthesis output."""

    PCM_F32LE = "pcm_f32le"  # 32-bit float little-endian (preferred)
    PCM_S16LE = "pcm_s16le"  # 16-bit signed integer little-endian
    M4A_AAC = "m4a_aac"  # M4A container with AAC codec (compressed)


class AudioStatus(str, Enum):
    """Status of audio synthesis."""

    SUCCESS = "success"  # Synthesis completed successfully
    PARTIAL = "partial"  # Synthesis completed with warnings (e.g., clamped speed)
    FAILED = "failed"  # Synthesis failed completely


# Allowed sample rates
ALLOWED_SAMPLE_RATES = [8000, 16000, 22050, 24000, 44100, 48000]

# Allowed channel counts
ALLOWED_CHANNELS = [1, 2]


# -----------------------------------------------------------------------------
# Configuration Models
# -----------------------------------------------------------------------------


class VoiceProfile(BaseModel):
    """Configuration for voice selection and synthesis parameters.

    This entity is used as input configuration, not persisted as an asset.
    """

    language: str = Field(..., description="Target language (ISO 639-1)")
    model_name: str | None = Field(
        default=None, description="Explicit model override"
    )
    fast_mode: bool = Field(
        default=False, description="Use fast model for low latency"
    )
    voice_sample_path: str | None = Field(
        default=None, description="Path to voice cloning sample"
    )
    speaker_name: str | None = Field(
        default=None, description="Named speaker fallback"
    )
    use_voice_cloning: bool = Field(
        default=False, description="Enable voice cloning (requires voice_sample_path)"
    )
    speed_clamp_min: float = Field(
        default=0.5, gt=0, description="Minimum speed factor for duration matching"
    )
    speed_clamp_max: float = Field(
        default=2.0, le=4.0, description="Maximum speed factor for duration matching"
    )
    only_speed_up: bool = Field(
        default=True, description="Only speed up (never slow down) for live fragments"
    )

    @field_validator("speed_clamp_max")
    @classmethod
    def validate_speed_clamp_max(cls, v: float, info: ValidationInfo) -> float:
        """Ensure speed_clamp_max > speed_clamp_min."""
        speed_clamp_min = info.data.get("speed_clamp_min", 0.5)
        if v <= speed_clamp_min:
            raise ValueError(
                f"speed_clamp_max ({v}) must be greater than speed_clamp_min ({speed_clamp_min})"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "language": "en",
                "fast_mode": False,
                "use_voice_cloning": False,
                "speaker_name": "p225",
                "speed_clamp_min": 0.5,
                "speed_clamp_max": 2.0,
                "only_speed_up": True,
            }
        }
    )


class TTSConfig(BaseModel):
    """Configuration for TTS component."""

    # Output format settings
    output_sample_rate_hz: int = Field(
        default=16000,
        description="Output audio sample rate",
    )
    output_channels: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Output audio channels (1=mono, 2=stereo)",
    )
    output_format: AudioFormat = Field(
        default=AudioFormat.PCM_F32LE,
        description="Output audio format",
    )

    # Processing settings
    timeout_ms: int = Field(
        default=5000,
        ge=1000,
        description="Maximum processing time per fragment (ms)",
    )
    debug_artifacts: bool = Field(
        default=False,
        description="Persist intermediate artifacts for debugging",
    )

    # Voice configuration path
    voices_config_path: str | None = Field(
        default=None,
        description="Path to coqui-voices.yaml configuration file",
    )

    @field_validator("output_sample_rate_hz")
    @classmethod
    def validate_sample_rate(cls, v: int) -> int:
        """Ensure sample rate is in allowed list."""
        if v not in ALLOWED_SAMPLE_RATES:
            raise ValueError(
                f"sample_rate_hz must be one of {ALLOWED_SAMPLE_RATES}, got {v}"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "output_sample_rate_hz": 16000,
                "output_channels": 1,
                "output_format": "pcm_f32le",
                "timeout_ms": 5000,
                "debug_artifacts": False,
            }
        }
    )


# -----------------------------------------------------------------------------
# Metrics Model
# -----------------------------------------------------------------------------


class TTSMetrics(BaseModel):
    """Structured metrics emitted per synthesis request for observability."""

    stream_id: str = Field(..., description="Logical stream identifier")
    sequence_number: int = Field(..., ge=0, description="Fragment index")
    asset_id: str = Field(..., description="AudioAsset.asset_id this metric belongs to")

    # Timing breakdown
    preprocess_time_ms: int = Field(..., ge=0, description="Time spent preprocessing text")
    synthesis_time_ms: int = Field(..., ge=0, description="Time spent synthesizing audio")
    alignment_time_ms: int = Field(
        default=0, ge=0, description="Time spent on duration matching"
    )
    total_time_ms: int = Field(..., ge=0, description="Total processing time")

    # Duration information
    baseline_duration_ms: int | None = Field(
        default=None, ge=0, description="Original synthesized audio duration"
    )
    target_duration_ms: int | None = Field(
        default=None, ge=0, description="Requested target duration"
    )
    final_duration_ms: int = Field(..., ge=0, description="Actual final audio duration")

    # Speed adjustment tracking
    speed_factor_applied: float | None = Field(
        default=None, description="Speed factor used for time-stretch"
    )
    speed_factor_clamped: bool | None = Field(
        default=None, description="Whether speed factor was clamped"
    )

    # Model and mode information
    model_used: str = Field(..., description="Model identifier (e.g., 'xtts_v2')")
    voice_cloning_active: bool = Field(..., description="Whether voice cloning was used")
    fast_mode_active: bool = Field(..., description="Whether fast mode was used")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc",
                "sequence_number": 42,
                "asset_id": "audio-uuid-456",
                "preprocess_time_ms": 5,
                "synthesis_time_ms": 1645,
                "alignment_time_ms": 200,
                "total_time_ms": 1850,
                "baseline_duration_ms": 2500,
                "target_duration_ms": 2000,
                "final_duration_ms": 2000,
                "speed_factor_applied": 1.25,
                "speed_factor_clamped": False,
                "model_used": "xtts_v2",
                "voice_cloning_active": False,
                "fast_mode_active": False,
            }
        }
    )


# -----------------------------------------------------------------------------
# Output Model
# -----------------------------------------------------------------------------


class AudioAsset(AssetIdentifiers):
    """Synthesized speech audio output with metadata and lineage.

    Produced by the TTS component per specs/004-sts-pipeline-design.md Section 6.4.
    """

    # Component identification
    component: str = Field(
        default="tts", description="Always 'tts' for this asset type"
    )
    component_instance: str = Field(
        ..., description="Provider identifier (e.g., 'coqui-xtts-v2')"
    )

    # Audio format metadata
    audio_format: AudioFormat = Field(..., description="Audio encoding format")
    sample_rate_hz: int = Field(..., description="Audio sample rate in Hz")
    channels: int = Field(..., ge=1, le=2, description="Number of audio channels")
    duration_ms: int = Field(..., ge=0, description="Audio duration in milliseconds")

    # Payload reference
    payload_ref: str = Field(
        ..., description="Reference to PCM bytes (mem:// or file://)"
    )

    # Audio bytes (actual synthesized audio data)
    audio_bytes: bytes = Field(
        default=b"", description="Raw audio bytes (PCM format)"
    )

    # Language metadata
    language: str = Field(..., description="Synthesis language (ISO 639-1)")

    # Status and errors
    status: AudioStatus = Field(..., description="Overall synthesis status")
    errors: list[TTSError] = Field(
        default_factory=list,
        description="List of errors encountered during processing",
    )

    # Processing metadata
    processing_time_ms: int | None = Field(
        default=None, ge=0, description="Total processing time in milliseconds"
    )
    voice_cloning_used: bool | None = Field(
        default=None, description="Whether voice cloning was active"
    )
    preprocessed_text: str | None = Field(
        default=None, description="Actual text used for synthesis (post-preprocessing)"
    )

    @field_validator("sample_rate_hz")
    @classmethod
    def validate_sample_rate(cls, v: int) -> int:
        """Ensure sample rate is in allowed list."""
        if v not in ALLOWED_SAMPLE_RATES:
            raise ValueError(
                f"sample_rate_hz must be one of {ALLOWED_SAMPLE_RATES}, got {v}"
            )
        return v

    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred during processing."""
        return len(self.errors) > 0

    @property
    def is_retryable(self) -> bool:
        """Whether this result should be retried.

        Returns True if status is FAILED and any error is retryable.
        """
        return self.status == AudioStatus.FAILED and any(
            e.retryable for e in self.errors
        )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc",
                "sequence_number": 42,
                "asset_id": "audio-uuid-456",
                "parent_asset_ids": ["text-uuid-123"],
                "created_at": "2025-12-30T10:30:00Z",
                "component": "tts",
                "component_instance": "coqui-xtts-v2",
                "audio_format": "pcm_f32le",
                "sample_rate_hz": 16000,
                "channels": 1,
                "duration_ms": 2000,
                "payload_ref": "mem://fragments/stream-abc/42",
                "language": "en",
                "status": "success",
                "errors": [],
                "processing_time_ms": 1850,
                "voice_cloning_used": False,
                "preprocessed_text": "Hello world! This is a test.",
            }
        }
    )
