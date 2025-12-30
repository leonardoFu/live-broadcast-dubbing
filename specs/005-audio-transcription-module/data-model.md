# Data Model: Audio Transcription Module (ASR Component)

**Feature**: 005-audio-transcription-module
**Date**: 2025-12-28
**Spec Reference**: `specs/005-audio-transcription-module.md` Section 4

This document defines the Pydantic models for the ASR component's input/output contracts.

---

## 1. Core Identifiers

All ASR artifacts carry these base identifiers per `specs/004-sts-pipeline-design.md` Section 5.1:

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class AssetIdentifiers(BaseModel):
    """Base identifiers for all STS assets."""

    stream_id: str = Field(..., description="Logical stream/session identifier")
    sequence_number: int = Field(..., ge=0, description="Monotonically increasing fragment index")
    asset_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique identifier for this artifact"
    )
    parent_asset_ids: list[str] = Field(
        default_factory=list,
        description="References to upstream assets used to create this artifact"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of artifact creation"
    )
    component: str = Field(..., description="Name of component that produced this artifact")
    component_instance: str = Field(..., description="Provider identifier (e.g., 'faster-whisper-base')")
```

---

## 2. Input: Audio Fragment

Minimum fields expected by the ASR component:

```python
from enum import Enum
from typing import Union
import numpy as np


class AudioFormat(str, Enum):
    """Supported audio formats."""
    PCM_F32LE = "pcm_f32le"  # 32-bit float little-endian
    PCM_S16LE = "pcm_s16le"  # 16-bit signed integer little-endian


class AudioFragment(BaseModel):
    """Input audio fragment for ASR processing.

    Represents a short window (~1-2 seconds) of audio from a live stream,
    suitable for low-latency transcription.
    """

    stream_id: str = Field(..., description="Logical stream/session identifier")
    sequence_number: int = Field(..., ge=0, description="Fragment index within stream")

    # Audio metadata
    audio_format: AudioFormat = Field(
        default=AudioFormat.PCM_F32LE,
        description="Audio encoding format"
    )
    sample_rate_hz: int = Field(
        default=16000,
        ge=8000,
        le=48000,
        description="Sample rate in Hz (faster-whisper expects 16kHz)"
    )
    channels: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Number of audio channels (mono recommended)"
    )

    # Timing
    start_time_ms: int = Field(..., ge=0, description="Fragment start in stream timeline (ms)")
    end_time_ms: int = Field(..., gt=0, description="Fragment end in stream timeline (ms)")

    # Payload
    payload_ref: str = Field(
        ...,
        description="Reference to PCM bytes (in-memory key or asset store path)"
    )

    # Optional configuration
    domain: Optional[str] = Field(
        default="general",
        description="Domain hint for vocabulary priming (sports, news, interview, general)"
    )
    language: Optional[str] = Field(
        default="en",
        description="Expected language code (ISO 639-1)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "stream_id": "stream-abc-123",
                "sequence_number": 42,
                "audio_format": "pcm_f32le",
                "sample_rate_hz": 16000,
                "channels": 1,
                "start_time_ms": 84000,
                "end_time_ms": 86000,
                "payload_ref": "mem://fragments/stream-abc-123/42",
                "domain": "sports",
                "language": "en"
            }
        }

    @property
    def duration_ms(self) -> int:
        """Fragment duration in milliseconds."""
        return self.end_time_ms - self.start_time_ms
```

---

## 3. Output: Transcript Asset

### 3.1 Word-Level Timing

```python
class WordTiming(BaseModel):
    """Word-level timing and confidence information."""

    start_time_ms: int = Field(..., ge=0, description="Word start (absolute stream time)")
    end_time_ms: int = Field(..., gt=0, description="Word end (absolute stream time)")
    word: str = Field(..., min_length=1, description="Recognized word text")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Word-level confidence (0.0-1.0)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_time_ms": 84100,
                "end_time_ms": 84350,
                "word": "touchdown",
                "confidence": 0.95
            }
        }
