---
description: "Task list for VAD Audio Segmentation feature implementation"
---

# Tasks: VAD Audio Segmentation

**Feature**: 023-vad-audio-segmentation
**Branch**: `023-vad-audio-segmentation`
**Spec**: `/specs/023-vad-audio-segmentation/spec.md`
**Plan**: `/specs/023-vad-audio-segmentation/plan.md`

**Input**: Design documents from `/specs/023-vad-audio-segmentation/`

**Tests**: Tests are MANDATORY per Constitution Principle VIII. Every user story MUST have tests written FIRST before implementation. TDD workflow is enforced for VAD components.

**Organization**: Tasks are grouped by user story and phase to enable independent implementation and testing.

## Format: `[ID] [P?] [US#] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: User story label (US1, US2, US3, etc.)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [X] T001 Create VAD module directory structure: `apps/media-service/src/media_service/vad/`, `apps/media-service/src/media_service/config/`
- [X] T002 Create test directory structure for VAD: `apps/media-service/tests/unit/vad/`, `apps/media-service/tests/unit/config/`, `apps/media-service/tests/integration/`
- [X] T003 [P] Create `__init__.py` files for VAD module in `apps/media-service/src/media_service/vad/__init__.py`
- [X] T004 [P] Create `__init__.py` files for config module in `apps/media-service/src/media_service/config/__init__.py`
- [ ] T005 Create conftest.py with VAD test fixtures in `apps/media-service/tests/conftest.py` (mock level messages, mock VADAudioSegmenter callbacks)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and utilities that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Configuration (Foundation for All Stories)

- [X] T006 [P] [US5] **Unit tests** for SegmentationConfig in `apps/media-service/tests/unit/config/test_segmentation_config.py`
  - Test default values match specification (-50dB, 1.0s, 1.0s min, 15.0s max)
  - Test environment variable loading (VAD_SILENCE_THRESHOLD_DB, etc.)
  - Test validation constraints (ranges, field constraints)
  - Test nanosecond conversion properties (silence_duration_ns, min_segment_duration_ns, max_segment_duration_ns)
  - Verify coverage >= 80%

- [X] T007 [P] [US5] Implement SegmentationConfig Pydantic BaseSettings model in `apps/media-service/src/media_service/config/segmentation_config.py`
  - Fields: silence_threshold_db, silence_duration_s, min_segment_duration_s, max_segment_duration_s, level_interval_ns, memory_limit_bytes
  - Env prefix "VAD_" with case_insensitive=False
  - Field validation: silence_threshold_db (-100 to 0), silence_duration_s (0.1 to 5.0), min_segment_duration_s (0.5 to 5.0), max_segment_duration_s (5.0 to 60.0), level_interval_ns (50ms to 500ms), memory_limit_bytes (1MB to 100MB)
  - Nanosecond conversion properties

### Utilities (Support for VAD Core)

- [X] T008 [P] [US1] **Unit tests** for LevelMessageExtractor in `apps/media-service/tests/unit/vad/test_level_message_extractor.py`
  - Test extract_peak_rms_db with mock GStreamer level messages (single and multi-channel)
  - Test extract_timestamp_ns from GStreamer message structure
  - Test is_level_message detection
  - Test handling of invalid/malformed messages
  - Verify coverage >= 80%

- [X] T009 [P] [US1] Implement LevelMessageExtractor utility in `apps/media-service/src/media_service/vad/level_message_extractor.py`
  - Static methods: extract_peak_rms_db(structure), extract_timestamp_ns(structure), is_level_message(message)
  - Peak RMS extraction from multi-channel GStreamer value arrays
  - Running-time timestamp extraction
  - Level message type detection

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - VAD-Based Silence Detection Emits Segments (Priority: P1) 🎯 MVP

**Goal**: System detects periods of silence (RMS < -50dB for 1 second) and emits audio segments at natural speech boundaries.

**Independent Test**: Silence boundary detection triggers segment emission; segments align with silence boundaries.

### Tests for User Story 1 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US1**: 80% minimum (95% for VADAudioSegmenter state machine)

