# Data Model: Dual Docker-Compose E2E Test Entities

**Feature**: 019-dual-docker-e2e-infrastructure
**Date**: 2026-01-01

This document defines the entities and data structures used in dual docker-compose E2E tests.

## 1. Dual Compose Environment Configuration

**Description**: Configuration for managing two separate docker-compose environments (media-service + sts-service).

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| media_compose_file | str | Path to media-service docker-compose.yml | Required, "apps/media-service/docker-compose.e2e.yml" |
| sts_compose_file | str | Path to sts-service docker-compose.yml | Required, "apps/sts-service/docker-compose.e2e.yml" |
| media_project_name | str | Docker Compose project name for media | Required, "e2e-media-019" |
| sts_project_name | str | Docker Compose project name for STS | Required, "e2e-sts-019" |
| environment_overrides | dict | Environment variable overrides | Optional, e.g., {"STS_PORT": "3001"} |

**State Transitions**:
1. **Stopped** → `docker-compose up -d` (both) → **Starting**
2. **Starting** → Health checks pass → **Ready**
3. **Ready** → Tests execute → **Running**
4. **Running** → `docker-compose down -v` (both) → **Stopped**

**Lifecycle Management**:
```python
# conftest.py
@pytest.fixture(scope="session")
def dual_compose_env():
    """Start both docker-compose environments."""
    media_manager = DockerComposeManager(
        compose_file="apps/media-service/docker-compose.e2e.yml",
        project_name="e2e-media-019"
    )
    sts_manager = DockerComposeManager(
        compose_file="apps/sts-service/docker-compose.e2e.yml",
        project_name="e2e-sts-019"
    )

    # Start both compositions
    media_manager.up(detach=True)
    sts_manager.up(detach=True)

    # Wait for health checks (60s timeout for STS model loading)
    assert media_manager.wait_for_health(timeout=60)
    assert sts_manager.wait_for_health(timeout=60)

    yield {"media": media_manager, "sts": sts_manager}

    # Cleanup: always runs
    media_manager.down(volumes=True)
    sts_manager.down(volumes=True)
```

**Health Check Endpoints**:
```python
HEALTH_CHECKS = {
    "mediamtx": "http://localhost:9997/v3/paths/list",
    "media_service": "http://localhost:8080/health",
    "sts_service": "http://localhost:3000/health"
}
```

---

## 2. Test Fixture Metadata

**Description**: 30-second video file with counting phrases for deterministic ASR validation.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| file_path | str | Absolute path to test video | Required, "tests/fixtures/test_streams/30s-counting-english.mp4" |
| duration_sec | int | Duration in seconds | Required, 30 |
| video_codec | str | Video codec | Required, "h264" |
| video_resolution | str | Resolution (WxH) | Required, "1280x720" |
| video_fps | int | Frame rate | Required, 30 |
| audio_codec | str | Audio codec | Required, "aac" |
| audio_sample_rate | int | Audio sample rate (Hz) | Required, 48000 |
| audio_channels | int | Audio channel count | Required, 2 (stereo) |
| expected_segments | int | Expected 6s segments | Calculated: 30 / 6 = 5 |
| expected_transcripts | list[str] | Expected ASR output per segment | See below |

**Expected ASR Transcripts** (deterministic validation):
```python
EXPECTED_TRANSCRIPTS = [
    "One, two, three, four, five, six",           # Segment 1 (0-6s)
    "Seven, eight, nine, ten, eleven, twelve",    # Segment 2 (6-12s)
    "Thirteen, fourteen, fifteen, sixteen, seventeen, eighteen",  # Segment 3 (12-18s)
    "Nineteen, twenty, twenty-one, twenty-two, twenty-three, twenty-four",  # Segment 4 (18-24s)
    "Twenty-five, twenty-six, twenty-seven, twenty-eight, twenty-nine, thirty"  # Segment 5 (24-30s)
]
```

