# Task List: VAD-Based Audio Segmentation

**Feature**: Dynamic VAD-Based Audio Segmentation
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Created**: 2026-01-06
**Status**: Ready for Implementation

## Task Dependency Graph

```
T001 (SegmentationConfig)
  │
  ├─→ T002 (VADConfig dataclass)
  │     │
  │     └─→ T003 (VADAudioSegmenter class)
  │           │
  │           └─→ T004 (Silence detection logic)
  │                 │
  │                 └─→ T005 (Buffer accumulation)
  │                       │
  │                       ├─→ T006 (Min duration guard)
  │                       │     │
  │                       │     └─→ T007 (Max duration guard)
  │                       │           │
  │                       │           └─→ T008 (EOS flush logic)
  │
  └─→ T010 (VAD metrics)
        │
        └─→ T011 (GStreamer level element - FATAL on failure)
              │
              ├─→ T012 (WorkerRunner integration)
              │     │
              │     └─→ T013 (Bus message handler)
              │           │
              │           └─→ T014 (Unit tests - VADAudioSegmenter)
              │                 │
              │                 ├─→ T015 (Unit tests - SegmentationConfig)
              │                 │     │
              │                 │     └─→ T016 (Integration tests - level element)
              │                 │           │
              │                 │           └─→ T017 (Integration tests - MediaMTX)
              │                 │                 │
              │                 │                 └─→ T018 (E2E tests - full pipeline)
              │                 │                       │
              │                 │                       ├─→ T020 (VAD tuning guide)
              │                 │                       └─→ T021 (Manual QA process)
              │                 │
              │                 └─→ T019 (Test fixtures - synthetic audio)

Note: T009 removed (no fallback logic - fatal error if level element fails)
```

---

## Phase 1: Foundation (Data Models & Configuration)

### Task T001: Create SegmentationConfig module
**Priority**: P1
**Depends on**: None
**Estimated effort**: S
**Files to modify/create**:
- `apps/media-service/src/media_service/config/segmentation.py` (new)

**Description**:
Create the SegmentationConfig data model to centralize VAD configuration management. This module loads VAD parameters from environment variables with sensible defaults and provides validation to ensure sane parameter ranges.

**Acceptance Criteria**:
- [ ] SegmentationConfig dataclass created with fields: vad_enabled, silence_threshold_db, silence_duration_ms, min_segment_duration_ns, max_segment_duration_ns
- [ ] from_env() class method loads configuration from environment variables (VAD_ENABLED, VAD_SILENCE_THRESHOLD_DB, VAD_SILENCE_DURATION_MS, VAD_MIN_SEGMENT_DURATION_MS, VAD_MAX_SEGMENT_DURATION_MS)
- [ ] Default values set: enabled=true, threshold=-40.0dB, silence_duration=1000ms, min=1000ms, max=15000ms
- [ ] Millisecond to nanosecond conversion handled internally
- [ ] validate() method rejects invalid configurations (threshold > 0, min > max, silence_duration < 100ms, min_segment < 500ms)
- [ ] ValueError raised with clear error messages for invalid configurations

**Tests Required**:
- `test_config_from_env_defaults()` - Verify default values when env vars not set
- `test_config_from_env_custom()` - Verify custom values loaded from environment
- `test_config_validation_rejects_positive_threshold()` - Reject threshold > 0dB
- `test_config_validation_rejects_min_greater_than_max()` - Reject min > max duration
- `test_config_validation_rejects_short_silence_duration()` - Reject silence_duration < 100ms
- `test_config_validation_rejects_short_min_segment()` - Reject min_segment < 500ms
- `test_config_ms_to_ns_conversion()` - Verify millisecond to nanosecond conversion

---

### Task T002: Create VADConfig dataclass
**Priority**: P1
**Depends on**: T001
**Estimated effort**: S
**Files to modify/create**:
- `apps/media-service/src/media_service/buffer/vad_audio_segmenter.py` (new, partial)

