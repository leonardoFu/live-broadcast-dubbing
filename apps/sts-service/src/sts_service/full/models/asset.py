"""Asset models for Full STS Service.

Defines typed models for pipeline asset lineage tracking per spec 021:
- TranscriptAsset: ASR output with confidence scores
- TranslationAsset: Translation output with source text
- AudioAsset: Synthesized audio with duration metadata

These models enable tracing the data flow through the pipeline:
FragmentData -> TranscriptAsset -> TranslationAsset -> AudioAsset -> FragmentResult
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssetStatus(str, Enum):
    """Asset processing status."""

    SUCCESS = "success"  # Asset created successfully
    PARTIAL = "partial"  # Asset created with warnings/fallbacks
    FAILED = "failed"  # Asset creation failed


class BaseAsset(BaseModel):
    """Base class for all pipeline assets.

    Provides common fields for asset lineage tracking.
    """

    asset_id: str = Field(
        min_length=1,
        description="Unique asset identifier (UUID)",
    )
    fragment_id: str = Field(
        min_length=1,
        description="Source fragment ID for traceability",
    )
    stream_id: str = Field(
        min_length=1,
        description="Parent stream ID",
    )
    status: AssetStatus = Field(
        default=AssetStatus.SUCCESS,
        description="Asset processing status",
    )
    parent_asset_ids: list[str] = Field(
        default_factory=list,
        description="IDs of parent assets in the pipeline",
    )
    latency_ms: int = Field(
        ge=0,
        description="Processing latency in milliseconds",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Asset creation timestamp",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if status is FAILED or PARTIAL",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for debugging",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class TranscriptSegment(BaseModel):
    """Individual word or segment from ASR with timing.

    Used for word-level alignment and confidence scoring.
    """

    text: str = Field(description="Transcribed text")
    start_ms: int = Field(ge=0, description="Start time in milliseconds")
    end_ms: int = Field(ge=0, description="End time in milliseconds")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Word-level confidence score",
    )

    @property
    def duration_ms(self) -> int:
        """Duration of this segment."""
        return self.end_ms - self.start_ms

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Hello",
                "start_ms": 0,
                "end_ms": 500,
                "confidence": 0.95,
            }
        }
    )


class TranscriptAsset(BaseAsset):
    """ASR output asset with transcript and confidence.

    Produced by the ASR stage, consumed by Translation stage.
    """

    transcript: str = Field(
        description="Full transcribed text",
    )
    segments: list[TranscriptSegment] = Field(
        default_factory=list,
        description="Word-level segments with timing",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall transcript confidence score",
    )
    language: str = Field(
        min_length=2,
        description="Detected or specified source language",
    )
    audio_duration_ms: int = Field(
        ge=0,
        description="Duration of input audio in milliseconds",
    )
    model_id: str = Field(
        default="faster-whisper",
        description="ASR model identifier",
    )

    @property
    def words_per_minute(self) -> float:
        """Calculate speaking rate."""
        if self.audio_duration_ms == 0:
            return 0.0
        word_count = len(self.transcript.split())
        return (word_count / self.audio_duration_ms) * 60000

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "asset_id": "asr-550e8400-e29b-41d4-a716-446655440000",
                "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
                "stream_id": "stream-abc-123",
                "status": "success",
                "parent_asset_ids": [],
                "latency_ms": 1200,
                "transcript": "Hello, welcome to the game.",
                "segments": [
                    {"text": "Hello", "start_ms": 0, "end_ms": 500, "confidence": 0.95},
                    {"text": "welcome", "start_ms": 600, "end_ms": 1100, "confidence": 0.92},
                ],
                "confidence": 0.93,
                "language": "en",
                "audio_duration_ms": 6000,
            }
        }
    )


class TranslationAsset(BaseAsset):
    """Translation output asset.

    Produced by the Translation stage, consumed by TTS stage.
    """

    translated_text: str = Field(
        description="Translated text in target language",
    )
    source_text: str = Field(
        description="Original source text (from ASR)",
    )
    source_language: str = Field(
        min_length=2,
        description="Source language code",
    )
    target_language: str = Field(
        min_length=2,
        description="Target language code",
    )
    model_id: str = Field(
        default="deepl",
        description="Translation model/API identifier",
    )
    character_count: int = Field(
        ge=0,
        description="Number of characters translated",
    )
    word_expansion_ratio: float = Field(
        ge=0.0,
        description="Ratio of target words to source words",
    )

    @classmethod
    def from_transcript(
        cls,
        transcript_asset: TranscriptAsset,
        translated_text: str,
        target_language: str,
        latency_ms: int,
        *,
        asset_id: str | None = None,
        model_id: str = "deepl",
    ) -> "TranslationAsset":
        """Create translation asset from transcript asset."""
        import uuid

        source_words = len(transcript_asset.transcript.split())
        target_words = len(translated_text.split())
        expansion_ratio = target_words / source_words if source_words > 0 else 1.0

        return cls(
            asset_id=asset_id or f"trans-{uuid.uuid4()}",
            fragment_id=transcript_asset.fragment_id,
            stream_id=transcript_asset.stream_id,
            status=AssetStatus.SUCCESS,
            parent_asset_ids=[transcript_asset.asset_id],
            latency_ms=latency_ms,
            translated_text=translated_text,
            source_text=transcript_asset.transcript,
            source_language=transcript_asset.language,
            target_language=target_language,
            model_id=model_id,
            character_count=len(translated_text),
            word_expansion_ratio=expansion_ratio,
        )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "asset_id": "trans-660e8400-e29b-41d4-a716-446655440000",
                "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
                "stream_id": "stream-abc-123",
                "status": "success",
                "parent_asset_ids": ["asr-550e8400-e29b-41d4-a716-446655440000"],
                "latency_ms": 150,
                "translated_text": "Hola, bienvenido al juego.",
                "source_text": "Hello, welcome to the game.",
                "source_language": "en",
                "target_language": "es",
                "model_id": "deepl",
                "character_count": 27,
                "word_expansion_ratio": 1.2,
            }
        }
    )


class DurationMatchMetadata(BaseModel):
    """Duration matching metadata for A/V synchronization."""

    original_duration_ms: int = Field(
        ge=0,
        description="Target duration (from original fragment)",
    )
    raw_duration_ms: int = Field(
        ge=0,
        description="Duration before time-stretching",
    )
    final_duration_ms: int = Field(
        ge=0,
        description="Duration after time-stretching",
    )
    duration_variance_percent: float = Field(
        ge=0,
        description="Variance as percentage",
    )
    speed_ratio: float = Field(
        ge=0.5,
        le=2.0,
        description="Applied speed ratio (1.0 = no change)",
    )
    speed_clamped: bool = Field(
        default=False,
        description="True if speed ratio was clamped to bounds",
    )

    @property
    def is_within_threshold(self) -> bool:
        """Check if duration variance is within 20% threshold."""
        return self.duration_variance_percent <= 20.0


class AudioAsset(BaseAsset):
    """TTS output audio asset.

    Produced by the TTS stage, the final pipeline output.
    """

    audio_bytes: bytes = Field(
        description="Raw audio data (PCM or encoded)",
    )
    format: str = Field(
        default="pcm_s16le",
        description="Audio format (pcm_s16le, wav, etc.)",
    )
    sample_rate_hz: int = Field(
        default=48000,
        ge=8000,
        le=96000,
        description="Sample rate in Hz",
    )
    channels: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Number of audio channels",
    )
    duration_ms: int = Field(
        ge=0,
        description="Audio duration in milliseconds",
    )
    duration_metadata: DurationMatchMetadata | None = Field(
        default=None,
        description="Duration matching metadata for A/V sync",
    )
    voice_profile: str = Field(
        default="default",
        description="TTS voice profile used",
    )
    model_id: str = Field(
        default="coqui-tts",
        description="TTS model identifier",
    )
    text_input: str = Field(
        description="Text that was synthesized",
    )

    @property
    def size_bytes(self) -> int:
        """Size of audio data in bytes."""
        return len(self.audio_bytes)

    @property
    def bitrate_kbps(self) -> float:
        """Calculate approximate bitrate."""
        if self.duration_ms == 0:
            return 0.0
        return (self.size_bytes * 8) / self.duration_ms

    @classmethod
    def from_translation(
        cls,
        translation_asset: TranslationAsset,
        audio_bytes: bytes,
        duration_ms: int,
        latency_ms: int,
        *,
        asset_id: str | None = None,
        voice_profile: str = "default",
        sample_rate_hz: int = 48000,
        duration_metadata: DurationMatchMetadata | None = None,
    ) -> "AudioAsset":
        """Create audio asset from translation asset."""
        import uuid

        return cls(
            asset_id=asset_id or f"audio-{uuid.uuid4()}",
            fragment_id=translation_asset.fragment_id,
            stream_id=translation_asset.stream_id,
            status=AssetStatus.SUCCESS,
            parent_asset_ids=[translation_asset.asset_id],
            latency_ms=latency_ms,
            audio_bytes=audio_bytes,
            format="pcm_s16le",
            sample_rate_hz=sample_rate_hz,
            channels=1,
            duration_ms=duration_ms,
            duration_metadata=duration_metadata,
            voice_profile=voice_profile,
            text_input=translation_asset.translated_text,
        )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "asset_id": "audio-770e8400-e29b-41d4-a716-446655440000",
                "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
                "stream_id": "stream-abc-123",
                "status": "success",
                "parent_asset_ids": ["trans-660e8400-e29b-41d4-a716-446655440000"],
                "latency_ms": 3100,
                "format": "pcm_s16le",
                "sample_rate_hz": 48000,
                "channels": 1,
                "duration_ms": 6050,
                "voice_profile": "spanish_male_1",
                "text_input": "Hola, bienvenido al juego.",
            }
        },
    )
