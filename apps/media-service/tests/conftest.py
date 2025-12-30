"""
Pytest fixtures for stream-orchestration service tests.

Includes fixtures for:
- FastAPI test client
- MediaMTX hook events
- GStreamer mocks (for unit tests)
- Socket.IO mocks (for STS client tests)
- Audio segment samples
- STS fragment mocks
"""

from __future__ import annotations

import base64
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from media_service.main import app

# =============================================================================
# FastAPI Test Client
# =============================================================================


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client fixture."""
    return TestClient(app)


# =============================================================================
# GStreamer Mocks (for unit tests without GStreamer installed)
# =============================================================================


@pytest.fixture
def mock_gst() -> Generator[MagicMock, None, None]:
    """Mock GStreamer for unit tests.

    This fixture mocks the gi.repository.Gst module to allow testing
    pipeline construction without requiring GStreamer to be installed.

    Usage:
        def test_something(mock_gst):
            mock_gst.Pipeline.return_value = MagicMock()
            # Test pipeline construction
    """
    with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock()}):
        mock_gi = MagicMock()
        mock_gst_module = MagicMock()

        # Mock common GStreamer types and constants
        mock_gst_module.Buffer = MagicMock()
        mock_gst_module.Pipeline = MagicMock()
        mock_gst_module.Element = MagicMock()
        mock_gst_module.ElementFactory = MagicMock()
        mock_gst_module.Caps = MagicMock()
        mock_gst_module.State = MagicMock()
        mock_gst_module.State.NULL = 0
        mock_gst_module.State.READY = 1
        mock_gst_module.State.PAUSED = 2
        mock_gst_module.State.PLAYING = 3
        mock_gst_module.StateChangeReturn = MagicMock()
        mock_gst_module.StateChangeReturn.SUCCESS = 1
        mock_gst_module.StateChangeReturn.ASYNC = 2
        mock_gst_module.StateChangeReturn.NO_PREROLL = 3
        mock_gst_module.FlowReturn = MagicMock()
        mock_gst_module.FlowReturn.OK = 0
        mock_gst_module.FlowReturn.EOS = 1
        mock_gst_module.FlowReturn.ERROR = -1

        # Mock init function
        mock_gst_module.init = MagicMock()

        mock_gi.repository.Gst = mock_gst_module
        mock_gi.repository.GstApp = MagicMock()

        with patch("gi.repository.Gst", mock_gst_module):
            yield mock_gst_module


@pytest.fixture
def mock_gst_buffer() -> MagicMock:
    """Create a mock GStreamer buffer with sample data.

    Returns:
        MagicMock configured to behave like a Gst.Buffer.
    """
    buffer = MagicMock()
    buffer.pts = 1_000_000_000  # 1 second in nanoseconds
    buffer.duration = 33_333_333  # ~30fps frame duration
    buffer.get_size.return_value = 1024

    # Mock buffer data extraction
    sample_data = b"\x00" * 1024
    map_info = MagicMock()
    map_info.data = sample_data
    buffer.map.return_value = (True, map_info)

    return buffer


# =============================================================================
# Socket.IO Mocks (for STS client tests)
# =============================================================================


@pytest.fixture
def mock_socketio() -> Generator[MagicMock, None, None]:
    """Mock Socket.IO AsyncClient for STS client tests.

    This fixture mocks the python-socketio AsyncClient to allow testing
    STS client behavior without a real Socket.IO server.

    Usage:
        def test_sts_client(mock_socketio):
            mock_socketio.connect = AsyncMock()
            # Test client behavior
    """
    with patch("socketio.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.emit = AsyncMock()
        mock_client.wait = AsyncMock()
        mock_client.connected = True

        # Store registered event handlers
        mock_client._handlers: dict[str, Any] = {}

        def on_handler(event: str):
            def decorator(func: Any) -> Any:
                mock_client._handlers[event] = func
                return func
            return decorator

        mock_client.on = on_handler
        mock_client.event = on_handler

        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_sts_stream_ready_response() -> dict:
    """Mock stream:ready response from STS service."""
    return {
        "stream_id": "test-stream",
        "session_id": "session-12345",
        "max_inflight": 3,
        "capabilities": {
            "batch_processing": False,
            "async_delivery": True,
        },
    }


@pytest.fixture
def mock_sts_fragment_ack_response() -> dict:
    """Mock fragment:ack response from STS service."""
    return {
        "fragment_id": "frag-001",
        "status": "queued",
        "queue_position": 0,
    }


@pytest.fixture
def mock_sts_fragment_processed_response() -> dict:
    """Mock fragment:processed response from STS service with dubbed audio."""
    # Create sample M4A data (minimal valid header)
    sample_m4a = b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41"

    return {
        "fragment_id": "frag-001",
        "stream_id": "test-stream",
        "sequence_number": 0,
        "status": "success",
        "dubbed_audio": {
            "format": "m4a",
            "sample_rate_hz": 48000,
            "channels": 2,
            "duration_ms": 6000,
            "data_base64": base64.b64encode(sample_m4a).decode(),
        },
        "transcript": "Hello world",
        "translated_text": "Hola mundo",
        "processing_time_ms": 1500,
        "stage_timings": {
            "asr_ms": 500,
            "translation_ms": 200,
            "tts_ms": 800,
        },
    }


@pytest.fixture
def mock_sts_backpressure_event() -> dict:
    """Mock backpressure event from STS service."""
    return {
        "stream_id": "test-stream",
        "severity": "medium",
        "current_inflight": 3,
        "queue_depth": 10,
        "action": "slow_down",
        "recommended_delay_ms": 500,
    }


@pytest.fixture
def mock_sts_error_response() -> dict:
    """Mock error response from STS service."""
    return {
        "error_id": "err-001",
        "stream_id": "test-stream",
        "fragment_id": "frag-001",
        "code": "TIMEOUT",
        "message": "Processing timeout exceeded",
        "severity": "warning",
        "retryable": True,
        "metadata": {
            "timeout_ms": 8000,
            "elapsed_ms": 8500,
        },
    }


# =============================================================================
# Audio Segment Samples
# =============================================================================


@pytest.fixture
def sample_m4a_audio() -> bytes:
    """Sample M4A audio data for testing.

    Returns minimal valid M4A file structure for testing audio processing.
    In real tests with fixtures, use actual audio files.
    """
    # Minimal ftyp box for M4A (AAC in MP4 container)
    ftyp = b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41"

    # Minimal moov box placeholder (not fully valid but sufficient for tests)
    moov = b"\x00\x00\x00\x08moov"

    # Minimal mdat box with silence (placeholder)
    mdat = b"\x00\x00\x00\x08mdat"

    return ftyp + moov + mdat


@pytest.fixture
def sample_pcm_audio() -> bytes:
    """Sample PCM audio data for testing (48kHz stereo, 16-bit).

    Returns 1 second of silence in PCM S16LE format.
    """
    # 48000 samples/sec * 2 channels * 2 bytes/sample = 192000 bytes per second
    return b"\x00" * 192000


# =============================================================================
# STS Fragment Test Data
# =============================================================================


@pytest.fixture
def mock_sts_fragment() -> dict:
    """Create a mock STS fragment for testing.

    Returns a dictionary representing an AudioSegment-like structure.
    """
    return {
        "fragment_id": "frag-001-uuid",
        "stream_id": "test-stream",
        "batch_number": 0,
        "t0_ns": 0,
        "duration_ns": 6_000_000_000,  # 6 seconds
        "file_path": "/tmp/test-stream/000000_audio.m4a",
        "file_size": 0,
    }


@pytest.fixture
def mock_video_segment() -> dict:
    """Create a mock video segment for testing."""
    return {
        "fragment_id": "frag-001-video-uuid",
        "stream_id": "test-stream",
        "batch_number": 0,
        "t0_ns": 0,
        "duration_ns": 6_000_000_000,  # 6 seconds
        "file_path": "/tmp/test-stream/000000_video.mp4",
        "file_size": 0,
    }


# =============================================================================
# Test Fixture Paths
# =============================================================================


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"


@pytest.fixture
def test_streams_dir(fixtures_dir: Path) -> Path:
    """Path to test streams fixture directory."""
    return fixtures_dir / "test-streams"


@pytest.fixture
def nfl_fixture_path(test_streams_dir: Path) -> Path:
    """Path to 1-min-nfl.mp4 test fixture."""
    return test_streams_dir / "1-min-nfl.mp4"


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================


@pytest.fixture
def tmp_segment_dir(tmp_path: Path) -> Path:
    """Create a temporary segment directory for tests."""
    segment_dir = tmp_path / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    return segment_dir


@pytest.fixture
def valid_ready_event() -> dict:
    """Valid ready event payload fixture."""
    return {
        "path": "live/test-stream/in",
        "query": "lang=es",
        "sourceType": "rtmp",
        "sourceId": "1",
    }


@pytest.fixture
def valid_not_ready_event() -> dict:
    """Valid not-ready event payload fixture."""
    return {
        "path": "live/test-stream/in",
        "query": None,
        "sourceType": "rtmp",
        "sourceId": "1",
    }


@pytest.fixture
def valid_ready_event_no_query() -> dict:
    """Valid ready event without query string."""
    return {
        "path": "live/stream123/in",
        "sourceType": "rtmp",
        "sourceId": "2",
    }


@pytest.fixture
def invalid_path_event() -> dict:
    """Invalid event with malformed path."""
    return {
        "path": "invalid/path",
        "sourceType": "rtmp",
        "sourceId": "1",
    }


@pytest.fixture
def invalid_source_type_event() -> dict:
    """Invalid event with unsupported source type."""
    return {
        "path": "live/test/in",
        "sourceType": "invalid",
        "sourceId": "1",
    }


@pytest.fixture
def mock_mtx_env_ready() -> dict:
    """Mock MediaMTX environment variables for ready hook."""
    return {
        "MTX_PATH": "live/test-stream/in",
        "MTX_QUERY": "lang=es",
        "MTX_SOURCE_TYPE": "rtmp",
        "MTX_SOURCE_ID": "1",
        "ORCHESTRATOR_URL": "http://stream-orchestration:8080",
    }


@pytest.fixture
def mock_mtx_env_not_ready() -> dict:
    """Mock MediaMTX environment variables for not-ready hook."""
    return {
        "MTX_PATH": "live/test-stream/in",
        "MTX_QUERY": "",
        "MTX_SOURCE_TYPE": "rtmp",
        "MTX_SOURCE_ID": "1",
        "ORCHESTRATOR_URL": "http://stream-orchestration:8080",
    }


@pytest.fixture
def mock_mtx_env_missing_path() -> dict:
    """Mock MediaMTX environment with missing MTX_PATH."""
    return {
        "MTX_QUERY": "",
        "MTX_SOURCE_TYPE": "rtmp",
        "MTX_SOURCE_ID": "1",
        "ORCHESTRATOR_URL": "http://stream-orchestration:8080",
    }
