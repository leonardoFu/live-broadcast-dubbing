"""Pytest configuration for dual docker-compose E2E tests.

Provides fixtures for orchestrating two separate docker-compose environments:
- Media Service composition (MediaMTX + media-service)
- STS Service composition (real STS service with ASR + Translation + TTS)

Session-scoped fixtures start both compositions once and use unique stream names
per test for isolation without restart overhead.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from helpers.docker_compose_manager import (
    DockerComposeManager,
    DualComposeManager,
)
from helpers.socketio_monitor import SocketIOMonitor
from helpers.stream_publisher import StreamPublisher

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MEDIA_COMPOSE_FILE = PROJECT_ROOT / "apps/media-service/docker-compose.yml"
STS_COMPOSE_FILE = PROJECT_ROOT / "apps/sts-service/docker-compose.yml"
TEST_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures/test-streams/1-min-nfl.mp4"


# =============================================================================
# Dual Compose Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def media_compose_env() -> Generator[DockerComposeManager, None, None]:
    """Session-scoped media service Docker Compose environment.

    Starts MediaMTX + media-service once per test session.
    Tests use unique stream names to avoid conflicts.

    Yields:
        DockerComposeManager for media composition
    """
    logger.info("Starting media service Docker Compose environment...")

    manager = DockerComposeManager(
        compose_file=MEDIA_COMPOSE_FILE,
        project_name="e2e-media",
        env={
            # MediaMTX Ports
            "MEDIAMTX_RTSP_PORT": "8554",
            "MEDIAMTX_RTMP_PORT": "1935",
            "MEDIAMTX_API_PORT": "8889",
            "MEDIAMTX_METRICS_PORT": "9998",
            "MEDIAMTX_PLAYBACK_PORT": "9996",

            # MediaMTX Container Config
            "MEDIAMTX_CONTAINER_NAME": "e2e-mediamtx",
            "MEDIAMTX_LOG_LEVEL": "info",
            "MEDIAMTX_PROTOCOLS": "tcp",

            # Media Service Config
            "MEDIA_SERVICE_PORT": "8080",
            "MEDIA_SERVICE_CONTAINER_NAME": "e2e-media-service",
            "MEDIA_SERVICE_IMAGE": "media-service:e2e",

            # STS Service URL (use container name for E2E shared network)
            "STS_SERVICE_URL": "http://e2e-echo-sts:3000",

            # Orchestrator URL (for MediaMTX hooks)
            "ORCHESTRATOR_URL": "http://media-service:8080",

            # Logging
            "LOG_LEVEL": "DEBUG",
            # GStreamer Debug (for audio pipeline investigation)
            # Include GST_PADS for linking and GST_CAPS for caps negotiation
            "GST_DEBUG": "flvdemux:5,aacparse:5,queue:6,appsink:6,GST_PADS:5,GST_CAPS:5",

            # Network (use default network name, will connect manually)
            # "NETWORK_NAME": "dubbing-network",  # Let compose create its own network

            # Volumes
            "SEGMENTS_VOLUME_NAME": "e2e-media-segments",

            # Circuit Breaker
            "CIRCUIT_BREAKER_THRESHOLD": "5",
            "CIRCUIT_BREAKER_TIMEOUT": "60",

            # Segment Config
            "SEGMENT_DIR": "/tmp/segments",
            "MAX_CONCURRENT_STREAMS": "10",
            "METRICS_ENABLED": "true",
        },
    )

    # Trust Docker's built-in health checks (defined in docker-compose.yml)
    # No need for explicit endpoint verification since containers have HEALTHCHECK directives

    try:
        manager.start(
            build=True,
            timeout=60,
        )
        yield manager
    finally:
        logger.info("Stopping media service Docker Compose environment...")
        manager.stop(volumes=True)


@pytest.fixture(scope="session")
def sts_compose_env() -> Generator[DockerComposeManager, None, None]:
    """Session-scoped STS service Docker Compose environment.

    Starts echo-sts service for E2E testing to verify media-service pipeline.
    Uses echo-sts from docker-compose.yml for fast pipeline validation.

    Yields:
        DockerComposeManager for STS composition
    """
    logger.info("Starting echo-sts Docker Compose environment...")

    manager = DockerComposeManager(
        compose_file=STS_COMPOSE_FILE,
        project_name="e2e-sts",
        env={
            # Echo STS Service Config
            "STS_CONTAINER_NAME": "e2e-echo-sts",
            "STS_HOST": "0.0.0.0",
            "STS_PORT": "3000",

            # Logging
            "LOG_LEVEL": "INFO",

            # Processing Config (CPU-only for macOS)
            "DEVICE": "cpu",
            "ASR_MODEL": "tiny",  # Smallest Whisper model for faster loading
            "TTS_PROVIDER": "coqui",  # Use real Coqui TTS (no mocking)
            "TRANSLATION_PROVIDER": "deepl",  # Use mock translation for E2E tests
            "DEEPL_AUTH_KEY": "8e373354-4ca7-4fec-b563-93b2fa6930cc:fx",

            # Network (use default network name, will connect manually)
            # "NETWORK_NAME": "sts-network",  # Let compose create its own network

            # Health Check
            "HEALTHCHECK_INTERVAL": "10s",
            "HEALTHCHECK_TIMEOUT": "5s",
            "HEALTHCHECK_RETRIES": "3",
            "HEALTHCHECK_START_PERIOD": "90s",  # Allow time for Whisper + Coqui TTS model loading
        },
    )

    # Trust Docker's built-in health checks

    try:
        # Start echo-sts for pipeline validation
        manager.start(
            build=True,
            timeout=30,  # Echo service starts quickly
            services=["echo-sts"],
        )
        yield manager
    finally:
        logger.info("Stopping STS service Docker Compose environment...")
        manager.stop(volumes=True)


@pytest.fixture(scope="session")
def dual_compose_env(
    media_compose_env: DockerComposeManager,
    sts_compose_env: DockerComposeManager,
) -> dict[str, DockerComposeManager]:
    """Session-scoped dual compose environment.

    Ensures both compositions are running before tests.
    Tests use unique stream names for isolation.
    Connects STS container to media network for inter-service communication.

    Returns:
        Dictionary with 'media' and 'sts' managers
    """
    import subprocess

    # Connect echo-sts container to media network for inter-service communication
    logger.info("Connecting echo-sts container to media network...")
    result = subprocess.run(
        ["docker", "network", "connect", "dubbing-network", "e2e-echo-sts"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        logger.info("Successfully connected echo-sts to media network")
    else:
        # May already be connected, log warning but continue
        logger.warning(f"Could not connect echo-sts to media network: {result.stderr}")

    logger.info("Dual compose environment ready")
    return {
        "media": media_compose_env,
        "sts": sts_compose_env,
    }


@pytest.fixture(scope="session")
def dual_compose_manager() -> Generator[DualComposeManager, None, None]:
    """Session-scoped dual compose manager (alternative to separate fixtures).

    Use this when you want a single manager controlling both compositions.

    Yields:
        DualComposeManager instance
    """
    logger.info("Starting dual compose manager...")

    manager = DualComposeManager(
        media_compose_file=MEDIA_COMPOSE_FILE,
        sts_compose_file=STS_COMPOSE_FILE,
        media_project_name="e2e-media-alt",
        sts_project_name="e2e-sts-alt",
    )

    media_health = [
        ("http://localhost:8889/v3/paths/list", "MediaMTX"),
        ("http://localhost:8080/health", "Media Service"),
    ]
    sts_health = [
        ("http://localhost:3000/health", "STS Service"),
    ]

    try:
        manager.start_all(
            build=True,
            timeout=90,
            media_health_endpoints=media_health,
            sts_health_endpoints=sts_health,
        )
        yield manager
    finally:
        logger.info("Stopping dual compose manager...")
        manager.stop_all(volumes=True)


# =============================================================================
# Stream Publisher Fixtures
# =============================================================================


@pytest.fixture
def publish_test_fixture(
    request: pytest.FixtureRequest,
    dual_compose_env: dict[str, DockerComposeManager],
) -> Generator[tuple[str, str], None, None]:
    """Publish 1-min NFL test fixture to MediaMTX.

    Uses unique stream name per test to avoid conflicts in session-scoped compose.

    Args:
        request: Pytest request for test name
        dual_compose_env: Dual compose environment

    Yields:
        Tuple of (stream_path, rtsp_url)
    """
    # Generate unique stream name
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    timestamp = int(time.time())
    stream_path = f"live/test_{test_name}_{timestamp}/in"

    # Verify fixture exists
    if not TEST_FIXTURE_PATH.exists():
        pytest.skip(f"Test fixture not found: {TEST_FIXTURE_PATH}")

    # Start publishing
    publisher = StreamPublisher(
        fixture_path=TEST_FIXTURE_PATH,
        rtmp_base_url="rtmp://localhost:1935",
    )

    try:
        publisher.start(stream_path=stream_path, realtime=True, loop=True)
        rtmp_url = f"rtmp://localhost:1935/{stream_path}"
        logger.info(f"Publishing test fixture to {rtmp_url}")
        yield stream_path, rtmp_url
    finally:
        # Cleanup: stop publishing
        if publisher.is_running():
            publisher.stop()


# =============================================================================
# Socket.IO Monitor Fixtures
# =============================================================================


@pytest.fixture
async def sts_monitor(dual_compose_env: dict[str, DockerComposeManager]) -> Generator[SocketIOMonitor, None, None]:
    """Socket.IO monitor for capturing STS events.

    Connects to real STS service and captures fragment:processed events.

    Args:
        dual_compose_env: Dual compose environment (ensures STS service is running)

    Yields:
        SocketIOMonitor instance
    """
    monitor = SocketIOMonitor(
        sts_url="http://localhost:3000",
        # Use default Socket.IO path (removed custom /ws/sts)
    )

    try:
        await monitor.connect()
        yield monitor
    finally:
        await monitor.disconnect()


# =============================================================================
# Utility Functions
# =============================================================================


def wait_for_condition(
    condition_fn,
    timeout_sec: float = 30,
    poll_interval_sec: float = 0.5,
    description: str = "condition",
) -> bool:
    """Wait for a condition to become true.

    Args:
        condition_fn: Callable that returns True when condition is met
        timeout_sec: Maximum wait time
        poll_interval_sec: Time between polls
        description: Description for logging

    Returns:
        True if condition was met, False if timeout
    """
    import time

    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            if condition_fn():
                return True
        except Exception as e:
            logger.debug(f"Condition check failed: {e}")

        time.sleep(poll_interval_sec)

    logger.warning(f"Timeout waiting for {description}")
    return False