**Description**:
Create the VADConfig dataclass and SegmentTrigger enum as internal data models for VADAudioSegmenter. VADConfig contains runtime configuration parameters, while SegmentTrigger tracks the reason for segment emission.

**Acceptance Criteria**:
- [ ] VADConfig dataclass created with fields: enabled, silence_threshold_db, silence_duration_ms, min_segment_duration_ns, max_segment_duration_ns
- [ ] SegmentTrigger enum created with values: SILENCE_DETECTED, MAX_DURATION_REACHED, EOS_FLUSH
- [ ] All fields have type annotations and docstrings
- [ ] Default values set matching SegmentationConfig defaults

**Tests Required**:
- `test_vad_config_dataclass_creation()` - Verify VADConfig can be instantiated with all fields
- `test_segment_trigger_enum_values()` - Verify all enum values exist

---

## Phase 2: Core VAD Implementation

### Task T003: Implement VADAudioSegmenter class skeleton
**Priority**: P1
**Depends on**: T002
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/src/media_service/buffer/vad_audio_segmenter.py` (extend)

**Description**:
Create the VADAudioSegmenter class skeleton with __init__, push_audio, handle_level_message, and flush_audio methods. Initialize internal state tracking (buffer accumulator, silence tracking).

**Acceptance Criteria**:
- [ ] VADAudioSegmenter class created with __init__ method accepting stream_id, segment_dir, config
- [ ] Internal state variables initialized: _accumulator (BufferAccumulator), _audio_batch_number, _silence_start_ns, _is_in_silence
- [ ] push_audio() method signature matches SegmentBuffer API: (buffer_data, pts_ns, duration_ns) -> (AudioSegment | None, bytes)
- [ ] handle_level_message() method signature: (rms_db, timestamp_ns) -> (AudioSegment | None, bytes)
- [ ] flush_audio() method signature: () -> (AudioSegment | None, bytes)
- [ ] Logger initialized for structured logging

**Tests Required**:
- `test_vad_segmenter_initialization()` - Verify segmenter initializes with config
- `test_vad_segmenter_initial_state()` - Verify initial state variables are correct

---

### Task T004: Implement silence detection logic
**Priority**: P1
**Depends on**: T003
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/src/media_service/buffer/vad_audio_segmenter.py` (extend)

**Description**:
Implement the handle_level_message() method to detect silence boundaries. Track when RMS level drops below threshold and emit silence boundary event after continuous silence duration (default 1s).

**Acceptance Criteria**:
- [ ] handle_level_message() compares rms_db against config.silence_threshold_db
- [ ] When RMS < threshold and not currently in silence, set _is_in_silence=True and _silence_start_ns=timestamp_ns
- [ ] When RMS < threshold and in silence, check duration: if (timestamp_ns - _silence_start_ns) >= silence_duration_ms * 1_000_000, trigger silence boundary
- [ ] When RMS >= threshold and in silence, reset silence tracking (_is_in_silence=False, _silence_start_ns=None)
- [ ] Silence boundary detection triggers segment emission (calls internal _emit_segment() method)
- [ ] Log silence detection events with RMS level and duration

**Tests Required**:
- `test_vad_silence_detection_starts_tracking()` - RMS below threshold starts silence tracking
- `test_vad_silence_detection_triggers_boundary()` - 1s continuous silence triggers boundary
- `test_vad_silence_detection_resets_on_speech()` - RMS above threshold resets silence tracking
- `test_vad_silence_detection_ignores_short_pauses()` - <1s silence does not trigger boundary
- `test_vad_silence_detection_accuracy()` - Boundary detected within 100ms of actual 1s threshold

---

