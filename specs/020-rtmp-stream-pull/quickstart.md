# Quick Start: RTMP Stream Pull Migration

**Feature**: 020-rtmp-stream-pull
**Audience**: Developers implementing the RTMP migration
**Time**: 30 minutes to implement + test

## Overview

This guide walks through migrating the media-service input pipeline from RTSP to RTMP stream pulling. Follow TDD workflow: write tests first, then implement changes.

## Prerequisites

- Python 3.10 development environment
- GStreamer 1.0 with rtmpsrc and flvdemux elements installed
- Docker Compose (for integration/E2E tests)
- MediaMTX configured for RTMP input

## Implementation Phases

### Phase 1: Update InputPipeline (TDD)

**Time**: 15 minutes

#### Step 1.1: Write Failing Unit Tests

Create/update tests in `apps/media-service/tests/unit/test_input_pipeline.py`:

```python
import pytest
from media_service.pipeline.input import InputPipeline


def test_input_pipeline_rtmp_url_validation():
    """Test RTMP URL format validation."""
    video_cb = lambda *args: None
    audio_cb = lambda *args: None

    # Valid RTMP URLs (should NOT raise)
    pipeline = InputPipeline("rtmp://mediamtx:1935/live/test/in", video_cb, audio_cb)
    assert pipeline._rtmp_url == "rtmp://mediamtx:1935/live/test/in"

    # Invalid URLs (should raise ValueError)
    with pytest.raises(ValueError, match="must start with 'rtmp://'"):
        InputPipeline("rtsp://mediamtx:8554/live/test/in", video_cb, audio_cb)

    with pytest.raises(ValueError, match="cannot be empty"):
        InputPipeline("", video_cb, audio_cb)


def test_input_pipeline_build_rtmp_elements(mock_gstreamer):
    """Test RTMP pipeline element creation."""
    with patch("media_service.pipeline.input.Gst.ElementFactory.make") as mock_make:
        # Mock element creation
        mock_elements = {
            "rtmpsrc": MagicMock(name="rtmpsrc"),
            "flvdemux": MagicMock(name="flvdemux"),
            "h264parse": MagicMock(name="h264parse"),
            "aacparse": MagicMock(name="aacparse"),
        }
        mock_make.side_effect = lambda name, *args: mock_elements.get(name, MagicMock())

        pipeline = InputPipeline("rtmp://mediamtx:1935/live/test/in", lambda: None, lambda: None)
        pipeline.build()

        # Assert RTMP elements created
        mock_make.assert_any_call("rtmpsrc", "rtmpsrc")
        mock_make.assert_any_call("flvdemux", "flvdemux")

        # Assert NO RTSP elements created
        assert not any("rtspsrc" in str(call) for call in mock_make.call_args_list)
        assert not any("rtph264depay" in str(call) for call in mock_make.call_args_list)
```

**Run tests** (should FAIL):
```bash
cd apps/media-service
pytest tests/unit/test_input_pipeline.py::test_input_pipeline_rtmp_url_validation -v
pytest tests/unit/test_input_pipeline.py::test_input_pipeline_build_rtmp_elements -v
```

Expected: Tests fail because InputPipeline still expects RTSP URLs and creates RTSP elements.

---

#### Step 1.2: Update InputPipeline Implementation

Edit `apps/media-service/src/media_service/pipeline/input.py`:

**Change 1: Update __init__ signature**
```python
# Before
def __init__(
    self,
    rtsp_url: str,
    on_video_buffer: BufferCallback,
    on_audio_buffer: BufferCallback,
    latency: int = 200,
) -> None:

# After
def __init__(
    self,
    rtmp_url: str,
    on_video_buffer: BufferCallback,
    on_audio_buffer: BufferCallback,
    max_buffers: int = 10,
) -> None:
```