```

### 3.2 Transcript Segment

```python
class TranscriptSegment(BaseModel):
    """A single transcript segment with timing and confidence.

    Segment times are ABSOLUTE in the stream timeline:
    segment_abs_time = fragment_start_time + segment_rel_time
    """

    start_time_ms: int = Field(..., ge=0, description="Segment start (absolute stream time)")
    end_time_ms: int = Field(..., gt=0, description="Segment end (absolute stream time)")
    text: str = Field(..., min_length=1, description="Human-readable transcript text")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Segment-level confidence score (0.0-1.0)"
    )

    # Optional detailed information
    words: Optional[list[WordTiming]] = Field(
        default=None,
        description="Word-level timestamps (when word_timestamps enabled)"
    )
    no_speech_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Probability that segment contains no speech (debug signal)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_time_ms": 84000,
                "end_time_ms": 86000,
                "text": "Touchdown Chiefs! Patrick Mahomes with another incredible play.",
                "confidence": 0.92,
                "words": [
                    {"start_time_ms": 84000, "end_time_ms": 84300, "word": "Touchdown", "confidence": 0.98},
                    {"start_time_ms": 84350, "end_time_ms": 84600, "word": "Chiefs!", "confidence": 0.95}
                ],
                "no_speech_probability": 0.02
            }
        }

    @property
    def duration_ms(self) -> int:
        """Segment duration in milliseconds."""
        return self.end_time_ms - self.start_time_ms
```

### 3.3 ASR Error

```python
class ASRErrorType(str, Enum):
    """Classification of ASR errors for orchestration policies."""

    NO_SPEECH = "no_speech"           # Silent/noise-only fragment
    MODEL_LOAD_ERROR = "model_load"   # Model initialization failed
    MEMORY_ERROR = "memory_error"     # Out of memory
    INVALID_AUDIO = "invalid_audio"   # Corrupt or unprocessable audio
    TIMEOUT = "timeout"               # Processing exceeded deadline
    PREPROCESSING_ERROR = "preprocessing"  # Audio preprocessing failed
    UNKNOWN = "unknown"               # Unclassified failure


class ASRError(BaseModel):
    """Structured error information for failed or partial transcriptions."""

    error_type: ASRErrorType = Field(..., description="Error classification")
    message: str = Field(..., description="Human-readable error message (safe for logs)")
    retryable: bool = Field(..., description="Whether this error is worth retrying")
    details: Optional[dict] = Field(
        default=None,
        description="Additional error context (debug info)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error_type": "timeout",
                "message": "Transcription exceeded 5000ms deadline",
                "retryable": True,
                "details": {"elapsed_ms": 5234, "deadline_ms": 5000}
            }
        }
```

### 3.4 Transcript Asset (Complete Output)

```python
class TranscriptStatus(str, Enum):
    """Status of transcript generation."""

    SUCCESS = "success"     # All segments produced successfully
    PARTIAL = "partial"     # Some segments produced, errors on others
    FAILED = "failed"       # No segments produced