**Validation Method**:
```python
def validate_fixture_properties(fixture_path: str):
    """Validate test fixture has expected properties."""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        fixture_path
    ], capture_output=True, text=True)

    data = json.loads(result.stdout)

    # Validate duration
    assert float(data["format"]["duration"]) == 30.0, "Duration must be 30s"

    # Validate video stream
    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert video_stream["codec_name"] == "h264"
    assert video_stream["width"] == 1280
    assert video_stream["height"] == 720

    # Validate audio stream
    audio_stream = next(s for s in data["streams"] if s["codec_type"] == "audio")
    assert audio_stream["codec_name"] == "aac"
    assert audio_stream["sample_rate"] == "48000"
    assert audio_stream["channels"] == 2
```

**Publishing Method**:
```python
# tests/e2e/helpers/stream_publisher.py
class StreamPublisher:
    def __init__(self, fixture_path: str, rtsp_url: str):
        self.fixture_path = fixture_path
        self.rtsp_url = rtsp_url
        self.process = None

    def start(self):
        """Publish test fixture to MediaMTX RTSP endpoint."""
        self.process = subprocess.Popen([
            "ffmpeg",
            "-re",  # Read at native frame rate
            "-i", self.fixture_path,
            "-c", "copy",  # Copy codecs (no re-encode)
            "-f", "rtsp",
            self.rtsp_url
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def stop(self):
        """Stop publishing."""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
```

---

## 3. Service Endpoint Configuration

**Description**: URL configuration for service communication (internal vs. external).

**Properties**:

| Service | Internal URL | External URL (from host) | Purpose |
|---------|-------------|--------------------------|---------|
| MediaMTX RTSP | rtsp://mediamtx:8554 | rtsp://localhost:8554 | Stream input (media-service → MediaMTX) |
| MediaMTX RTMP | rtmp://mediamtx:1935 | rtmp://localhost:1935 | Stream output (media-service → MediaMTX) |
| MediaMTX API | http://mediamtx:9997 | http://localhost:9997 | Health checks, stream metadata |
| STS Service | http://host.docker.internal:3000 | http://localhost:3000 | Fragment processing (media-service → STS) |
| Media Service Metrics | http://media-service:8080 | http://localhost:8080 | Prometheus metrics |

**Stream URL Pattern**:
```python
def get_stream_urls(test_name: str) -> dict:
    """Generate unique stream URLs for test."""
    timestamp = int(time.time())
    stream_name = f"test_{test_name}_{timestamp}"

    return {
        "rtsp_input": f"rtsp://localhost:8554/live/{stream_name}/in",
        "rtmp_output": f"rtmp://localhost:1935/live/{stream_name}/out",
        "stream_name": stream_name
    }
```

**Environment Variable Mapping**:
```python
# apps/media-service/docker-compose.e2e.yml environment
MEDIA_SERVICE_ENV = {
    "MEDIAMTX_RTSP_URL": "rtsp://mediamtx:8554",  # Internal container name
    "MEDIAMTX_RTMP_URL": "rtmp://mediamtx:1935",
    "STS_SERVICE_URL": "http://host.docker.internal:3000",  # Host network access
    "PORT": "8080",
    "LOG_LEVEL": "DEBUG"
}

# apps/sts-service/docker-compose.e2e.yml environment
STS_SERVICE_ENV = {
    "HOST": "0.0.0.0",  # Listen on all interfaces
    "PORT": "3000",
    "ASR_MODEL": "whisper-small",
    "TTS_PROVIDER": "coqui",
    "DEVICE": "cpu"
}
```

---

## 4. Pipeline Validation Metrics

**Description**: Metrics and events captured for test assertions.

**Socket.IO Event Schema**:
```json
{
  "event": "fragment:processed",
  "payload": {
    "fragment_id": "stream123_0001",
    "transcript": "One, two, three, four, five, six",
    "translated_text": "Uno, dos, tres, cuatro, cinco, seis",
    "dubbed_audio": "<base64-encoded-audio>",
    "processing_time_ms": 12500,
    "target_language": "es"
  }
}
```

**Prometheus Metrics**:

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| worker_audio_fragments_total | counter | status=sent\|processed\|fallback | Total fragments by status |
| worker_inflight_fragments | gauge | - | Current in-flight count |
| worker_av_sync_delta_ms | histogram | - | A/V sync delta distribution |
| worker_sts_processing_time_ms | histogram | - | STS processing latency |