### Task T005: Implement buffer accumulation logic
**Priority**: P1
**Depends on**: T004
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/src/media_service/buffer/vad_audio_segmenter.py` (extend)

**Description**:
Implement the push_audio() method to accumulate audio buffers with PTS tracking. Use BufferAccumulator from existing SegmentBuffer to maintain compatibility with existing buffer management logic.

**Acceptance Criteria**:
- [ ] push_audio() creates BufferAccumulator on first call if not exists
- [ ] Audio buffers accumulated with _accumulator.push(buffer_data, pts_ns, duration_ns)
- [ ] First buffer PTS stored as segment t0_ns
- [ ] Accumulated duration tracked in nanoseconds
- [ ] push_audio() returns (None, empty bytes) when no segment ready
- [ ] Preserves existing BufferAccumulator API and PTS tracking logic

**Tests Required**:
- `test_vad_buffer_accumulation_single_buffer()` - Single buffer accumulated correctly
- `test_vad_buffer_accumulation_multiple_buffers()` - Multiple buffers accumulated with correct total duration
- `test_vad_buffer_accumulation_tracks_pts()` - First buffer PTS stored as t0_ns
- `test_vad_buffer_accumulation_no_emission_until_trigger()` - No segment emitted without trigger

---

### Task T006: Implement minimum duration guard
**Priority**: P1
**Depends on**: T005
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/src/media_service/buffer/vad_audio_segmenter.py` (extend)

**Description**:
Implement minimum duration guard to prevent emitting segments shorter than 1 second. When silence boundary detected, check accumulated duration; if < min_segment_duration_ns, continue buffering until minimum reached.

**Acceptance Criteria**:
- [ ] _should_emit_segment() internal method checks accumulated_duration >= config.min_segment_duration_ns
- [ ] On silence boundary with duration < 1s, segment NOT emitted, buffers continue accumulating
- [ ] On silence boundary with duration >= 1s, segment emitted normally
- [ ] Subsequent speech appended to buffered sub-minimum audio until total >= 1s
- [ ] Metrics counter vad_min_duration_violations_total incremented when buffering due to min duration
- [ ] Log min duration violations with buffered duration

**Tests Required**:
- `test_vad_min_duration_prevents_short_emission()` - Segment < 1s not emitted on silence boundary
- `test_vad_min_duration_accumulates_across_boundaries()` - Sub-1s segments accumulated until >= 1s
- `test_vad_min_duration_emits_when_threshold_reached()` - Accumulated 1.3s segment emitted after buffering 0.5s + 0.8s
- `test_vad_min_duration_violation_metric()` - Metric incremented on buffering

---

### Task T007: Implement maximum duration guard
**Priority**: P1
**Depends on**: T006
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/src/media_service/buffer/vad_audio_segmenter.py` (extend)

**Description**:
Implement maximum duration guard to forcibly emit segments at 15 seconds regardless of silence detection. This prevents unbounded accumulation during continuous speech or noisy audio.

**Acceptance Criteria**:
- [ ] push_audio() checks if accumulated_duration >= config.max_segment_duration_ns
- [ ] When max duration reached, segment forcibly emitted with trigger=MAX_DURATION_REACHED
- [ ] After forced emission, new segment starts accumulating from continuation point
- [ ] Silence tracking reset after forced emission
- [ ] Metrics counter vad_forced_emissions_total incremented
- [ ] Log forced emissions with duration and reason

**Tests Required**:
- `test_vad_max_duration_forces_emission()` - Segment forcibly emitted at 15s without silence
- `test_vad_max_duration_resets_accumulator()` - New segment starts after forced emission
- `test_vad_max_duration_continues_buffering()` - Audio continues accumulating after forced emission
- `test_vad_max_duration_forced_emission_metric()` - Metric incremented on forced emission
- `test_vad_max_duration_no_segment_exceeds_max()` - No segment exceeds 15s duration

---

### Task T008: Implement EOS flush logic
**Priority**: P1
**Depends on**: T007
**Estimated effort**: S
**Files to modify/create**:
- `apps/media-service/src/media_service/buffer/vad_audio_segmenter.py` (extend)

**Description**:
Implement flush_audio() method for end-of-stream handling. Emit remaining buffered audio as partial segment if >= 1s, discard if < 1s. Maintains compatibility with existing MIN_PARTIAL_DURATION_NS logic.

**Acceptance Criteria**:
- [ ] flush_audio() checks accumulated duration
- [ ] If duration >= min_segment_duration_ns (1s), emit as partial segment with trigger=EOS_FLUSH
- [ ] If duration < 1s, return (None, empty bytes) - partial discarded
- [ ] After flush, accumulator reset and state cleared
- [ ] Log flush events with partial duration and decision (emitted/discarded)

**Tests Required**:
- `test_vad_eos_flush_emits_valid_partial()` - 1.5s partial emitted on flush
- `test_vad_eos_flush_discards_short_partial()` - 0.8s partial discarded on flush
- `test_vad_eos_flush_at_min_boundary()` - Exactly 1.0s partial emitted
- `test_vad_eos_flush_resets_state()` - State cleared after flush

---

## Phase 3: Metrics and Observability

### Task T010: Add VAD metrics to WorkerMetrics
**Priority**: P1
**Depends on**: T001
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/src/media_service/metrics/prometheus.py`

