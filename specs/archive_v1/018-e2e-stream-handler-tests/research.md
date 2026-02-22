# Research: E2E Test Infrastructure Patterns

**Date**: 2025-12-30
**Feature**: 018-e2e-stream-handler-tests

This document resolves technical unknowns from the implementation plan Phase 0 research tasks.

## 1. Docker Compose Test Patterns

**Question**: How to manage Docker Compose lifecycle in pytest fixtures?

**Decision**: Use subprocess-based Docker Compose management in conftest.py fixtures

**Rationale**:
- **pytest-docker plugin**: Adds dependency, limited flexibility for custom health checks
- **subprocess approach**: Direct control, standard tool (docker-compose CLI), works in all environments
- **Health checks**: Use `docker-compose ps` + retry logic for service readiness

**Implementation Pattern**:

```python
# tests/e2e/conftest.py
import subprocess
import time
import pytest

@pytest.fixture(scope="session")
def docker_services():
    """Start Docker Compose services and wait for readiness."""
    compose_file = "tests/e2e/docker-compose.yml"

    # Start services
    subprocess.run(
        ["docker-compose", "-f", compose_file, "up", "-d"],
        check=True,
        cwd="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler"
    )

    # Wait for services to be healthy
    max_retries = 30
    for i in range(max_retries):
        result = subprocess.run(
            ["docker-compose", "-f", compose_file, "ps", "--format", "json"],
            capture_output=True,
            text=True
        )
        # Check if all services are "running" (parse JSON output)
        if all_services_healthy(result.stdout):
            break
        time.sleep(1)
    else:
        raise RuntimeError("Services did not become healthy in time")

    yield  # Tests run here

    # Cleanup
    subprocess.run(
        ["docker-compose", "-f", compose_file, "down", "-v"],
        check=True
    )
```

