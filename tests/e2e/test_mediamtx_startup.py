"""
E2E tests for MediaMTX service startup and health.

Tests verify that MediaMTX starts successfully via Docker Compose and
all endpoints (Control API, Metrics, RTMP, RTSP) are accessible.
"""

import httpx
import pytest


@pytest.mark.e2e
class TestMediaMTXStartup:
    """Test MediaMTX service startup and basic health checks."""

    def test_mediamtx_container_is_running(self, docker_services: None) -> None:
        """Test that MediaMTX container is running after docker-compose up."""
        import subprocess

        result = subprocess.run(
            ["docker", "ps", "--filter", "name=mediamtx", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True,
        )

        assert "Up" in result.stdout, "MediaMTX container should be running"

    def test_mediamtx_control_api_accessible(
        self,
        docker_services: None,
        http_client_with_auth: httpx.Client,
        mediamtx_control_api_url: str,
    ) -> None:
        """Test MediaMTX Control API is accessible on port 9997 (FR-008)."""
        response = http_client_with_auth.get(f"{mediamtx_control_api_url}/v3/paths/list")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_mediamtx_control_api_returns_valid_json(
        self,
        docker_services: None,
        http_client_with_auth: httpx.Client,
        mediamtx_control_api_url: str,
    ) -> None:
        """Test MediaMTX Control API returns valid JSON structure (FR-008)."""
        response = http_client_with_auth.get(f"{mediamtx_control_api_url}/v3/paths/list")
        data = response.json()

        assert "items" in data, "Response should contain 'items' field"
        assert isinstance(data["items"], list), "'items' should be a list"

    def test_mediamtx_prometheus_metrics_accessible(
        self,
        docker_services: None,
        http_client_with_auth: httpx.Client,
        mediamtx_metrics_url: str,
    ) -> None:
        """Test MediaMTX Prometheus metrics endpoint is accessible on port 9998 (FR-009)."""
        response = http_client_with_auth.get(f"{mediamtx_metrics_url}/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_mediamtx_prometheus_metrics_contain_expected_metrics(
        self,
        docker_services: None,
        http_client_with_auth: httpx.Client,
        mediamtx_metrics_url: str,
    ) -> None:
        """Test MediaMTX Prometheus metrics contain expected metrics (FR-009)."""
        response = http_client_with_auth.get(f"{mediamtx_metrics_url}/metrics")
        metrics_text = response.text

        # Check for key metrics (case-insensitive)
        metrics_lower = metrics_text.lower()
        assert "paths" in metrics_lower
        assert "rtmp" in metrics_lower

    def test_mediamtx_control_api_response_time(
        self,
        docker_services: None,
        http_client_with_auth: httpx.Client,
        mediamtx_control_api_url: str,
    ) -> None:
        """Test MediaMTX Control API responds within 100ms (SC-006)."""
        import time

        start = time.time()
        response = http_client_with_auth.get(f"{mediamtx_control_api_url}/v3/paths/list")
        duration_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration_ms < 100, f"Control API should respond in <100ms, took {duration_ms:.2f}ms"

    def test_mediamtx_metrics_response_time(
        self,
        docker_services: None,
        http_client_with_auth: httpx.Client,
        mediamtx_metrics_url: str,
    ) -> None:
        """Test MediaMTX Prometheus metrics respond within 100ms (SC-007)."""
        import time

        start = time.time()
        response = http_client_with_auth.get(f"{mediamtx_metrics_url}/metrics")
        duration_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration_ms < 100, f"Metrics should respond in <100ms, took {duration_ms:.2f}ms"


@pytest.mark.e2e
@pytest.mark.slow
class TestMediaMTXPorts:
    """Test that all MediaMTX ports are properly exposed."""

    def test_rtmp_port_listening(self, docker_services: None) -> None:
        """Test RTMP port 1935 is listening (FR-002)."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", 1935))
        sock.close()

        assert result == 0, "RTMP port 1935 should be listening"

    def test_rtsp_port_listening(self, docker_services: None) -> None:
        """Test RTSP port 8554 is listening (FR-003)."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", 8554))
        sock.close()

        assert result == 0, "RTSP port 8554 should be listening"

    def test_control_api_port_listening(self, docker_services: None) -> None:
        """Test Control API port 9997 is listening (FR-008)."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", 9997))
        sock.close()

        assert result == 0, "Control API port 9997 should be listening"

    def test_metrics_port_listening(self, docker_services: None) -> None:
        """Test Prometheus metrics port 9998 is listening (FR-009)."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", 9998))
        sock.close()

        assert result == 0, "Metrics port 9998 should be listening"

    def test_playback_port_listening(self, docker_services: None) -> None:
        """Test Playback server port 9996 is listening (FR-010)."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", 9996))
        sock.close()

        assert result == 0, "Playback port 9996 should be listening"