class TranscriptAsset(AssetIdentifiers):
    """Complete ASR output for a single audio fragment.

    Produced by the ASR component per specs/004-sts-pipeline-design.md Section 6.2.
    """

    # Override component field with ASR-specific default
    component: str = Field(default="asr", description="Always 'asr' for this asset type")

    # Language information
    language: str = Field(..., description="Detected or specified language code")
    language_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Language detection confidence (if auto-detected)"
    )

    # Transcript content
    segments: list[TranscriptSegment] = Field(
        default_factory=list,
        description="Ordered list of transcript segments"
    )

    # Status and errors
    status: TranscriptStatus = Field(..., description="Overall transcription status")
    errors: list[ASRError] = Field(
        default_factory=list,
        description="List of errors encountered during processing"
    )

    # Processing metadata
    processing_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total processing time in milliseconds"
    )
    model_info: Optional[str] = Field(
        default=None,
        description="Model identifier used (e.g., 'faster-whisper-base-int8')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "stream_id": "stream-abc-123",
                "sequence_number": 42,
                "asset_id": "asr-asset-uuid-here",
                "parent_asset_ids": ["audio-fragment-uuid"],
                "created_at": "2025-12-28T10:30:00Z",
                "component": "asr",
                "component_instance": "faster-whisper-base",
                "language": "en",
                "language_probability": 0.99,
                "segments": [
                    {
                        "start_time_ms": 84000,
                        "end_time_ms": 86000,
                        "text": "Touchdown Chiefs!",
                        "confidence": 0.92
                    }
                ],
                "status": "success",
                "errors": [],
                "processing_time_ms": 450,
                "model_info": "faster-whisper-base-int8"
            }
        }

    @property
    def total_text(self) -> str:
        """Concatenated text from all segments."""
        return " ".join(seg.text for seg in self.segments)

    @property
    def average_confidence(self) -> float:
        """Average confidence across all segments."""
        if not self.segments:
            return 0.0
        return sum(seg.confidence for seg in self.segments) / len(self.segments)

    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred during processing."""
        return len(self.errors) > 0

    @property
    def is_retryable(self) -> bool:
        """Whether this result should be retried."""
        return self.status == TranscriptStatus.FAILED and any(e.retryable for e in self.errors)
```

---

## 4. Configuration Models

### 4.1 ASR Component Configuration

```python
class ASRModelConfig(BaseModel):
    """Configuration for the Whisper model instance."""

    model_size: str = Field(
        default="base",
        pattern="^(tiny|base|small|medium|large-v[123]|turbo)$",
        description="Whisper model size"
    )
    device: str = Field(
        default="cpu",
        pattern="^(cpu|cuda|cuda:\\d+)$",
        description="Compute device"
    )
    compute_type: str = Field(
        default="int8",
        pattern="^(int8|float16|float32)$",
        description="Compute precision"
    )


class VADConfig(BaseModel):
    """Voice Activity Detection configuration."""

    enabled: bool = Field(default=True, description="Enable VAD filtering")
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Speech probability threshold"
    )
    min_silence_duration_ms: int = Field(
        default=300,
        ge=0,
        description="Minimum silence to separate speech chunks"
    )
    min_speech_duration_ms: int = Field(
        default=250,
        ge=0,
        description="Discard speech shorter than this"
    )
    speech_pad_ms: int = Field(
        default=400,
        ge=0,
        description="Padding around detected speech"
    )


class TranscriptionConfig(BaseModel):
    """Transcription behavior configuration."""

    language: str = Field(default="en", description="Expected language code")
    word_timestamps: bool = Field(default=True, description="Enable word-level timestamps")
    beam_size: int = Field(default=8, ge=1, le=10, description="Beam search width")
    best_of: int = Field(default=8, ge=1, le=10, description="Number of candidates")
    temperature: list[float] = Field(
        default=[0.0, 0.2, 0.4],
        description="Temperature ensemble for sampling"
    )
    compression_ratio_threshold: float = Field(
        default=2.4,
        ge=1.0,
        description="Compression ratio quality guard"
    )
    log_prob_threshold: float = Field(
        default=-1.0,
        description="Log probability quality guard"
    )
    no_speech_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="No-speech detection threshold"
    )


class UtteranceShapingConfig(BaseModel):
    """Utterance boundary improvement configuration."""

    merge_threshold_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Merge segments shorter than this"
    )
    max_segment_duration_seconds: float = Field(
        default=6.0,
        ge=1.0,
        description="Split segments longer than this"
    )


class ASRConfig(BaseModel):
    """Complete ASR component configuration."""

    model: ASRModelConfig = Field(default_factory=ASRModelConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    utterance_shaping: UtteranceShapingConfig = Field(default_factory=UtteranceShapingConfig)

    # Operational settings
    timeout_ms: int = Field(
        default=5000,
        ge=1000,
        description="Maximum processing time per fragment"
    )
    debug_artifacts: bool = Field(
        default=False,
        description="Persist input audio and output transcripts for debugging"
    )
```

---

## 5. Observability Models

```python
class ASRMetrics(BaseModel):
    """Structured metrics emitted per fragment for observability."""

    stream_id: str
    sequence_number: int

    # Timing breakdown
    preprocess_time_ms: int = Field(..., ge=0)
    transcription_time_ms: int = Field(..., ge=0)
    postprocess_time_ms: int = Field(..., ge=0)
    total_time_ms: int = Field(..., ge=0)

    # Output summary
    segment_count: int = Field(..., ge=0)
    total_text_length: int = Field(..., ge=0)
    average_confidence: float = Field(..., ge=0.0, le=1.0)

    # Error tracking
    error_count: int = Field(default=0, ge=0)
    retryable_error_count: int = Field(default=0, ge=0)
```

---

## 6. Model Relationships

```
AudioFragment
    |
    v
[ASR Component]
    |
    v
TranscriptAsset
    |-- segments: list[TranscriptSegment]
    |       |-- words: list[WordTiming] (optional)
    |-- errors: list[ASRError]

Configuration:
ASRConfig
    |-- model: ASRModelConfig
    |-- vad: VADConfig
    |-- transcription: TranscriptionConfig
    |-- utterance_shaping: UtteranceShapingConfig
```

---

## 7. Validation Rules

1. **Timestamp Consistency**:
   - `segment.start_time_ms >= fragment.start_time_ms`
   - `segment.end_time_ms <= fragment.end_time_ms`
   - `segment.start_time_ms < segment.end_time_ms`

2. **Segment Ordering**:
   - Segments must be ordered by `start_time_ms`
   - No overlapping segments within a transcript

3. **Status Consistency**:
   - `SUCCESS`: `len(errors) == 0` and `len(segments) >= 0`
   - `PARTIAL`: `len(errors) > 0` and `len(segments) > 0`
   - `FAILED`: `len(segments) == 0` (errors may or may not be present for NO_SPEECH)

4. **Asset Lineage**:
   - `TranscriptAsset.parent_asset_ids` must contain the input `AudioFragment` asset ID
