"""
TTS (Text-to-Speech) Audio Synthesis Module.

This module provides text-to-speech synthesis capabilities for the STS pipeline,
converting translated text into synthesized speech audio with duration matching
for live stream synchronization.

Key Components:
- TTSComponent: Protocol defining the TTS interface
- BaseTTSComponent: Abstract base class for implementations
- AudioAsset: Output model with synthesized audio and metadata
- VoiceProfile: Configuration for voice selection
- create_tts_component: Factory function for creating TTS instances

Usage:
    from sts_service.tts import create_tts_component
    from sts_service.translation.models import TextAsset

    tts = create_tts_component(provider="coqui")
    audio_asset = tts.synthesize(text_asset, target_duration_ms=2000)

Based on specs/008-tts-module/.
"""

from .errors import TTSError, TTSErrorType, classify_error, is_retryable_error_type
from .factory import create_tts_component
from .interface import BaseTTSComponent, TTSComponent
from .models import (
    ALLOWED_CHANNELS,
    ALLOWED_SAMPLE_RATES,
    AudioAsset,
    AudioFormat,
    AudioStatus,
    TTSConfig,
    TTSMetrics,
    VoiceProfile,
)

__all__ = [
    # Interface
    "TTSComponent",
    "BaseTTSComponent",
    # Models
    "AudioAsset",
    "AudioFormat",
    "AudioStatus",
    "VoiceProfile",
    "TTSConfig",
    "TTSMetrics",
    # Errors
    "TTSError",
    "TTSErrorType",
    "classify_error",
    "is_retryable_error_type",
    # Factory
    "create_tts_component",
    # Constants
    "ALLOWED_SAMPLE_RATES",
    "ALLOWED_CHANNELS",
]
