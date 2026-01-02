# Test Expectations Contract - RTMP Migration

**Feature**: 020-rtmp-stream-pull
**Purpose**: Define expected test behaviors and assertions for RTMP migration validation

## Unit Test Expectations

### test_input_pipeline_rtmp_url_validation()

**Location**: `apps/media-service/tests/unit/test_input_pipeline.py`

**Purpose**: Validate RTMP URL format checking in InputPipeline initialization

**Assertions**:
```python
# Valid RTMP URLs (should NOT raise)
InputPipeline("rtmp://mediamtx:1935/live/stream/in", video_cb, audio_cb)
InputPipeline("rtmp://localhost:1935/app/test/in", video_cb, audio_cb)

# Invalid URLs (should raise ValueError)
with pytest.raises(ValueError, match="must start with 'rtmp://'"):
    InputPipeline("rtsp://mediamtx:8554/live/stream/in", video_cb, audio_cb)

with pytest.raises(ValueError, match="must start with 'rtmp://'"):
    InputPipeline("http://mediamtx:1935/live/stream/in", video_cb, audio_cb)

with pytest.raises(ValueError, match="cannot be empty"):
    InputPipeline("", video_cb, audio_cb)

with pytest.raises(ValueError, match="cannot be empty"):
    InputPipeline(None, video_cb, audio_cb)
```

**Contract**:
- MUST reject empty or None URLs
- MUST reject URLs not starting with "rtmp://"
- MUST accept any URL starting with "rtmp://"
- Error messages MUST be descriptive

---

### test_input_pipeline_build_rtmp_elements()

**Location**: `apps/media-service/tests/unit/test_input_pipeline.py`

**Purpose**: Verify correct GStreamer elements are created for RTMP pipeline

**Mocking Strategy**:
```python
# Mock GStreamer element factory
with patch("media_service.pipeline.input.Gst.ElementFactory.make") as mock_make:
    mock_make.side_effect = [
        MagicMock(name="rtmpsrc"),
        MagicMock(name="flvdemux"),
        MagicMock(name="h264parse"),
        MagicMock(name="video_queue"),
        MagicMock(name="video_appsink"),
        MagicMock(name="aacparse"),
        MagicMock(name="audio_queue"),
        MagicMock(name="audio_appsink"),
    ]

    pipeline = InputPipeline("rtmp://mediamtx:1935/live/test/in", video_cb, audio_cb)
    pipeline.build()

    # Assert element creation calls
    assert mock_make.call_count == 8
    mock_make.assert_any_call("rtmpsrc", "rtmpsrc")
    mock_make.assert_any_call("flvdemux", "flvdemux")

    # Assert NO calls to RTSP-specific elements
    assert not any(call[0][0] == "rtspsrc" for call in mock_make.call_args_list)
    assert not any(call[0][0] == "rtph264depay" for call in mock_make.call_args_list)
    assert not any(call[0][0] == "rtpmp4gdepay" for call in mock_make.call_args_list)
```

**Contract**:
- MUST create rtmpsrc element (NOT rtspsrc)
- MUST create flvdemux element (NOT rtph264depay or rtpmp4gdepay)
- MUST create exactly 8 elements total
- MUST NOT create any RTP-specific elements

---

### test_input_pipeline_rtmp_element_configuration()

**Location**: `apps/media-service/tests/unit/test_input_pipeline.py`

**Purpose**: Verify RTMP elements are configured with correct properties

**Assertions**:
```python
with patch("media_service.pipeline.input.Gst") as mock_gst:
    rtmpsrc_mock = MagicMock()
    flvdemux_mock = MagicMock()

    pipeline = InputPipeline(
        "rtmp://mediamtx:1935/live/test/in",
        video_cb,
        audio_cb,
        max_buffers=15
    )
    pipeline.build()

    # Assert rtmpsrc configuration
    rtmpsrc_mock.set_property.assert_any_call("location", "rtmp://mediamtx:1935/live/test/in")

    # Assert flvdemux configuration
    flvdemux_mock.set_property.assert_any_call("max-buffers", 15)

    # Assert NO RTSP-specific properties
    rtmpsrc_mock.set_property.assert_not_called_with("protocols", "tcp")
    rtmpsrc_mock.set_property.assert_not_called_with("latency", ANY)
```

**Contract**:
- MUST set rtmpsrc.location to provided RTMP URL
- MUST set flvdemux.max-buffers to provided max_buffers parameter
- MUST NOT configure RTSP-specific properties (protocols, latency)

---

### test_worker_runner_builds_rtmp_pipeline()

**Location**: `apps/media-service/tests/unit/test_worker_runner.py`

