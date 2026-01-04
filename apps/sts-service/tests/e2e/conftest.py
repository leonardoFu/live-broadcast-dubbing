"""E2E test configuration for Full STS Service.

Provides Docker Compose fixtures for starting/stopping the full-sts-service
with all required dependencies (ASR, Translation, TTS).

Requirements:
- DEEPL_AUTH_KEY environment variable (for translation)
- NVIDIA GPU with CUDA support (for ASR and TTS)
- docker-compose.full.yml in apps/sts-service/

Usage:
    @pytest.mark.e2e
    async def test_my_e2e(full_sts_service):
        # Service is running, health checked
        async with SocketIOClient("http://localhost:8000") as client:
            # Test implementation
            pass
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Generator

import httpx
import pytest

logger = logging.getLogger(__name__)

# Constants
FULL_STS_SERVICE_URL = "http://localhost:8000"
HEALTH_ENDPOINT = f"{FULL_STS_SERVICE_URL}/health"
DOCKER_COMPOSE_FILE = "docker-compose.full.yml"
SERVICE_NAME = "full-sts-service"
STARTUP_TIMEOUT = 120  # 2 minutes for model loading
HEALTH_CHECK_INTERVAL = 2  # seconds
DEEPL_AUTH_KEY = "8e373354-4ca7-4fec-b563-93b2fa6930cc:fx"


@pytest.fixture(scope="session")
def docker_compose_file() -> Path:
    """Get path to docker-compose.full.yml.

    Returns:
        Path to docker-compose file

    Raises:
        FileNotFoundError: If docker-compose file not found
    """
    repo_root = Path(__file__).resolve().parents[5]  # Navigate to repo root
    compose_file = repo_root / "apps" / "sts-service" / DOCKER_COMPOSE_FILE

    if not compose_file.exists():
        raise FileNotFoundError(
            f"Docker Compose file not found: {compose_file}\n"
            f"Expected location: apps/sts-service/{DOCKER_COMPOSE_FILE}"
        )

    logger.info(f"Using Docker Compose file: {compose_file}")
    return compose_file


@pytest.fixture(scope="session")
def docker_compose_env() -> dict[str, str]:
    """Environment variables for Docker Compose.

    Returns:
        Environment variables including DEEPL_AUTH_KEY
    """
    env = os.environ.copy()
    env["DEEPL_AUTH_KEY"] = DEEPL_AUTH_KEY
    env["LOG_LEVEL"] = "INFO"
    env["ENABLE_ARTIFACT_LOGGING"] = "true"

    logger.info("Configured Docker Compose environment variables")
    return env


@pytest.fixture(scope="session")
def full_sts_service(
    docker_compose_file: Path,
    docker_compose_env: dict[str, str],
) -> Generator[str, None, None]:
    """Start Full STS Service with Docker Compose.

    This fixture:
    1. Starts full-sts-service container with GPU support
    2. Waits for /health endpoint to return 200
    3. Yields service URL
    4. Stops and cleans up containers on test completion

    Yields:
        Service URL (http://localhost:8000)

    Raises:
        RuntimeError: If service fails to start or become healthy
    """
    logger.info("=" * 80)
    logger.info("Starting Full STS Service for E2E tests")
    logger.info("=" * 80)

    # Change to directory containing docker-compose file
    compose_dir = docker_compose_file.parent
    original_dir = Path.cwd()

    try:
        os.chdir(compose_dir)

        # Stop any existing containers
        logger.info("Stopping any existing containers...")
        subprocess.run(
            ["docker", "compose", "-f", DOCKER_COMPOSE_FILE, "down", "-v"],
            env=docker_compose_env,
            capture_output=True,
            check=False,  # Don't fail if nothing to stop
        )

        # Start service
        logger.info("Starting Full STS Service...")
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                DOCKER_COMPOSE_FILE,
                "up",
                "-d",
                "--build",
            ],
            env=docker_compose_env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Failed to start service:\n{result.stderr}")
            raise RuntimeError(f"Docker Compose up failed: {result.stderr}")

        logger.info(f"Service started, waiting for health check at {HEALTH_ENDPOINT}")

        # Wait for health check
        start_time = time.time()
        last_error = None

        while time.time() - start_time < STARTUP_TIMEOUT:
            try:
                response = httpx.get(HEALTH_ENDPOINT, timeout=5.0)
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    logger.info(f"✓ Service healthy after {elapsed:.1f}s: {response.json()}")
                    logger.info("=" * 80)
                    break
                else:
                    last_error = f"Health check returned {response.status_code}"
            except httpx.RequestError as e:
                last_error = str(e)
            except Exception as e:
                last_error = str(e)

            time.sleep(HEALTH_CHECK_INTERVAL)
        else:
            # Timeout - dump logs for debugging
            logger.error("Service failed to become healthy, dumping logs...")
            logs_result = subprocess.run(
                ["docker", "compose", "-f", DOCKER_COMPOSE_FILE, "logs", "--tail=100"],
                env=docker_compose_env,
                capture_output=True,
                text=True,
            )
            logger.error(f"Service logs:\n{logs_result.stdout}")

            raise RuntimeError(
                f"Service did not become healthy within {STARTUP_TIMEOUT}s. "
                f"Last error: {last_error}"
            )

        # Service is ready
        yield FULL_STS_SERVICE_URL

    finally:
        # Cleanup
        os.chdir(original_dir)
        logger.info("=" * 80)
        logger.info("Stopping Full STS Service")
        logger.info("=" * 80)

        os.chdir(compose_dir)
        result = subprocess.run(
            ["docker", "compose", "-f", DOCKER_COMPOSE_FILE, "down", "-v"],
            env=docker_compose_env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning(f"Error stopping service: {result.stderr}")
        else:
            logger.info("✓ Service stopped and cleaned up")

        os.chdir(original_dir)


@pytest.fixture
async def wait_for_service_ready(full_sts_service: str) -> None:
    """Wait for service to be fully ready between tests.

    This ensures the service is healthy before each test runs.

    Args:
        full_sts_service: Service URL from session fixture
    """
    max_retries = 5
    for i in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{full_sts_service}/health", timeout=5.0)
                if response.status_code == 200:
                    return
        except httpx.RequestError:
            if i < max_retries - 1:
                await asyncio.sleep(1)
            else:
                raise

    raise RuntimeError("Service not healthy after waiting")


# Mark all tests in this directory as e2e
def pytest_collection_modifyitems(items):
    """Automatically mark all tests in e2e/ as e2e tests."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
