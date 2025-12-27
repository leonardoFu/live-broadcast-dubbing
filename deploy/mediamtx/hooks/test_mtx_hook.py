"""
Unit tests for MediaMTX hook wrapper script.

These tests verify the hook script logic with mocked environment variables.
Coverage target: 100% (simple deterministic code, critical path).
"""

import json
import os
import sys
from typing import Dict
from unittest import mock

import pytest


# Import the hook script functions
# Since it's a script, we need to import it as a module
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util

spec = importlib.util.spec_from_file_location("mtx_hook", "mtx-hook")
mtx_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mtx_hook)


@pytest.mark.unit
class TestMTXHookEnvironmentParsing:
    """Test environment variable parsing."""

    def test_parse_mtx_env_happy_path(self) -> None:
        """Test happy path: valid environment variables → JSON payload."""
        with mock.patch.dict(os.environ, {
            "MTX_PATH": "live/test-stream/in",
            "MTX_QUERY": "lang=es",
            "MTX_SOURCE_TYPE": "rtmp",
            "MTX_SOURCE_ID": "1",
        }):
            payload = mtx_hook.parse_env_vars()

            assert payload["path"] == "live/test-stream/in"
            assert payload["query"] == "lang=es"
            assert payload["sourceType"] == "rtmp"
            assert payload["sourceId"] == "1"

    def test_parse_mtx_env_no_query(self) -> None:
        """Test edge case: empty MTX_QUERY → excluded from payload."""
        with mock.patch.dict(os.environ, {
            "MTX_PATH": "live/test-stream/in",
            "MTX_QUERY": "",
            "MTX_SOURCE_TYPE": "rtmp",
            "MTX_SOURCE_ID": "1",
        }, clear=True):
            payload = mtx_hook.parse_env_vars()

            assert payload["path"] == "live/test-stream/in"
            assert "query" not in payload
            assert payload["sourceType"] == "rtmp"
            assert payload["sourceId"] == "1"

    def test_parse_mtx_env_missing_path(self) -> None:
        """Test error case: missing MTX_PATH → error with clear message."""
        with mock.patch.dict(os.environ, {
            "MTX_QUERY": "",
            "MTX_SOURCE_TYPE": "rtmp",
            "MTX_SOURCE_ID": "1",
        }, clear=True):
            with pytest.raises(ValueError, match="MTX_PATH environment variable is required"):
                mtx_hook.parse_env_vars()

    def test_parse_mtx_env_missing_source_type(self) -> None:
        """Test error case: missing MTX_SOURCE_TYPE → error."""
        with mock.patch.dict(os.environ, {
            "MTX_PATH": "live/test/in",
            "MTX_SOURCE_ID": "1",
        }, clear=True):
            with pytest.raises(ValueError, match="MTX_SOURCE_TYPE environment variable is required"):
                mtx_hook.parse_env_vars()

    def test_parse_mtx_env_missing_source_id(self) -> None:
        """Test error case: missing MTX_SOURCE_ID → error."""
        with mock.patch.dict(os.environ, {
            "MTX_PATH": "live/test/in",
            "MTX_SOURCE_TYPE": "rtmp",
        }, clear=True):
            with pytest.raises(ValueError, match="MTX_SOURCE_ID environment variable is required"):
                mtx_hook.parse_env_vars()


