"""
Integration tests for MediaMTX and stream-orchestration service startup.

Tests SC-001: Services start within 30 seconds.
Tests FR-008, FR-009, FR-011a: API and metrics endpoints are reachable.
"""

import subprocess
import time
from typing import Generator

import pytest
import requests


@pytest.mark.integration
class TestLocalEnvironmentStartup:
    """Test local development environment startup."""

    @pytest.fixture(scope="class")
    def docker_compose_up(self) -> Generator[None, None, None]:
        """Start Docker Compose services for integration tests."""
        # Start services
        subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.yml", "up", "-d"],
            check=True,
            cwd="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud",
        )

        # Wait for services to be ready
        time.sleep(10)

        yield

        # Tear down services
        subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.yml", "down"],
            check=False,
            cwd="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud",
        )

    def test_services_start_within_timeout(self, docker_compose_up: None) -> None:
        """Test all services start within 30 seconds (SC-001)."""
        start_time = time.time()
        timeout = 30

        # Check MediaMTX API
        mediamtx_ready = False
        orchestrator_ready = False

        while time.time() - start_time < timeout:
            try:
                # Check MediaMTX Control API
                response = requests.get("http://localhost:9997/v3/paths/list", timeout=2)
                if response.status_code == 200:
                    mediamtx_ready = True

                # Check stream-orchestration health
                response = requests.get("http://localhost:8080/health", timeout=2)
                if response.status_code == 200:
                    orchestrator_ready = True

                if mediamtx_ready and orchestrator_ready:
                    break

            except (requests.ConnectionError, requests.Timeout):
                time.sleep(1)
                continue

        elapsed_time = time.time() - start_time

        assert mediamtx_ready, f"MediaMTX Control API not ready after {elapsed_time:.1f}s"
        assert orchestrator_ready, f"stream-orchestration not ready after {elapsed_time:.1f}s"
        assert elapsed_time < timeout, f"Services took {elapsed_time:.1f}s to start (expected <{timeout}s)"

    def test_mediamtx_control_api_reachable(
        self, docker_compose_up: None, mediamtx_api_url: str
    ) -> None:
        """Test MediaMTX Control API is reachable at localhost:9997 (FR-008)."""
        response = requests.get(f"{mediamtx_api_url}/v3/paths/list", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_mediamtx_metrics_reachable(
        self, docker_compose_up: None, mediamtx_metrics_url: str
    ) -> None:
        """Test MediaMTX Prometheus metrics reachable at localhost:9998 (FR-009)."""
        response = requests.get(f"{mediamtx_metrics_url}/metrics", timeout=5)
        assert response.status_code == 200
        assert "mediamtx" in response.text.lower() or "paths" in response.text.lower()

    def test_stream_orchestration_reachable(
        self, docker_compose_up: None, orchestrator_url: str
    ) -> None:
        """Test stream-orchestration service reachable at localhost:8080 (FR-011a)."""
        response = requests.get(f"{orchestrator_url}/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"

    def test_services_stop_cleanly(self) -> None:
        """Test services stop cleanly within 10 seconds."""
        start_time = time.time()

        result = subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.yml", "down"],
            check=True,
            cwd="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud",
            capture_output=True,
        )

        elapsed_time = time.time() - start_time

        assert result.returncode == 0, "Docker Compose down failed"
        assert elapsed_time < 10, f"Services took {elapsed_time:.1f}s to stop (expected <10s)"
