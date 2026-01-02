"""Pytest configuration and shared fixtures for E2E tests.

Provides fixtures for:
- Docker Compose service management
- Stream publishing
- Metrics parsing
- Log capture
- Resource cleanup
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.config import (  # noqa: E402
    DockerComposeConfig,
    EchoSTSConfig,
    MediaMTXConfig,
    MediaServiceConfig,
    TestConfig,
    TestFixtureConfig,
    TimeoutConfig,
)
from tests.e2e.helpers.docker_manager import DockerManager  # noqa: E402
from tests.e2e.helpers.metrics_parser import MetricsParser  # noqa: E402
from tests.e2e.helpers.stream_analyzer import StreamAnalyzer  # noqa: E402
from tests.e2e.helpers.stream_publisher import StreamPublisher  # noqa: E402

if TYPE_CHECKING:
    pass

# Configure logging for E2E tests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "e2e: End-to-end tests requiring Docker services")
    config.addinivalue_line("markers", "p1: Priority 1 tests (core functionality)")
    config.addinivalue_line("markers", "p2: Priority 2 tests (resilience)")
    config.addinivalue_line("markers", "p3: Priority 3 tests (reconnection)")
    config.addinivalue_line("markers", "slow: Tests that take longer than 60 seconds")


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    """Add e2e marker to all tests in this directory."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


# =============================================================================
# Docker Service Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def docker_manager() -> Generator[DockerManager, None, None]:
    """Session-scoped Docker manager.

    Manages Docker Compose lifecycle for all E2E tests.
    Starts services once per test session.
    """
    manager = DockerManager(
        compose_file=DockerComposeConfig.COMPOSE_FILE,
        project_name=DockerComposeConfig.PROJECT_NAME,
    )

    yield manager

    # Cleanup on session end (even if tests fail)
    if manager.is_running():
        manager.stop()


@pytest.fixture(scope="session")
def docker_services(docker_manager: DockerManager) -> Generator[DockerManager, None, None]:
    """Session-scoped Docker services.

    Ensures all E2E services are running before tests.
    """
    logger.info("Starting E2E Docker services...")

    try:
        docker_manager.start(build=True, timeout=TimeoutConfig.SERVICE_STARTUP)
        yield docker_manager
    finally:
        logger.info("Stopping E2E Docker services...")
        docker_manager.stop(volumes=True)


@pytest.fixture
def docker_logs(docker_manager: DockerManager) -> Generator[None, None, None]:
    """Capture Docker logs on test failure.

    Use this fixture when you want to see logs if a test fails.
    """
    yield

    # Fixture teardown - could capture logs here on failure
    # This is handled by pytest hooks instead


# =============================================================================
# Stream Publisher Fixtures
# =============================================================================


@pytest.fixture
def stream_publisher() -> Generator[StreamPublisher, None, None]:
    """Stream publisher for pushing test fixtures to MediaMTX via RTMP.

    Per spec 020-rtmp-stream-pull, streams are published via RTMP.
    Each test gets a fresh publisher instance.
    """
    publisher = StreamPublisher(
        fixture_path=TestFixtureConfig.FIXTURE_PATH,
        rtmp_base_url=MediaMTXConfig.RTMP_URL,
    )

    yield publisher

    # Cleanup: ensure stream is stopped
    if publisher.is_running():
        publisher.stop()


@pytest.fixture
def published_stream(
    docker_services: DockerManager,
    stream_publisher: StreamPublisher,
) -> Generator[str, None, None]:
    """Published stream fixture.

    Starts publishing test fixture via RTMP and yields the stream URL.
    Per spec 020-rtmp-stream-pull, media-service pulls streams via RTMP.
    Automatically stops on teardown.
    """
    stream_path = f"live/{TestConfig.STREAM_ID}/in"

    # Verify fixture exists
    if not TestFixtureConfig.FIXTURE_PATH.exists():
        pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

    # Start publishing via RTMP
    stream_publisher.start(stream_path=stream_path, realtime=True)

    rtmp_url = f"{MediaMTXConfig.RTMP_URL}/{stream_path}"
    yield rtmp_url

    # Stop publishing
    stream_publisher.stop()


# =============================================================================
# Metrics and Analysis Fixtures
# =============================================================================


@pytest.fixture
def metrics_parser() -> MetricsParser:
    """Metrics parser for querying Prometheus metrics."""
    return MetricsParser(metrics_url=MediaServiceConfig.METRICS_URL)


@pytest.fixture
def stream_analyzer() -> StreamAnalyzer:
    """Stream analyzer for ffprobe-based analysis."""
    return StreamAnalyzer(rtmp_base_url=MediaMTXConfig.RTMP_URL)


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def test_config() -> TestConfig:
    """Test configuration."""
    return TestConfig()


@pytest.fixture
def mediamtx_config() -> MediaMTXConfig:
    """MediaMTX configuration."""
    return MediaMTXConfig()


@pytest.fixture
def echo_sts_config() -> EchoSTSConfig:
    """Echo STS configuration."""
    return EchoSTSConfig()


@pytest.fixture
def timeout_config() -> TimeoutConfig:
    """Timeout configuration."""
    return TimeoutConfig()


# =============================================================================
# Socket.IO Client Fixtures
# =============================================================================


@pytest.fixture
async def sts_client():
    """Socket.IO client for Echo STS Service.

    Use this to send configuration events to Echo STS.
    """
    import socketio

    client = socketio.AsyncClient()

    await client.connect(
        EchoSTSConfig.URL,
        socketio_path=EchoSTSConfig.SOCKETIO_PATH,
    )

    yield client

    if client.connected:
        await client.disconnect()


# =============================================================================
# Cleanup Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup_resources():
    """Autouse fixture for resource cleanup.

    Runs after each test to ensure clean state.
    """
    yield

    # Post-test cleanup would go here
    # Currently handled by individual fixtures


# =============================================================================
# Test Fixture Verification
# =============================================================================


@pytest.fixture(scope="session")
def verify_test_fixture() -> bool:
    """Verify test fixture exists and has correct properties.

    Runs once per session to validate fixture.
    """
    from tests.e2e.helpers.stream_publisher import verify_fixture

    fixture_path = TestFixtureConfig.FIXTURE_PATH

    if not fixture_path.exists():
        logger.warning(f"Test fixture not found: {fixture_path}")
        return False

    try:
        info = verify_fixture(fixture_path)
        logger.info(f"Test fixture verified: {info.get('format', {})}")
        return True
    except Exception as e:
        logger.error(f"Failed to verify test fixture: {e}")
        return False


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


# =============================================================================
# Import Dual Compose Fixtures
# =============================================================================

# Import dual compose fixtures from conftest_dual_compose
# These can be used alongside the existing single-compose fixtures
try:
    from tests.e2e.conftest_dual_compose import (
        dual_compose_env,
        dual_compose_manager,
        media_compose_env,
        publish_test_fixture,
        sts_compose_env,
        sts_monitor,
    )

    # Make dual compose fixtures available
    __all__ = [
        "wait_for_condition",
        "dual_compose_env",
        "dual_compose_manager",
        "media_compose_env",
        "sts_compose_env",
        "publish_test_fixture",
        "sts_monitor",
    ]
except ImportError:
    # Dual compose fixtures not available
    __all__ = [
        "wait_for_condition",
    ]
