# Feature Specification: VAD Audio Segmentation

**Feature Branch**: `023-vad-audio-segmentation`
**Created**: 2026-01-08
**Status**: Draft
**Input**: User description: "Replace fixed 6-second audio fragments with dynamic VAD-based segmentation to improve translation quality by sending complete utterances to STS instead of arbitrary time-based chunks."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - VAD-Based Silence Detection Emits Segments (Priority: P1)

When audio is being processed through the pipeline, the system detects periods of silence (RMS level below -50dB for 1 second) and uses these natural speech boundaries to emit audio segments. This ensures segments contain complete utterances rather than being cut mid-sentence.

**Why this priority**: This is the core functionality that replaces the fixed 6-second segmentation. Without silence-based detection, the system cannot identify natural speech boundaries, making this the foundation for all other VAD features.

**Independent Test**: Verify silence boundary detection triggers segment emission
- **Unit test**: `test_vad_silence_boundary_emits_segment()` validates that 1 second of silence (RMS < -50dB) triggers segment emission
- **Unit test**: `test_vad_level_message_extraction()` validates RMS value extraction from GStreamer level element messages
- **Contract test**: `test_audio_segment_format()` validates emitted AudioSegment structure contains correct metadata (duration, timestamp, audio data)
- **Integration test**: `test_vad_integration_with_real_audio()` validates end-to-end VAD detection with actual audio containing speech and silence
- **Success criteria**: All tests pass, segments align with silence boundaries, 80% coverage achieved

**Acceptance Scenarios**:

1. **Given** audio stream is being processed with speech followed by 1s of silence, **When** silence duration threshold is reached, **Then** segment is emitted containing all accumulated audio up to the silence boundary
2. **Given** level element is inserted in audio pipeline, **When** audio buffers flow through, **Then** level messages are posted to GStreamer bus with RMS values every 100ms
3. **Given** RMS level drops below -50dB, **When** this persists for 1.0 seconds, **Then** silence state is detected and segment boundary is triggered

---

### User Story 2 - Maximum Duration Forces Segment Emission (Priority: P1)

When a speaker talks continuously for 15 seconds without any silence, the system must force a segment emission to prevent memory buildup and ensure timely processing. This guards against edge cases where speakers do not pause.

**Why this priority**: Without maximum duration enforcement, a continuous monologue could cause unbounded memory growth and excessive latency. This is a critical safety mechanism that must work alongside silence detection.

**Independent Test**: Verify forced emission at maximum duration
- **Unit test**: `test_vad_max_duration_forces_emission()` validates segment is emitted when duration reaches 15 seconds regardless of silence
- **Unit test**: `test_vad_max_duration_counter_reset()` validates counter resets after forced emission
- **Contract test**: `test_forced_emission_metric()` validates `vad_forced_emissions_total` counter increments
- **Integration test**: `test_vad_max_duration_with_continuous_speech()` validates behavior with real continuous audio
- **Success criteria**: All tests pass, forced emissions tracked in metrics, no segments exceed 15 seconds

**Acceptance Scenarios**:

1. **Given** audio stream with continuous speech (no silence), **When** accumulated duration reaches 15 seconds, **Then** segment is emitted immediately and accumulator is reset
2. **Given** segment is force-emitted at max duration, **When** emission completes, **Then** `vad_forced_emissions_total` metric is incremented
3. **Given** forced emission occurs, **When** new audio arrives, **Then** accumulation starts fresh from zero duration

---

### User Story 3 - Minimum Duration Buffers Short Segments (Priority: P2)

When silence is detected but the accumulated audio is shorter than 1 second, the system continues buffering instead of emitting a short segment. This prevents emitting fragments too small for meaningful translation.

**Why this priority**: While not as critical as P1 features, minimum duration enforcement prevents the STS service from receiving audio too short to translate effectively, improving overall translation quality.