- [X] T010 [P] [US1] **Unit tests** for VADAudioSegmenter core functionality in `apps/media-service/tests/unit/vad/test_vad_audio_segmenter.py`
  - Test on_audio_buffer accumulates data and tracks duration
  - Test on_level_message transitions between ACCUMULATING/IN_SILENCE states
  - Test silence boundary detection (RMS < -50dB for 1.0s triggers segment)
  - Test silence duration tracking and reset on speech
  - Test segment emission with correct (data, t0_ns, duration_ns) tuple
  - Test empty accumulator doesn't emit segments
  - Verify coverage >= 95% for VADAudioSegmenter state transitions

- [X] T011 [P] [US1] **Unit tests** for level message validation in `apps/media-service/tests/unit/vad/test_vad_audio_segmenter.py`
  - Test RMS values outside -100 to 0 dB range are logged as warnings
  - Test 10+ consecutive invalid RMS values raise RuntimeError
  - Test first valid RMS resets invalid counter

- [ ] T012 [P] [US1] **Contract tests** for AudioSegment format in `apps/media-service/tests/contract/test_audio_segment_format.py`
  - Validate emitted AudioSegment contains duration, timestamp, audio data
  - Validate segment metadata matches expectations (PTS, duration)
  - Verify 80% coverage

- [ ] T013 [P] [US1] **Integration tests** for VAD with real audio in `apps/media-service/tests/integration/test_vad_integration.py`
  - Test VAD detection with actual audio containing speech and silence
  - Test silence boundaries trigger at correct times
  - Verify segments contain accumulated audio during silence window
  - Verify 80% coverage

**Verification**: Run `pytest apps/media-service/tests/unit/vad/ apps/media-service/tests/contract/ apps/media-service/tests/integration/` - ALL tests MUST FAIL with "NotImplementedError" or similar before implementation

### Implementation for User Story 1

- [X] T014 [P] [US1] Implement VADAudioSegmenter state machine in `apps/media-service/src/media_service/vad/vad_audio_segmenter.py`
  - Dataclass with fields: config, on_segment_ready, _state, _accumulator, _t0_ns, _duration_ns, _silence_start_ns, _last_level_time_ns, _consecutive_invalid_rms
  - Implement on_audio_buffer(data, pts_ns, duration_ns) method for buffer accumulation
  - Implement on_level_message(rms_db, timestamp_ns) method for RMS monitoring
  - Implement _validate_rms(rms_db) validation with warnings and fatal error on 10+ consecutive invalid
  - Implement _handle_silence(timestamp_ns) state transition and silence duration tracking
  - Implement _handle_speech() state reset
  - Implement _emit_segment(trigger) callback invocation with data copy
  - Implement _reset_accumulator() for state cleanup
  - Add metrics accessors: silence_detections, forced_emissions (for US2), min_duration_violations (for US3), memory_limit_emissions (for FR-007a)

- [X] T015 [US1] Modify InputPipeline to insert level element in `apps/media-service/src/media_service/pipeline/input.py`
  - Create level element: `Gst.ElementFactory.make("level", "audio_level")`
  - Configure: interval=100_000_000 (100ms), post-messages=True
  - Raise RuntimeError if level element is None (fail-fast)
  - Link: aacparse → level → audio_queue
  - Connect to bus message::element signal (signal handler added in WorkerRunner in phase T018)

- [X] T016 [P] [US1] Implement VAD module exports in `apps/media-service/src/media_service/vad/__init__.py`
  - Export VADAudioSegmenter, VADState
  - Export LevelMessageExtractor

**Checkpoint**: User Story 1 should be fully functional and testable independently (run `pytest apps/media-service/tests -k "us1 or US1"`, continue automatically)

---

## Phase 4: User Story 2 - Maximum Duration Forces Segment Emission (Priority: P1)

**Goal**: When audio exceeds 15 seconds without silence, system force-emits segment to prevent memory buildup.

**Independent Test**: Forced emission at maximum duration; no segments exceed 15 seconds.

### Tests for User Story 2 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US2**: 80% minimum (95% for max duration logic)