**Description**:
Extend WorkerMetrics class with VAD-specific Prometheus metrics: gauges for status, counters for events, and histogram for duration distribution. Add accessor methods for recording VAD events.

**Acceptance Criteria**:
- [ ] Counter vad_segments_total added, labeled by stream_id and trigger (silence_detected | max_duration_reached | eos_flush)
- [ ] Counter vad_silence_detections_total added, labeled by stream_id
- [ ] Counter vad_forced_emissions_total added, labeled by stream_id
- [ ] Histogram vad_segment_duration_seconds added with buckets [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0], labeled by stream_id
- [ ] Counter vad_min_duration_violations_total added, labeled by stream_id
- [ ] Accessor methods: record_vad_segment(), record_vad_silence_detection(), record_vad_forced_emission(), record_vad_min_duration_violation()
- [ ] Metrics initialized in _ensure_metrics_initialized() class method
- [ ] All metrics follow naming convention: media_service_worker_vad_*

**Tests Required**:
- `test_vad_metrics_initialization()` - Verify all VAD metrics initialized
- `test_vad_segment_metric_recorded()` - record_vad_segment() increments counter with correct labels
- `test_vad_segment_duration_histogram()` - Duration histogram records values in correct buckets
- `test_vad_metrics_exposed()` - Metrics exposed on /metrics endpoint

---

## Phase 4: GStreamer Pipeline Integration

### Task T011: Add level element to InputPipeline
**Priority**: P1
**Depends on**: T010
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/src/media_service/pipeline/input.py`

**Description**:
Modify InputPipeline to add GStreamer level element to audio branch. Insert level between aacparse and appsink, configure level properties (interval=100ms, message=True), and set up bus watch for level messages. **FATAL ERROR if level element unavailable** - VAD is required, no fallback.

**Acceptance Criteria**:
- [ ] level element created with Gst.ElementFactory.make("level", "audio_level")
- [ ] level.set_property("interval", 100000000) - 100ms interval in nanoseconds
- [ ] level.set_property("message", True) - enable bus messages
- [ ] Audio branch pipeline: aacparse → level → appsink (linked correctly)
- [ ] If level element creation fails, raise RuntimeError("VAD requires gst-plugins-good level element")
- [ ] Bus watch added with bus.add_signal_watch() and bus.connect("message::element", _on_level_message)
- [ ] _on_level_message() callback extracts RMS from message structure
- [ ] RMS value extracted from message.get_structure().get_value("rms")[0] (first channel)
- [ ] Timestamp extracted from message.timestamp
- [ ] Callback wiring: on_level_callback parameter added to InputPipeline.__init__()

**Tests Required**:
- `test_level_element_added_to_pipeline()` - Verify level element exists in pipeline
- `test_level_element_configured_correctly()` - Verify interval and message properties set
- `test_level_element_linked_correctly()` - Verify pipeline topology: aacparse → level → appsink
- `test_level_element_raises_on_failure()` - RuntimeError raised if level element unavailable
- `test_level_message_parsing()` - RMS and timestamp extracted correctly from message

---

### Task T012: Integrate VADAudioSegmenter into WorkerRunner
**Priority**: P1
**Depends on**: T011
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/src/media_service/worker/worker_runner.py`
- `apps/media-service/src/media_service/config/segmentation.py` (import)