**Independent Test**: Verify minimum duration buffering
- **Unit test**: `test_vad_min_duration_buffers_segment()` validates segments under 1 second are not emitted
- **Unit test**: `test_vad_min_duration_violation_metric()` validates `vad_min_duration_violations_total` counter increments
- **Contract test**: `test_short_segment_handling()` validates short audio is concatenated with next segment
- **Integration test**: `test_vad_min_duration_with_quick_pauses()` validates behavior with audio containing rapid speech/silence alternations
- **Success criteria**: All tests pass, no segments under 1 second emitted, violations tracked in metrics

**Acceptance Scenarios**:

1. **Given** audio stream with 0.5 seconds of speech followed by silence, **When** silence threshold is reached, **Then** segment is NOT emitted and audio remains in accumulator
2. **Given** short audio is buffered due to min duration, **When** more audio arrives, **Then** new audio is appended to existing accumulator
3. **Given** min duration violation occurs, **When** audio is buffered, **Then** `vad_min_duration_violations_total` metric is incremented

---

### User Story 4 - Fail-Fast on Missing Level Element (Priority: P2)

When the GStreamer `level` element from gst-plugins-good is not available, the system must fail immediately at startup with a clear error message. This ensures proper deployment and prevents silent degradation to a non-functional state.

**Why this priority**: Fail-fast behavior is critical for deployment validation but is not the primary user-facing functionality. It ensures operational correctness rather than feature functionality.

**Independent Test**: Verify fail-fast behavior
- **Unit test**: `test_vad_level_element_raises_on_failure()` validates RuntimeError is raised when level element creation fails
- **Unit test**: `test_vad_error_message_clarity()` validates error message clearly indicates gst-plugins-good requirement
- **Integration test**: `test_vad_integration_level_element_failure_fatal()` validates service fails to start without level element
- **Success criteria**: All tests pass, clear error message displayed, no fallback behavior exists

**Acceptance Scenarios**:

1. **Given** gst-plugins-good is not installed, **When** pipeline attempts to create level element, **Then** fatal RuntimeError is raised immediately
2. **Given** level element creation fails, **When** error is raised, **Then** error message specifies "gst-plugins-good must be installed"
3. **Given** level element is unavailable, **When** service starts, **Then** service fails to start (does NOT fall back to fixed 6s segments)

---

### User Story 5 - Configuration via Environment Variables (Priority: P2)

All VAD parameters must be configurable via environment variables, allowing operators to tune thresholds for different content types without code changes.

**Why this priority**: Configuration flexibility is important for operational tuning but the system works with defaults. This enables optimization without requiring the core functionality.

**Independent Test**: Verify environment variable configuration
- **Unit test**: `test_vad_config_from_env()` validates all parameters read from environment variables
- **Unit test**: `test_vad_config_defaults()` validates default values when environment variables not set
- **Contract test**: `test_segmentation_config_pydantic_model()` validates SegmentationConfig model structure
- **Success criteria**: All tests pass, all parameters configurable, defaults match specification

**Acceptance Scenarios**:

1. **Given** VAD_SILENCE_THRESHOLD_DB is set to -40, **When** SegmentationConfig is loaded, **Then** silence_threshold_db equals -40.0
2. **Given** VAD_MAX_SEGMENT_DURATION_S is set to 20, **When** SegmentationConfig is loaded, **Then** max_segment_duration_s equals 20.0
3. **Given** no environment variables set, **When** SegmentationConfig is loaded, **Then** defaults are used (-50dB, 1.0s silence, 1.0s min, 15.0s max)

---

### User Story 6 - End-of-Stream Flush Handling (Priority: P3)

When the stream ends (EOS signal received), the system must flush any remaining accumulated audio. If the accumulated audio is at least 1 second, it is emitted; otherwise, it is discarded.

**Why this priority**: EOS handling is an edge case that occurs infrequently during normal operation. While important for completeness, it does not affect the primary real-time segmentation flow.

