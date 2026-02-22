# Data Model: E2E Test Entities

**Feature**: 018-e2e-stream-handler-tests
**Date**: 2025-12-30

This document defines the entities and data structures used in E2E tests.

## 1. E2E Test Environment

**Description**: Docker Compose environment running MediaMTX, media-service, and echo-sts.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| services | dict | Service configurations (mediamtx, media-service, echo-sts) | Required, all 3 services present |
| network | str | Shared Docker network name | Required, e.g., "e2e-test-network" |
| volumes | dict | Volume mappings for test fixtures | Optional, maps host paths to container paths |
| environment | dict | Environment variable overrides | Optional, e.g., RTSP_URL, STS_URL |

**State Transitions**:
1. **Stopped** → `docker-compose up -d` → **Starting**
2. **Starting** → All health checks pass → **Ready**
3. **Ready** → Tests execute → **Running**
4. **Running** → `docker-compose down -v` → **Stopped**

**Lifecycle Management**:
- Created in `conftest.py` session-scoped fixture
- Started before any tests run
- Health checks wait for service readiness
- Cleaned up after all tests complete (even on failure)

**Example**:
```yaml
# tests/e2e/docker-compose.yml
version: '3.8'

services:
  mediamtx:
    image: bluenviron/mediamtx:latest
    ports:
      - "8554:8554"  # RTSP
      - "1935:1935"  # RTMP
    networks:
      - e2e-test-network

  media-service:
    build:
      context: ../../apps/media-service
      dockerfile: deploy/Dockerfile
    environment:
      - RTSP_URL=rtsp://mediamtx:8554/live/test/in
      - STS_URL=http://echo-sts:8080
      - METRICS_PORT=8000
    ports:
      - "8000:8000"  # Metrics
    networks:
      - e2e-test-network
    depends_on:
      - mediamtx
      - echo-sts

  echo-sts:
    build:
      context: ../../apps/media-service
      dockerfile: deploy/Dockerfile.echo-sts
    ports:
      - "8080:8080"  # Socket.IO
    networks:
      - e2e-test-network

networks:
  e2e-test-network:
    driver: bridge
```

---

## 2. Test Fixture

**Description**: Pre-recorded video file with known properties for deterministic testing.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| file_path | str | Absolute path to test video | Required, must exist |
| duration_sec | int | Duration in seconds | Required, 60s |
| video_codec | str | Video codec | Required, "h264" |
| video_resolution | str | Resolution (WxH) | Required, "1280x720" |
| video_fps | int | Frame rate | Required, 30 |
| audio_codec | str | Audio codec | Required, "aac" |
| audio_sample_rate | int | Audio sample rate (Hz) | Required, 48000 |
| audio_channels | int | Audio channel count | Required, 2 (stereo) |
| expected_segments | int | Expected 6s segments | Calculated: duration_sec / 6 |

**Validation Rules**:
- File must exist before tests run
- Duration verified with ffprobe
- Video and audio streams must be present
- File size < 50 MB (reasonable for test fixtures)

**Publishing Method**:
```python
# tests/e2e/helpers/stream_publisher.py
import subprocess

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
            "-stream_loop", "-1",  # Loop indefinitely
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

**Example**:
```python
# Usage in conftest.py
@pytest.fixture
def stream_publisher(docker_services):
    publisher = StreamPublisher(
        fixture_path="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/fixtures/test-streams/1-min-nfl.mp4",
        rtsp_url="rtsp://localhost:8554/live/test/in"
    )
    publisher.start()
    time.sleep(2)  # Wait for stream to be ready
    yield publisher
    publisher.stop()
```

---

## 3. Pipeline Metrics Snapshot

**Description**: Captured Prometheus metrics at test completion for validation.

**Properties**:

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| worker_audio_fragments_total | counter | status=sent\|processed\|fallback | Total fragments by status |
| worker_fallback_total | counter | reason=timeout\|error\|circuit_open | Fallback audio usage |
| worker_inflight_fragments | gauge | - | Current in-flight count |
| worker_av_sync_delta_ms | histogram | - | A/V sync delta distribution |
| worker_sts_breaker_state | gauge | - | Circuit breaker state (0=closed, 1=open, 2=half-open) |
| worker_backpressure_events_total | counter | action=pause\|slow_down\|none | Backpressure events by action |
| worker_reconnection_total | counter | - | Total reconnection attempts |

**Parsing Method**:
```python
# tests/e2e/helpers/metrics_parser.py
from prometheus_client.parser import text_string_to_metric_families
import requests

class MetricsClient:
    def __init__(self, metrics_url: str):
        self.metrics_url = metrics_url

    def get_counter(self, name: str, labels: dict = None) -> float:
        """Get counter value (current total)."""
        response = requests.get(self.metrics_url)
        response.raise_for_status()

        for family in text_string_to_metric_families(response.text):
            if family.name == name:
                for sample in family.samples:
                    if labels is None or self._labels_match(sample.labels, labels):
                        return sample.value
        raise ValueError(f"Counter {name} not found")

    def get_gauge(self, name: str) -> float:
        """Get gauge current value."""
        # Similar to get_counter

    @staticmethod
    def _labels_match(sample_labels: dict, target_labels: dict) -> bool:
        return all(sample_labels.get(k) == v for k, v in target_labels.items())
