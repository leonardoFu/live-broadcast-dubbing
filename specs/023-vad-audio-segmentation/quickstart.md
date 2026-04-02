# Quickstart: VAD Audio Segmentation

**Feature**: 023-vad-audio-segmentation
**Date**: 2026-01-09

## Test Scenarios

### Unit Tests

All unit tests should be written BEFORE implementation per Constitution Principle VIII.

#### 1. SegmentationConfig Tests

**File**: `apps/media-service/tests/unit/config/test_segmentation_config.py`

```python
def test_segmentation_config_defaults():
    """Verify default values when no environment variables set."""
    config = SegmentationConfig()
    assert config.silence_threshold_db == -50.0
    assert config.silence_duration_s == 1.0
    assert config.min_segment_duration_s == 1.0
    assert config.max_segment_duration_s == 15.0
    assert config.level_interval_ns == 100_000_000
    assert config.memory_limit_bytes == 10_485_760

def test_segmentation_config_from_env(monkeypatch):
    """Verify parameters read from environment variables."""
    monkeypatch.setenv("VAD_SILENCE_THRESHOLD_DB", "-40")
    monkeypatch.setenv("VAD_MAX_SEGMENT_DURATION_S", "20")

    config = SegmentationConfig()
    assert config.silence_threshold_db == -40.0
    assert config.max_segment_duration_s == 20.0

def test_segmentation_config_validation_out_of_range():
    """Verify validation rejects out-of-range values."""
    with pytest.raises(ValidationError):
        SegmentationConfig(silence_threshold_db=10.0)  # Above 0

def test_segmentation_config_ns_properties():
    """Verify nanosecond conversion properties."""
    config = SegmentationConfig(
        silence_duration_s=1.5,
        min_segment_duration_s=2.0,
        max_segment_duration_s=10.0,
    )
    assert config.silence_duration_ns == 1_500_000_000
    assert config.min_segment_duration_ns == 2_000_000_000
    assert config.max_segment_duration_ns == 10_000_000_000
```

#### 2. VADAudioSegmenter Tests

**File**: `apps/media-service/tests/unit/vad/test_vad_audio_segmenter.py`

```python
def test_vad_silence_boundary_emits_segment():
    """Verify 1 second of silence triggers segment emission."""
    segments_emitted = []
    def on_segment(data, t0_ns, duration_ns):
        segments_emitted.append((data, t0_ns, duration_ns))

    config = SegmentationConfig()
    segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

    # Accumulate 2 seconds of audio
    segmenter.on_audio_buffer(b"audio1", pts_ns=0, duration_ns=1_000_000_000)
    segmenter.on_audio_buffer(b"audio2", pts_ns=1_000_000_000, duration_ns=1_000_000_000)

    # Simulate silence for 1 second (10 level messages at 100ms intervals)
    for i in range(10):
        segmenter.on_level_message(rms_db=-60.0, timestamp_ns=2_000_000_000 + i * 100_000_000)

    assert len(segments_emitted) == 1
    assert segments_emitted[0][0] == b"audio1audio2"
    assert segmenter.silence_detections == 1

def test_vad_max_duration_forces_emission():
    """Verify segment is emitted at 15 seconds regardless of silence."""
    segments_emitted = []
    def on_segment(data, t0_ns, duration_ns):
        segments_emitted.append((data, t0_ns, duration_ns))

    config = SegmentationConfig(max_segment_duration_s=15.0)
    segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

    # Accumulate exactly 15 seconds of audio (continuous speech)
    for i in range(15):
        segmenter.on_audio_buffer(
            data=b"x" * 1000,
            pts_ns=i * 1_000_000_000,
            duration_ns=1_000_000_000,
        )
        # Send speech level (above threshold)
        segmenter.on_level_message(rms_db=-30.0, timestamp_ns=i * 1_000_000_000)

    assert len(segments_emitted) == 1
    assert segmenter.forced_emissions == 1

def test_vad_min_duration_buffers_segment():
    """Verify segments under 1 second are not emitted."""
    segments_emitted = []
    def on_segment(data, t0_ns, duration_ns):
        segments_emitted.append((data, t0_ns, duration_ns))

    config = SegmentationConfig()
    segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

    # Accumulate only 0.5 seconds
    segmenter.on_audio_buffer(b"short", pts_ns=0, duration_ns=500_000_000)

    # Trigger silence
    for i in range(10):
        segmenter.on_level_message(rms_db=-60.0, timestamp_ns=500_000_000 + i * 100_000_000)

    assert len(segments_emitted) == 0  # Not emitted
    assert segmenter.min_duration_violations == 1

def test_vad_level_message_extraction():
    """Verify RMS value extraction from GStreamer level messages."""
    # Mock GStreamer structure
    mock_structure = MockGstStructure(rms=[-45.0, -42.0])  # Stereo

    extractor = LevelMessageExtractor()
    peak_rms = extractor.extract_peak_rms_db(mock_structure)

    assert peak_rms == -42.0  # Max of channels

def test_vad_invalid_rms_treated_as_speech():
    """Verify invalid RMS values are logged and treated as speech."""
    segments_emitted = []
    def on_segment(data, t0_ns, duration_ns):
        segments_emitted.append((data, t0_ns, duration_ns))

    config = SegmentationConfig()
    segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

    # Accumulate audio
    segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=2_000_000_000)

    # Send invalid RMS (out of range)
    segmenter.on_level_message(rms_db=10.0, timestamp_ns=0)  # Invalid: > 0

    # Should NOT emit (invalid treated as speech)
    assert len(segments_emitted) == 0

def test_vad_consecutive_invalid_rms_raises_error():
    """Verify 10+ consecutive invalid RMS values raises RuntimeError."""
    config = SegmentationConfig()
    segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

    # Send 10 invalid RMS values
    with pytest.raises(RuntimeError, match="Pipeline malfunction"):
        for i in range(10):
            segmenter.on_level_message(rms_db=10.0, timestamp_ns=i * 100_000_000)

def test_vad_eos_flush_emits_valid_segment():
    """Verify EOS flushes segment if duration >= minimum."""
    segments_emitted = []
    def on_segment(data, t0_ns, duration_ns):
        segments_emitted.append((data, t0_ns, duration_ns))

    config = SegmentationConfig()
    segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

    # Accumulate 3 seconds (above minimum)
    segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=3_000_000_000)

    segmenter.flush()

    assert len(segments_emitted) == 1

def test_vad_eos_discards_short_segment():
    """Verify EOS discards segment if duration < minimum."""
    segments_emitted = []
    def on_segment(data, t0_ns, duration_ns):
        segments_emitted.append((data, t0_ns, duration_ns))

    config = SegmentationConfig()
    segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

    # Accumulate only 0.5 seconds
    segmenter.on_audio_buffer(b"short", pts_ns=0, duration_ns=500_000_000)

    segmenter.flush()

    assert len(segments_emitted) == 0  # Discarded
```