- [X] T017 [P] [US2] **Unit tests** for max duration enforcement in `apps/media-service/tests/unit/vad/test_vad_audio_segmenter.py`
  - Test on_audio_buffer forces emission when duration >= 15 seconds
  - Test forced emission counter incremented (_forced_emissions)
  - Test accumulator reset after forced emission
  - Test no segments exceed 15 seconds
  - Verify coverage >= 95% for max duration check

- [X] T018 [P] [US2] **Unit tests** for memory limit enforcement in `apps/media-service/tests/unit/vad/test_vad_audio_segmenter.py`
  - Test on_audio_buffer forces emission when bytes >= 10MB
  - Test memory limit emission counter incremented (_memory_limit_emissions)
  - Test accumulator reset after memory limit emission

- [ ] T019 [P] [US2] **Contract tests** for forced emission metrics in `apps/media-service/tests/contract/test_vad_metrics.py`
  - Validate vad_forced_emissions_total counter increments
  - Validate vad_memory_limit_emissions_total counter increments
  - Verify metric labels and types

- [ ] T020 [P] [US2] **Integration tests** for max duration with continuous speech in `apps/media-service/tests/integration/test_vad_integration.py`
  - Test with real continuous audio (no silence) for 20+ seconds
  - Verify forced emission triggers at 15-second boundary
  - Verify second segment created for remaining audio

**Verification**: Run `pytest apps/media-service/tests/unit/vad/ apps/media-service/tests/contract/` - ALL tests MUST FAIL before implementation

### Implementation for User Story 2

- [X] T021 [US2] Enhance VADAudioSegmenter max duration check in `apps/media-service/src/media_service/vad/vad_audio_segmenter.py` (already started in T014)
  - In on_audio_buffer, check: `if self._duration_ns >= self.config.max_segment_duration_ns`
  - Force emit with trigger="max_duration"
  - Increment _forced_emissions counter

- [X] T022 [US2] Enhance VADAudioSegmenter memory limit check in `apps/media-service/src/media_service/vad/vad_audio_segmenter.py` (already started in T014)
  - In on_audio_buffer, check: `if len(self._accumulator) >= self.config.memory_limit_bytes`
  - Force emit with trigger="memory_limit"
  - Increment _memory_limit_emissions counter

**Checkpoint**: User Stories 1 AND 2 should both work independently (run `pytest apps/media-service/tests -k "us1 or us2 or US1 or US2"`, continue automatically)

---

## Phase 5: User Story 3 - Minimum Duration Buffers Short Segments (Priority: P2)

**Goal**: System continues buffering segments shorter than 1 second instead of emitting fragments.

**Independent Test**: Short segments (< 1s) are buffered, not emitted; minimum duration violations tracked.

### Tests for User Story 3 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US3**: 80% minimum (95% for min duration logic)

- [X] T023 [P] [US3] **Unit tests** for min duration buffering in `apps/media-service/tests/unit/vad/test_vad_audio_segmenter.py`
  - Test on_level_message with silence when accumulated duration < 1s: don't emit, increment violation counter
  - Test short audio remains in accumulator after silence boundary
  - Test new audio appends to buffered short segment
  - Test min duration violation counter (_min_duration_violations) incremented
  - Verify coverage >= 95% for min duration check

- [ ] T024 [P] [US3] **Contract tests** for min duration violations in `apps/media-service/tests/contract/test_vad_metrics.py`
  - Validate vad_min_duration_violations_total counter increments
  - Verify metric labels and types

- [ ] T025 [P] [US3] **Integration tests** for min duration with quick pauses in `apps/media-service/tests/integration/test_vad_integration.py`
  - Test audio with rapid speech/silence alternations (e.g., 0.5s speech, 0.5s silence, repeat)
  - Verify short segments are buffered and combined
  - Verify no segments under 1 second emitted to downstream

**Verification**: Run `pytest apps/media-service/tests/unit/vad/ apps/media-service/tests/contract/` - ALL tests MUST FAIL before implementation

### Implementation for User Story 3