**Independent Test**: Verify EOS flush behavior
- **Unit test**: `test_vad_eos_flush()` validates EOS triggers flush of accumulated audio
- **Unit test**: `test_vad_eos_discards_short_segment()` validates segments under 1 second are discarded on EOS
- **Unit test**: `test_vad_eos_emits_valid_segment()` validates segments over 1 second are emitted on EOS
- **Success criteria**: All tests pass, EOS handling complete, no audio lost above minimum threshold

**Acceptance Scenarios**:

1. **Given** stream has 3 seconds of audio in accumulator, **When** EOS is received, **Then** segment is emitted with the 3 seconds of audio
2. **Given** stream has 0.5 seconds of audio in accumulator, **When** EOS is received, **Then** audio is discarded (not emitted)
3. **Given** EOS is received with empty accumulator, **When** flush is called, **Then** no segment is emitted and no error occurs

---

### User Story 7 - Prometheus Metrics Exposure (Priority: P3)

All VAD operations must be instrumented with Prometheus metrics to enable monitoring and alerting on segmentation behavior, including segment counts, durations, silence detections, and edge case occurrences.

**Why this priority**: Observability is important for production operations but does not affect core functionality. Metrics enable debugging and optimization after initial deployment.

**Independent Test**: Verify metrics exposure
- **Unit test**: `test_vad_segment_counter_incremented()` validates `vad_segments_total` counter with trigger label
- **Unit test**: `test_vad_duration_histogram_recorded()` validates `vad_segment_duration_seconds` histogram receives values
- **Contract test**: `test_prometheus_metrics_format()` validates metrics follow Prometheus exposition format
- **Integration test**: `test_vad_integration_with_mediamtx()` validates metrics are exposed during real stream processing
- **Success criteria**: All tests pass, all specified metrics exposed, metrics endpoint accessible

**Acceptance Scenarios**:

1. **Given** segment is emitted due to silence, **When** emission completes, **Then** `vad_segments_total{trigger="silence"}` is incremented
2. **Given** segment is emitted, **When** emission completes, **Then** segment duration is recorded in `vad_segment_duration_seconds` histogram
3. **Given** media-service is running, **When** metrics endpoint is queried, **Then** all VAD metrics are present in response

---

### Edge Cases