**Description**:
Update WorkerRunner to use VADAudioSegmenter for audio path instead of SegmentBuffer. Load SegmentationConfig from environment, instantiate VADAudioSegmenter with configuration, and wire up to InputPipeline.

**Acceptance Criteria**:
- [ ] SegmentationConfig loaded in __init__() via SegmentationConfig.from_env()
- [ ] SegmentationConfig.validate() called at initialization
- [ ] VADAudioSegmenter instantiated for audio path with stream_id, segment_dir, and VADConfig from SegmentationConfig
- [ ] SegmentBuffer still used for video path (unchanged)
- [ ] _on_audio_buffer() calls vad_segmenter.push_audio() instead of SegmentBuffer.push_audio()
- [ ] Level element initialization failure propagates as fatal error (no fallback)

**Tests Required**:
- `test_worker_runner_loads_segmentation_config()` - Config loaded from environment
- `test_worker_runner_initializes_vad_segmenter()` - VADAudioSegmenter created with correct config
- `test_worker_runner_uses_segment_buffer_for_video()` - Video path unchanged
- `test_worker_runner_raises_on_level_failure()` - RuntimeError propagated if level element fails

---

### Task T013: Implement bus message handler in WorkerRunner
**Priority**: P1
**Depends on**: T012
**Estimated effort**: S
**Files to modify/create**:
- `apps/media-service/src/media_service/worker/worker_runner.py`

**Description**:
Add _on_level_message() handler to WorkerRunner to process RMS level messages from GStreamer bus. Call vad_segmenter.handle_level_message() and process returned segments.

**Acceptance Criteria**:
- [ ] _on_level_message(rms_db, timestamp_ns) method added to WorkerRunner
- [ ] Method calls vad_segmenter.handle_level_message(rms_db, timestamp_ns)
- [ ] If segment returned (not None), segment added to _audio_queue.put_nowait((segment, segment_data))
- [ ] Callback passed to InputPipeline: on_level_message=self._on_level_message
- [ ] Log level messages at DEBUG level with RMS and timestamp

**Tests Required**:
- `test_worker_runner_level_message_handler()` - Handler calls vad_segmenter.handle_level_message()
- `test_worker_runner_level_message_queues_segment()` - Segment added to queue when returned

---

## Phase 5: Testing (Unit)

### Task T014: Unit tests for VADAudioSegmenter
**Priority**: P1
**Depends on**: T009
**Estimated effort**: L
**Files to modify/create**:
- `apps/media-service/tests/unit/buffer/test_vad_audio_segmenter.py` (new)

**Description**:
Create comprehensive unit tests for VADAudioSegmenter covering silence detection, buffer accumulation, min/max duration guards, EOS flush, and PTS tracking.

**Acceptance Criteria**:
- [ ] Test suite achieves >= 80% code coverage on VADAudioSegmenter
- [ ] All acceptance criteria from T003-T008 tested
- [ ] Tests use synthetic audio patterns (controlled RMS levels, known durations)
- [ ] Tests verify segment emission triggers (silence, max duration, EOS)
- [ ] Tests verify PTS and duration accuracy
- [ ] Tests run in < 5 seconds (fast unit tests)

**Tests Required**:
- `test_vad_silence_detection_triggers_emission()` - Silence boundary triggers segment emission
- `test_vad_max_duration_forces_emission()` - 15s max duration forces emission
- `test_vad_min_duration_violation_buffers_segment()` - <1s segments buffered
- `test_vad_pts_tracking_accurate()` - PTS and duration tracked correctly
- `test_vad_eos_flush_discards_short_partials()` - <1s partials discarded
- `test_vad_eos_flush_emits_valid_partials()` - >=1s partials emitted
- `test_vad_accumulates_across_silence_boundaries()` - Sub-minimum segments accumulated
- `test_vad_silence_resets_on_speech()` - Silence tracking resets when RMS rises
- `test_vad_continuous_speech_reaches_max_duration()` - Continuous speech hits 15s guard

---