@pytest.mark.unit
class TestMTXHookURLConstruction:
    """Test ORCHESTRATOR_URL construction."""

    def test_construct_url_ready_event(self) -> None:
        """Test URL construction for ready event."""
        with mock.patch.dict(os.environ, {
            "ORCHESTRATOR_URL": "http://stream-orchestration:8080",
        }):
            url = mtx_hook.construct_endpoint_url("ready")
            assert url == "http://stream-orchestration:8080/v1/mediamtx/events/ready"

    def test_construct_url_not_ready_event(self) -> None:
        """Test URL construction for not-ready event."""
        with mock.patch.dict(os.environ, {
            "ORCHESTRATOR_URL": "http://stream-orchestration:8080",
        }):
            url = mtx_hook.construct_endpoint_url("not-ready")
            assert url == "http://stream-orchestration:8080/v1/mediamtx/events/not-ready"

    def test_construct_url_trailing_slash(self) -> None:
        """Test URL construction handles trailing slash."""
        with mock.patch.dict(os.environ, {
            "ORCHESTRATOR_URL": "http://stream-orchestration:8080/",
        }):
            url = mtx_hook.construct_endpoint_url("ready")
            assert url == "http://stream-orchestration:8080/v1/mediamtx/events/ready"
            assert "//" not in url.replace("http://", "")

    def test_construct_url_missing_orchestrator_url(self) -> None:
        """Test error case: missing ORCHESTRATOR_URL → error."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="ORCHESTRATOR_URL environment variable is required"):
                mtx_hook.construct_endpoint_url("ready")


@pytest.mark.unit
class TestMTXHookHTTPClient:
    """Test HTTP POST request logic."""

    def test_send_hook_event_success(self) -> None:
        """Test successful HTTP POST request."""
        payload = {"path": "live/test/in", "sourceType": "rtmp", "sourceId": "1"}
        endpoint_url = "http://stream-orchestration:8080/v1/mediamtx/events/ready"

        # Mock urllib.request.urlopen
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.Mock()
            mock_response.getcode.return_value = 200
            mock_response.__enter__.return_value = mock_response
            mock_response.__exit__.return_value = None
            mock_urlopen.return_value = mock_response

            # Should not raise exception
            mtx_hook.send_hook_event(endpoint_url, payload)

            # Verify HTTP request was made
            assert mock_urlopen.called

    def test_send_hook_event_http_error(self) -> None:
        """Test HTTP error handling."""
        payload = {"path": "live/test/in", "sourceType": "rtmp", "sourceId": "1"}
        endpoint_url = "http://stream-orchestration:8080/v1/mediamtx/events/ready"

        # Mock HTTP 500 error
        import urllib.error
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url=endpoint_url,
                code=500,
                msg="Internal Server Error",
                hdrs={},
                fp=None,
            )

            with pytest.raises(Exception, match="HTTP error 500"):
                mtx_hook.send_hook_event(endpoint_url, payload)

    def test_send_hook_event_network_error(self) -> None:
        """Test network error handling."""
        payload = {"path": "live/test/in", "sourceType": "rtmp", "sourceId": "1"}
        endpoint_url = "http://stream-orchestration:8080/v1/mediamtx/events/ready"

        # Mock network error
        import urllib.error
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            with pytest.raises(Exception, match="Network error"):
                mtx_hook.send_hook_event(endpoint_url, payload)


@pytest.mark.unit
class TestMTXHookMain:
    """Test main entry point."""

    def test_main_success_ready_event(self) -> None:
        """Test main with ready event."""
        with mock.patch.dict(os.environ, {
            "MTX_PATH": "live/test/in",
            "MTX_SOURCE_TYPE": "rtmp",
            "MTX_SOURCE_ID": "1",
            "ORCHESTRATOR_URL": "http://stream-orchestration:8080",
        }):
            with mock.patch("sys.argv", ["mtx-hook", "ready"]):
                with mock.patch("urllib.request.urlopen") as mock_urlopen:
                    mock_response = mock.Mock()
                    mock_response.getcode.return_value = 200
                    mock_response.__enter__.return_value = mock_response
                    mock_response.__exit__.return_value = None
                    mock_urlopen.return_value = mock_response

                    exit_code = mtx_hook.main()
                    assert exit_code == 0

    def test_main_missing_event_type_argument(self) -> None:
        """Test main with missing event type argument."""
        with mock.patch("sys.argv", ["mtx-hook"]):
            exit_code = mtx_hook.main()
            assert exit_code == 1

    def test_main_invalid_event_type(self) -> None:
        """Test main with invalid event type."""
        with mock.patch("sys.argv", ["mtx-hook", "invalid"]):
            exit_code = mtx_hook.main()
            assert exit_code == 1

    def test_main_missing_env_vars(self) -> None:
        """Test main with missing environment variables."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("sys.argv", ["mtx-hook", "ready"]):
                exit_code = mtx_hook.main()
                assert exit_code == 1

    def test_main_http_failure(self) -> None:
        """Test main with HTTP request failure."""
        with mock.patch.dict(os.environ, {
            "MTX_PATH": "live/test/in",
            "MTX_SOURCE_TYPE": "rtmp",
            "MTX_SOURCE_ID": "1",
            "ORCHESTRATOR_URL": "http://stream-orchestration:8080",
        }):
            with mock.patch("sys.argv", ["mtx-hook", "ready"]):
                import urllib.error
                with mock.patch("urllib.request.urlopen") as mock_urlopen:
                    mock_urlopen.side_effect = urllib.error.HTTPError(
                        url="http://stream-orchestration:8080/v1/mediamtx/events/ready",
                        code=500,
                        msg="Internal Server Error",
                        hdrs={},
                        fp=None,
                    )

                    exit_code = mtx_hook.main()
                    assert exit_code == 1
