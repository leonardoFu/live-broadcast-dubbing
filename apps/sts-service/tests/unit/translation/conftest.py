"""
Test fixtures for Translation component tests.

Based on specs/006-translation-component/spec.md test strategy.
"""

from datetime import datetime

import pytest

# -----------------------------------------------------------------------------
# Sports Domain Fixtures
# -----------------------------------------------------------------------------

SPORTS_FIXTURES = [
    "1:54 REMAINING IN THE FOURTH QUARTER",
    "TOUCHDOWN CHIEFS!",
    "NFL PLAYOFFS: CHIEFS VS BILLS",
    "15-12 FINAL SCORE",
    "TEN-YARD LINE",
    "The score is 21-14 at halftime.",
]


@pytest.fixture
def sports_texts() -> list[str]:
    """Sports domain text samples."""
    return SPORTS_FIXTURES.copy()


# -----------------------------------------------------------------------------
# Conversation with Speaker Labels Fixtures
# -----------------------------------------------------------------------------

CONVERSATION_FIXTURES = [
    "Alice: How are you today?",
    ">> Bob: I'm doing great, thanks!",
    "Charlie: That's wonderful to hear.",
    ">> David: What about you, Alice?",
]


@pytest.fixture
def conversation_texts() -> list[str]:
    """Conversation text samples with speaker labels."""
    return CONVERSATION_FIXTURES.copy()


# -----------------------------------------------------------------------------
# Punctuation-Heavy Fixtures
# -----------------------------------------------------------------------------

PUNCTUATION_FIXTURES = [
    "Wait... what did you say?",
    'The score is 21-14\u2014an exciting game!',  # em-dash
    'She said, \u201cI\'ll be there soon.\u201d',  # smart quotes
    'This is \u201cgreat\u201d news!',  # smart quotes
    "What\u2019s happening?",  # smart apostrophe
]


@pytest.fixture
def punctuation_texts() -> list[str]:
    """Punctuation-heavy text samples."""
    return PUNCTUATION_FIXTURES.copy()


# -----------------------------------------------------------------------------
# False Positive Avoidance Fixtures
# -----------------------------------------------------------------------------

FALSE_POSITIVE_FIXTURES = [
    "Time: 1:54 remaining",  # Time format, not speaker
    "Score: 21-14",  # Score header, not speaker
    "URL: https://example.com",  # URL prefix, not speaker
    "Note: Please review",  # Common word with colon
]


@pytest.fixture
def false_positive_texts() -> list[str]:
    """Text samples that should NOT trigger speaker detection."""
    return FALSE_POSITIVE_FIXTURES.copy()


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def create_mock_transcript_asset(
    text: str,
    stream_id: str = "test-stream-001",
    sequence_number: int = 0,
    language: str = "en",
) -> dict:
    """Create a mock TranscriptAsset-like dict for testing.

    This is a helper to simulate the input from ASR module.
    The actual TranscriptAsset model is imported from asr.models.

    Args:
        text: Transcript text
        stream_id: Logical stream identifier
        sequence_number: Fragment index
        language: Source language code

    Returns:
        Dict matching TranscriptAsset structure
    """
    import uuid

    return {
        "stream_id": stream_id,
        "sequence_number": sequence_number,
        "asset_id": str(uuid.uuid4()),
        "parent_asset_ids": [],
        "created_at": datetime.utcnow().isoformat(),
        "component": "asr",
        "component_instance": "mock-asr",
        "language": language,
        "language_probability": 0.99,
        "segments": [
            {
                "start_time_ms": 0,
                "end_time_ms": 2000,
                "text": text,
                "confidence": 0.95,
                "words": None,
            }
        ],
        "status": "success",
        "errors": [],
        "processing_time_ms": 100,
        "model_info": "mock-asr",
    }


@pytest.fixture
def mock_transcript_factory():
    """Factory fixture for creating mock transcript assets."""
    return create_mock_transcript_asset


# -----------------------------------------------------------------------------
# Normalization Fixtures
# -----------------------------------------------------------------------------

NORMALIZATION_TEST_CASES = [
    # (input, expected_normalized) tuples
    ("1:54 REMAINING", "1:54 remaining"),
    ("TEN-YARD LINE", "TEN YARD LINE"),
    ("NFL GAME", "N F L GAME"),
    ("vs. BILLS", "versus BILLS"),
    ("100%", "100 percent "),
    ("$50", " dollars 50"),
    ("M&M", "M and M"),
]


@pytest.fixture
def normalization_cases() -> list[tuple[str, str]]:
    """Input/expected pairs for normalization testing."""
    return NORMALIZATION_TEST_CASES.copy()


# -----------------------------------------------------------------------------
# TTS Cleanup Fixtures
# -----------------------------------------------------------------------------

TTS_CLEANUP_TEST_CASES = [
    # (input, expected_cleaned) tuples
    ('\u201cHello\u201d', '"Hello"'),  # smart quotes
    ('\u201cHello\u201d', '"Hello"'),  # smart double quotes
    ('\u2018Hi\u2019', "'Hi'"),  # smart single quotes
    ("15-12", "15 to 12"),  # score
    ("21\u201414", "21-14"),  # em-dash to hyphen
    ("a  b   c", "a b c"),  # multiple spaces
]


@pytest.fixture
def tts_cleanup_cases() -> list[tuple[str, str]]:
    """Input/expected pairs for TTS cleanup testing."""
    return TTS_CLEANUP_TEST_CASES.copy()


# -----------------------------------------------------------------------------
# Speaker Detection Fixtures
# -----------------------------------------------------------------------------

SPEAKER_DETECTION_TEST_CASES = [
    # (input, expected_speaker, expected_text) tuples
    ("Alice: How are you?", "Alice", "How are you?"),
    (">> Bob: I'm great!", "Bob", "I'm great!"),
    ("Charlie: Thanks", "Charlie", "Thanks"),
    ("Hello world", "default", "Hello world"),  # No speaker
]


@pytest.fixture
def speaker_detection_cases() -> list[tuple[str, str, str]]:
    """Input/expected pairs for speaker detection testing."""
    return SPEAKER_DETECTION_TEST_CASES.copy()