**Metrics Parser**:
```python
# tests/e2e/helpers/metrics_parser.py
from prometheus_client.parser import text_string_to_metric_families
import requests

class MetricsClient:
    def __init__(self, metrics_url: str = "http://localhost:8080/metrics"):
        self.metrics_url = metrics_url

    def get_counter(self, name: str, labels: dict = None) -> float:
        """Get counter value."""
        response = requests.get(self.metrics_url)
        response.raise_for_status()

        for family in text_string_to_metric_families(response.text):
            if family.name == name:
                for sample in family.samples:
                    if not labels or self._labels_match(sample.labels, labels):
                        return sample.value
        raise ValueError(f"Counter {name} not found")

    @staticmethod
    def _labels_match(sample_labels: dict, target_labels: dict) -> bool:
        return all(sample_labels.get(k) == v for k, v in target_labels.items())
```

**Audio Fingerprint Validation**:
```python
# tests/e2e/helpers/stream_analyzer.py
import numpy as np
from scipy.io import wavfile
from scipy.fft import rfft

def compute_audio_fingerprint(audio_file: str) -> str:
    """Compute simple spectral hash of audio file."""
    sample_rate, audio = wavfile.read(audio_file)

    # Convert to mono if stereo
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    # Compute FFT for first 5 seconds
    chunk = audio[:5 * sample_rate]
    spectrum = np.abs(rfft(chunk))

    # Hash top 100 frequency bins
    top_bins = np.argsort(spectrum)[-100:]
    return str(hash(tuple(top_bins)))

def validate_dubbed_audio(original_path: str, output_path: str) -> bool:
    """Verify output audio differs from original."""
    original_fp = compute_audio_fingerprint(original_path)
    output_fp = compute_audio_fingerprint(output_path)

    return original_fp != output_fp
```

---

## 5. Session State Tracking

**Description**: Pytest session-level state for managing dual compose lifecycle.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| compositions_started_at | float | Timestamp when docker-compose started | Required |
| health_checks_passed_at | float | Timestamp when all health checks passed | Required |
| test_stream_registry | dict | Map test_name → stream_name | Updated per test |
| cleanup_tasks | list | Processes/resources to clean up | Appended during tests |

**Test Stream Registry**:
```python
# Managed by conftest.py
TEST_STREAM_REGISTRY = {}

@pytest.fixture
def publish_test_fixture(request, dual_compose_env):
    """Publish test fixture to unique stream."""
    test_name = request.node.name
    urls = get_stream_urls(test_name)

    # Register stream for cleanup
    TEST_STREAM_REGISTRY[test_name] = urls["stream_name"]

    publisher = StreamPublisher(
        "tests/fixtures/test_streams/30s-counting-english.mp4",
        urls["rtsp_input"]
    )
    publisher.start()
    time.sleep(2)  # Wait for stream to be ready

    yield urls

    # Cleanup
    publisher.stop()
    del TEST_STREAM_REGISTRY[test_name]
```

**Cleanup Tracking**:
```python
CLEANUP_TASKS = []

def register_cleanup(task):
    """Register cleanup task (process, file, etc.)."""
    CLEANUP_TASKS.append(task)

def execute_cleanup():
    """Execute all cleanup tasks."""
    for task in CLEANUP_TASKS:
        try:
            if isinstance(task, subprocess.Popen):
                task.terminate()
                task.wait(timeout=5)
            elif callable(task):
                task()
        except Exception as e:
            print(f"Cleanup task failed: {e}")

# Register cleanup in conftest.py
@pytest.fixture(scope="session", autouse=True)
def cleanup_on_exit():
    yield
    execute_cleanup()
```

---

## 6. Socket.IO Event Monitor

**Description**: Async client for capturing fragment:processed events during tests.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| url | str | STS service URL | Required, "http://localhost:3000" |
| client | AsyncClient | SocketIO client instance | Required |
| events | asyncio.Queue | Event queue for captured events | Required |
| connected | bool | Connection state | Updated on connect/disconnect |