### Task T015: Unit tests for SegmentationConfig
**Priority**: P1
**Depends on**: T001
**Estimated effort**: S
**Files to modify/create**:
- `apps/media-service/tests/unit/config/test_segmentation.py` (new)

**Description**:
Create unit tests for SegmentationConfig covering environment variable loading, default values, custom values, and validation logic.

**Acceptance Criteria**:
- [ ] Test suite achieves >= 95% code coverage on SegmentationConfig
- [ ] All acceptance criteria from T001 tested
- [ ] Tests use mocked environment variables (os.environ)
- [ ] Tests verify default values when env vars not set
- [ ] Tests verify custom values loaded correctly
- [ ] Tests verify validation rejects invalid configurations

**Tests Required**:
- `test_config_from_env_defaults()` - Default values loaded
- `test_config_from_env_custom()` - Custom values from environment
- `test_config_validation_rejects_positive_threshold()` - Positive threshold rejected
- `test_config_validation_rejects_min_greater_than_max()` - Min > max rejected
- `test_config_validation_rejects_short_silence_duration()` - <100ms silence rejected
- `test_config_validation_rejects_short_min_segment()` - <500ms min segment rejected
- `test_config_ms_to_ns_conversion()` - Millisecond to nanosecond conversion correct

---

## Phase 6: Testing (Integration)

### Task T016: Integration tests for level element
**Priority**: P1
**Depends on**: T014
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/tests/integration/buffer/test_vad_integration.py` (new)

**Description**:
Create integration tests for level element integration with InputPipeline. Test with real audio files containing known silence patterns, verify RMS messages received, and validate segment emission.

**Acceptance Criteria**:
- [ ] Test uses real audio file with known pattern (3s speech, 1s silence, 2s speech)
- [ ] Test runs InputPipeline → VADAudioSegmenter full integration
- [ ] Test verifies level messages received on bus with correct RMS values
- [ ] Test verifies 2 segments emitted with durations ~3s and ~2s
- [ ] Test verifies RuntimeError raised if level element unavailable

**Tests Required**:
- `test_vad_integration_with_real_audio()` - Full pipeline with test audio file
- `test_vad_integration_raises_on_level_failure()` - RuntimeError when level element fails
- `test_vad_integration_level_message_accuracy()` - RMS values match expected audio levels
- `test_vad_integration_variable_segment_durations()` - Segments have variable durations

---

### Task T017: Integration tests with MediaMTX
**Priority**: P2
**Depends on**: T016
**Estimated effort**: M
**Files to modify/create**:
- `apps/media-service/tests/integration/buffer/test_vad_mediamtx_integration.py` (new)

**Description**:
Create integration tests for VAD with MediaMTX and full WorkerRunner. Start MediaMTX in Docker, publish test stream with speech patterns, verify variable-length segments written to disk, and check metrics.

**Acceptance Criteria**:
- [ ] Test starts MediaMTX in Docker via docker-compose
- [ ] Test publishes RTMP test stream with known silence pattern
- [ ] Test starts WorkerRunner with VAD enabled
- [ ] Test verifies variable-length audio segments written to segment_dir
- [ ] Test verifies vad_enabled metric = 1
- [ ] Test verifies vad_segments_total increments
- [ ] Test cleanup stops Docker containers

**Tests Required**:
- `test_vad_with_mediamtx_variable_segments()` - Variable segments written to disk
- `test_vad_with_mediamtx_metrics_exposed()` - Metrics show VAD activity
- `test_vad_with_mediamtx_segment_metadata_correct()` - AudioSegment metadata accurate

---

## Phase 7: Testing (E2E)

### Task T018: E2E tests for full pipeline with VAD
**Priority**: P1
**Depends on**: T017
**Estimated effort**: L
**Files to modify/create**:
- `tests/e2e/test_vad_full_pipeline.py` (new)

**Description**:
Create E2E tests for complete dubbing pipeline with VAD segmentation. Start full stack (MediaMTX + media-service + STS), publish test stream, verify variable-length fragments sent to STS, validate A/V sync maintained, and verify output stream.

**Acceptance Criteria**:
- [ ] Test starts full E2E stack with docker-compose (MediaMTX, media-service, STS)
- [ ] Test publishes test stream with speech + silence patterns
- [ ] Test verifies variable-length audio fragments sent to STS (fragment:data events)
- [ ] Test verifies A/V sync delta < 120ms for 95% of segments
- [ ] Test verifies output stream plays correctly
- [ ] Test verifies metrics: vad_segments_total>0, vad_segment_duration_seconds histogram populated

**Tests Required**:
- `test_e2e_vad_full_pipeline()` - Full pipeline with VAD enabled
- `test_e2e_vad_metrics_exposed()` - Metrics endpoint shows VAD activity
- `test_e2e_vad_av_sync_maintained()` - A/V sync delta < 120ms
- `test_e2e_vad_variable_fragments_to_sts()` - Variable-length fragments sent to STS

---

### Task T019: Create synthetic audio test fixtures
**Priority**: P1
**Depends on**: None (can run in parallel)
**Estimated effort**: S
**Files to modify/create**:
- `tests/fixtures/audio/speech_with_silence.aac` (new)
- `tests/fixtures/audio/continuous_speech.aac` (new)
- `tests/fixtures/audio/rapid_speech.aac` (new)
- `tests/fixtures/audio/generate_fixtures.py` (new script)

**Description**:
Create synthetic audio test fixtures with known RMS patterns and durations for unit and integration tests. Use ffmpeg or pydub to generate AAC files with controlled audio levels and silence periods.

**Acceptance Criteria**:
- [ ] speech_with_silence.aac created: 3s speech (RMS -30dB), 1s silence (RMS -50dB), 2s speech (RMS -30dB)
- [ ] continuous_speech.aac created: 20s continuous speech (RMS -30dB, no pauses)
- [ ] rapid_speech.aac created: 0.8s speech, 0.5s pause, 0.7s speech, 0.4s pause (rapid pattern)
- [ ] generate_fixtures.py script generates all fixtures with controlled RMS levels
- [ ] Fixtures use AAC codec, 48kHz sample rate, mono audio
- [ ] README documents fixture patterns and usage

**Implementation Guidance** (L-002 fix):
```python
# generate_fixtures.py skeleton using pydub
from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise
import numpy as np