```

**Example Assertions**:
```python
def test_full_pipeline_metrics(docker_services, stream_publisher):
    metrics = MetricsClient("http://localhost:8000/metrics")

    # Wait for pipeline to complete
    time.sleep(90)

    # Assert 10 fragments sent (60s / 6s = 10)
    fragments_sent = metrics.get_counter(
        "worker_audio_fragments_total",
        labels={"status": "sent"}
    )
    assert fragments_sent == 10

    # Assert all fragments processed (no fallback)
    fragments_processed = metrics.get_counter(
        "worker_audio_fragments_total",
        labels={"status": "processed"}
    )
    assert fragments_processed == 10

    # Assert no in-flight fragments at end
    inflight = metrics.get_gauge("worker_inflight_fragments")
    assert inflight == 0
```

---

## 4. A/V Sync Measurement

**Description**: PTS delta between video and audio at each output segment pair.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| segment_index | int | Segment number (0-9 for 60s stream) | Required |
| video_pts | float | Video PTS in seconds | Required, monotonically increasing |
| audio_pts | float | Audio PTS in seconds | Required, monotonically increasing |
| delta_ms | float | Sync delta in milliseconds | Calculated: (audio_pts - video_pts) * 1000 |
| within_threshold | bool | Delta < 120ms threshold | Calculated: abs(delta_ms) < 120 |

**Extraction Method**:
```python
# tests/e2e/helpers/stream_analyzer.py
import subprocess
import json

def extract_segment_pts(rtmp_url: str, duration: int = 60) -> list[dict]:
    """Extract PTS for video and audio segments.

    Returns:
        List of dicts: [
            {"segment": 0, "video_pts": 0.0, "audio_pts": 0.02, "delta_ms": 20},
            {"segment": 1, "video_pts": 6.0, "audio_pts": 6.01, "delta_ms": 10},
            ...
        ]
    """
    # Get video PTS
    video_pts = _get_stream_pts(rtmp_url, "video", duration)
    audio_pts = _get_stream_pts(rtmp_url, "audio", duration)

    # Sample at 6s intervals (segment boundaries)
    segments = []
    for i in range(10):  # 60s / 6s = 10 segments
        segment_time = i * 6.0

        # Find nearest PTS to segment boundary
        v_pts = min(video_pts, key=lambda p: abs(p - segment_time))
        a_pts = min(audio_pts, key=lambda p: abs(p - segment_time))

        delta_ms = (a_pts - v_pts) * 1000

        segments.append({
            "segment": i,
            "video_pts": v_pts,
            "audio_pts": a_pts,
            "delta_ms": delta_ms,
            "within_threshold": abs(delta_ms) < 120
        })

    return segments

def _get_stream_pts(rtmp_url: str, stream_type: str, duration: int) -> list[float]:
    """Internal helper to extract PTS from stream."""
    stream_specifier = "v:0" if stream_type == "video" else "a:0"

    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_packets",
        "-select_streams", stream_specifier,
        "-print_format", "json",
        "-read_intervals", f"%+{duration}",
        rtmp_url
    ], capture_output=True, text=True, timeout=duration + 10)

    data = json.loads(result.stdout)
    return [float(p["pts_time"]) for p in data.get("packets", []) if "pts_time" in p]
```

**Example Test**:
```python
def test_av_sync_within_threshold(docker_services, stream_publisher):
    # Wait for pipeline to complete
    time.sleep(90)

    # Extract PTS measurements
    segments = extract_segment_pts("rtmp://localhost:1935/live/test/out", duration=60)

    # Assert 95% of segments within threshold
    within_threshold_count = sum(s["within_threshold"] for s in segments)
    assert within_threshold_count / len(segments) >= 0.95

    # Log deltas for debugging
    for s in segments:
        print(f"Segment {s['segment']}: delta={s['delta_ms']:.2f}ms")
```

---

## 5. Circuit Breaker State Log

**Description**: Captured state transitions during circuit breaker testing.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| timestamp | float | Event timestamp (seconds since epoch) | Required |
| state | str | Breaker state | Required: "closed" \| "open" \| "half-open" |
| trigger | str | Event that caused transition | Optional: "failure" \| "timeout" \| "success" |
| failure_count | int | Consecutive failures before open | Optional, >= 5 to trigger open |

**Extraction Method**:
```python
# Parse from container logs
def extract_breaker_transitions(container_name: str) -> list[dict]:
    """Extract circuit breaker state transitions from logs."""
    result = subprocess.run([
        "docker", "logs", container_name
    ], capture_output=True, text=True)

    transitions = []
    for line in result.stdout.splitlines():
        if "circuit breaker" in line.lower():
            # Parse structured log: {"msg": "circuit breaker opened", "state": "open", ...}
            log_entry = json.loads(line)
            transitions.append({
                "timestamp": log_entry["timestamp"],
                "state": log_entry["state"],
                "trigger": log_entry.get("trigger"),
                "failure_count": log_entry.get("failure_count")
            })

    return transitions
