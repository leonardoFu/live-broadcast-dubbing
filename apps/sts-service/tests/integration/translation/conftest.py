"""
Integration test fixtures for ASR -> Translation pipeline.

Provides fixtures and adapter functions for testing the complete
ASR to Translation flow.
"""

import os
from collections.abc import Callable

import pytest
from sts_service.asr.models import (
    TranscriptAsset,
    TranscriptSegment,
    TranscriptStatus,
)
from sts_service.translation.interface import TranslationComponent
from sts_service.translation.models import (
    NormalizationPolicy,
    SpeakerPolicy,
    TextAsset,
)

# -----------------------------------------------------------------------------
# ASR -> Translation Adapter
# -----------------------------------------------------------------------------


def translate_transcript(
    transcript: TranscriptAsset,
    translator: TranslationComponent,
    target_language: str,
    speaker_policy: SpeakerPolicy | None = None,
    normalization_policy: NormalizationPolicy | None = None,
) -> TextAsset:
    """Translate a TranscriptAsset using the Translation component.

    This adapter bridges the ASR output to Translation input, ensuring
    proper lineage tracking through parent_asset_ids.

    Args:
        transcript: TranscriptAsset from ASR component
        translator: Translation component instance
        target_language: Target language code (e.g., "zh", "es")
        speaker_policy: Optional speaker detection policy
        normalization_policy: Optional normalization policy

    Returns:
        TextAsset with translation results and proper lineage

    Example:
        >>> transcript = asr_component.transcribe(audio_fragment)
        >>> translated = translate_transcript(transcript, translator, "zh")
        >>> assert transcript.asset_id in translated.parent_asset_ids
    """
    return translator.translate(
        source_text=transcript.total_text,
        stream_id=transcript.stream_id,
        sequence_number=transcript.sequence_number,
        source_language=transcript.language,
        target_language=target_language,
        parent_asset_ids=[transcript.asset_id],
        speaker_policy=speaker_policy,
        normalization_policy=normalization_policy,
    )


# -----------------------------------------------------------------------------
# Factory Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def translate_transcript_fn() -> Callable:
    """Fixture providing the translate_transcript adapter function."""
    return translate_transcript


# -----------------------------------------------------------------------------
# Sample TranscriptAsset Fixtures
# -----------------------------------------------------------------------------


def create_transcript_asset(
    text: str,
    stream_id: str = "integration-test-stream",
    sequence_number: int = 0,
    language: str = "en",
    confidence: float = 0.95,
) -> TranscriptAsset:
    """Create a TranscriptAsset for testing.

    Args:
        text: Transcript text
        stream_id: Stream identifier
        sequence_number: Sequence number
        language: Source language code
        confidence: Confidence score

    Returns:
        TranscriptAsset instance
    """
    return TranscriptAsset(
        stream_id=stream_id,
        sequence_number=sequence_number,
        component_instance="integration-test-asr",
        language=language,
        language_probability=0.99,
        segments=[
            TranscriptSegment(
                start_time_ms=0,
                end_time_ms=2000,
                text=text,
                confidence=confidence,
            )
        ],
        status=TranscriptStatus.SUCCESS,
        processing_time_ms=100,
        model_info="integration-test-asr",
    )


@pytest.fixture
def transcript_factory() -> Callable[..., TranscriptAsset]:
    """Factory fixture for creating TranscriptAssets."""
    return create_transcript_asset


@pytest.fixture
def english_greeting_transcript() -> TranscriptAsset:
    """Sample English greeting transcript."""
    return create_transcript_asset(
        text="Hello, how are you today?",
        sequence_number=1,
    )


@pytest.fixture
def english_sports_transcript() -> TranscriptAsset:
    """Sample English sports commentary transcript."""
    return create_transcript_asset(
        text="Touchdown! The Chiefs score with 1:54 remaining in the fourth quarter.",
        sequence_number=2,
    )


@pytest.fixture
def english_technical_transcript() -> TranscriptAsset:
    """Sample English technical content transcript."""
    return create_transcript_asset(
        text="The API endpoint returns a JSON response with status code 200.",
        sequence_number=3,
    )


@pytest.fixture
def english_conversation_transcript() -> TranscriptAsset:
    """Sample English conversation with speaker label."""
    return create_transcript_asset(
        text="Alice: Thank you for joining us today.",
        sequence_number=4,
    )


@pytest.fixture
def multi_fragment_transcripts() -> list[TranscriptAsset]:
    """Multiple sequential transcripts for stream testing."""
    texts = [
        "Welcome to the live broadcast.",
        "Today we will be discussing the latest developments.",
        "Let me introduce our first speaker.",
        "Thank you for having me here today.",
        "The topic is very important for everyone.",
    ]
    return [
        create_transcript_asset(
            text=text,
            sequence_number=i,
        )
        for i, text in enumerate(texts)
    ]


# -----------------------------------------------------------------------------
# Policy Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def default_normalization_policy() -> NormalizationPolicy:
    """Default normalization policy for integration tests."""
    return NormalizationPolicy(
        enabled=True,
        normalize_time_phrases=True,
        expand_abbreviations=True,
        normalize_hyphens=True,
        normalize_symbols=True,
        tts_cleanup=False,
    )


@pytest.fixture
def speaker_detection_policy() -> SpeakerPolicy:
    """Policy with speaker detection enabled."""
    return SpeakerPolicy(detect_and_remove=True)


@pytest.fixture
def tts_optimized_policy() -> NormalizationPolicy:
    """Normalization policy optimized for TTS output."""
    return NormalizationPolicy(
        enabled=True,
        normalize_time_phrases=True,
        expand_abbreviations=True,
        normalize_hyphens=True,
        normalize_symbols=True,
        tts_cleanup=True,
    )


# -----------------------------------------------------------------------------
# DeepL Test Markers
# -----------------------------------------------------------------------------


def pytest_configure(config):
    """Register custom markers for integration tests."""
    config.addinivalue_line(
        "markers",
        "deepl_live: marks tests requiring live DeepL API (deselect with '-m \"not deepl_live\"')",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )


def has_deepl_api_key() -> bool:
    """Check if DeepL API key is available."""
    return bool(os.environ.get("DEEPL_AUTH_KEY"))


# Skip marker for tests requiring DeepL API
skip_without_deepl = pytest.mark.skipif(
    not has_deepl_api_key(),
    reason="DEEPL_AUTH_KEY environment variable not set",
)