def generate_audio_at_rms(duration_ms: int, target_rms_db: float, sample_rate: int = 48000) -> AudioSegment:
    """Generate audio at specific RMS level in dB."""
    # RMS in dB: 20 * log10(rms_linear)
    # rms_linear = 10^(rms_db / 20)
    rms_linear = 10 ** (target_rms_db / 20)
    # Generate white noise and normalize to target RMS
    noise = WhiteNoise().to_audio_segment(duration=duration_ms, volume=target_rms_db)
    return noise.set_frame_rate(sample_rate).set_channels(1)

def generate_speech_with_silence():
    """3s speech (-30dB) + 1s silence (-60dB) + 2s speech (-30dB)"""
    speech1 = generate_audio_at_rms(3000, -30)
    silence = generate_audio_at_rms(1000, -60)  # Very quiet = silence
    speech2 = generate_audio_at_rms(2000, -30)
    combined = speech1 + silence + speech2
    combined.export("speech_with_silence.aac", format="adts")

# Usage: python generate_fixtures.py --fixture speech_with_silence
```

**Tests Required**:
- `test_fixture_speech_with_silence_pattern()` - Verify silence pattern detected
- `test_fixture_continuous_speech_duration()` - Verify 20s duration
- `test_fixture_rapid_speech_pattern()` - Verify rapid utterance pattern

---

## Phase 8: Documentation

### Task T020: Create VAD tuning guide documentation
**Priority**: P2
**Depends on**: T001, T018
**Estimated effort**: S
**Files to modify/create**:
- `docs/vad-tuning-guide.md` (new)

**Description**:
Create operator documentation for tuning VAD parameters for different content types. Include recommended configurations for studio speech, live broadcast, noisy environments, and multi-speaker content.

**Acceptance Criteria**:
- [ ] Document explains RMS threshold concept and units (dB)
- [ ] Document explains silence duration threshold and tradeoffs
- [ ] 4 preset configurations documented with rationale:
  - Studio speech: threshold=-50dB, silence=800ms (quiet environment, faster detection)
  - Live broadcast: threshold=-40dB, silence=1000ms (default, typical noise floor)
  - Noisy environment: threshold=-30dB, silence=1200ms (higher noise, longer silence needed)
  - Multi-speaker: threshold=-35dB, silence=600ms (faster transitions between speakers)
- [ ] Troubleshooting section: "Too many forced emissions" → lower threshold or increase max duration
- [ ] Troubleshooting section: "Not detecting pauses" → raise threshold or decrease silence duration
- [ ] Examples show how to interpret vad_segment_duration_seconds histogram for tuning decisions
- [ ] Document linked from main README.md

**Tests Required**:
- Manual review by operator/QA for clarity and completeness

---

### Task T021: Document manual QA process for SC-007
**Priority**: P2
**Depends on**: T018
**Estimated effort**: S
**Files to modify/create**:
- `docs/vad-qa-process.md` (new)

**Description**:
Document manual QA process to validate SC-007 (20% reduction in mid-phrase splits). Define baseline collection, evaluation criteria, and acceptance threshold.

**Acceptance Criteria**:
- [ ] Baseline process documented:
  1. Run 60-second test fixture with fixed 6s segmentation (VAD_ENABLED=false)
  2. Collect 10 audio segments
  3. Manually count mid-phrase splits (segment ends mid-word or mid-sentence)
  4. Record baseline: X splits out of 10 segments
- [ ] VAD evaluation process documented:
  1. Run same 60-second test fixture with VAD enabled (default settings)
  2. Collect all variable-length audio segments
  3. Manually count mid-phrase splits
  4. Calculate reduction: (baseline_splits - vad_splits) / baseline_splits * 100%
- [ ] Acceptance criteria: >= 20% reduction in mid-phrase splits
- [ ] Sample evaluation form/checklist provided
- [ ] Process repeatable by any QA engineer

**Tests Required**:
- Manual execution of QA process before production deployment

---

## Summary

**Total Tasks**: 20 (T009 removed - no fallback logic)
**P1 Tasks**: 16
**P2 Tasks**: 4

**Phase Breakdown**:
- Phase 1 (Foundation): 2 tasks (T001-T002)
- Phase 2 (Core VAD): 6 tasks (T003-T008) - no fallback
- Phase 3 (Metrics): 1 task (T010)
- Phase 4 (GStreamer Integration): 3 tasks (T011-T013) - fatal on level element failure
- Phase 5 (Unit Tests): 2 tasks (T014-T015)
- Phase 6 (Integration Tests): 2 tasks (T016-T017)
- Phase 7 (E2E Tests): 2 tasks (T018-T019)
- Phase 8 (Documentation): 2 tasks (T020-T021)

**Critical Path**:
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T010 → T011 → T012 → T013 → T014 → T016 → T018

**Parallelizable Tasks**:
- T019 (test fixtures) can start immediately in parallel
- T015 (SegmentationConfig tests) can start after T001
- T010 (metrics) can start after T001 (independent of T002-T009)
- T020-T021 (documentation) can start after T018

**Estimated Total Effort**:
- Small (S): 8 tasks × 0.5 days = 4 days
- Medium (M): 11 tasks × 1.5 days = 16.5 days
- Large (L): 2 tasks × 3 days = 6 days
- **Total: ~26.5 developer-days (~5.5 weeks @ 1 developer)**

**Next Steps**:
1. Start with T001 (SegmentationConfig) - foundation for all other tasks
2. Run T019 (test fixtures) in parallel - needed for testing
3. Follow critical path through core VAD implementation (T002-T009)
4. Complete metrics and integration (T010-T013)
5. Finish with comprehensive testing (T014-T018)
6. Complete documentation (T020-T021) before production deployment