```

**Example Test**:
```python
def test_circuit_breaker_opens_on_sts_failures(docker_services):
    # Configure Echo STS to return 5 consecutive errors
    # ...

    # Wait for breaker to open
    time.sleep(30)

    # Verify state transitions
    transitions = extract_breaker_transitions("media-service")
    assert len(transitions) >= 2  # closed → open

    # Verify breaker opened after 5 failures
    open_transition = next(t for t in transitions if t["state"] == "open")
    assert open_transition["failure_count"] == 5

    # Verify metric reflects open state
    breaker_state = MetricsClient("http://localhost:8000/metrics").get_gauge(
        "worker_sts_breaker_state"
    )
    assert breaker_state == 1  # 1 = open
```

---

## 6. Backpressure Event Log

**Description**: Captured backpressure events during backpressure testing.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| timestamp | float | Event timestamp | Required |
| severity | str | Backpressure severity | Required: "low" \| "medium" \| "high" |
| action | str | Recommended action | Required: "none" \| "slow_down" \| "pause" |
| recommended_delay_ms | int | Delay to insert (if action=slow_down) | Optional, > 0 |

**Schema** (from spec 017):
```json
{
  "severity": "medium",
  "action": "slow_down",
  "recommended_delay_ms": 500
}
```

**Example Test**:
```python
def test_worker_respects_backpressure(docker_services):
    # Configure Echo STS to emit backpressure
    # ...

    # Wait for backpressure events
    time.sleep(30)

    # Verify metrics
    metrics = MetricsClient("http://localhost:8000/metrics")

    pause_events = metrics.get_counter(
        "worker_backpressure_events_total",
        labels={"action": "pause"}
    )
    assert pause_events >= 1

    slow_down_events = metrics.get_counter(
        "worker_backpressure_events_total",
        labels={"action": "slow_down"}
    )
    assert slow_down_events >= 1
```

---

## 7. Reconnection Attempt Log

**Description**: Captured reconnection attempts with backoff timing validation.

**Properties**:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| attempt | int | Reconnection attempt number | Required, 1-5 |
| timestamp | float | Attempt timestamp | Required |
| backoff_delay_sec | float | Expected delay before this attempt | Calculated: 2^attempt |
| actual_delay_sec | float | Measured delay from previous attempt | Calculated from timestamps |
| success | bool | Reconnection succeeded | Required |

**Expected Backoff Schedule**:
- Attempt 1: 2s delay
- Attempt 2: 4s delay
- Attempt 3: 8s delay
- Attempt 4: 16s delay
- Attempt 5: 32s delay

**Extraction Method**:
```python
def extract_reconnection_attempts(container_name: str) -> list[dict]:
    """Extract reconnection attempts from logs."""
    result = subprocess.run([
        "docker", "logs", container_name
    ], capture_output=True, text=True)

    attempts = []
    for line in result.stdout.splitlines():
        if "reconnection attempt" in line.lower():
            log_entry = json.loads(line)
            attempts.append({
                "attempt": log_entry["attempt"],
                "timestamp": log_entry["timestamp"],
                "success": log_entry.get("success", False)
            })

    # Calculate delays
    for i in range(1, len(attempts)):
        attempts[i]["actual_delay_sec"] = (
            attempts[i]["timestamp"] - attempts[i - 1]["timestamp"]
        )
        attempts[i]["expected_delay_sec"] = 2 ** attempts[i]["attempt"]

    return attempts
```

**Example Test**:
```python
def test_worker_reconnects_after_sts_disconnect(docker_services):
    # Force disconnect via Echo STS
    # ...

    # Wait for reconnection sequence
    time.sleep(40)  # 2+4+8+16 = 30s + buffer

    # Verify reconnection attempts
    attempts = extract_reconnection_attempts("media-service")

    # Verify backoff timing (within 20% tolerance)
    for attempt in attempts[1:]:  # Skip first (immediate)
        expected = attempt["expected_delay_sec"]
        actual = attempt["actual_delay_sec"]
        assert abs(actual - expected) / expected < 0.2  # 20% tolerance

    # Verify reconnection succeeded
    assert any(a["success"] for a in attempts)

    # Verify metric
    reconnect_count = MetricsClient("http://localhost:8000/metrics").get_counter(
        "worker_reconnection_total"
    )
    assert reconnect_count >= 1
```

---

## Summary

This data model defines 7 key entities for E2E testing:

1. **E2E Test Environment**: Docker Compose services (MediaMTX, media-service, echo-sts)
2. **Test Fixture**: 60s video file with known properties
3. **Pipeline Metrics Snapshot**: Prometheus metrics for validation
4. **A/V Sync Measurement**: PTS deltas between video/audio segments
5. **Circuit Breaker State Log**: State transitions during failure testing
6. **Backpressure Event Log**: Backpressure events and worker response
7. **Reconnection Attempt Log**: Reconnection attempts with backoff timing

All entities have well-defined extraction methods and validation rules for deterministic testing.
