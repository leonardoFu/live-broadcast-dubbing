"""
Deterministic test fixtures for STS events (Constitution Principle II).

These fixtures mock STS service events (`fragment:data`, `fragment:processed`)
for contract and integration testing without requiring live services.
"""
import base64
from typing import Dict, Any


def mock_fragment_data_event(
    fragment_id: str = "test-frag-001",
    stream_id: str = "test-stream",
    sequence_number: int = 1,
    duration_ms: int = 1000,
    sample_rate: int = 16000,
    channels: int = 1
) -> Dict[str, Any]:
    """
    Generate mock `fragment:data` event for testing.

    Args:
        fragment_id: Unique fragment identifier
        stream_id: Stream identifier
        sequence_number: Monotonic fragment sequence
        duration_ms: Fragment duration in milliseconds
        sample_rate: Audio sample rate (Hz)
        channels: Number of audio channels

    Returns:
        Dict matching STS fragment:data schema
    """
    # Generate deterministic PCM audio (silence)
    num_samples = (sample_rate * duration_ms) // 1000
    pcm_data = b'\x00\x00' * num_samples * channels  # S16LE silence

    return {
        "event": "fragment:data",
        "fragment_id": fragment_id,
        "stream_id": stream_id,
        "sequence_number": sequence_number,
        "audio_data": base64.b64encode(pcm_data).decode('utf-8'),
        "duration_ms": duration_ms,
        "sample_rate": sample_rate,
        "channels": channels,
        "timestamp": 1640000000.0  # Deterministic timestamp
    }


def mock_fragment_processed_event(
    fragment_id: str = "test-frag-001",
    stream_id: str = "test-stream",
    duration_ms: int = 1000,
    sample_rate: int = 16000,
    channels: int = 1,
    transcription: str = "Test transcription",
    translation: str = "Test translation"
) -> Dict[str, Any]:
    """
    Generate mock `fragment:processed` event for testing.

    Returns:
        Dict matching STS fragment:processed schema
    """
    # Generate deterministic dubbed audio (silence)
    num_samples = (sample_rate * duration_ms) // 1000
    dubbed_pcm = b'\x00\x00' * num_samples * channels

    return {
        "event": "fragment:processed",
        "fragment_id": fragment_id,
        "stream_id": stream_id,
        "dubbed_audio": base64.b64encode(dubbed_pcm).decode('utf-8'),
        "duration_ms": duration_ms,
        "sample_rate": sample_rate,
        "channels": channels,
        "metadata": {
            "transcription": transcription,
            "translation": translation,
            "processing_time_ms": 150
        }
    }


def mock_sts_api_success_response(
    fragment_id: str = "test-frag-001",
    duration_ms: int = 1000
) -> Dict[str, Any]:
    """Generate mock STS API success response."""
    return {
        "status": "success",
        "fragment_id": fragment_id,
        "dubbed_audio": base64.b64encode(b'\x00\x00' * 16000).decode('utf-8'),
        "duration_ms": duration_ms,
        "sample_rate": 16000,
        "channels": 1
    }


def mock_sts_api_error_response(
    error_type: str = "timeout",
    fragment_id: str = "test-frag-001"
) -> Dict[str, Any]:
    """Generate mock STS API error response."""
    return {
        "status": "error",
        "error_type": error_type,
        "fragment_id": fragment_id,
        "message": f"STS processing failed: {error_type}"
    }