#### 3. InputPipeline Level Element Tests

**File**: `apps/media-service/tests/unit/pipeline/test_input_level_element.py`

```python
def test_level_element_creation_success(mock_gst):
    """Verify level element is created when gst-plugins-good available."""
    pipeline = InputPipeline(
        rtmp_url="rtmp://localhost/live/test",
        on_video_buffer=lambda *args: None,
        on_audio_buffer=lambda *args: None,
    )
    pipeline.build()

    assert pipeline._level is not None
    assert pipeline._level.get_property("post-messages") == True
    assert pipeline._level.get_property("interval") == 100_000_000

def test_level_element_raises_on_failure(mock_gst_no_level):
    """Verify RuntimeError when level element unavailable."""
    pipeline = InputPipeline(
        rtmp_url="rtmp://localhost/live/test",
        on_video_buffer=lambda *args: None,
        on_audio_buffer=lambda *args: None,
    )

    with pytest.raises(RuntimeError, match="gst-plugins-good"):
        pipeline.build()

def test_level_message_callback_wired():
    """Verify bus message handler connected for level messages."""
    level_messages = []

    def on_level(rms_db, timestamp_ns):
        level_messages.append((rms_db, timestamp_ns))

    pipeline = InputPipeline(
        rtmp_url="rtmp://localhost/live/test",
        on_video_buffer=lambda *args: None,
        on_audio_buffer=lambda *args: None,
        on_level_message=on_level,
    )
    pipeline.build()

    # Simulate level message
    mock_message = create_mock_level_message(rms=[-45.0])
    pipeline._on_bus_message(None, mock_message)

    assert len(level_messages) == 1
    assert level_messages[0][0] == -45.0
```

#### 4. SegmentBuffer VAD Integration Tests

**File**: `apps/media-service/tests/unit/buffer/test_segment_buffer_vad.py`

```python
def test_segment_buffer_vad_mode_disabled_by_default():
    """Verify SegmentBuffer uses fixed duration by default."""
    buffer = SegmentBuffer(
        stream_id="test",
        segment_dir=Path("/tmp/test"),
    )

    # Accumulate exactly 6 seconds
    for i in range(6):
        segment, data = buffer.push_audio(b"x" * 1000, i * 1_000_000_000, 1_000_000_000)
        if i < 5:
            assert segment is None

    assert segment is not None  # Emitted at 6s

def test_segment_buffer_vad_mode_enabled():
    """Verify SegmentBuffer with VAD segmenter uses silence boundaries."""
    vad_config = SegmentationConfig()
    buffer = SegmentBuffer(
        stream_id="test",
        segment_dir=Path("/tmp/test"),
        vad_segmenter=VADAudioSegmenter(config=vad_config, on_segment_ready=buffer._on_vad_segment),
    )

    # VAD segmenter controls emission, not fixed duration
    # This test validates the integration
    assert buffer._vad_segmenter is not None
```

