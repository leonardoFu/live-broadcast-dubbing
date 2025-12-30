"""
Shared fixtures for ASR unit tests.

Provides mock objects and test data generators for unit testing.
"""

import numpy as np
import pytest


@pytest.fixture
def sample_audio_bytes() -> bytes:
    """Return sample PCM float32 audio bytes for testing."""
    # Generate 1 second of 440Hz sine wave at 16kHz
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    return audio.astype(np.float32).tobytes()


@pytest.fixture
def sample_audio_array() -> np.ndarray:
    """Return sample audio as numpy array for testing."""
    # Generate 1 second of 440Hz sine wave at 16kHz
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    return 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)


@pytest.fixture
def silent_audio_bytes() -> bytes:
    """Return silent PCM float32 audio bytes for testing."""
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    return np.zeros(samples, dtype=np.float32).tobytes()


@pytest.fixture
def noisy_audio_bytes() -> bytes:
    """Return white noise PCM float32 audio bytes for testing."""
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    np.random.seed(42)  # Deterministic for testing
    noise = np.random.uniform(-0.5, 0.5, samples).astype(np.float32)
    return noise.tobytes()
