# Quick Start Guide: Stream Worker Implementation

**Feature**: Stream Worker Implementation
**Date**: 2025-12-28
**Time to First Test**: ~15 minutes

## Prerequisites

### System Requirements

- Python 3.10.x
- Docker and Docker Compose
- GStreamer 1.x with Python bindings (optional for unit tests, required for integration)
- ffmpeg/ffprobe (for fixture verification)

### Verify GStreamer Installation

```bash
# Check GStreamer version
gst-launch-1.0 --version

# Check Python bindings
python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; Gst.init(None); print('GStreamer OK')"
```

### Install GStreamer (if needed)

**macOS**:
```bash
brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav pygobject3
```

**Ubuntu/Debian**:
```bash
apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3-gi \
    gir1.2-gst-plugins-base-1.0
```

## Setup Development Environment

### 1. Clone and Navigate

```bash
cd /path/to/live-broadcast-dubbing-cloud
git checkout 003-stream-worker
cd apps/media-service
```

### 2. Create Virtual Environment

```bash
# Using make target (recommended)
make media-setup

# Or manually
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Verify Test Fixture

```bash
# Check fixture exists and is valid
ffprobe -v quiet -print_format json -show_format tests/fixtures/test-streams/1-min-nfl.mp4

# Expected: 60s H.264 video + AAC audio
```

## Run Tests

### Unit Tests (No Docker Required)

```bash
# Run all unit tests
make media-test-unit

# Run specific test file
pytest tests/unit/test_stream_worker.py -v

# Run with coverage
pytest tests/unit/ --cov=media_service --cov-report=term-missing
```

### Integration Tests (Docker Required)

```bash
# Start MediaMTX container
make media-dev

# Wait for MediaMTX to be ready
curl -s http://localhost:9997/v3/paths/list

# Run integration tests
make media-test-integration

# View logs if tests fail
make media-logs
```

### All Tests with Coverage

```bash
make media-test-coverage
```

## Manual Testing with Test Fixture

### 1. Start MediaMTX

```bash
make media-dev
```

### 2. Publish Test Stream

```bash
# Using FFmpeg (recommended)
ffmpeg -re -stream_loop -1 \
    -i tests/fixtures/test-streams/1-min-nfl.mp4 \
    -c copy \
    -f rtmp rtmp://localhost:1935/live/test/in

# Or using GStreamer
gst-launch-1.0 filesrc location=tests/fixtures/test-streams/1-min-nfl.mp4 \
    ! qtdemux name=demux \
    demux.video_0 ! queue ! h264parse ! flvmux name=mux \
    demux.audio_0 ! queue ! aacparse ! mux. \
    mux. ! rtmpsink location='rtmp://localhost:1935/live/test/in'
```

### 3. Verify Input Stream

```bash
# Check stream appears in MediaMTX
curl -s http://localhost:9997/v3/paths/list | jq '.items[] | select(.name | contains("test"))'

# Play input stream
ffplay rtmp://localhost:1935/live/test/in
```

### 4. Run Worker (Passthrough Mode)

```bash
# Run worker in passthrough mode
python -m media_service.worker.stream_worker \
    --stream-id test \
    --sts-mode passthrough
```

### 5. Verify Output Stream

```bash
# Play output stream
ffplay rtmp://localhost:1935/live/test/out

# Probe output codec (should be H.264)
ffprobe -v quiet -select_streams v -show_entries stream=codec_name \
    rtmp://localhost:1935/live/test/out
```

### 6. Check Metrics

```bash
curl http://localhost:8000/metrics
```

## TDD Workflow

Follow this workflow for each new component:

### 1. Write Failing Tests

```bash
# Example: Audio Chunker
# Create test file first
touch tests/unit/test_chunker.py
```

```python
# tests/unit/test_chunker.py
import pytest

class TestAudioChunker:
    def test_chunker_accumulates_to_target_duration(self):
        from media_service.audio.chunker import AudioChunker

        chunker = AudioChunker(target_duration_ms=1000)

        # Simulate 50 x 20ms PCM buffers (48kHz stereo S16LE)
        buffer_size = int(0.020 * 48000 * 2 * 2)  # 3840 bytes per 20ms
        for i in range(50):
            chunk = chunker.push(b'\x00' * buffer_size, pts_ns=i * 20_000_000)
            if i < 49:
                assert chunk is None

        # 50th buffer should emit a chunk
        assert chunk is not None
        assert 990 <= chunk.duration_ns / 1_000_000 <= 1010
