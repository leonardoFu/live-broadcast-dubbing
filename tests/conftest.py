"""
Global pytest fixtures for integration tests.
"""

import pytest


@pytest.fixture
def mediamtx_base_url() -> str:
    """MediaMTX base URL for integration tests."""
    return "http://localhost"


@pytest.fixture
def mediamtx_rtmp_url() -> str:
    """MediaMTX RTMP publish URL."""
    return "rtmp://localhost:1935"


@pytest.fixture
def mediamtx_rtsp_url() -> str:
    """MediaMTX RTSP read URL."""
    return "rtsp://localhost:8554"


@pytest.fixture
def mediamtx_api_url() -> str:
    """MediaMTX Control API URL."""
    return "http://localhost:9997"


@pytest.fixture
def mediamtx_metrics_url() -> str:
    """MediaMTX Prometheus metrics URL."""
    return "http://localhost:9998"


@pytest.fixture
def orchestrator_url() -> str:
    """Stream orchestration service URL."""
    return "http://localhost:8080"


@pytest.fixture
def test_stream_id() -> str:
    """Test stream ID for integration tests."""
    return "test-stream"


@pytest.fixture
def test_stream_path_in(test_stream_id: str) -> str:
    """Test stream input path."""
    return f"live/{test_stream_id}/in"


@pytest.fixture
def test_stream_path_out(test_stream_id: str) -> str:
    """Test stream output path."""
    return f"live/{test_stream_id}/out"
