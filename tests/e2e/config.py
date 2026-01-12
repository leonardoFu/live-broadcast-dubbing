"""E2E Test Configuration.

Configuration settings for cross-service E2E tests.
Centralizes all URLs, timeouts, and test parameters.
"""

from pathlib import Path

# Base paths
E2E_TEST_DIR = Path(__file__).parent
PROJECT_ROOT = E2E_TEST_DIR.parent.parent


class MediaMTXConfig:
    """MediaMTX server configuration.

    Per spec 020-rtmp-stream-pull:
    - Media service pulls streams via RTMP (port 1935)
    - RTSP is deprecated for stream pulling
    """

    # RTMP URLs (primary for spec 020-rtmp-stream-pull)
    RTMP_URL = "rtmp://localhost:1935"
    RTMP_URL_INTERNAL = "rtmp://mediamtx:1935"

    # RTSP URLs (deprecated, kept for backward compatibility)
    RTSP_URL = "rtsp://localhost:8554"
    RTSP_URL_INTERNAL = "rtsp://mediamtx:8554"

    # Control and metrics
    CONTROL_API_URL = "http://localhost:8889"
    METRICS_URL = "http://localhost:9998"


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
    """Test-specific configuration.

    Updated for spec 021-fragment-length-30s:
    - Segment duration increased from 6s to 30s
    - Expected segments reduced from 10 to 2 (60s / 30s = 2)
    - A/V sync threshold reduced to 100ms (per spec 021 FR-013)
    """

    # Stream identifiers
    STREAM_ID = "e2e-test-stream"
    WORKER_ID = "e2e-worker-001"

    # Pipeline configuration (spec 021: 30s segments)
    SEGMENT_DURATION_SEC = 30  # spec 021: increased from 6s to 30s
    SEGMENT_DURATION_NS = 30_000_000_000  # spec 021: 30s in nanoseconds
    MAX_INFLIGHT = 3

    # Expected values for 60-second test fixture (spec 021)
    EXPECTED_SEGMENTS = 2  # 60s / 30s = 2 segments (spec 021)
    EXPECTED_DURATION_SEC = 60

    # A/V sync thresholds (spec 021: 100ms for logging only)
    AV_SYNC_THRESHOLD_MS = 100  # spec 021: reduced from 120ms to 100ms
    AV_SYNC_PASS_RATE = 0.95  # 95% of segments must be within threshold


class TimeoutConfig:
    """Timeout configuration (in seconds).

    Updated for spec 021-fragment-length-30s:
    - Fragment timeout increased from 8s to 60s (FR-006)
    - Pipeline completion increased for 30s segments
    """

    SERVICE_STARTUP = 60
    SERVICE_HEALTH_CHECK = 30
    STREAM_PUBLISH = 30
    PIPELINE_COMPLETION = 120  # spec 021: increased for 30s segments
    RECONNECTION = 60
    CIRCUIT_BREAKER_COOLDOWN = 30
    FRAGMENT_TIMEOUT = 60  # spec 021: increased from 8s to 60s (FR-006)


class TestFixtureConfig:
    """Test fixture configuration."""

    FIXTURE_DIR = PROJECT_ROOT / "fixtures" / "test-streams"
    FIXTURE_FILE = "1-min-nfl.mp4"
    FIXTURE_PATH = FIXTURE_DIR / FIXTURE_FILE

    # Expected fixture properties
    DURATION_SEC = 60
    VIDEO_CODEC = "h264"
    AUDIO_CODEC = "aac"
    VIDEO_WIDTH = 1280
    VIDEO_HEIGHT = 720
    VIDEO_FPS = 30
    AUDIO_SAMPLE_RATE = 44100
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
