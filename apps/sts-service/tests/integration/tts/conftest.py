"""
Integration test fixtures for Translation -> TTS pipeline.

Provides fixtures and adapter functions for testing the complete
Translation to TTS flow.
"""

from collections.abc import Callable

import pytest
from sts_service.translation.models import (
    TextAsset,
    TranslationStatus,
)
from sts_service.tts.interface import TTSComponent
from sts_service.tts.models import (
    AudioAsset,
    VoiceProfile,
)

# -----------------------------------------------------------------------------
# Translation -> TTS Adapter
# -----------------------------------------------------------------------------


def synthesize_from_translation(
    text_asset: TextAsset,
    tts: TTSComponent,
    target_duration_ms: int | None = None,
    output_sample_rate_hz: int = 16000,
    output_channels: int = 1,
    voice_profile: VoiceProfile | None = None,
) -> AudioAsset:
    """Synthesize audio from a TextAsset using the TTS component.

    This adapter bridges the Translation output to TTS input, ensuring
    proper lineage tracking through parent_asset_ids.

    Args:
        text_asset: TextAsset from Translation component
        tts: TTS component instance
        target_duration_ms: Optional target duration for duration matching
        output_sample_rate_hz: Output sample rate (default 16kHz)
        output_channels: Output channels (default mono)
        voice_profile: Optional voice configuration

    Returns:
        AudioAsset with synthesis results and proper lineage

    Example:
        >>> text_asset = translator.translate(...)
        >>> audio = synthesize_from_translation(text_asset, tts_component)
        >>> assert text_asset.asset_id in audio.parent_asset_ids
    """
    return tts.synthesize(
        text_asset=text_asset,
        target_duration_ms=target_duration_ms,
        output_sample_rate_hz=output_sample_rate_hz,
        output_channels=output_channels,
        voice_profile=voice_profile,
    )


# -----------------------------------------------------------------------------
# Factory Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def synthesize_from_translation_fn() -> Callable:
    """Fixture providing the synthesize_from_translation adapter function."""
    return synthesize_from_translation


# -----------------------------------------------------------------------------
# Sample TextAsset Fixtures
# -----------------------------------------------------------------------------


def create_text_asset(
    text: str,
    stream_id: str = "integration-test-stream",
    sequence_number: int = 0,
    source_language: str = "en",
    target_language: str = "es",
) -> TextAsset:
    """Create a TextAsset for testing.

    Args:
        text: Translated text content
        stream_id: Stream identifier
        sequence_number: Sequence number
        source_language: Source language code
        target_language: Target language code

    Returns:
        TextAsset instance
    """
    return TextAsset(
        stream_id=stream_id,
        sequence_number=sequence_number,
        component_instance="integration-test-translation",
        source_language=source_language,
        target_language=target_language,
        translated_text=text,
        status=TranslationStatus.SUCCESS,
        processing_time_ms=100,
    )


@pytest.fixture
def text_asset_factory() -> Callable[..., TextAsset]:
    """Factory fixture for creating TextAssets."""
    return create_text_asset


@pytest.fixture
def english_greeting_text_asset() -> TextAsset:
    """Sample English greeting text asset."""
    return create_text_asset(
        text="Hello, how are you today?",
        target_language="en",
        sequence_number=1,
    )


@pytest.fixture
def spanish_greeting_text_asset() -> TextAsset:
    """Sample Spanish greeting text asset."""
    return create_text_asset(
        text="Hola, como estas hoy?",
        target_language="es",
        sequence_number=1,
    )


@pytest.fixture
def english_sports_text_asset() -> TextAsset:
    """Sample English sports commentary text asset."""
    return create_text_asset(
        text="Touchdown! The Chiefs score with 1:54 remaining in the fourth quarter.",
        target_language="en",
        sequence_number=2,
    )


@pytest.fixture
def multi_fragment_text_assets() -> list[TextAsset]:
    """Multiple sequential text assets for stream testing."""
    texts = [
        "Welcome to the live broadcast.",
        "Today we will be discussing the latest developments.",
        "Let me introduce our first speaker.",
        "Thank you for having me here today.",
        "The topic is very important for everyone.",
    ]
    return [
        create_text_asset(
            text=text,
            target_language="en",
            sequence_number=i,
        )
        for i, text in enumerate(texts)
    ]


# -----------------------------------------------------------------------------
# VoiceProfile Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def default_voice_profile() -> VoiceProfile:
    """Default voice profile for English synthesis."""
    return VoiceProfile(
        language="en",
        fast_mode=False,
        use_voice_cloning=False,
        speed_clamp_min=0.5,
        speed_clamp_max=2.0,
        only_speed_up=True,
    )


@pytest.fixture
def fast_mode_voice_profile() -> VoiceProfile:
    """Fast mode voice profile for low-latency synthesis."""
    return VoiceProfile(
        language="en",
        fast_mode=True,
        use_voice_cloning=False,
        speed_clamp_min=0.5,
        speed_clamp_max=2.0,
        only_speed_up=True,
    )


@pytest.fixture
def spanish_voice_profile() -> VoiceProfile:
    """Spanish voice profile."""
    return VoiceProfile(
        language="es",
        fast_mode=False,
        use_voice_cloning=False,
    )


# -----------------------------------------------------------------------------
# TTS Test Markers
# -----------------------------------------------------------------------------


def pytest_configure(config):
    """Register custom markers for integration tests."""
    config.addinivalue_line(
        "markers",
        "coqui_live: marks tests requiring live Coqui TTS library (deselect with '-m \"not coqui_live\"')",
    )
    config.addinivalue_line(
        "markers",
        "rubberband: marks tests requiring rubberband CLI (deselect with '-m \"not rubberband\"')",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )


def has_coqui_tts() -> bool:
    """Check if Coqui TTS library is available."""
    try:
        from TTS.api import TTS  # noqa: F401

        return True
    except ImportError:
        return False


def has_rubberband() -> bool:
    """Check if rubberband CLI is available."""
    import subprocess

    try:
        result = subprocess.run(
            ["rubberband", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Skip markers for tests requiring specific dependencies
skip_without_coqui = pytest.mark.skipif(
    not has_coqui_tts(),
    reason="Coqui TTS library not installed",
)

skip_without_rubberband = pytest.mark.skipif(
    not has_rubberband(),
    reason="rubberband CLI not installed",
)