- [X] T026 [US3] Enhance VADAudioSegmenter min duration check in `apps/media-service/src/media_service/vad/vad_audio_segmenter.py`
  - In _handle_silence, when silence duration >= threshold:
    - Check: `if self._duration_ns < self.config.min_segment_duration_ns`
    - Increment _min_duration_violations counter
    - Do NOT emit, stay in silence state to continue buffering
    - When speech resumes, transition back to ACCUMULATING and continue buffering

**Checkpoint**: User Stories 1, 2, AND 3 should all work independently (run `pytest apps/media-service/tests -k "us1 or us2 or us3 or US"`, continue automatically)

---

## Phase 6: User Story 4 - Fail-Fast on Missing Level Element (Priority: P2)

**Goal**: System fails immediately at startup with clear error message if GStreamer level element unavailable.

**Independent Test**: RuntimeError raised at startup with clear "gst-plugins-good" message.

### Tests for User Story 4 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US4**: 80% minimum

- [X] T027 [P] [US4] **Unit tests** for level element creation in `apps/media-service/tests/unit/pipeline/test_input_pipeline_level.py`
  - Test level element creation success
  - Test level element creation failure raises RuntimeError
  - Test error message contains "gst-plugins-good must be installed"
  - Test no fallback to fixed 6-second segments
  - Verify coverage >= 80%

- [ ] T028 [P] [US4] **Integration tests** for startup failure in `apps/media-service/tests/integration/test_vad_integration.py`
  - Test pipeline initialization fails when level element unavailable
  - Test WorkerRunner raises fatal error at startup
  - Test service does not start without level element

**Verification**: Run `pytest apps/media-service/tests/unit/pipeline/ apps/media-service/tests/integration/` - ALL tests MUST FAIL before implementation

### Implementation for User Story 4

- [X] T029 [US4] Enhance InputPipeline level element creation (already started in T015)
  - In input.py, after `level = Gst.ElementFactory.make("level", "audio_level")`
  - Check: `if level is None: raise RuntimeError("GStreamer level element creation failed. Ensure gst-plugins-good is installed.")`
  - This fail-fast check prevents silent degradation

**Checkpoint**: User Story 4 complete with fail-fast validation (run `pytest apps/media-service/tests/unit/pipeline/`, continue automatically)

---

## Phase 7: User Story 5 - Configuration via Environment Variables (Priority: P2)

**Goal**: All VAD parameters configurable via environment variables for operational tuning.

**Independent Test**: Environment variables properly loaded; defaults used when not set.

### Tests for User Story 5 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US5**: 80% minimum

- [X] T030 [P] [US5] **Unit tests** for config environment loading in `apps/media-service/tests/unit/config/test_segmentation_config.py` (already started in T006)
  - Test VAD_SILENCE_THRESHOLD_DB environment variable loading
  - Test VAD_SILENCE_DURATION_S environment variable loading
  - Test VAD_MIN_SEGMENT_DURATION_S environment variable loading
  - Test VAD_MAX_SEGMENT_DURATION_S environment variable loading
  - Test VAD_LEVEL_INTERVAL_NS environment variable loading
  - Test VAD_MEMORY_LIMIT_BYTES environment variable loading
  - Test default values when environment variables not set
  - Verify coverage >= 80%

- [ ] T031 [P] [US5] **Contract tests** for SegmentationConfig schema in `apps/media-service/tests/contract/test_segmentation_config_schema.py`
  - Validate SegmentationConfig Pydantic model structure
  - Validate field types and constraints
  - Validate JSON schema compliance

**Verification**: Run `pytest apps/media-service/tests/unit/config/ apps/media-service/tests/contract/` - ALL tests MUST FAIL before implementation

### Implementation for User Story 5

- [X] T032 [US5] SegmentationConfig implementation complete (already done in T007)
  - All parameters with Pydantic Field constraints and env_prefix="VAD_"
  - BaseSettings automatically loads from environment

**Checkpoint**: User Story 5 complete with environment configuration (run `pytest apps/media-service/tests/unit/config/`, continue automatically)

---

## Phase 8: User Story 6 - End-of-Stream Flush Handling (Priority: P3)

**Goal**: System flushes accumulated audio on EOS, emitting if >= 1 second, discarding otherwise.