**Change 2: Update URL validation**
```python
# Before
if not rtsp_url.startswith("rtsp://"):
    raise ValueError(f"Invalid RTSP URL: must start with 'rtsp://' - got '{rtsp_url}'")
self._rtsp_url = rtsp_url

# After
if not rtmp_url.startswith("rtmp://"):
    raise ValueError(f"Invalid RTMP URL: must start with 'rtmp://' - got '{rtmp_url}'")
self._rtmp_url = rtmp_url
```

**Change 3: Update build() method**
```python
# Before
rtspsrc = Gst.ElementFactory.make("rtspsrc", "rtspsrc")
rtspsrc.set_property("location", self._rtsp_url)
rtspsrc.set_property("protocols", "tcp")
rtspsrc.set_property("latency", self._latency)

rtph264depay = Gst.ElementFactory.make("rtph264depay", "rtph264depay")
# ... dynamic audio depayloader creation in _on_pad_added

# After
rtmpsrc = Gst.ElementFactory.make("rtmpsrc", "rtmpsrc")
rtmpsrc.set_property("location", self._rtmp_url)

flvdemux = Gst.ElementFactory.make("flvdemux", "flvdemux")
flvdemux.set_property("max-buffers", self._max_buffers)
```

**Change 4: Simplify _on_pad_added**
```python
# Before (complex RTP encoding detection)
def _on_pad_added(self, element, pad):
    # ... 80 lines of RTP caps parsing and dynamic depayloader creation

# After (simple FLV pad handling)
def _on_pad_added(self, element, pad):
    """Handle flvdemux pad creation for video/audio."""
    caps = pad.get_current_caps() or pad.query_caps(None)
    if caps is None or caps.is_empty():
        return

    structure = caps.get_structure(0)
    name = structure.get_name()

    if name.startswith("video"):
        sink_pad = self._h264parse.get_static_pad("sink")
        if sink_pad and not sink_pad.is_linked():
            pad.link(sink_pad)
            logger.info("Linked flvdemux video pad to h264parse")
    elif name.startswith("audio"):
        sink_pad = self._aacparse.get_static_pad("sink")
        if sink_pad and not sink_pad.is_linked():
            pad.link(sink_pad)
            logger.info("Linked flvdemux audio pad to aacparse")
```

**Change 5: Update element linking**
```python
# Before
rtspsrc.connect("pad-added", self._on_pad_added)  # Dynamic linking

# After
flvdemux.connect("pad-added", self._on_pad_added)  # Simpler dynamic linking

# Static linking (same as before, but source is flvdemux instead of depayloaders)
# h264parse -> video_queue -> video_appsink
# aacparse -> audio_queue -> audio_appsink
```

**Run tests** (should PASS):
```bash
pytest tests/unit/test_input_pipeline.py -v
```

Expected: All unit tests pass.

---

### Phase 2: Update WorkerRunner (TDD)

**Time**: 5 minutes

#### Step 2.1: Write Failing Unit Tests

Edit `apps/media-service/tests/unit/test_worker_runner.py`:

```python
def test_worker_runner_constructs_rtmp_url():
    """Test WorkerRunner builds RTMP URL from configuration."""
    with patch("media_service.worker.worker_runner.InputPipeline") as mock_pipeline:
        config = WorkerConfig(
            mediamtx_host="mediamtx",
            mediamtx_rtmp_port=1935,
            app_path="live",
            stream_id="test123",
        )

        runner = WorkerRunner(config)
        runner.initialize()

        # Assert InputPipeline initialized with RTMP URL
        mock_pipeline.assert_called_once()
        rtmp_url = mock_pipeline.call_args[0][0]
        assert rtmp_url == "rtmp://mediamtx:1935/live/test123/in"
        assert rtmp_url.startswith("rtmp://")
```

**Run tests** (should FAIL):
```bash
pytest tests/unit/test_worker_runner.py::test_worker_runner_constructs_rtmp_url -v
```

---

#### Step 2.2: Update WorkerRunner Implementation

Edit `apps/media-service/src/media_service/worker/worker_runner.py`:

**Change 1: Update URL construction**
```python
# Before
rtsp_url = f"rtsp://{self.config.mediamtx_host}:{self.config.mediamtx_rtsp_port}/live/{self.stream_id}/in"
self.input_pipeline = InputPipeline(
    rtsp_url,
    self._on_video_buffer,
    self._on_audio_buffer,
    latency=200
)

# After
rtmp_url = f"rtmp://{self.config.mediamtx_host}:{self.config.mediamtx_rtmp_port}/live/{self.stream_id}/in"
self.input_pipeline = InputPipeline(
    rtmp_url,
    self._on_video_buffer,
    self._on_audio_buffer,
    max_buffers=10
)
```

**Change 2: Update configuration model**

Edit `apps/media-service/src/media_service/models/config.py`:

```python
# Before
class WorkerConfig(BaseModel):
    mediamtx_rtsp_port: int = 8554

# After
class WorkerConfig(BaseModel):
    mediamtx_rtmp_port: int = 1935
```

**Run tests** (should PASS):
```bash
pytest tests/unit/test_worker_runner.py -v
```

---

### Phase 3: Update Integration Tests (TDD)

**Time**: 5 minutes

#### Step 3.1: Update Test Fixtures

Edit `apps/media-service/tests/integration/conftest.py`:

```python
# Before
@pytest.fixture
def publish_test_stream():
    """Publish test stream via RTSP."""
    process = subprocess.Popen([
        "ffmpeg", "-re", "-i", "tests/fixtures/test-30s.mp4",
        "-c:v", "copy", "-c:a", "copy",
        "-f", "rtsp", "rtsp://mediamtx:8554/live/integration-test/in"
    ])
    time.sleep(2)  # Wait for stream ready
    yield
    process.terminate()

# After
@pytest.fixture
def publish_test_stream():
    """Publish test stream via RTMP."""
    process = subprocess.Popen([
        "ffmpeg", "-re", "-i", "tests/fixtures/test-30s.mp4",
        "-c:v", "copy", "-c:a", "copy",
        "-f", "flv", "rtmp://mediamtx:1935/live/integration-test/in"
    ])
    time.sleep(2)  # Wait for stream ready
    yield
    process.terminate()
```

#### Step 3.2: Update Integration Test Assertions

Edit `apps/media-service/tests/integration/test_segment_pipeline.py`:

```python
# Before
def test_input_pipeline_integration(mediamtx_running, publish_test_stream):
    pipeline = InputPipeline(
        "rtsp://mediamtx:8554/live/integration-test/in",
        on_video,
        on_audio
    )

# After
def test_input_pipeline_integration(mediamtx_running, publish_test_stream):
    pipeline = InputPipeline(
        "rtmp://mediamtx:1935/live/integration-test/in",
        on_video,
        on_audio
    )
```

**Run tests**:
```bash
make media-test-integration
```

Expected: All integration tests pass with RTMP streams.

---

### Phase 4: Update E2E Tests

**Time**: 5 minutes

#### Step 4.1: Update Docker Compose Configuration

Edit `apps/media-service/docker-compose.e2e.yml`:

```yaml
# Before
services:
  mediamtx:
    ports:
      - "8554:8554"  # RTSP

# After
services:
  mediamtx:
    ports:
      - "1935:1935"  # RTMP
```

#### Step 4.2: Update E2E Test

Edit `tests/e2e/test_dual_compose_full_pipeline.py`:

```python
# Before
publish_cmd = [
    "ffmpeg", "-re", "-i", "tests/fixtures/test-30s.mp4",
    "-c:v", "copy", "-c:a", "copy",
    "-f", "rtsp", "rtsp://localhost:8554/live/e2e-test/in"
]

# After
publish_cmd = [
    "ffmpeg", "-re", "-i", "tests/fixtures/test-30s.mp4",
    "-c:v", "copy", "-c:a", "copy",
    "-f", "flv", "rtmp://localhost:1935/live/e2e-test/in"
]
```

**Run tests**:
```bash
make e2e-test
```

Expected: All E2E tests pass with RTMP publishing.

---

## Verification Checklist

After implementation, verify:

