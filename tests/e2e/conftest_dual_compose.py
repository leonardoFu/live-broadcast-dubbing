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

from tests.e2e.helpers.docker_compose_manager import (
    DockerComposeManager,
    DualComposeManager,
)
from tests.e2e.helpers.socketio_monitor import SocketIOMonitor
from tests.e2e.helpers.stream_publisher import StreamPublisher

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MEDIA_COMPOSE_FILE = PROJECT_ROOT / "apps/media-service/docker-compose.e2e.yml"
STS_COMPOSE_FILE = PROJECT_ROOT / "apps/sts-service/docker-compose.e2e.yml"
TEST_FIXTURE_PATH = Path(__file__).parent / "fixtures/test_streams/30s-counting-english.mp4"


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
            "MEDIAMTX_RTSP_PORT": "8554",
            "MEDIAMTX_RTMP_PORT": "1935",
            "MEDIAMTX_API_PORT": "8889",
            "MEDIA_SERVICE_PORT": "8080",
            "STS_SERVICE_URL": "http://host.docker.internal:3000",
        },
    )

    # Trust Docker's built-in health checks (defined in docker-compose.e2e.yml)
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

    Starts real STS service once per test session.
    Model loading (30s+) happens once, amortized across all tests.

    Yields:
        DockerComposeManager for STS composition
    """
    logger.info("Starting STS service Docker Compose environment...")

    manager = DockerComposeManager(
        compose_file=STS_COMPOSE_FILE,
        project_name="e2e-sts",
        env={
            "STS_PORT": "3000",
            "HOST": "0.0.0.0",
            "ASR_MODEL": "whisper-small",
            "TTS_PROVIDER": "coqui",
            "DEVICE": "cpu",
        },
    )

    # Trust Docker's built-in health checks

    try:
        manager.start(
            build=True,
            timeout=90,  # Allow time for model loading
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

    Returns:
        Dictionary with 'media' and 'sts' managers
    """
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
    """Publish 30s counting test fixture to MediaMTX.

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
