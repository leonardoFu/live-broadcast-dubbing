"""
Example contract test for STS events.

This demonstrates:
- Event schema validation
- Mock fixture usage
- Contract testing patterns
"""
import sys
from pathlib import Path

# Add .specify/templates/test-fixtures to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".specify" / "templates" / "test-fixtures"))

from sts_events import (
    mock_fragment_data_event,
    mock_fragment_processed_event,
)


def validate_fragment_data_schema(event: dict) -> bool:
    """
    Validate fragment:data event schema.

    Required fields:
    - event: "fragment:data"
    - fragment_id: str
    - stream_id: str
    - sequence_number: int
    - audio_data: str (base64)
    - duration_ms: int
    - sample_rate: int
    - channels: int
    """
    required_fields = [
        "event", "fragment_id", "stream_id", "sequence_number",
        "audio_data", "duration_ms", "sample_rate", "channels"
    ]

    for field in required_fields:
        if field not in event:
            return False

    return event["event"] == "fragment:data"


def test_sts_fragment_data_schema():
    """Test fragment:data event matches expected schema."""
    event = mock_fragment_data_event(
        fragment_id="test-001",
        stream_id="stream-123",
        sequence_number=1
    )

    assert validate_fragment_data_schema(event)
    assert event["fragment_id"] == "test-001"
    assert event["stream_id"] == "stream-123"
    assert event["sequence_number"] == 1
    assert event["sample_rate"] == 16000
    assert event["channels"] == 1


def test_sts_fragment_processed_schema():
    """Test fragment:processed event matches expected schema."""
    event = mock_fragment_processed_event(
        fragment_id="test-001",
        transcription="Hello world",
        translation="Hola mundo"
    )

    assert event["event"] == "fragment:processed"
    assert event["fragment_id"] == "test-001"
    assert "dubbed_audio" in event
    assert event["metadata"]["transcription"] == "Hello world"
    assert event["metadata"]["translation"] == "Hola mundo"
