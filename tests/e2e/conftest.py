"""
E2E test fixtures for Docker Compose service testing.

Manages Docker Compose lifecycle for end-to-end testing of MediaMTX and media-service.
"""

import subprocess
import time
from typing import Generator

import httpx
import pytest


@pytest.fixture(scope="session")
def docker_compose_file() -> str:
    """Path to docker-compose.yml file."""
    return "deploy/docker-compose.yml"


@pytest.fixture(scope="session")
def docker_services(docker_compose_file: str) -> Generator[None, None, None]:
    """
    Start Docker Compose services for e2e tests.

    Yields control after services are healthy, then tears down on test completion.
    """
    # Start services
    subprocess.run(
        ["docker", "compose", "-f", docker_compose_file, "up", "-d", "--build"],
        check=True,
        capture_output=True,
    )

    # Wait for services to be healthy
    max_wait = 60  # seconds
    start_time = time.time()

    print("\n⏳ Waiting for Docker services to be healthy...")

    while time.time() - start_time < max_wait:
        result = subprocess.run(
            ["docker", "compose", "-f", docker_compose_file, "ps", "--format", "json"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Check if all services are running
            import json
            services = [json.loads(line) for line in result.stdout.strip().split('\n') if line]

            if all(svc.get("State") == "running" for svc in services):
                print("✅ All services running, checking health endpoints...")

                # Give services a moment to fully initialize
                time.sleep(5)

                # Verify health endpoints are responding
                try:
                    # Check MediaMTX Control API (with basic auth)
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.get(
                            "http://localhost:9997/v3/paths/list",
                            auth=("admin", "admin")
                        )
                        resp.raise_for_status()

                    # Check media-service health
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.get("http://localhost:8080/health")
                        resp.raise_for_status()

                    print("✅ Docker services are healthy and ready")
                    break
                except (httpx.HTTPError, httpx.ConnectError) as e:
                    print(f"⏳ Health check failed: {e}, retrying...")

        time.sleep(2)
    else:
        # Timeout - print logs for debugging
        subprocess.run(["docker", "compose", "-f", docker_compose_file, "logs"])
        raise TimeoutError("Docker services failed to become healthy within 60 seconds")

    yield

    # Teardown - stop and remove services
    print("\n🧹 Cleaning up Docker services...")
    subprocess.run(
        ["docker", "compose", "-f", docker_compose_file, "down", "-v"],
        check=False,  # Don't fail if already stopped
        capture_output=True,
    )
    print("✅ Docker services cleaned up")


@pytest.fixture
def http_client() -> Generator[httpx.Client, None, None]:
    """HTTP client for making requests to services."""
    with httpx.Client(timeout=10.0) as client:
        yield client


@pytest.fixture
def http_client_with_auth() -> Generator[httpx.Client, None, None]:
    """HTTP client with MediaMTX basic auth for Control API requests."""
    with httpx.Client(timeout=10.0, auth=("admin", "admin")) as client:
        yield client


@pytest.fixture
def mediamtx_control_api_url() -> str:
    """MediaMTX Control API base URL."""
    return "http://localhost:9997"


@pytest.fixture
def media_service_url() -> str:
    """Media service base URL."""
    return "http://localhost:8080"


@pytest.fixture
def mediamtx_metrics_url() -> str:
    """MediaMTX Prometheus metrics URL."""
    return "http://localhost:9998"