- **No speech detected (all silence)**: System MUST NOT emit empty segments. If accumulated audio is below minimum threshold when silence is detected, it is buffered and combined with subsequent audio.
- **Extremely loud background noise above threshold**: System treats any audio above -50dB as speech. Operators may need to adjust threshold via environment variable for noisy content.
- **Rapid silence/speech alternation**: System applies minimum duration guard to prevent fragmentation. Multiple quick pauses result in combined segments until minimum duration is met.
- **Level element returns invalid RMS values**: System validates RMS values are within expected range (-100dB to 0dB). Invalid values are logged as warnings and treated as speech (no segment boundary). If 10+ consecutive invalid values are received, system raises fatal error to prevent silent malfunction.
- **Audio buffer timestamps out of order**: System tracks segment duration using accumulated buffer sizes rather than timestamps, preventing issues with out-of-order delivery.
- **Multiple audio channels**: System extracts RMS from all channels and uses the peak (maximum) value for silence detection, ensuring any channel with speech prevents segment boundary.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST insert GStreamer `level` element into audio pipeline path between source and segment buffer
- **FR-002**: System MUST configure level element with interval=100ms and post-messages=true for real-time RMS monitoring
- **FR-003**: System MUST listen for level messages on GStreamer bus and extract RMS values from message structure
- **FR-003a**: System MUST log warnings for level messages delayed >500ms from expected interval
- **FR-003b**: System MUST raise fatal error if no level messages received for 5 seconds (indicates pipeline malfunction)
- **FR-004**: System MUST detect silence when RMS value drops below configurable threshold (default -50dB)
- **FR-005**: System MUST track silence duration and emit segment boundary when silence persists for configurable duration (default 1.0 second)
- **FR-005a**: System MUST include silent audio buffers in emitted segments to preserve natural pauses (audio accumulates continuously during silence detection window)
- **FR-006**: System MUST enforce minimum segment duration (default 1.0 second), buffering short segments until threshold is met
- **FR-006a**: System MUST concatenate buffered short segments indefinitely until minimum duration is met or maximum duration is reached (no separate concatenation limit)
- **FR-007**: System MUST enforce maximum segment duration (default 15.0 seconds), force-emitting segment regardless of silence state
- **FR-007a**: System MUST enforce maximum audio accumulator memory limit of 10MB per stream, force-emitting segment when reached (treated as max-duration event)
- **FR-008**: System MUST flush remaining audio on EOS, emitting if above minimum duration, discarding otherwise
- **FR-009**: System MUST raise fatal RuntimeError at startup if level element cannot be created
- **FR-010**: System MUST NOT provide fallback to fixed-duration segmentation if VAD fails
- **FR-011**: System MUST expose all VAD parameters via environment variables (VAD_SILENCE_THRESHOLD_DB, VAD_SILENCE_DURATION_S, VAD_MIN_SEGMENT_DURATION_S, VAD_MAX_SEGMENT_DURATION_S, VAD_LEVEL_INTERVAL_NS, VAD_MEMORY_LIMIT_BYTES)
- **FR-012**: System MUST use Pydantic BaseSettings model for configuration with environment variable support
- **FR-013**: System MUST maintain video pass-through behavior unaffected by VAD boundaries (video flows continuously)
- **FR-014**: System MUST rely on flvmux for A/V sync via PTS timestamps (no keyframe alignment needed)
- **FR-015**: System MUST expose Prometheus metrics for VAD operations (vad_segments_total, vad_segment_duration_seconds, vad_silence_detections_total, vad_forced_emissions_total, vad_min_duration_violations_total, vad_memory_limit_emissions_total)
- **FR-016**: System MUST use peak channel RMS value when multiple audio channels are present
- **FR-016a**: System MUST validate RMS values are within -100dB to 0dB range, log warnings for invalid values, and treat them as speech
- **FR-016b**: System MUST raise fatal error if 10+ consecutive invalid RMS values are received from level element
- **FR-017**: VADAudioSegmenter class MUST manage state machine with _accumulator, _silence_start_ns, _is_in_silence tracking
- **FR-018**: VADAudioSegmenter MUST provide on_audio_buffer(), on_level_message(), and flush_audio() methods

### Key Entities

- **SegmentationConfig**: Pydantic configuration model containing all VAD parameters (silence_threshold_db, silence_duration_s, min_segment_duration_s, max_segment_duration_s) loaded from environment variables
- **VADAudioSegmenter**: State machine class managing audio accumulation, silence tracking, and segment emission based on VAD algorithm
- **AudioSegment**: Output entity containing segmented audio data with metadata (duration, start timestamp, audio bytes)
- **SilenceState**: Internal state tracking whether system is currently detecting silence and timestamp when silence began
- **Level Message**: GStreamer bus message from level element containing RMS values for each audio channel

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Audio segments are variable length between 1-15 seconds based on speech patterns, verified by segment duration histogram showing non-uniform distribution
- **SC-002**: Segments align with natural speech boundaries, verified by >80% of segments having silence-triggered emissions (not forced at max duration)
- **SC-003**: A/V synchronization maintained with delta < 120ms between video and dubbed audio, measured via ffprobe analysis of output stream
- **SC-004**: Service fails to start within 5 seconds with clear error message if gst-plugins-good level element is unavailable
- **SC-005**: All VAD parameters configurable via environment variables, verified by integration test with non-default values
- **SC-006**: Prometheus metrics endpoint exposes all 6 VAD metrics with correct labels and types (including vad_memory_limit_emissions_total)
- **SC-007**: Translation quality improved with fewer mid-sentence cuts, verified by manual review of 10 sample segments showing complete utterances
- **SC-008**: Unit test coverage for VAD components achieves minimum 80%
- **SC-009**: No segments shorter than minimum duration (1.0s) are emitted to STS service
- **SC-010**: No segments longer than maximum duration (15.0s) exist in output

