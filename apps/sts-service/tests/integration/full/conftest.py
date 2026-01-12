"""
Shared fixtures for Full STS integration tests.

Provides fixtures for testing with real ASR, Translation, and TTS modules.
"""

import base64
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest
from sts_service.full.models.asset import AssetStatus, DurationMatchMetadata
from sts_service.full.models.fragment import AudioData, FragmentData, FragmentMetadata
from sts_service.full.models.stream import StreamConfig, StreamSession, StreamState

# Path to test fixtures directory (shared with e2e tests)
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent.parent / "tests" / "fixtures" / "test-streams"
)


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


@pytest.fixture
def sample_stream_session() -> StreamSession:
    """Create a sample StreamSession for testing."""
    return StreamSession(
        stream_id="stream-integration-test",
        session_id="session-int-001",
        worker_id="worker-test",
        socket_id="sid-test-12345",
        config=StreamConfig(
            source_language="en",
            target_language="es",
            voice_profile="default",
            chunk_duration_ms=6000,
            sample_rate_hz=16000,  # Use 16kHz for ASR compatibility
            channels=1,
            format="pcm_s16le",
            domain_hints=["sports"],
        ),
        state=StreamState.READY,
        max_inflight=3,
    )


@pytest.fixture
def create_fragment_data() -> Callable[[bytes, str, int, int], FragmentData]:
    """
    Factory fixture to create FragmentData from audio bytes.

    Args:
        audio_bytes: Raw PCM audio bytes
        fragment_id: Fragment identifier
        sequence_number: Sequence number in stream
        duration_ms: Audio duration in milliseconds

    Returns:
        FragmentData instance
    """

    def _create(
        audio_bytes: bytes,
        fragment_id: str = "frag-001",
        sequence_number: int = 0,
        duration_ms: int = 6000,
        sample_rate_hz: int = 16000,
    ) -> FragmentData:
        """Create FragmentData from audio bytes."""
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return FragmentData(
            fragment_id=fragment_id,
            stream_id="stream-integration-test",
            sequence_number=sequence_number,
            timestamp=1704067200000 + (sequence_number * duration_ms),
            audio=AudioData(
                format="pcm_f32le",
                sample_rate_hz=sample_rate_hz,
                channels=1,
                duration_ms=duration_ms,
                data_base64=audio_b64,
            ),
            metadata=FragmentMetadata(pts_ns=sequence_number * duration_ms * 1_000_000),
        )

    return _create


@pytest.fixture
def mock_translation_component():
    """Create a mock Translation component that returns SUCCESS.

    Used when testing ASR integration without requiring DeepL API key.
    """
    mock = MagicMock()
    mock.component_name = "translate"
    mock.component_instance = "mock-translate-v1"
    mock.is_ready = True

    def translate_side_effect(source_text: str, *args: Any, **kwargs: Any) -> MagicMock:
        """Return translated text (mock Spanish translation)."""
        result = MagicMock()
        result.asset_id = f"trans-asset-{hash(source_text) % 10000:04d}"
        result.fragment_id = kwargs.get("fragment_id", "frag-001")
        result.stream_id = kwargs.get("stream_id", "stream-test")
        result.status = AssetStatus.SUCCESS
        result.translated_text = f"[ES] {source_text}"  # Mock translation
        result.source_text = source_text
        result.source_language = "en"
        result.target_language = "es"
        result.character_count = len(source_text)
        result.word_expansion_ratio = 1.2
        result.latency_ms = 50
        result.parent_asset_ids = kwargs.get("parent_asset_ids", [])
        result.error_message = None
        return result

    mock.translate.side_effect = translate_side_effect
    return mock


@pytest.fixture
def mock_tts_component():
    """Create a mock TTS component that returns SUCCESS.

    Used when testing without requiring TTS model download.
    """
    mock = MagicMock()
    mock.component_name = "tts"
    mock.component_instance = "mock-tts-v1"
    mock.is_ready = True

    def synthesize_side_effect(
        text_asset: Any, target_duration_ms: int | None = None, **kwargs: Any
    ) -> MagicMock:
        """Return synthesized audio (silence)."""
        duration_ms = target_duration_ms or 6000
        sample_rate = kwargs.get("output_sample_rate_hz", 16000)

        # Generate silence audio
        samples = int(sample_rate * duration_ms / 1000)
        audio_bytes = b"\x00\x00" * samples

        result = MagicMock()
        result.asset_id = "audio-asset-mock"
        result.fragment_id = getattr(text_asset, "fragment_id", "frag-001")
        result.stream_id = getattr(text_asset, "stream_id", "stream-test")
        result.status = AssetStatus.SUCCESS
        result.audio_bytes = audio_bytes
        result.format = "pcm_s16le"
        result.sample_rate_hz = sample_rate
        result.channels = kwargs.get("output_channels", 1)
        result.duration_ms = duration_ms
        result.duration_metadata = DurationMatchMetadata(
            original_duration_ms=duration_ms,
            raw_duration_ms=duration_ms + 50,
            final_duration_ms=duration_ms,
            duration_variance_percent=0.83,
            speed_ratio=1.0,
            speed_clamped=False,
        )
        result.voice_profile = "default"
        result.text_input = getattr(text_asset, "translated_text", "")
        result.latency_ms = 100
        result.parent_asset_ids = [getattr(text_asset, "asset_id", "")]
        result.error_message = None
        return result

    mock.synthesize.side_effect = synthesize_side_effect
    return mock


def check_gpu_available() -> bool:
    """Check if CUDA GPU is available."""
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


def check_faster_whisper_available() -> bool:
    """Check if faster-whisper is available."""
    try:
        from faster_whisper import WhisperModel  # noqa: F401

        return True
    except ImportError:
        return False


def check_deepl_key_available() -> bool:
    """Check if DeepL API key is available."""
    import os

    return bool(os.environ.get("DEEPL_AUTH_KEY"))


def check_coqui_available() -> bool:
    """Check if Coqui TTS is available."""
    try:
        from TTS.api import TTS  # noqa: F401

        return True
    except ImportError:
        return False


# Pytest markers for skipping tests
requires_gpu = pytest.mark.skipif(
    not check_gpu_available(),
    reason="GPU not available (CUDA required)",
)

requires_faster_whisper = pytest.mark.skipif(
    not check_faster_whisper_available(),
    reason="faster-whisper not installed",
)

requires_deepl_key = pytest.mark.skipif(
    not check_deepl_key_available(),
    reason="DEEPL_AUTH_KEY environment variable not set",
)

requires_coqui = pytest.mark.skipif(
    not check_coqui_available(),
    reason="Coqui TTS not installed",
)
