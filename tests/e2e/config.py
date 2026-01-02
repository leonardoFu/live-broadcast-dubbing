"""E2E Test Configuration.

Configuration settings for cross-service E2E tests.
Centralizes all URLs, timeouts, and test parameters.
"""

from pathlib import Path

# Base paths
E2E_TEST_DIR = Path(__file__).parent
PROJECT_ROOT = E2E_TEST_DIR.parent.parent


class MediaMTXConfig:
    """MediaMTX server configuration."""

    RTSP_URL = "rtsp://localhost:8554"
    RTMP_URL = "rtmp://localhost:1935"
    CONTROL_API_URL = "http://localhost:8889"
    METRICS_URL = "http://localhost:9998"

    # Container URLs (for inter-service communication)
    RTSP_URL_INTERNAL = "rtsp://mediamtx:8554"
    RTMP_URL_INTERNAL = "rtmp://mediamtx:1935"


class EchoSTSConfig:
    """Echo STS Service configuration."""

    URL = "http://localhost:8000"
    SOCKETIO_PATH = "/socket.io/"  # Default Socket.IO path (changed from /ws/sts)

    # Container URL
    URL_INTERNAL = "http://echo-sts:8000"


class MediaServiceConfig:
    """Media Service configuration."""

    URL = "http://localhost:8080"
    HEALTH_URL = "http://localhost:8080/health"
    METRICS_URL = "http://localhost:8080/metrics"


class TestConfig:
    """Test-specific configuration."""

    # Stream identifiers
    STREAM_ID = "e2e-test-stream"
    WORKER_ID = "e2e-worker-001"

    # Pipeline configuration
    SEGMENT_DURATION_SEC = 6
    SEGMENT_DURATION_NS = 6_000_000_000
    MAX_INFLIGHT = 3

    # Expected values for 60-second test fixture
    EXPECTED_SEGMENTS = 10  # 60s / 6s = 10 segments
    EXPECTED_DURATION_SEC = 60

    # A/V sync thresholds
    AV_SYNC_THRESHOLD_MS = 120
    AV_SYNC_PASS_RATE = 0.95  # 95% of segments must be within threshold


class TimeoutConfig:
    """Timeout configuration (in seconds)."""

    SERVICE_STARTUP = 60
    SERVICE_HEALTH_CHECK = 30
    STREAM_PUBLISH = 30
    PIPELINE_COMPLETION = 90
    RECONNECTION = 60
    CIRCUIT_BREAKER_COOLDOWN = 30
    FRAGMENT_TIMEOUT = 8


class TestFixtureConfig:
    """Test fixture configuration."""

    FIXTURE_DIR = E2E_TEST_DIR / "fixtures" / "test-streams"
    FIXTURE_FILE = "1-min-nfl.mp4"
    FIXTURE_PATH = FIXTURE_DIR / FIXTURE_FILE

    # Expected fixture properties
    DURATION_SEC = 60
    VIDEO_CODEC = "h264"
    AUDIO_CODEC = "aac"
    VIDEO_WIDTH = 1280
    VIDEO_HEIGHT = 720
    VIDEO_FPS = 30
    AUDIO_SAMPLE_RATE = 48000
    AUDIO_CHANNELS = 2


class DockerComposeConfig:
    """Docker Compose configuration."""

    COMPOSE_FILE = E2E_TEST_DIR / "docker-compose.yml"
    PROJECT_NAME = "e2e-tests"

    # Service names
    MEDIAMTX_SERVICE = "mediamtx"
    ECHO_STS_SERVICE = "echo-sts"
    MEDIA_SERVICE = "media-service"

    # Container names
    MEDIAMTX_CONTAINER = "e2e-mediamtx"
    ECHO_STS_CONTAINER = "e2e-echo-sts"
    MEDIA_SERVICE_CONTAINER = "e2e-media-service"
