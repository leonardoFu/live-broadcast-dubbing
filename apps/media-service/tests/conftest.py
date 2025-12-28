"""
Pytest fixtures for stream-orchestration service tests.
"""

import pytest
from fastapi.testclient import TestClient

from media_service.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client fixture."""
    return TestClient(app)


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