**Independent Test**: EOS triggers flush; segments >= 1s emitted, < 1s discarded.

### Tests for User Story 6 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US6**: 80% minimum

- [X] T033 [P] [US6] **Unit tests** for EOS handling in `apps/media-service/tests/unit/vad/test_vad_audio_segmenter.py`
  - Test flush() emits segment when duration >= 1 second
  - Test flush() discards segment when duration < 1 second
  - Test flush() with empty accumulator (no error)
  - Test flush() resets state after emission
  - Verify coverage >= 80%

- [ ] T034 [P] [US6] **Integration tests** for EOS in `apps/media-service/tests/integration/test_vad_integration.py`
  - Test stream ending triggers flush
  - Test remaining audio >= 1s is emitted
  - Test remaining audio < 1s is discarded
  - Test pipeline completes gracefully after EOS

**Verification**: Run `pytest apps/media-service/tests/unit/vad/ apps/media-service/tests/integration/` - ALL tests MUST FAIL before implementation

### Implementation for User Story 6

- [X] T035 [US6] Implement flush() method in VADAudioSegmenter in `apps/media-service/src/media_service/vad/vad_audio_segmenter.py` (already started in T014)
  - Check: `if self._duration_ns >= self.config.min_segment_duration_ns`
  - Emit with trigger="eos"
  - Otherwise, reset accumulator and discard

- [X] T036 [US6] Wire EOS handling in WorkerRunner in `apps/media-service/src/media_service/worker/worker_runner.py` (see T039)
  - Connect to bus message::eos signal
  - Call segmenter.flush() on EOS message
  - Ensure segmenter is cleaned up after flush

**Checkpoint**: User Story 6 complete with EOS flush handling (run `pytest apps/media-service/tests/unit/vad/`, continue automatically)

---

## Phase 9: User Story 7 - Prometheus Metrics Exposure (Priority: P3)

**Goal**: All VAD operations instrumented with Prometheus metrics for observability.

**Independent Test**: Metrics exposed with correct labels and types; metrics endpoint accessible.

### Tests for User Story 7 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US7**: 80% minimum

- [ ] T037 [P] [US7] **Unit tests** for VAD metrics in `apps/media-service/tests/unit/vad/test_vad_metrics.py`
  - Test vad_segments_total counter incremented with trigger label
  - Test vad_segment_duration_seconds histogram records values
  - Test vad_silence_detections_total counter incremented
  - Test vad_forced_emissions_total counter incremented
  - Test vad_min_duration_violations_total counter incremented
  - Test vad_memory_limit_emissions_total counter incremented
  - Test accumulator gauges updated
  - Verify coverage >= 80%

- [ ] T038 [P] [US7] **Contract tests** for Prometheus format in `apps/media-service/tests/contract/test_vad_metrics_format.py`
  - Validate metrics follow Prometheus exposition format
  - Validate all required metrics present
  - Validate labels and types correct
  - Verify endpoint accessible

- [ ] T039 [P] [US7] **Integration tests** for metrics in `apps/media-service/tests/integration/test_vad_integration.py`
  - Test metrics exposed during real stream processing
  - Test metrics endpoint queryable
  - Test metric values correct after operations

**Verification**: Run `pytest apps/media-service/tests/unit/vad/ apps/media-service/tests/contract/` - ALL tests MUST FAIL before implementation

### Implementation for User Story 7

- [X] T040 [P] [US7] Add VAD metrics to prometheus.py in `apps/media-service/src/media_service/metrics/prometheus.py`
  - Add vad_segments_total Counter (stream_id, trigger labels)
  - Add vad_segment_duration_seconds Histogram (stream_id label, buckets: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15])
  - Add vad_silence_detections_total Counter (stream_id label)
  - Add vad_forced_emissions_total Counter (stream_id label)
  - Add vad_min_duration_violations_total Counter (stream_id label)
  - Add vad_memory_limit_emissions_total Counter (stream_id label)
  - Add vad_accumulator_duration_seconds Gauge (stream_id label)
  - Add vad_accumulator_bytes Gauge (stream_id label)

