"""
ASR (Automatic Speech Recognition) Module for STS Service.

This module provides audio transcription capabilities using faster-whisper.

Public API:
-----------
Components:
    - FasterWhisperASR: Production ASR component using faster-whisper
    - MockASRComponent: Deterministic mock for testing
    - create_asr_component: Factory function for component creation

Interface:
    - ASRComponent: Protocol defining the ASR contract
    - BaseASRComponent: Abstract base class

Models:
    - AudioFragment: Input audio fragment
    - TranscriptAsset: Complete transcription output
    - TranscriptSegment: Single transcript segment
    - TranscriptStatus: SUCCESS, PARTIAL, FAILED
    - ASRError, ASRErrorType: Error handling
    - ASRConfig: Component configuration

Example Usage:
--------------
    # Production usage
    from sts_service.asr import FasterWhisperASR, ASRConfig

    config = ASRConfig()
    asr = FasterWhisperASR(config=config)
    result = asr.transcribe(
        audio_data=audio_bytes,
        stream_id="stream-123",
        sequence_number=0,
        start_time_ms=0,
        end_time_ms=2000,
        domain="sports",
    )

    # Testing with mock
    from sts_service.asr import MockASRComponent, MockASRConfig

    mock = MockASRComponent(MockASRConfig(default_text="Test"))
    result = mock.transcribe(...)
"""

# Core implementations (lazy import for transcriber to avoid loading faster-whisper)
from .confidence import calculate_confidence
from .domain_prompts import DOMAIN_PROMPTS, get_domain_prompt
from .errors import classify_error, create_asr_error, is_retryable
from .factory import create_asr_component

# Interface
from .interface import ASRComponent, AudioPayloadRef, AudioPayloadStore, BaseASRComponent
from .mock import MockASRComponent, MockASRConfig

# Models
from .models import (
    ASRConfig,
    ASRError,
    ASRErrorType,
    # Observability
    ASRMetrics,
    # Configuration
    ASRModelConfig,
    AssetIdentifiers,
    # Enums
    AudioFormat,
    # Input models
    AudioFragment,
    TranscriptAsset,
    TranscriptionConfig,
    TranscriptSegment,
    TranscriptStatus,
    UtteranceShapingConfig,
    VADConfig,
    # Output models
    WordTiming,
)
from .postprocessing import improve_sentence_boundaries, shape_utterances, split_long_segments

# Preprocessing and postprocessing utilities
from .preprocessing import preprocess_audio


def get_transcriber() -> type:
    """Get the FasterWhisperASR class (lazy import).

    This avoids loading faster-whisper until actually needed.

    Returns:
        FasterWhisperASR class
    """
    from .transcriber import FasterWhisperASR
    return FasterWhisperASR


__all__ = [
    # Components
    "FasterWhisperASR",  # Accessed via get_transcriber() or direct import
    "MockASRComponent",
    "MockASRConfig",
    "create_asr_component",
    "get_transcriber",
    # Interface
    "ASRComponent",
    "BaseASRComponent",
    "AudioPayloadRef",
    "AudioPayloadStore",
    # Models - Enums
    "AudioFormat",
    "ASRErrorType",
    "TranscriptStatus",
    # Models - Input
    "AudioFragment",
    # Models - Output
    "WordTiming",
    "TranscriptSegment",
    "ASRError",
    "AssetIdentifiers",
    "TranscriptAsset",
    # Models - Configuration
    "ASRModelConfig",
    "VADConfig",
    "TranscriptionConfig",
    "UtteranceShapingConfig",
    "ASRConfig",
    # Models - Observability
    "ASRMetrics",
    # Utilities
    "preprocess_audio",
    "shape_utterances",
    "improve_sentence_boundaries",
    "split_long_segments",
    "get_domain_prompt",
    "DOMAIN_PROMPTS",
    "calculate_confidence",
    "classify_error",
    "create_asr_error",
    "is_retryable",
]


# Lazy attribute for FasterWhisperASR
def __getattr__(name: str) -> type:
    if name == "FasterWhisperASR":
        from .transcriber import FasterWhisperASR
        return FasterWhisperASR
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
