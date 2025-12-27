"""
E2E tests for service-to-service communication.

Tests verify that MediaMTX and media-service can communicate with each other
through the Docker network.
"""

import subprocess

import httpx
import pytest


@pytest.mark.e2e
class TestServiceCommunication:
    """Test communication between MediaMTX and media-service."""

    def test_mediamtx_can_reach_media_service(self, docker_services: None) -> None:
        """Test MediaMTX container can reach media-service via Docker network (FR-006a)."""
        # Execute curl from inside MediaMTX container to media-service
        result = subprocess.run(
            [
                "docker",
                "exec",
                "mediamtx",
                "wget",
                "-q",
                "-O",
                "-",
                "http://media-service:8080/health",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, \
            f"MediaMTX should be able to reach media-service. Error: {result.stderr}"
        assert "ok" in result.stdout.lower(), "Should receive valid health response"

    def test_mediamtx_can_reach_media_service_hook_endpoint(
        self, docker_services: None
    ) -> None:
        """Test MediaMTX can reach media-service hook endpoint (FR-007)."""
        # Test the ready endpoint that MediaMTX hooks will use
        test_payload = '{"path":"live/test/in","sourceType":"rtmp","sourceId":"test"}'

        result = subprocess.run(
            [
                "docker",
                "exec",
                "mediamtx",
                "wget",
                "-q",
                "-O",
                "-",
                "--header=Content-Type: application/json",
                f"--post-data={test_payload}",
                "http://media-service:8080/v1/mediamtx/events/ready",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, \
            f"MediaMTX should be able to POST to hook endpoint. Error: {result.stderr}"
        assert "received" in result.stdout.lower(), \
            "Should receive hook event acknowledgment"

    def test_media_service_can_reach_mediamtx_control_api(
        self, docker_services: None
    ) -> None:
        """Test media-service can reach MediaMTX Control API via Docker network."""
        # Execute curl from inside media-service container to MediaMTX
        result = subprocess.run(
            [
                "docker",
                "exec",
                "media-service",
                "wget",
                "-q",
                "-O",
                "-",
                "--user=admin",
                "--password=admin",
                "http://mediamtx:9997/v3/paths/list",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, \
            f"media-service should be able to reach MediaMTX. Error: {result.stderr}"
        assert "items" in result.stdout, "Should receive valid Control API response"

    def test_services_on_same_docker_network(self, docker_services: None) -> None:
        """Test that both services are on the same Docker network (dubbing-network)."""
        # Check MediaMTX network
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "mediamtx",
                "--format",
                "{{range $key, $value := .NetworkSettings.Networks}}{{$key}}{{end}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        mediamtx_network = result.stdout.strip()

        # Check media-service network
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "media-service",
                "--format",
                "{{range $key, $value := .NetworkSettings.Networks}}{{$key}}{{end}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        media_service_network = result.stdout.strip()

        assert mediamtx_network == media_service_network, \
            "Services should be on the same Docker network"
        assert "dubbing-network" in mediamtx_network, \
            "Services should be on dubbing-network"


@pytest.mark.e2e
class TestEnvironmentVariables:
    """Test that environment variables are correctly configured."""

    def test_mediamtx_has_orchestrator_url_env_var(
        self, docker_services: None
    ) -> None:
        """Test MediaMTX container has ORCHESTRATOR_URL environment variable (FR-006a)."""
        result = subprocess.run(
            ["docker", "exec", "mediamtx", "printenv", "ORCHESTRATOR_URL"],
            capture_output=True,
            text=True,
            check=True,
        )

        orchestrator_url = result.stdout.strip()
        assert orchestrator_url == "http://media-service:8080", \
            f"ORCHESTRATOR_URL should be http://media-service:8080, got {orchestrator_url}"

    def test_media_service_has_correct_port_env_var(
        self, docker_services: None
    ) -> None:
        """Test media-service has correct PORT environment variable."""
        result = subprocess.run(
            ["docker", "exec", "media-service", "printenv", "PORT"],
            capture_output=True,
            text=True,
            check=True,
        )

        port = result.stdout.strip()
        assert port == "8080", f"PORT should be 8080, got {port}"


@pytest.mark.e2e
@pytest.mark.slow
class TestEndToEndWorkflow:
    """Test complete end-to-end workflow simulation."""

    def test_hook_event_delivery_simulation(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """
        Test simulated hook event delivery from MediaMTX to media-service.

        This simulates what happens when MediaMTX calls the hook script.
        """
        # Simulate a stream becoming ready
        ready_event = {
            "path": "live/e2e-test-stream/in",
            "sourceType": "rtmp",
            "sourceId": "e2e-test-123",
            "query": "lang=en",
        }

        response = http_client.post(
            f"{media_service_url}/v1/mediamtx/events/ready",
            json=ready_event,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "received"

        # Simulate stream becoming not ready
        not_ready_event = {
            "path": "live/e2e-test-stream/in",
            "sourceType": "rtmp",
            "sourceId": "e2e-test-123",
        }

        response = http_client.post(
            f"{media_service_url}/v1/mediamtx/events/not-ready",
            json=not_ready_event,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_services_restart_and_reconnect(
        self,
        docker_services: None,
        http_client: httpx.Client,
        media_service_url: str,
    ) -> None:
        """Test services can restart and reconnect successfully."""
        import time

        # Restart media-service
        subprocess.run(
            ["docker", "restart", "media-service"],
            check=True,
            capture_output=True,
        )

        # Wait for service to be ready
        max_wait = 30
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                response = http_client.get(f"{media_service_url}/health")
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise TimeoutError("media-service did not restart within 30 seconds")

        # Verify MediaMTX can still reach it
        result = subprocess.run(
            [
                "docker",
                "exec",
                "mediamtx",
                "wget",
                "-q",
                "-O",
                "-",
                "http://media-service:8080/health",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        assert "ok" in result.stdout.lower(), \
            "MediaMTX should still be able to reach media-service after restart"
