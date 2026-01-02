"""
Shared fixtures for ASR integration tests.

Provides access to audio test fixtures and audio loading utilities.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

# Path to test fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "tests" / "fixtures" / "test-streams"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def nfl_audio_path(fixtures_dir: Path) -> Path:
    """Return the path to the NFL audio fixture (1-min-nfl.m4a)."""
    path = fixtures_dir / "1-min-nfl.m4a"
    if not path.exists():
        pytest.skip(f"NFL audio fixture not found: {path}")
    return path


@pytest.fixture
def nfl_video_path(fixtures_dir: Path) -> Path:
    """Return the path to the NFL video fixture (1-min-nfl.mp4)."""
    path = fixtures_dir / "1-min-nfl.mp4"
    if not path.exists():
        pytest.skip(f"NFL video fixture not found: {path}")
    return path


@pytest.fixture
def bunny_video_path(fixtures_dir: Path) -> Path:
    """Return the path to the Big Buck Bunny video fixture."""
    path = fixtures_dir / "big-buck-bunny.mp4"
    if not path.exists():
        pytest.skip(f"Big Buck Bunny fixture not found: {path}")
    return path


@pytest.fixture
def load_audio_fragment() -> Callable[[Path, int, int, int], bytes]:
    """
    Return a function that loads an audio fragment from a file.

    The function extracts a segment of audio and returns PCM float32 bytes.

    Args:
        path: Path to audio/video file
        start_ms: Start time in milliseconds
        duration_ms: Duration in milliseconds
        sample_rate: Target sample rate (default 16000)

    Returns:
        PCM float32 bytes (mono, little-endian)
    """

    def _load_fragment(
        path: Path,
        start_ms: int,
        duration_ms: int,
        sample_rate: int = 16000,
    ) -> bytes:
        """Extract audio fragment using ffmpeg and return as PCM float32 bytes."""
        start_seconds = start_ms / 1000.0
        duration_seconds = duration_ms / 1000.0

        # Use ffmpeg to extract audio and convert to PCM float32
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_seconds),
            "-t",
            str(duration_seconds),
            "-i",
            str(path),
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "pipe:1",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg failed: {e.stderr.decode()}") from e
        except FileNotFoundError:
            pytest.skip("ffmpeg not installed")

    return _load_fragment


@pytest.fixture
def load_audio_array() -> Callable[[Path, int, int, int], np.ndarray]:
    """
    Return a function that loads an audio fragment as a numpy array.

    Args:
        path: Path to audio/video file
        start_ms: Start time in milliseconds
        duration_ms: Duration in milliseconds
        sample_rate: Target sample rate (default 16000)

    Returns:
        numpy array of float32 samples
    """

    def _load_array(
        path: Path,
        start_ms: int,
        duration_ms: int,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """Extract audio fragment and return as numpy array."""
        start_seconds = start_ms / 1000.0
        duration_seconds = duration_ms / 1000.0

        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_seconds),
            "-t",
            str(duration_seconds),
            "-i",
            str(path),
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "pipe:1",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
            )
            return np.frombuffer(result.stdout, dtype=np.float32)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg failed: {e.stderr.decode()}") from e
        except FileNotFoundError:
            pytest.skip("ffmpeg not installed")

    return _load_array


@pytest.fixture
def generate_synthetic_audio() -> Callable[[float, int, int], bytes]:
    """
    Return a function that generates synthetic audio for testing.

    Args:
        duration_seconds: Duration of audio
        sample_rate: Sample rate (default 16000)
        frequency_hz: Frequency of sine wave (default 440)

    Returns:
        PCM float32 bytes
    """

    def _generate(
        duration_seconds: float,
        sample_rate: int = 16000,
        frequency_hz: int = 440,
    ) -> bytes:
        """Generate a sine wave audio fragment."""
        t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), dtype=np.float32)
        audio = 0.5 * np.sin(2 * np.pi * frequency_hz * t)
        return audio.astype(np.float32).tobytes()

    return _generate


@pytest.fixture
def generate_silence() -> Callable[[float, int], bytes]:
    """
    Return a function that generates silent audio.

    Args:
        duration_seconds: Duration of silence
        sample_rate: Sample rate (default 16000)

    Returns:
        PCM float32 bytes (all zeros)
    """

    def _generate(
        duration_seconds: float,
        sample_rate: int = 16000,
    ) -> bytes:
        """Generate silent audio."""
        samples = int(sample_rate * duration_seconds)
        audio = np.zeros(samples, dtype=np.float32)
        return audio.tobytes()

    return _generate