## Assumptions

- GStreamer level element from gst-plugins-good provides accurate RMS measurements for AAC audio decoded to PCM
- -50dB RMS threshold is appropriate for distinguishing speech from silence in broadcast audio content
- 1.0 second of silence is sufficient to identify natural speech boundaries without over-segmenting
- 15.0 second maximum duration balances latency and segment completeness for typical broadcast content
- 10MB memory limit per stream is sufficient for typical broadcast audio (roughly 60s of 16kHz PCM)
- Audio pipeline already decodes AAC to PCM before reaching segment buffer
- flvmux correctly handles variable-length audio segments with appropriate PTS timestamps for A/V sync
- GStreamer bus message handling does not introduce significant latency (<10ms per message)
- Level element interval of 100ms provides sufficient granularity for silence detection
- Level messages arrive within reasonable time bounds (normally <100ms, warning threshold 500ms)

## Dependencies

- GStreamer 1.0 with gst-plugins-good (level element)
- Pydantic >= 2.0 (BaseSettings for configuration)
- prometheus_client (metrics instrumentation)
- Existing InputPipeline architecture for element insertion
- Existing SegmentBuffer interface for segment emission
- Existing WorkerRunner for callback wiring

## Clarifications

This section documents decisions made during specification:

### Session 2026-01-09

- Q: What happens if the audio accumulator memory grows beyond system capacity before 15s max duration is reached? → A: Enforce a hard memory limit of 10MB per stream (roughly 60s of 16kHz PCM audio) and force-emit segment when reached, treating it as a max-duration event.
- Q: How should the system handle invalid RMS values from the level element (warning vs fatal error)? → A: RMS values outside -100dB to 0dB range are logged as warnings and treated as speech (no boundary). If level element returns 10+ consecutive invalid values, raise fatal error to prevent silent malfunction.
- Q: Do audio buffers continue to accumulate during the silence detection window, or is silent audio excluded from segments? → A: Audio buffers are accumulated continuously, including during the silence detection window. When silence threshold is met, emit all accumulated audio INCLUDING the silent portion to preserve natural pauses in speech.
- Q: What happens if level messages from GStreamer bus are significantly delayed or stop arriving? → A: Level messages delayed >500ms are logged as warnings but do not affect VAD operation (silence tracking continues based on last received RMS value). If no level messages received for 5 seconds, raise fatal error indicating pipeline malfunction.
- Q: When short segments (below minimum duration) are buffered, is there a limit on how many can be concatenated before forcing emission? → A: Short segments are buffered and concatenated indefinitely until either: (1) combined duration exceeds minimum threshold and next silence is detected, OR (2) maximum duration (15s) is reached. The max duration limit provides sufficient upper bound.

### Original Clarifications

1. **Fail-Fast Design**: System will NOT fall back to fixed 6-second segments if VAD fails. Fatal error at startup ensures proper deployment verification and prevents silent degradation.

2. **Video Pass-Through**: Video stream flows continuously and is not affected by VAD segment boundaries. No keyframe alignment is performed. flvmux handles A/V synchronization via PTS timestamps.

3. **Native GStreamer Level Element**: Using GStreamer's built-in level element from gst-plugins-good instead of WebRTC VAD library. This provides real-time RMS monitoring without additional dependencies.

4. **Global Configuration**: All streams use the same VAD parameters (no per-stream configuration). This simplifies implementation for MVP while allowing operator tuning via environment variables.

5. **Peak Channel RMS**: For multi-channel audio, the peak (maximum) RMS value across channels is used for silence detection. This ensures speech in any channel prevents segment boundary.

6. **Not Included in Scope**:
   - Grafana dashboard (ops work, separate feature)
   - E2E tests in this workflow (manual testing for now)
   - Per-stream VAD configuration
   - WebRTC VAD library integration