**Implementation**:
```python
# tests/e2e/helpers/socketio_monitor.py
import asyncio
from socketio import AsyncClient

class SocketIOMonitor:
    def __init__(self, url: str = "http://localhost:3000"):
        self.url = url
        self.client = AsyncClient()
        self.events = asyncio.Queue()
        self.connected = False

    async def connect(self):
        """Connect to STS service and register handlers."""
        @self.client.on("fragment:processed")
        async def on_fragment_processed(data):
            await self.events.put(data)

        await self.client.connect(self.url)
        self.connected = True

    async def wait_for_events(self, count: int, timeout: float = 180) -> list:
        """Wait for N fragment:processed events."""
        collected = []
        deadline = asyncio.get_event_loop().time() + timeout

        while len(collected) < count:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Only received {len(collected)}/{count} events in {timeout}s"
                )

            try:
                event = await asyncio.wait_for(
                    self.events.get(),
                    timeout=remaining
                )
                collected.append(event)
            except asyncio.TimeoutError:
                break

        return collected

    async def disconnect(self):
        """Disconnect from STS service."""
        if self.connected:
            await self.client.disconnect()
            self.connected = False
```

**Usage in Tests**:
```python
@pytest.mark.asyncio
async def test_full_pipeline_media_to_sts_to_output(
    dual_compose_env,
    publish_test_fixture
):
    monitor = SocketIOMonitor()
    await monitor.connect()

    # Wait for 5 segments to be processed
    events = await monitor.wait_for_events(count=5, timeout=180)

    # Validate all events have dubbed_audio
    for event in events:
        assert "dubbed_audio" in event
        assert len(event["dubbed_audio"]) > 0

    await monitor.disconnect()
```

---

## 7. Output Stream Validation Model

**Description**: Data model for validating output stream properties.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| stream_url | str | RTMP output URL | Required, rtmp://localhost:1935/live/{test}/out |
| duration_sec | float | Stream duration | Required, ~30s (+/- 0.5s tolerance) |
| video_codec | str | Video codec | Required, "h264" |
| audio_codec | str | Audio codec | Required, "aac" |
| av_sync_deltas | list[float] | PTS deltas per segment (ms) | All values < 120ms |
| audio_fingerprint | str | Spectral hash of output audio | Must differ from original |

**Validation Method**:
```python
def validate_output_stream(rtmp_url: str, original_audio_path: str) -> dict:
    """Validate output stream properties."""
    # 1. Check stream is playable
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        rtmp_url
    ], capture_output=True, text=True, timeout=10)

    data = json.loads(result.stdout)

    # 2. Validate codecs
    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert video_stream["codec_name"] == "h264"

    audio_stream = next(s for s in data["streams"] if s["codec_type"] == "audio")
    assert audio_stream["codec_name"] == "aac"

    # 3. Validate duration
    duration = float(data["format"]["duration"])
    assert 29.5 <= duration <= 30.5, f"Duration {duration}s out of range"

    # 4. Validate A/V sync
    av_sync_deltas = extract_av_sync_deltas(rtmp_url, duration)
    assert all(abs(d) < 120 for d in av_sync_deltas), "A/V sync delta > 120ms"

    # 5. Validate audio fingerprint
    output_audio = extract_audio_to_wav(rtmp_url)
    assert validate_dubbed_audio(original_audio_path, output_audio)

    return {
        "duration": duration,
        "av_sync_deltas": av_sync_deltas,
        "validation_passed": True
    }
```

---

## Summary

This data model defines 7 key entities for dual docker-compose E2E testing:

1. **Dual Compose Environment Configuration**: Manages two separate docker-compose files with health checks
2. **Test Fixture Metadata**: 30s counting phrases video with deterministic ASR validation
3. **Service Endpoint Configuration**: Internal vs. external URLs for cross-compose communication
4. **Pipeline Validation Metrics**: Socket.IO events, Prometheus metrics, audio fingerprinting
5. **Session State Tracking**: Test stream registry, cleanup tasks, lifecycle management
6. **Socket.IO Event Monitor**: Async client for capturing fragment:processed events
7. **Output Stream Validation Model**: Comprehensive output stream quality checks

All entities support session-scoped fixtures with unique stream names for optimal performance and isolation.