**Health Check Strategy**:
- MediaMTX: Query RTSP endpoint (rtsp://localhost:8554/live/test/in with ffprobe)
- Echo STS: HTTP health check (GET http://localhost:8080/health)
- media-service: HTTP metrics endpoint (GET http://localhost:8000/metrics)

**Alternatives Considered**:
- pytest-docker: Rejected (adds dependency, less control over health checks)
- Docker SDK for Python: Rejected (overkill for simple compose lifecycle)
- Manual docker commands: Rejected (docker-compose handles networking better)

---

## 2. Prometheus Metrics Parsing

**Question**: How to parse /metrics endpoint in tests?

**Decision**: Use `prometheus_client.parser.text_string_to_metric_families()`

**Rationale**:
- prometheus_client is already a project dependency (used by media-service)
- Parser handles Prometheus text format correctly (metrics, labels, types)
- Returns structured data for easy assertions

**Implementation Pattern**:

```python
# tests/e2e/helpers/metrics_parser.py
import requests
from prometheus_client.parser import text_string_to_metric_families

def get_metric_value(url: str, metric_name: str, labels: dict = None) -> float:
    """Query /metrics endpoint and extract specific metric value."""
    response = requests.get(url)
    response.raise_for_status()

    for family in text_string_to_metric_families(response.text):
        if family.name == metric_name:
            for sample in family.samples:
                # Match labels if provided
                if labels is None or all(sample.labels.get(k) == v for k, v in labels.items()):
                    return sample.value

    raise ValueError(f"Metric {metric_name} not found")

# Usage in tests
def test_full_pipeline_metrics(docker_services):
    # ... run pipeline ...

    # Assert fragment count
    fragments_total = get_metric_value(
        "http://localhost:8000/metrics",
        "worker_audio_fragments_total"
    )
    assert fragments_total == 10  # 60s / 6s = 10 fragments

    # Assert in-flight count
    inflight = get_metric_value(
        "http://localhost:8000/metrics",
        "worker_inflight_fragments"
    )
    assert inflight == 0  # All completed
```

**Metric Assertions**:
- Counters: Check increment (final value - initial value)
- Gauges: Check current value (e.g., inflight_fragments == 0 at end)
- State enums: Check state transitions (breaker state: 0=closed, 1=open, 2=half-open)

**Alternatives Considered**:
- Regex parsing: Rejected (fragile, doesn't handle metric types)
- HTTP endpoint JSON: Rejected (Prometheus uses text format)
- Grafana API: Rejected (overkill for tests)

---

## 3. ffprobe PTS Analysis

**Question**: How to extract and compare PTS from output stream?

**Decision**: Use `ffprobe -show_packets -select_streams` with JSON output

**Rationale**:
- ffprobe provides packet-level PTS information
- JSON output is easy to parse in Python
- Can filter by stream type (video vs. audio)

**Implementation Pattern**:

```python
# tests/e2e/helpers/stream_analyzer.py
import subprocess
import json

def get_stream_pts(rtmp_url: str, stream_type: str, duration: int = 60) -> list[float]:
    """Extract PTS values from RTMP stream.

    Args:
        rtmp_url: RTMP stream URL (e.g., rtmp://localhost:1935/live/test/out)
        stream_type: 'video' or 'audio'
        duration: How long to capture (seconds)

    Returns:
        List of PTS values in seconds
    """
    stream_specifier = "v:0" if stream_type == "video" else "a:0"

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-show_packets",
            "-select_streams", stream_specifier,
            "-print_format", "json",
            "-read_intervals", f"%+{duration}",  # Read for N seconds
            rtmp_url
        ],
        capture_output=True,
        text=True,
        timeout=duration + 10
    )

    data = json.loads(result.stdout)
    pts_values = [
        float(packet["pts_time"])
        for packet in data.get("packets", [])
        if "pts_time" in packet
    ]

    return pts_values

def calculate_av_sync_delta(video_pts: list[float], audio_pts: list[float]) -> list[float]:
    """Calculate A/V sync delta for aligned segments.

    Returns:
        List of sync deltas in milliseconds (positive = audio ahead)
    """
    # Align by nearest PTS values (assume 6s segments)
    deltas = []
    for v_pts in video_pts[::180]:  # Sample every 6s (30fps * 6s = 180 frames)
        # Find nearest audio PTS
        nearest_a_pts = min(audio_pts, key=lambda a: abs(a - v_pts))
        delta_ms = (nearest_a_pts - v_pts) * 1000
        deltas.append(delta_ms)

    return deltas

# Usage in tests
def test_av_sync_within_threshold(docker_services, stream_publisher):
    # ... run pipeline ...

    # Extract PTS from output stream
    video_pts = get_stream_pts("rtmp://localhost:1935/live/test/out", "video", duration=60)
    audio_pts = get_stream_pts("rtmp://localhost:1935/live/test/out", "audio", duration=60)

    # Calculate sync deltas
    deltas = calculate_av_sync_delta(video_pts, audio_pts)

    # Assert 95% of segments within 120ms threshold
    within_threshold = [abs(d) < 120 for d in deltas]
    assert sum(within_threshold) / len(within_threshold) >= 0.95
```

**Key Considerations**:
- RTMP streams require timeout handling (ffprobe can hang)
- PTS values are in stream timebase, convert to seconds with `pts_time`
- A/V alignment requires matching video/audio segments (use sampling)

**Alternatives Considered**:
- MediaInfo: Rejected (doesn't provide packet-level PTS)
- GStreamer probes: Rejected (requires running pipeline, not output analysis)
- Manual stream parsing: Rejected (complex, error-prone)

---

## 4. Socket.IO Server-Side Disconnect

**Question**: How does Echo STS force disconnect from server?

**Decision**: Use `socketio.disconnect(sid)` in event handler

**Rationale**:
- python-socketio provides `disconnect(sid)` method to force client disconnect
- Cleanly closes connection, triggers client reconnection logic
- Can be wrapped in event handler for test control

**Implementation Pattern**:

```python
# apps/media-service/src/media_service/sts/echo_server.py (enhancement)
import socketio
import asyncio

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

@sio.event
async def simulate_disconnect(sid, data):
    """Force disconnect for testing reconnection logic.

    Args:
        sid: Socket.IO session ID
        data: { "delay_ms": 0 } - Optional delay before disconnect
    """
    delay_ms = data.get("delay_ms", 0)

    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)

    # Force disconnect
    await sio.disconnect(sid)

    # No response - connection will be closed

# Usage in E2E test
async def test_worker_reconnects_after_disconnect(docker_services):
    import socketio

    # Trigger disconnect via test client
    test_client = socketio.AsyncClient()
    await test_client.connect("http://localhost:8080")
    await test_client.emit("simulate:disconnect", {"delay_ms": 0})

    # Wait for worker to reconnect
    await asyncio.sleep(5)  # Allow for backoff

    # Verify reconnection via metrics
    reconnect_count = get_metric_value(
        "http://localhost:8000/metrics",
        "worker_reconnection_total"
    )
    assert reconnect_count == 1
```

**Disconnect Behavior**:
- Server calls `sio.disconnect(sid)`
- Client receives `disconnect` event
- Client triggers reconnection logic (exponential backoff: 2s, 4s, 8s, 16s, 32s)
- Client re-sends `stream:init` after reconnection

**Alternatives Considered**:
- Container restart: Rejected (slow, affects other tests)
- Network manipulation (iptables): Rejected (requires root, platform-specific)
- Mock Socket.IO client: Rejected (doesn't test real reconnection logic)

---

## 5. Test Fixture Acquisition

**Question**: Where to get deterministic 60s video file?

**Decision**: Use Big Buck Bunny 60s clip (Creative Commons license)

**Rationale**:
- Big Buck Bunny is copyright-free (Creative Commons Attribution 3.0)
- High quality H.264 + AAC source available
- Predictable properties (known resolution, frame rate, duration)
- Widely used for video testing

**Source**:
- URL: https://test-videos.co.uk/bigbuckbunny/mp4-h264 (60s clips available)
- Alternative: Generate with ffmpeg from full movie

**Fallback - Generate Synthetic Fixture**:

```bash
# Generate 60s test video with color bars and tone
ffmpeg -f lavfi -i testsrc=duration=60:size=1280x720:rate=30 \
       -f lavfi -i sine=frequency=440:duration=60:sample_rate=48000 \
       -c:v libx264 -preset fast -crf 22 \
       -c:a aac -b:a 128k \
       tests/e2e/fixtures/test-streams/1-min-synthetic.mp4
```

**Fixture Properties**:
- File: `tests/e2e/fixtures/test-streams/1-min-nfl.mp4` (or Big Buck Bunny)
- Duration: 60 seconds (verified with `ffprobe -show_format`)
- Video: H.264, 1280x720, 30fps
- Audio: AAC, 48kHz stereo, 128kbps
- File size: ~5-10 MB (acceptable for git LFS or fixture download)

**Alternatives Considered**:
- Custom recording: Rejected (copyright issues, inconsistent quality)
- Random test videos: Rejected (not deterministic)
- Tiny video (10s): Rejected (too short for fragment testing)

---

## Summary of Decisions

| Research Task | Decision | Key Tool/Library |
|---------------|----------|------------------|
| Docker Compose lifecycle | subprocess-based management | docker-compose CLI |
| Metrics parsing | Parse Prometheus text format | prometheus_client.parser |
| PTS analysis | ffprobe JSON output | ffprobe -show_packets |
| Server-side disconnect | socketio.disconnect(sid) | python-socketio server |
| Test fixture | Big Buck Bunny 60s clip | ffmpeg (fallback: synthetic) |

All research tasks resolved. Ready for Phase 1 design (data-model.md, contracts/).