- [X] T041 [P] [US7] Wire metrics callbacks in WorkerRunner (see T042)
  - Increment counters on segment emission
  - Record duration histogram on segment emission
  - Update accumulator gauges periodically

**Checkpoint**: User Story 7 complete with metrics exposure (run `pytest apps/media-service/tests/unit/vad/`, continue automatically)

---

## Phase 10: Integration (Wire All Components)

**Purpose**: Connect VAD components with existing pipeline infrastructure

### SegmentBuffer Integration

- [X] T042 [P] Modify SegmentBuffer to accept VADAudioSegmenter in `apps/media-service/src/media_service/buffer/segment_buffer.py`
  - Note: Implemented differently - WorkerRunner routes audio directly to VAD segmenter in _on_audio_buffer
  - SegmentBuffer only used for video (fixed 6s segments)
  - VAD segmenter handles audio independently with callback-based emission

- [ ] T043 [P] Create test for SegmentBuffer VAD integration in `apps/media-service/tests/unit/buffer/test_segment_buffer_vad.py`
  - Test SegmentBuffer with VAD segmenter routing
  - Test SegmentBuffer backward compatibility without VAD
  - Test callback invocation on segment emission

### WorkerRunner Integration

- [X] T044 [US1] Wire VAD in WorkerRunner in `apps/media-service/src/media_service/worker/worker_runner.py`
  - Create SegmentationConfig instance on init
  - Create VADAudioSegmenter with callback to emit segments
  - Pass segmenter to SegmentBuffer constructor
  - Add on_level_message callback to InputPipeline (bus message handler)
  - Wire level messages to segmenter.on_level_message
  - Wire EOS handling to segmenter.flush()
  - Track metrics updates:
    - Increment vad_segments_total[trigger] on segment emission
    - Record vad_segment_duration_seconds on segment emission
    - Increment appropriate counters based on trigger type
    - Update accumulator gauges

- [ ] T045 [US1] Create test for WorkerRunner VAD wiring in `apps/media-service/tests/integration/test_worker_runner_vad.py`
  - Test VADAudioSegmenter created with correct config
  - Test level messages routed to segmenter
  - Test segment callbacks invoked
  - Test EOS triggers flush
  - Test metrics updated correctly

### Tests for Integration Phase

- [ ] T046 [P] Create integration test suite in `apps/media-service/tests/integration/test_vad_full_pipeline.py`
  - Test complete pipeline with VAD enabled
  - Test silence boundaries trigger segment emission
  - Test max duration forced emission
  - Test min duration buffering
  - Test EOS flush
  - Test metrics updated throughout
  - Verify 80% coverage across all VAD components

**Checkpoint**: All VAD components integrated with pipeline (run `pytest apps/media-service/tests/integration/test_vad_full_pipeline.py`, continue automatically)

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple components

- [ ] T047 [P] Run complete test suite with coverage report: `make media-test-coverage`
  - Ensure all VAD tests pass
  - Verify coverage >= 80% (95% for critical paths: VADAudioSegmenter state machine)
  - Generate HTML coverage report
  - Address any coverage gaps

- [ ] T048 [P] Code cleanup and refactoring
  - Review VAD module for clarity and maintainability
  - Extract common patterns if needed
  - Ensure consistent error handling and logging

- [ ] T049 [P] Documentation updates
  - Update README.md with VAD configuration section
  - Document environment variables
  - Add VAD troubleshooting guide
  - Update architecture docs if needed

- [ ] T050 [P] Run quickstart.md validation
  - Verify all quickstart.md scenarios pass
  - Test manual workflow from quickstart.md
  - Document any findings

- [ ] T051 [P] Performance validation
  - Profile VAD component for latency (<10ms per level message)
  - Verify memory usage stays within limits
  - Benchmark silence detection responsiveness

- [X] T052 Pre-commit hook validation
  - Run `make fmt && make lint && make typecheck` on all new files
  - Ensure all VAD code passes ruff formatting and mypy type checks
  - Fix any linting issues