### Integration Tests

**File**: `apps/media-service/tests/integration/test_vad_integration.py`

```python
@pytest.mark.integration
def test_vad_integration_with_real_audio():
    """Verify VAD detection with actual audio containing speech and silence."""
    # Use audiotestsrc with gaps
    # Requires GStreamer and gst-plugins-good installed
    pass  # Detailed implementation in tasks

@pytest.mark.integration
def test_vad_integration_level_element_failure_fatal():
    """Verify service fails to start without level element."""
    # Mock Gst.ElementFactory.make to return None for "level"
    pass  # Detailed implementation in tasks
```

### Contract Tests

**File**: `apps/media-service/tests/contract/test_vad_contracts.py`

```python
def test_segmentation_config_schema_valid():
    """Verify SegmentationConfig matches JSON schema."""
    from jsonschema import validate
    import json

    with open("specs/023-vad-audio-segmentation/contracts/segmentation-config-schema.json") as f:
        schema = json.load(f)

    config = SegmentationConfig()
    config_dict = config.model_dump()

    validate(instance=config_dict, schema=schema)

def test_vad_metrics_schema_valid():
    """Verify VAD metrics match schema definition."""
    # Validate Prometheus metric names and labels match schema
    pass
```

---

## Manual Testing Checklist

### Prerequisites

1. Docker and Docker Compose installed
2. gst-plugins-good installed (provides level element)
3. Test stream with speech and silence patterns

### Test Cases

#### TC1: Basic VAD Segmentation

```bash
# 1. Set VAD environment variables (optional, use defaults)
export VAD_SILENCE_THRESHOLD_DB=-50
export VAD_SILENCE_DURATION_S=1.0

# 2. Start services
make e2e-up

# 3. Publish test stream with speech/silence
ffmpeg -re -i tests/e2e/fixtures/test_streams/speech_with_pauses.mp4 \
  -c copy -f flv rtmp://localhost:1935/live/test/in

# 4. Check logs for VAD segment emissions
make e2e-logs | grep "Audio segment emitted"
# Expected: Segments at natural speech boundaries (variable duration 1-15s)

# 5. Verify metrics
curl http://localhost:9090/metrics | grep vad_
# Expected: vad_segments_total, vad_segment_duration_seconds, etc.
```

#### TC2: Max Duration Enforcement

```bash
# 1. Use test stream with continuous speech (no pauses)
ffmpeg -re -i tests/e2e/fixtures/test_streams/continuous_speech.mp4 \
  -c copy -f flv rtmp://localhost:1935/live/test/in

# 2. Verify forced emissions
make e2e-logs | grep "forced emission"
# Expected: Segments emitted every 15 seconds

# 3. Check metrics
curl http://localhost:9090/metrics | grep vad_forced_emissions_total
# Expected: Counter incrementing every ~15s
```

#### TC3: Min Duration Buffering

```bash
# 1. Use test stream with rapid speech/silence alternation
# (words separated by 0.5s pauses)

# 2. Verify short segments are buffered
make e2e-logs | grep "min duration violation"
# Expected: Violations logged, segments combined

# 3. Check metrics
curl http://localhost:9090/metrics | grep vad_min_duration_violations_total
```

#### TC4: Fail-Fast Verification

```bash
# 1. Remove gst-plugins-good (simulate missing dependency)
docker exec e2e-media-service apt-get remove gstreamer1.0-plugins-good

# 2. Restart service
docker-compose restart media-service

# 3. Check logs for fatal error
make e2e-logs | grep "level element not available"
# Expected: RuntimeError with clear message about gst-plugins-good

# 4. Reinstall for other tests
docker exec e2e-media-service apt-get install gstreamer1.0-plugins-good
```

---

## Success Criteria Verification

| SC | Test | Command | Expected |
|----|------|---------|----------|
| SC-001 | Segment duration histogram | `curl localhost:9090/metrics \| grep vad_segment_duration` | Non-uniform distribution (1-15s) |
| SC-002 | Silence trigger rate | `curl localhost:9090/metrics \| grep trigger="silence"` | >80% of total segments |
| SC-003 | A/V sync | `ffprobe output.flv` | Delta < 120ms |
| SC-004 | Fail-fast timing | `time docker-compose up media-service` | Fails within 5 seconds |
| SC-005 | Env var config | Set VAD_* vars, check logs | Values applied |
| SC-006 | Metrics count | `curl localhost:9090/metrics \| grep vad_ \| wc -l` | 6+ metrics |
| SC-008 | Unit test coverage | `make media-test-coverage` | >= 80% |
| SC-009 | No short segments | Check all emitted segments | All >= 1.0s |
| SC-010 | No long segments | Check all emitted segments | All <= 15.0s |