**Purpose**: Validate WorkerRunner constructs RTMP URLs correctly

**Assertions**:
```python
with patch("media_service.worker.worker_runner.InputPipeline") as mock_pipeline:
    config = WorkerConfig(
        mediamtx_host="mediamtx",
        mediamtx_rtmp_port=1935,
        app_path="live",
        stream_id="test123",
        sts_endpoint="http://sts:8000",
    )

    runner = WorkerRunner(config)
    runner.initialize()

    # Assert InputPipeline called with RTMP URL
    mock_pipeline.assert_called_once()
    call_args = mock_pipeline.call_args
    assert call_args[0][0] == "rtmp://mediamtx:1935/live/test123/in"

    # Assert NOT called with RTSP URL
    assert not call_args[0][0].startswith("rtsp://")
```

**Contract**:
- MUST construct RTMP URL from configuration (rtmp://{host}:{port}/{app}/{stream}/in)
- MUST use port 1935 (RTMP standard port)
- MUST NOT construct RTSP URLs

---

## Integration Test Expectations

### test_input_pipeline_rtmp_integration()

**Location**: `apps/media-service/tests/integration/test_segment_pipeline.py`

**Purpose**: Validate full InputPipeline with MediaMTX RTMP source

**Setup**:
```bash
# Publish test stream via RTMP (NOT RTSP)
ffmpeg -re -i tests/fixtures/test-30s.mp4 \
    -c:v copy -c:a copy \
    -f flv rtmp://mediamtx:1935/live/integration-test/in
```

**Assertions**:
```python
def test_input_pipeline_rtmp_integration(mediamtx_running):
    """Test InputPipeline pulls RTMP stream from MediaMTX."""
    video_buffers = []
    audio_buffers = []

    def on_video(data, pts, duration):
        video_buffers.append((data, pts, duration))

    def on_audio(data, pts, duration):
        audio_buffers.append((data, pts, duration))

    pipeline = InputPipeline(
        "rtmp://mediamtx:1935/live/integration-test/in",
        on_video,
        on_audio,
        max_buffers=10
    )

    pipeline.build()
    assert pipeline.start()

    # Wait for buffers
    time.sleep(5)

    # Assert both video and audio received
    assert len(video_buffers) > 0, "No video buffers received"
    assert len(audio_buffers) > 0, "No audio buffers received"

    # Assert timestamps are valid
    assert all(pts > 0 for _, pts, _ in video_buffers)
    assert all(pts > 0 for _, pts, _ in audio_buffers)

    pipeline.stop()
```

**Contract**:
- MUST receive video buffers from RTMP stream
- MUST receive audio buffers from RTMP stream
- MUST provide valid PTS values (> 0)
- MUST connect successfully to MediaMTX RTMP endpoint

---

### test_input_pipeline_rejects_video_only_stream()

**Location**: `apps/media-service/tests/integration/test_segment_pipeline.py`

**Purpose**: Validate audio track validation rejects video-only streams

**Setup**:
```bash
# Publish video-only stream via RTMP
ffmpeg -re -i tests/fixtures/test-30s.mp4 \
    -c:v copy -an \
    -f flv rtmp://mediamtx:1935/live/video-only-test/in
```

**Assertions**:
```python
def test_input_pipeline_rejects_video_only_stream(mediamtx_running):
    """Test InputPipeline rejects streams without audio track."""
    pipeline = InputPipeline(
        "rtmp://mediamtx:1935/live/video-only-test/in",
        lambda *args: None,
        lambda *args: None
    )

    pipeline.build()

    # Assert start() raises RuntimeError with descriptive message
    with pytest.raises(RuntimeError, match="Audio track required for dubbing pipeline"):
        pipeline.start()

    # Assert pipeline state is ERROR
    assert pipeline.get_state() == "ERROR"
```

**Contract**:
- MUST detect missing audio track during startup
- MUST raise RuntimeError with descriptive message
- MUST NOT transition to PLAYING state
- MUST set pipeline state to ERROR

---

## E2E Test Expectations

### test_dual_compose_full_pipeline_rtmp()

**Location**: `tests/e2e/test_dual_compose_full_pipeline.py`

**Purpose**: Validate end-to-end RTMP flow from stream publish to STS processing

**Docker Compose Updates**:
```yaml
# docker-compose.e2e.yml
services:
  mediamtx:
    ports:
      - "1935:1935"  # RTMP (NOT 8554 for RTSP)
    environment:
      - RTMP_ENABLED=yes
```

**Test Flow**:
```python
def test_dual_compose_full_pipeline_rtmp():
    """E2E test: RTMP publish -> media-service -> STS -> output"""

    # Step 1: Start services
    subprocess.run(["docker-compose", "-f", "docker-compose.e2e.yml", "up", "-d"])

    # Step 2: Publish stream via RTMP (NOT RTSP)
    publish_process = subprocess.Popen([
        "ffmpeg", "-re", "-i", "tests/fixtures/test-30s.mp4",
        "-c:v", "copy", "-c:a", "copy",
        "-f", "flv", "rtmp://localhost:1935/live/e2e-test/in"
    ])

    # Step 3: Wait for stream ready
    time.sleep(5)

    # Step 4: Verify media-service logs show RTMP connection
    logs = subprocess.check_output([
        "docker-compose", "-f", "docker-compose.e2e.yml", "logs", "media-service"
    ]).decode()
    assert "rtmpsrc" in logs.lower()
    assert "flvdemux" in logs.lower()
    assert "rtspsrc" not in logs.lower()  # MUST NOT use RTSP

    # Step 5: Verify segments written
    assert_segments_written(stream_id="e2e-test", min_segments=3)

    # Step 6: Verify STS received audio fragments
    sts_logs = subprocess.check_output([
        "docker-compose", "-f", "docker-compose.e2e.yml", "logs", "sts-service"
    ]).decode()
    assert "fragment:data" in sts_logs

    # Cleanup
    publish_process.terminate()
    subprocess.run(["docker-compose", "-f", "docker-compose.e2e.yml", "down"])
```

**Contract**:
- MUST publish streams via RTMP (port 1935)
- MUST NOT use RTSP protocol anywhere in E2E flow
- MUST verify media-service uses rtmpsrc and flvdemux elements
- MUST verify video and audio segments reach disk
- MUST verify STS service receives audio fragments

---

## Test Fixture Updates

### ffmpeg RTMP Publish Commands

**Before (RTSP)**:
```bash
ffmpeg -re -i test.mp4 -c:v copy -c:a copy -f rtsp rtsp://mediamtx:8554/live/test/in
```

**After (RTMP)**:
```bash
ffmpeg -re -i test.mp4 -c:v copy -c:a copy -f flv rtmp://mediamtx:1935/live/test/in
```

**Contract**:
- MUST use `-f flv` (NOT `-f rtsp`)
- MUST use port 1935 (NOT 8554)
- MUST use `rtmp://` protocol (NOT `rtsp://`)

---

### MediaMTX Configuration Updates

**Before (RTSP focus)**:
```yaml
# mediamtx.yml
paths:
  live:
    source: publisher
    sourceProtocol: rtsp
```

**After (RTMP focus)**:
```yaml
# mediamtx.yml
rtmpAddress: :1935
rtmpEncryption: "no"
rtmpServerKey: ""
rtmpServerCert: ""

paths:
  live:
    source: publisher
    # No sourceProtocol constraint - accept RTMP
```

**Contract**:
- MUST enable RTMP on port 1935
- MUST accept RTMP streams on configured paths
- MAY disable RTSP if not used elsewhere (optional cleanup)

---

## Coverage Requirements

### Unit Tests
- **Target**: 80% minimum, 95% for InputPipeline (critical path)
- **Focus**: RTMP URL validation, element creation, configuration, error handling
- **Mocking**: All GStreamer elements, no real pipeline execution

### Integration Tests
- **Target**: 80% minimum
- **Focus**: Real RTMP stream consumption, audio validation, MediaMTX integration
- **Requires**: Docker Compose with MediaMTX + media-service

### E2E Tests
- **Target**: Happy path coverage only (optional for regression)
- **Focus**: Full pipeline flow from RTMP publish to STS processing
- **Requires**: Full docker-compose environment (media-service + sts-service + MediaMTX)

---

## Test Naming Conventions

Follow TDD naming from constitution:

- `test_<function>_happy_path()` - Normal RTMP operation
- `test_<function>_error_<condition>()` - Error handling (invalid URL, missing audio, etc.)
- `test_<function>_edge_<case>()` - Boundary conditions (empty URL, max_buffers=0, etc.)
- `test_<function>_integration_<workflow>()` - Integration scenarios (RTMP publish + consume)

---

## Removed Test Expectations

**RTSP-Specific Tests (DELETE)**:
- `test_input_pipeline_rtsp_url_validation()` - Replaced with RTMP equivalent
- `test_input_pipeline_dynamic_depayloader()` - RTP depayloader logic removed
- `test_rtspsrc_latency_configuration()` - RTSP latency property removed
- Any integration tests using `rtsp://` URLs - Replaced with `rtmp://` URLs

**Contract**: All RTSP references must be removed from test suite. No backward compatibility testing required.
