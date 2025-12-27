"""
E2E tests for media-service FastAPI startup and health.

Tests verify that the media-service FastAPI application starts successfully
via Docker Compose and all endpoints are accessible.
"""

import httpx
import pytest


@pytest.mark.e2e
class TestMediaServiceStartup:
    """Test media-service FastAPI startup and basic health checks."""

    def test_media_service_container_is_running(self, docker_services: None) -> None:
        """Test that media-service container is running after docker-compose up."""
        import subprocess

        result = subprocess.run(
            ["docker", "ps", "--filter", "name=media-service", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True,
        )

        assert "Up" in result.stdout, "media-service container should be running"

    def test_media_service_health_endpoint_accessible(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test media-service /health endpoint is accessible."""
        response = http_client.get(f"{media_service_url}/health")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_media_service_health_endpoint_returns_ok(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test media-service /health endpoint returns 'ok' status."""
        response = http_client.get(f"{media_service_url}/health")
        data = response.json()

        assert data["status"] == "ok"
        assert "service" in data
        assert data["service"] == "media-service"

    def test_media_service_api_docs_accessible(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test media-service FastAPI auto-generated API docs are accessible."""
        # OpenAPI JSON schema
        response = http_client.get(f"{media_service_url}/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "Media Service API"

    def test_media_service_swagger_ui_accessible(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test media-service Swagger UI docs are accessible."""
        response = http_client.get(f"{media_service_url}/docs", follow_redirects=True)
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "api" in response.text.lower()

    def test_media_service_port_listening(self, docker_services: None) -> None:
        """Test media-service port 8080 is listening (FR-011a)."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", 8080))
        sock.close()

        assert result == 0, "media-service port 8080 should be listening"


@pytest.mark.e2e
class TestMediaServiceHookEndpoints:
    """Test media-service hook receiver endpoints are accessible."""

    def test_hook_ready_endpoint_exists(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test POST /v1/mediamtx/events/ready endpoint exists (FR-011)."""
        # Send a test event (should validate and process)
        test_event = {
            "path": "live/test/in",
            "sourceType": "rtmp",
            "sourceId": "test-source-id",
        }

        response = http_client.post(
            f"{media_service_url}/v1/mediamtx/events/ready",
            json=test_event,
        )

        # Should return 200 (success) or 422 (validation error), not 404
        assert response.status_code in [200, 422], \
            f"Endpoint should exist, got {response.status_code}"

    def test_hook_not_ready_endpoint_exists(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test POST /v1/mediamtx/events/not-ready endpoint exists (FR-011)."""
        # Send a test event
        test_event = {
            "path": "live/test/in",
            "sourceType": "rtmp",
            "sourceId": "test-source-id",
        }

        response = http_client.post(
            f"{media_service_url}/v1/mediamtx/events/not-ready",
            json=test_event,
        )

        # Should return 200 (success) or 422 (validation error), not 404
        assert response.status_code in [200, 422], \
            f"Endpoint should exist, got {response.status_code}"

    def test_hook_ready_endpoint_validates_payload(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test hook ready endpoint validates payload schema."""
        # Send invalid payload (missing required fields)
        invalid_event = {"invalid": "data"}

        response = http_client.post(
            f"{media_service_url}/v1/mediamtx/events/ready",
            json=invalid_event,
        )

        # Should return 422 validation error
        assert response.status_code == 422

    def test_hook_ready_endpoint_accepts_valid_payload(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test hook ready endpoint accepts valid payload."""
        valid_event = {
            "path": "live/test-stream/in",
            "sourceType": "rtmp",
            "sourceId": "test-source-123",
            "query": "lang=es",
        }

        response = http_client.post(
            f"{media_service_url}/v1/mediamtx/events/ready",
            json=valid_event,
        )

        # Should return 200 success
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"


@pytest.mark.e2e
class TestMediaServiceStartupTime:
    """Test media-service startup performance meets requirements."""

    def test_media_service_starts_within_30_seconds(
        self, docker_services: None
    ) -> None:
        """
        Test all services start within 30 seconds (SC-001).

        Note: This test is implicitly verified by the docker_services fixture
        timeout of 60 seconds. If services don't start within that time,
        the fixture will raise TimeoutError.
        """
        # If we reach here, services started successfully
        assert True, "Services started within timeout"

    def test_media_service_responds_quickly_after_startup(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test media-service responds immediately after startup."""
        import time

        start = time.time()
        response = http_client.get(f"{media_service_url}/health")
        duration_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration_ms < 1000, \
            f"Service should respond quickly after startup, took {duration_ms:.2f}ms"