```

### 2. Run Tests - Verify Failure

```bash
pytest tests/unit/test_chunker.py -v
# Expected: ImportError or test failure
```

### 3. Implement Minimal Code

```python
# src/media_service/audio/chunker.py
from dataclasses import dataclass

@dataclass
class PcmChunk:
    fragment_id: str
    t0_ns: int
    duration_ns: int
    pcm_s16le: bytes

class AudioChunker:
    def __init__(self, target_duration_ms: int = 1000):
        self.target_bytes = int(target_duration_ms / 1000 * 48000 * 2 * 2)
        # ... implementation
```

### 4. Run Tests - Verify Pass

```bash
pytest tests/unit/test_chunker.py -v
# Expected: PASSED
```

### 5. Check Coverage

```bash
pytest tests/unit/test_chunker.py --cov=media_service.audio --cov-fail-under=80
```

## Directory Structure After Implementation

```
apps/media-service/
├── src/
│   └── media_service/
│       ├── __init__.py
│       ├── worker/
│       │   ├── stream_worker.py      # Extended
│       │   └── worker_runner.py      # New
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── input.py
│       │   ├── output.py
│       │   └── elements.py
│       ├── audio/
│       │   ├── __init__.py
│       │   └── chunker.py
│       ├── sts/
│       │   ├── __init__.py
│       │   ├── client.py
│       │   └── circuit_breaker.py
│       ├── sync/
│       │   ├── __init__.py
│       │   └── av_sync.py
│       └── metrics/
│           ├── __init__.py
│           └── prometheus.py
└── tests/
    ├── unit/
    │   ├── test_stream_worker.py     # Existing
    │   ├── test_chunker.py           # New
    │   ├── test_sts_client.py        # New
    │   ├── test_circuit_breaker.py   # New
    │   └── test_av_sync.py           # New
    └── integration/
        ├── test_pipeline_passthrough.py
        └── conftest.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDIAMTX_HOST` | `localhost` | MediaMTX server hostname |
| `MEDIAMTX_RTSP_PORT` | `8554` | RTSP port for input |
| `MEDIAMTX_RTMP_PORT` | `1935` | RTMP port for output |
| `WORKER_STS_SERVICE_URL` | - | STS Service API URL |
| `WORKER_STS_API_KEY` | - | STS Service API key |
| `WORKER_STS_TIMEOUT_MS` | `8000` | STS request timeout |
| `WORKER_STS_MAX_RETRIES` | `2` | STS retry attempts |
| `WORKER_FRAGMENT_TARGET_DUR` | `1000` | Target chunk duration (ms) |
| `WORKER_AV_OFFSET_NS` | `6000000000` | A/V sync offset (6s) |
| `WORKER_METRICS_PORT` | `8000` | Prometheus metrics port |

## Troubleshooting

### GStreamer Not Found

```bash
# Check if gi module is available
python3 -c "import gi"

# If not, install system-wide (not in venv)
pip install PyGObject
```

### MediaMTX Connection Refused

```bash
# Check if container is running
docker-compose ps

# Check logs
docker-compose logs mediamtx

# Restart
docker-compose down && docker-compose up -d
```

### Test Fixture Missing

```bash
# Download or create test fixture
# The 1-min-nfl.mp4 should be in tests/fixtures/test-streams/
ls -la tests/fixtures/test-streams/

# Verify fixture format
ffprobe tests/fixtures/test-streams/1-min-nfl.mp4
```

### Coverage Below 80%

```bash
# Identify uncovered lines
pytest --cov=media_service --cov-report=html
open htmlcov/index.html
```

## Next Steps

1. Run `/speckit.tasks` to generate implementation tasks
2. Start Phase 1: GStreamer Pipeline Foundation
3. Follow TDD workflow for each module
4. Run integration tests with 1-min-nfl.mp4 after each phase