- [ ] All unit tests pass (`make media-test-unit`)
- [ ] All integration tests pass (`make media-test-integration`)
- [ ] All E2E tests pass (`make e2e-test`)
- [ ] Code coverage >= 80% (`make media-test-coverage`)
- [ ] No RTSP references in logs during test runs
- [ ] MediaMTX logs show RTMP connections (not RTSP)
- [ ] Both video and audio segments written to disk
- [ ] STS service receives audio fragments

---

## Common Issues & Solutions

### Issue 1: "rtmpsrc element not found"

**Symptom**: RuntimeError during pipeline build: "Failed to create rtmpsrc element"

**Solution**: Install GStreamer bad plugins
```bash
# Ubuntu/Debian
sudo apt-get install gstreamer1.0-plugins-bad

# macOS
brew install gst-plugins-bad
```

---

### Issue 2: "Audio track validation fails"

**Symptom**: RuntimeError: "Audio track required for dubbing pipeline"

**Solution**: Verify test stream has audio track
```bash
# Check stream with ffprobe
ffprobe tests/fixtures/test-30s.mp4

# Ensure both video and audio streams present
# If audio missing, use different fixture or add audio track
```

---

### Issue 3: "Connection refused to port 1935"

**Symptom**: MediaMTX not accepting RTMP connections

**Solution**: Verify MediaMTX RTMP configuration
```yaml
# deploy/mediamtx/mediamtx.yml
rtmpAddress: :1935
rtmpEncryption: "no"

paths:
  live:
    source: publisher
```

Restart MediaMTX:
```bash
docker-compose restart mediamtx
```

---

### Issue 4: "Tests pass but no buffers received"

**Symptom**: Integration tests timeout waiting for buffers

**Solution**: Check GStreamer pipeline state transitions
```python
# Add debug logging in InputPipeline
logger.info(f"Pipeline state: {self.get_state()}")
logger.info(f"Video pad linked: {self._has_video_pad}")
logger.info(f"Audio pad linked: {self._has_audio_pad}")
```

Verify pads are linked during caps negotiation.

---

## Performance Validation

After implementation, measure latency:

```python
# Add PTS tracking in InputPipeline
def _on_video_sample(self, appsink):
    start_time = time.time()
    # ... existing code
    latency_ms = (time.time() - start_time) * 1000
    logger.debug(f"Video buffer latency: {latency_ms:.2f}ms")
```

**Target**: < 300ms total latency from rtmpsrc to segment write

If latency exceeds budget:
1. Profile each pipeline stage (rtmpsrc, flvdemux, parsers, queues)
2. Adjust `max_buffers` property on flvdemux
3. Tune queue `max-size-time` properties

---

## Next Steps

After completing quickstart:

1. **Run full test suite**: `make media-test` (unit + integration)
2. **Check coverage**: `make media-test-coverage` (verify >= 80%)
3. **Review logs**: Ensure no RTSP references remain
4. **Update documentation**: Remove RTSP references from READMEs
5. **Create PR**: Link to spec.md, include test evidence

---

## Documentation Updates Required

After implementation, update:

- [ ] `apps/media-service/README.md` - Change RTSP to RTMP in examples
- [ ] `tests/e2e/README.md` - Update E2E setup instructions
- [ ] `CLAUDE.md` - Update MediaMTX configuration examples
- [ ] `.env.e2e.example` - Change RTSP_PORT to RTMP_PORT

---

## TDD Workflow Summary

This quickstart follows strict TDD:

1. **Write failing test** (define expected behavior)
2. **Run test** (verify it fails for the right reason)
3. **Implement code** (make test pass)
4. **Run test** (verify it passes)
5. **Refactor** (clean up while keeping tests green)
6. **Repeat** for next requirement

**Time breakdown**:
- Phase 1 (InputPipeline): 15 min (60% of work)
- Phase 2 (WorkerRunner): 5 min (20% of work)
- Phase 3 (Integration): 5 min (10% of work)
- Phase 4 (E2E): 5 min (10% of work)

**Total**: ~30 minutes for experienced developer following this guide.
