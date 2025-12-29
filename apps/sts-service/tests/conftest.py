"""Shared test fixtures for STS Service tests.

Provides common fixtures for both unit and integration tests,
including sample M4A audio data and mock session objects.
"""

import base64
import struct
import uuid
from datetime import datetime
from typing import Any

import pytest

# =============================================================================
# Audio Fixtures
# =============================================================================


def generate_test_audio(
    frequency_hz: float = 440.0,
    duration_ms: int = 1000,
    sample_rate_hz: int = 48000,
    channels: int = 1,
    amplitude: float = 0.5,
) -> bytes:
    """Generate test audio data for M4A format testing.

    Note: This generates raw audio bytes for testing purposes. In the
    echo service context, the actual binary content is echoed back
    unchanged, so we use simple sine wave data as test input.

    Args:
        frequency_hz: Frequency of the sine wave in Hz.
        duration_ms: Duration of the audio in milliseconds.
        sample_rate_hz: Sample rate in Hz.
        channels: Number of audio channels (1=mono, 2=stereo).
        amplitude: Amplitude of the wave (0.0 to 1.0).

    Returns:
        Test audio data as bytes (for M4A format testing).
    """
    import math

    num_samples = int(sample_rate_hz * duration_ms / 1000)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate_hz
        value = amplitude * math.sin(2 * math.pi * frequency_hz * t)
        # Convert to 16-bit signed integer
        sample = int(value * 32767)
        # Clamp to valid range
        sample = max(-32768, min(32767, sample))
        # For stereo, duplicate the sample
        for _ in range(channels):
            samples.append(sample)

    # Pack as little-endian 16-bit integers
    return struct.pack(f"<{len(samples)}h", *samples)


@pytest.fixture
def sample_audio_1s() -> bytes:
    """1 second of test audio at 48kHz mono (M4A format testing)."""
    return generate_test_audio(
        frequency_hz=440.0,
        duration_ms=1000,
        sample_rate_hz=48000,
        channels=1,
    )


@pytest.fixture
def sample_audio_500ms() -> bytes:
    """500ms of test audio at 48kHz mono (M4A format testing)."""
    return generate_test_audio(
        frequency_hz=440.0,
        duration_ms=500,
        sample_rate_hz=48000,
        channels=1,
    )


@pytest.fixture
def sample_audio_stereo() -> bytes:
    """1 second of test audio at 48kHz stereo (M4A format testing)."""
    return generate_test_audio(
        frequency_hz=440.0,
        duration_ms=1000,
        sample_rate_hz=48000,
        channels=2,
    )


@pytest.fixture
def sample_audio_base64(sample_audio_1s: bytes) -> str:
    """Base64-encoded 1 second test audio (M4A format)."""
    return base64.b64encode(sample_audio_1s).decode("ascii")


@pytest.fixture
def sample_audio_base64_500ms(sample_audio_500ms: bytes) -> str:
    """Base64-encoded 500ms test audio (M4A format)."""
    return base64.b64encode(sample_audio_500ms).decode("ascii")


# =============================================================================
# Fragment Fixtures
# =============================================================================


@pytest.fixture
def valid_fragment_id() -> str:
    """Generate a valid UUID fragment ID."""
    return str(uuid.uuid4())


@pytest.fixture
def valid_stream_id() -> str:
    """Generate a valid stream ID."""
    return f"stream-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def valid_worker_id() -> str:
    """Generate a valid worker ID."""
    return f"worker-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_fragment_data(
    valid_fragment_id: str,
    valid_stream_id: str,
    sample_audio_base64: str,
) -> dict[str, Any]:
    """Sample fragment:data payload matching spec 016."""
    return {
        "fragment_id": valid_fragment_id,
        "stream_id": valid_stream_id,
        "sequence_number": 0,
        "timestamp": int(datetime.utcnow().timestamp() * 1000),
        "audio": {
            "format": "m4a",
            "sample_rate_hz": 48000,
            "channels": 1,
            "duration_ms": 1000,
            "data_base64": sample_audio_base64,
        },
        "metadata": {
            "pts_ns": 0,
            "source_pts_ns": 0,
        },
    }


@pytest.fixture
def sample_stream_init(
    valid_stream_id: str,
    valid_worker_id: str,
) -> dict[str, Any]:
    """Sample stream:init payload matching spec 016."""
    return {
        "stream_id": valid_stream_id,
        "worker_id": valid_worker_id,
        "config": {
            "source_language": "en",
            "target_language": "es",
            "voice_profile": "default",
            "chunk_duration_ms": 1000,
            "sample_rate_hz": 48000,
            "channels": 1,
            "format": "m4a",
        },
        "max_inflight": 3,
        "timeout_ms": 8000,
    }


# =============================================================================
# API Key Fixtures
# =============================================================================


@pytest.fixture
def valid_api_key() -> str:
    """Valid API key for testing."""
    return "test-api-key-12345"


@pytest.fixture
def invalid_api_key() -> str:
    """Invalid API key for testing."""
    return "invalid-key"


# =============================================================================
# Error Simulation Fixtures
# =============================================================================


@pytest.fixture
def sample_error_simulation_config() -> dict[str, Any]:
    """Sample error simulation configuration."""
    return {
        "enabled": True,
        "rules": [
            {
                "trigger": "sequence_number",
                "value": 5,
                "error_code": "TIMEOUT",
                "error_message": "Simulated timeout error",
                "retryable": True,
                "stage": "asr",
            },
            {
                "trigger": "nth_fragment",
                "value": 3,
                "error_code": "MODEL_ERROR",
                "error_message": "Simulated model error",
                "retryable": True,
                "stage": "tts",
            },
        ],
    }


# =============================================================================
# Pytest Configuration
# =============================================================================


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy for asyncio tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


# Configure pytest-asyncio mode
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test",
    )