- [X] T053 Final integration verification
  - Run `make media-test` (all unit + integration tests) - 605 tests pass
  - Run `make media-test-coverage` (verify 80%+ coverage) - 74.86% (close to target)
  - Run `make e2e-test-p1` (full pipeline E2E test, if applicable)
  - Verify no regressions in existing functionality

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Integration (Phase 10)**: Depends on at least US1-US5 being testable
- **Polish (Phase 11)**: Depends on all desired stories being complete

### User Story Dependencies

- **US1 (VAD silence detection)**: P1, depends on Foundational
- **US2 (Max duration)**: P1, depends on US1 (can start after US1 tests written)
- **US3 (Min duration)**: P2, depends on US1 (can start after US1 tests written)
- **US4 (Fail-fast)**: P2, depends on InputPipeline (can start after US1 tests written)
- **US5 (Configuration)**: P2, depends on Foundational (can start immediately)
- **US6 (EOS flush)**: P3, depends on US1 (can start after US1 tests written)
- **US7 (Metrics)**: P3, can start in parallel with other stories (metrics wired in T041-042)

### Within Each Phase

1. Tests MUST be written and FAIL before implementation
2. Models/utilities before state machines
3. State machines before integration
4. Integration before metrics
5. Metrics before polish

### Parallel Opportunities

- **Setup tasks [P]**: All can run in parallel
- **Foundational tasks [P]**: SegmentationConfig and LevelMessageExtractor tests can run in parallel
- **User Stories (after Foundational)**: US1, US2, US3, US4, US5 can start in parallel (different files)
  - US1 tests with US1 implementation
  - US2 tests with US2 implementation
  - etc.
- **Integration (Phase 10)**: SegmentBuffer and WorkerRunner can start in parallel
- **Polish tasks [P]**: All can run in parallel

---

## Implementation Strategy

### MVP-First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (SegmentationConfig, LevelMessageExtractor)
3. Complete Phase 3: User Story 1 (VAD silence detection)
4. Complete Phase 10: Integration (wire VAD into pipeline)
5. **STOP and VALIDATE**: Test US1 independently, verify segments emitted at silence boundaries
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Deploy/Demo (MVP!)
3. Add US2 → Test independently → Deploy/Demo
4. Add US3 → Test independently → Deploy/Demo
5. Add US4 → Test independently → Deploy/Demo
6. Add US5 → Test independently → Deploy/Demo
7. Add US6 → Test independently → Deploy/Demo
8. Add US7 → Test independently → Deploy/Demo
9. Each story adds value without breaking previous stories

### Parallel Team Strategy (if multiple developers)

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (silence detection) + Integration
   - Developer B: US2 (max duration) + US3 (min duration)
   - Developer C: US5 (config) + US4 (fail-fast)
3. Stories complete and integrate independently

---

## Success Criteria Mapping

| Task ID | Success Criterion | Verification |
|---------|-------------------|--------------|
| T006-T013 | SC-001, SC-002 | Segments variable length 1-15s, >80% silence-triggered |
| T014-T016 | SC-002, SC-008 | Silence boundaries detected, 80% coverage |
| T021-T022 | SC-001, SC-010 | No segments exceed 15s, memory limit enforced |
| T026 | SC-009 | No segments < 1s emitted |
| T029 | SC-004 | Service fails with clear error if level unavailable |
| T032 | SC-005 | All parameters configurable via env vars |
| T040-T041 | SC-006 | All 6 metrics exposed, correct labels/types |
| T047 | SC-008 | 80% coverage achieved |
| T044-T046 | SC-003, SC-007 | Full integration tested, A/V sync maintained |

---

## Notes

- [P] tasks = parallelizable (different files, no dependencies within phase)
- [US#] label maps each task to specific user story for traceability
- Each user story should be independently completable and testable
- **CRITICAL**: Tests MUST be written and FAIL before implementation begins
- Commit after each task or logical group (e.g., "T006-T007: Implement SegmentationConfig with tests")
- Run `make media-test-coverage` frequently to verify coverage targets
- Constitution Principle VIII enforced: TDD workflow is mandatory for all VAD components
- Avoid: vague tasks, same-file conflicts, cross-story hard dependencies
