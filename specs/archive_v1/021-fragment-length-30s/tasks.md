# Tasks: Fragment Length Increase from 6s to 30s

**Feature ID**: 021-fragment-length-30s
**Spec**: specs/021-fragment-length-30s/spec.md
**Plan**: specs/021-fragment-length-30s/plan.md
**Generated**: 2026-01-11
**Status**: Ready for Implementation

**ARCHITECTURAL CHANGE**: This task list uses the "buffer and wait" approach for A/V synchronization. All av_offset_ns and drift correction tasks have been removed. **Output is re-encoded with PTS starting from 0** (not original stream PTS).

---

## Task Summary

| Phase | Name | Tasks | Complexity | Est. Duration |
|-------|------|-------|-----------|--------------|
| **Setup** | Prerequisite validation | T001-T002 | S | 15 min |
| **Phase 1 (TDD)** | Unit tests (write first) | T003-T012 | M | 1-2 hrs |
| **Phase 2** | Media service core | T013-T021 | M | 2-3 hrs |
| **Phase 3** | STS service changes | T022-T028 | M | 1-2 hrs |
| **Phase 4** | E2E test config | T029-T033 | S | 1 hr |
| **Phase 5** | Validation & testing | T034-T040 | M | 2-3 hrs |
| **Phase 6** | Documentation & cleanup | T041-T045 | S | 1 hr |
| **Phase 7** | Git & PR | T046-T050 | S | 30 min |

**Total Tasks**: 50
**Parallelizable**: 10
**Dependencies**: Strictly ordered by phase (TDD: tests before implementation)

---

## Implementation Tasks

### PHASE 0: SETUP

- [X] T001 [P] Setup Check prerequisites and environment
  - **Files**: `.specify/scripts/bash/check-prerequisites.sh`
  - **Complexity**: S
  - **Acceptance**: Run `make setup` succeeds, all dependencies installed
  - **Commands**: `cd /Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud && make setup`

- [X] T002 [P] Create Create feature branch `021-fragment-length-30s`
  - **Files**: `.git/` (git branch operations)
  - **Complexity**: S
  - **Acceptance**: Branch created, can list with `git branch`
  - **Commands**: `git checkout -b 021-fragment-length-30s`

---

### PHASE 1: TEST INFRASTRUCTURE (TDD - Tests First)

**Priority**: P0 - MUST complete before Phase 2-4
**Key Principle**: Write failing tests first, implementation follows
**Success**: `make media-test-unit` and `make sts-test-unit` run, tests FAIL with current 6s values

#### Media Service Unit Tests

- [X] T003 Update segment duration assertions in `test_models_segments.py`
  - **File**: `apps/media-service/tests/unit/test_models_segments.py`
  - **Complexity**: S
  - **Changes**:
    - Update `test_video_segment_duration()` assertion to expect 30_000_000_000 (was 6_000_000_000)
    - Update `test_audio_segment_duration()` assertion to expect 30_000_000_000 (was 6_000_000_000)
    - Add new test: `test_video_segment_duration_30s()` validating FR-001
    - Add new test: `test_audio_segment_duration_30s()` validating FR-002
  - **Acceptance**: Tests updated, `pytest apps/media-service/tests/unit/test_models_segments.py -v` shows 4 tests, all FAIL before implementation

- [X] T004 Update A/V sync state tests in `test_models_state.py` (Buffer and Wait)
  - **File**: `apps/media-service/tests/unit/test_models_state.py`
  - **Complexity**: M
  - **Changes**:
    - **REMOVE** any `test_av_sync_state_offset()` tests (av_offset_ns removed)
    - **REMOVE** any `test_needs_correction()` tests (drift correction removed)
    - **REMOVE** any `test_apply_slew_correction()` tests (drift correction removed)
    - Add new test: `test_av_sync_state_no_offset()` validating av_offset_ns is removed
    - Add new test: `test_av_sync_state_tracks_pts()` validating video_pts_last, audio_pts_last
    - Add new test: `test_av_sync_state_calculates_delta()` validating sync_delta_ns
  - **Acceptance**: Tests updated, av_offset tests removed, buffer-and-wait tests added

- [X] T005 Update segment buffer assertions in `test_segment_buffer.py`
  - **File**: `apps/media-service/tests/unit/test_segment_buffer.py`
  - **Complexity**: M
  - **Changes**:
    - Update all duration threshold checks from 6_000_000_000 to 30_000_000_000
    - Update expected segment count for 60s fixture from 10 to 2
    - Add new test: `test_segment_buffer_accumulates_30s()` validating FR-003
    - Update or add test for 60s fixture expecting 2 segments (not 10)
  - **Acceptance**: `pytest apps/media-service/tests/unit/test_segment_buffer.py -v` shows duration tests FAIL

- [X] T006 Update A/V sync manager tests in `test_av_sync.py` (Buffer and Wait, PTS=0)
  - **File**: `apps/media-service/tests/unit/test_av_sync.py`
  - **Complexity**: M
  - **Changes**:
    - **REMOVE** any `av_offset_ns` parameter tests (offset removed)
    - **REMOVE** any drift correction tests (drift correction removed)
    - **REMOVE** any original PTS preservation tests (PTS now reset to 0)
    - Add new test: `test_av_sync_manager_buffers_video_until_audio_ready()` validating FR-010
    - Add new test: `test_av_sync_manager_buffers_audio_until_video_ready()` validating FR-010
    - Add new test: `test_sync_pair_pts_starts_from_zero()` validating FR-012 (PTS=0)
    - Add new test: `test_output_is_reencoded()` validating FR-012 (re-encoding)
    - Add new test: `test_av_sync_manager_no_drift_correction()` validating FR-013
  - **Acceptance**: Tests updated, offset tests removed, buffer-and-wait and PTS=0 tests added

- [ ] T007 Update STS communication model tests in `test_sts_models.py`
  - **File**: `apps/media-service/tests/unit/test_sts_models.py`
  - **Complexity**: S
  - **Changes**:
    - Update `test_stream_config_chunk_duration()` assertion from 6000 to 30000
    - Add new test: `test_stream_config_chunk_duration_30000()` validating FR-006
  - **Acceptance**: `pytest apps/media-service/tests/unit/test_sts_models.py -v` shows chunk_duration test FAILS

- [ ] T008 Update worker configuration tests in `test_worker_runner.py`
  - **File**: `apps/media-service/tests/unit/test_worker_runner.py`
  - **Complexity**: S
  - **Changes**:
    - Update `test_worker_config_segment_duration()` assertion from 6_000_000_000 to 30_000_000_000
    - Add new test validating FR-021 (WorkerConfig.segment_duration_ns)
  - **Acceptance**: Worker duration tests FAIL

#### STS Service Unit Tests

- [ ] T009 [P] Create new test file `test_session.py` for StreamSession defaults
  - **File**: `apps/sts-service/tests/unit/test_session.py` (create new)
  - **Complexity**: M
  - **Changes**:
    - Create file with imports: `from sts_service.full.session import StreamSession`
    - Add test: `test_stream_session_timeout_ms_default_60000()` validating FR-008
    - Add test: `test_stream_session_chunk_duration_30000()` validating FR-007
    - Include __init__.py if missing
  - **Acceptance**: File created, 2 new tests exist, both FAIL before implementation

- [ ] T010 [P] Create new test file `test_stream_models.py` for validation constraints
  - **File**: `apps/sts-service/tests/unit/test_stream_models.py` (create new)
  - **Complexity**: M
  - **Changes**:
    - Create file with imports: `from sts_service.echo.models.stream import StreamConfigPayload, StreamInitPayload`
    - Add test: `test_stream_config_payload_accepts_30000ms()` validating FR-014
    - Add test: `test_stream_init_payload_timeout_120000_valid()` validating FR-015
    - Include __init__.py if missing
  - **Acceptance**: File created, 2 new tests exist, both FAIL before implementation

- [ ] T011 Verify unit tests fail with current values
  - **Complexity**: S
  - **Acceptance**:
    - `make media-test-unit` runs, shows test failures for 30s duration expectations
    - `make sts-test-unit` runs, shows test failures for 30s/60s timeout expectations
  - **Key Point**: This validates TDD setup before implementation starts

#### E2E Test Config

- [X] T012 [P] Update E2E test configuration in `config.py`
  - **File**: `tests/e2e/config.py`
  - **Complexity**: S
  - **Changes**:
    - Update `TestConfig.SEGMENT_DURATION_SEC`: 6 -> 30
    - Update `TestConfig.SEGMENT_DURATION_NS`: 6_000_000_000 -> 30_000_000_000
    - Update `TestConfig.EXPECTED_SEGMENTS`: 10 -> 2 (for 60s fixture)
    - Update `TimeoutConfig.FRAGMENT_TIMEOUT`: 8 -> 60
    - Update `TimeoutConfig.PIPELINE_COMPLETION`: 90 -> 120
  - **Acceptance**: Config values updated, can import and verify: `from tests.e2e.config import TestConfig; assert TestConfig.SEGMENT_DURATION_SEC == 30`

---

### PHASE 2: MEDIA SERVICE CORE CHANGES

**Priority**: P1 - Core functionality
**Dependency**: Phase 1 tests must exist and fail
**Success**: `make media-test-unit` passes all updated assertions

#### Segment Duration Constants

- [X] T013 Update VideoSegment and AudioSegment constants in `segments.py`
  - **File**: `apps/media-service/src/media_service/models/segments.py`
  - **Complexity**: S
  - **Changes**:
    - Line 49: `DEFAULT_SEGMENT_DURATION_NS: ClassVar[int] = 6_000_000_000` -> `30_000_000_000`
    - Line 152: `DEFAULT_SEGMENT_DURATION_NS: ClassVar[int] = 6_000_000_000` -> `30_000_000_000` (AudioSegment)
    - Update docstring line 8: "~6 seconds" -> "~30 seconds"
    - Update docstring lines 36-37: "6_000_000_000 (6 seconds)" -> "30_000_000_000 (30 seconds)"
    - Update docstring lines 137-138: Same for AudioSegment
  - **Acceptance**:
    - `pytest apps/media-service/tests/unit/test_models_segments.py::test_video_segment_duration_30s -v` PASSES
    - `pytest apps/media-service/tests/unit/test_models_segments.py::test_audio_segment_duration_30s -v` PASSES

- [X] T014 Update SegmentBuffer duration constant in `segment_buffer.py`
  - **File**: `apps/media-service/src/media_service/buffer/segment_buffer.py`
  - **Complexity**: S
  - **Changes**:
    - Line 68: `DEFAULT_SEGMENT_DURATION_NS = 6_000_000_000` -> `30_000_000_000`
    - Update docstring line 5: "default 6 seconds" -> "default 30 seconds"
    - Update docstring line 8: "6-second segments" -> "30-second segments"
    - Update docstring line 54: "6-second segments" -> "30-second segments"
    - Update docstring line 83: "6 seconds" -> "30 seconds"
  - **Acceptance**:
    - `pytest apps/media-service/tests/unit/test_segment_buffer.py::test_segment_buffer_accumulates_30s -v` PASSES
    - Segment accumulation respects 30s threshold

#### A/V Synchronization (Buffer and Wait Refactor)

- [X] T015 Simplify AvSyncState in `state.py` (Remove av_offset, drift correction)
  - **File**: `apps/media-service/src/media_service/models/state.py`
  - **Complexity**: M
  - **Changes**:
    - **REMOVE**: `av_offset_ns` field (line 192)
    - **REMOVE**: `slew_rate_ns` field (line 197)
    - **REMOVE**: `av_offset_ms` property (lines 205-207)
    - **REMOVE**: `adjust_video_pts()` method (lines 209-218)
    - **REMOVE**: `adjust_audio_pts()` method (lines 220-229)
    - **REMOVE**: `needs_correction()` method (lines 244-250)
    - **REMOVE**: `apply_slew_correction()` method (lines 252-281)
    - Update docstring: "buffer-and-wait approach" instead of "offset-based"
    - Update `drift_threshold_ns` to 100_000_000 (100ms for logging only)
  - **Acceptance**:
    - `pytest apps/media-service/tests/unit/test_models_state.py -v` PASSES
    - AvSyncState has no av_offset_ns attribute
    - AvSyncState has no needs_correction() method
    - AvSyncState has no apply_slew_correction() method

- [X] T016 Update AvSyncManager in `av_sync.py` (Buffer and Wait, PTS=0)
  - **File**: `apps/media-service/src/media_service/sync/av_sync.py`
  - **Complexity**: M
  - **Changes**:
    - **REMOVE**: `av_offset_ns` parameter from __init__ (line 65)
    - **REMOVE**: `drift_threshold_ns` parameter from __init__ (line 66) - use state default
    - **REMOVE**: original PTS preservation logic (PTS now reset to 0)
    - Update `_create_pair()` to set `pts_ns=0` (re-encoded output)
    - Add `requires_reencode=True` flag to SyncPair
    - **REMOVE**: drift correction logic in `_create_pair()` (lines 186-192)
    - Add warning log if original PTS sync_delta_ns > drift_threshold_ns (informational only)
    - Update docstring: remove "6-second default offset" references, add "PTS=0" note
  - **Acceptance**:
    - `pytest apps/media-service/tests/unit/test_av_sync.py -v` PASSES
    - AvSyncManager() creates without av_offset_ns parameter
    - SyncPair.pts_ns is always 0 (PTS reset)
    - SyncPair.requires_reencode is True

#### STS Communication Models

- [ ] T017 Update StreamConfig chunk duration in `sts/models.py`
  - **File**: `apps/media-service/src/media_service/sts/models.py`
  - **Complexity**: S
  - **Changes**:
    - Line 43: `chunk_duration_ms: int = 6000` -> `30000`
    - Update any associated docstring references
  - **Acceptance**:
    - `pytest apps/media-service/tests/unit/test_sts_models.py::test_stream_config_chunk_duration_30000 -v` PASSES
    - StreamConfig().chunk_duration_ms == 30000

#### Output Pipeline Configuration

- [ ] T017.5 Configure output pipeline for PTS=0 and re-encoding
  - **File**: `apps/media-service/src/media_service/pipelines/output_pipeline.py`
  - **Complexity**: M
  - **Changes**:
    - Configure output muxer to start PTS from 0 for each segment
    - Ensure video re-encoding (not passthrough) - required for PTS reset
    - Dubbed audio is already re-encoded by TTS
    - Update GStreamer pipeline elements for re-encoding if needed
  - **Acceptance**:
    - Output segments start with PTS=0 (verified via ffprobe)
    - Video is re-encoded (not passthrough)
    - A/V sync maintained in output

#### Worker Configuration

- [X] T018 Update WorkerConfig segment duration in `worker_runner.py`
  - **File**: `apps/media-service/src/media_service/worker/worker_runner.py`
  - **Complexity**: S
  - **Changes**:
    - Line 66: `segment_duration_ns: int = 6_000_000_000` -> `30_000_000_000`
    - Update docstring line 6: "6s segments" -> "30s segments"
    - Update docstring line 75: "6-second segments" -> "30-second segments"
  - **Acceptance**:
    - `pytest apps/media-service/tests/unit/test_worker_runner.py -v` shows worker config tests PASS
    - WorkerConfig.segment_duration_ns == 30_000_000_000

#### Media Service Verification

- [X] T019 Run media-service unit tests
  - **Complexity**: S
  - **Acceptance**: `make media-test-unit` produces PASS for all media-service tests
  - **Must Pass**: test_models_segments, test_segment_buffer, test_models_state, test_av_sync, test_sts_models, test_worker_runner

- [X] T020 [P] Review and update any other files referencing av_offset_ns
  - **Files**: Search across `apps/media-service/src/`
  - **Complexity**: S
  - **Changes**: Grep for `av_offset_ns` and update any remaining references
  - **Commands**: `grep -r "av_offset_ns" apps/media-service/src/`
  - **Acceptance**: No remaining references to av_offset_ns in media-service source

- [X] T021 [P] Review and update any files referencing drift correction
  - **Files**: Search across `apps/media-service/src/`
  - **Complexity**: S
  - **Changes**: Grep for `needs_correction`, `apply_slew_correction`, `slew_rate` and update
  - **Commands**: `grep -r "needs_correction\|apply_slew_correction\|slew_rate" apps/media-service/src/`
  - **Acceptance**: No remaining references to drift correction in media-service source

---

### PHASE 3: STS SERVICE CHANGES

**Priority**: P1 - Required for timeout and validation
**Dependency**: Phase 1 tests must exist and fail, Phase 2 may proceed in parallel
**Success**: `make sts-test-unit` passes all updated assertions

#### Session Defaults

- [X] T022 Update StreamSession defaults in `full/session.py`
  - **File**: `apps/sts-service/src/sts_service/full/session.py`
  - **Complexity**: S
  - **Changes**:
    - Line 95: `chunk_duration_ms: int = 6000` -> `30000`
    - Line 100: `timeout_ms: int = 8000` -> `60000`
    - Update any associated docstring references
  - **Acceptance**:
    - `pytest apps/sts-service/tests/unit/test_session.py::test_stream_session_timeout_ms_default_60000 -v` PASSES
    - `pytest apps/sts-service/tests/unit/test_session.py::test_stream_session_chunk_duration_30000 -v` PASSES
    - StreamSession defaults are 30000ms (chunk) and 60000ms (timeout)

#### Validation Constraints

- [X] T023 Update StreamConfigPayload validation in `echo/models/stream.py`
  - **File**: `apps/sts-service/src/sts_service/echo/models/stream.py`
  - **Complexity**: S
  - **Changes**:
    - Line 31: `le=6000` -> `le=30000` (chunk_duration_ms constraint)
    - Update comment: "6000ms (6 second segments)" -> "30000ms (30 second segments)"
  - **Acceptance**:
    - `pytest apps/sts-service/tests/unit/test_stream_models.py::test_stream_config_payload_accepts_30000ms -v` PASSES
    - StreamConfigPayload(chunk_duration_ms=30000) validates without error

- [X] T024 Update StreamInitPayload timeout validation in `echo/models/stream.py`
  - **File**: `apps/sts-service/src/sts_service/echo/models/stream.py`
  - **Complexity**: S
  - **Changes**:
    - Line 73-74: `le=30000` -> `le=120000` (timeout_ms constraint)
    - Update comment: "Allow extended timeouts up to 120s for slow models"
  - **Acceptance**:
    - `pytest apps/sts-service/tests/unit/test_stream_models.py::test_stream_init_payload_timeout_120000_valid -v` PASSES
    - StreamInitPayload(timeout_ms=120000) validates without error

#### ASR Postprocessing

- [X] T025 Update ASR max duration in `asr/postprocessing.py`
  - **File**: `apps/sts-service/src/sts_service/asr/postprocessing.py`
  - **Complexity**: S
  - **Changes**:
    - Line 95 (approx): `max_duration_seconds: float = 6.0` -> `30.0`
    - Check UtteranceShapingConfig for any related defaults that need updating (FR-016)
  - **Acceptance**:
    - ASR postprocessing accepts 30-second audio segments
    - `split_long_segments(audio, max_duration_seconds=30.0)` functions correctly

#### STS Service Verification

- [ ] T026 Run STS service unit tests
  - **Complexity**: S
  - **Acceptance**: `make sts-test-unit` produces PASS for all sts-service tests
  - **Must Pass**: test_session, test_stream_models

- [ ] T027 [P] Review integration tests for STS service
  - **File**: `apps/sts-service/tests/integration/` (review, don't modify yet)
  - **Complexity**: S
  - **Changes**: Identify any hardcoded duration expectations
  - **Acceptance**: List of integration tests needing updates documented

- [ ] T028 [P] Update STS integration tests if needed
  - **File**: `apps/sts-service/tests/integration/`
  - **Complexity**: M
  - **Changes**: Update any hardcoded 6s expectations to 30s
  - **Acceptance**: `make sts-test-integration` PASSES (if applicable)

---

### PHASE 4: E2E TEST CONFIGURATION

**Priority**: P2 - Required for test validation
**Dependency**: Phases 2-3 must be substantially complete
**Success**: E2E test configuration reflects 30s fragment duration

#### Configuration Updates

- [ ] T029 Verify E2E config updates from T012 are complete
  - **File**: `tests/e2e/config.py`
  - **Complexity**: S
  - **Changes**: Verify all updates from T012 are in place:
    - SEGMENT_DURATION_SEC = 30
    - SEGMENT_DURATION_NS = 30_000_000_000
    - EXPECTED_SEGMENTS = 2
    - FRAGMENT_TIMEOUT = 60
    - PIPELINE_COMPLETION = 120
  - **Acceptance**: `from tests.e2e.config import TestConfig, TimeoutConfig; assert TestConfig.SEGMENT_DURATION_SEC == 30; assert TimeoutConfig.FRAGMENT_TIMEOUT == 60`

#### E2E Test Assertions

- [ ] T030 [P] Review E2E test expectations in `test_full_pipeline.py`
  - **File**: `tests/e2e/test_full_pipeline.py`
  - **Complexity**: M
  - **Changes**: Identify and flag all hardcoded expectations for:
    - Segment counts (should expect 2 for 60s fixture, not 10)
    - Timeout values
    - Duration validations
    - Timing assertions
    - A/V sync expectations (now < 100ms from pairing, not offset-based)
  - **Acceptance**: Documentation of all required assertion updates

- [ ] T031 [P] Update E2E test assertions for segment counts
  - **File**: `tests/e2e/test_full_pipeline.py`
  - **Complexity**: M
  - **Changes**: Update all segment count assertions:
    - If test uses 60s fixture, expect 2 segments (not 10)
    - Update any duration validation checks
    - Update fragment processing timeout expectations
    - Update A/V sync assertions (expect < 100ms from pairing)
  - **Acceptance**: E2E full pipeline test expects correct segment counts

#### Test Fixture Review

- [ ] T032 [P] Verify test fixtures are appropriate for 30s segments
  - **File**: `tests/e2e/fixtures/test_streams/`
  - **Complexity**: S
  - **Changes**: Confirm:
    - 1-min-nfl.mp4 is 60 seconds (produces 2 segments with 30s duration)
    - Other fixtures have appropriate durations
  - **Acceptance**: Test fixture durations documented and appropriate

- [ ] T033 [P] Review and mark integration tests that will fail
  - **File**: `apps/media-service/tests/integration/` (review, don't modify yet)
  - **Complexity**: S
  - **Changes**: Identify any hardcoded duration expectations (e.g., segment count, timeout)
  - **Acceptance**: List of integration tests needing updates documented

---

### PHASE 5: INTEGRATION & VALIDATION TESTING

**Priority**: P2 - Validation
**Dependency**: Phases 2-4 complete
**Success**: All tests pass with new configuration

#### Integration Tests

- [ ] T034 Run media-service integration tests
  - **Complexity**: M
  - **Acceptance**: `make media-test-integration` produces PASS
  - **Note**: Integration tests require Docker; may need assertion updates if they validate segment counts

- [ ] T035 Update integration test assertions if needed
  - **File**: `apps/media-service/tests/integration/`
  - **Complexity**: M
  - **Changes**: If integration tests failed in T034, update assertions for:
    - Segment count expectations
    - Duration validations
    - MediaMTX stream duration handling
  - **Acceptance**: `make media-test-integration` produces PASS

#### E2E Testing

- [ ] T036 Run E2E P1 tests (critical path)
  - **Complexity**: M
  - **Commands**: `make e2e-test-p1`
  - **Acceptance**:
    - All P1 E2E tests PASS
    - 60-second fixture produces exactly 2 segments (SC-001)
    - A/V sync remains < 100ms (SC-003, from buffer-and-wait pairing)

- [ ] T037 Run full E2E test suite
  - **Complexity**: M
  - **Commands**: `make e2e-test-full`
  - **Acceptance**:
    - All E2E tests PASS with new configuration
    - Services start and stop cleanly
    - Test fixtures process completely

- [ ] T038 Validate A/V sync with 30s fragments (Buffer and Wait, PTS=0)
  - **File**: `tests/e2e/test_full_pipeline.py` (verify test)
  - **Complexity**: M
  - **Acceptance**:
    - A/V sync delta consistently < 100ms with 30s segments (SC-003)
    - Output video and audio remain synchronized (from pairing)
    - Output PTS starts from 0 for both tracks (SC-010, verified via ffprobe)
    - No visual sync issues in test output
    - No av_offset_ns references in output logs

#### Coverage Validation

- [ ] T039 Run coverage reports for all services
  - **Complexity**: M
  - **Commands**:
    - `make media-test-coverage`
    - `make sts-test-coverage`
  - **Acceptance**:
    - Media service coverage >= 80%
    - STS service coverage >= 80%
    - Critical path coverage >= 95% (segment buffer, av_sync, session management)

- [ ] T040 Verify removed code is not covered (dead code check)
  - **Complexity**: S
  - **Changes**: Ensure av_offset_ns, needs_correction(), apply_slew_correction(), original PTS preservation are completely removed
  - **Commands**: `grep -r "av_offset_ns\|needs_correction\|apply_slew_correction" apps/`
  - **Acceptance**: No references to removed code in source files

- [ ] T040.5 Verify output PTS=0 via ffprobe
  - **Complexity**: S
  - **Commands**: `ffprobe -show_entries stream=start_time,start_pts -of json output_segment.mp4`
  - **Acceptance**:
    - Video stream start_pts is 0 or close to 0
    - Audio stream start_pts is 0 or close to 0

---

### PHASE 6: DOCUMENTATION & POLISH

**Priority**: P3 - Quality
**Dependency**: Phases 2-5 complete, all tests passing
**Success**: Documentation reflects 30s configuration and buffer-and-wait approach

#### Documentation Updates

- [ ] T041 Update README files with 30s segment information
  - **Files**:
    - `apps/media-service/README.md`
    - `apps/sts-service/README.md`
    - Root `README.md`
  - **Complexity**: S
  - **Changes**:
    - Update any references to "6-second segments" -> "30-second segments"
    - Update latency expectations: "6-8s initial delay" -> "35-55s initial delay"
    - Update memory impact notes (~162MB peak with buffer-and-wait)
    - Update timeout configuration references
    - Add note about buffer-and-wait A/V sync approach
  - **Acceptance**: Documentation accurately reflects 30s segment duration and buffer-and-wait

- [ ] T042 Update API/contract documentation
  - **Files**:
    - `libs/contracts/README.md` (if exists)
    - Inline docstrings for Socket.IO contracts
  - **Complexity**: S
  - **Changes**: Ensure all Socket.IO event documentation reflects:
    - chunk_duration_ms = 30000
    - timeout_ms = 60000
    - No av_offset references
  - **Acceptance**: Contract documentation is current

#### Code Quality

- [ ] T043 Run linting and formatting
  - **Complexity**: S
  - **Commands**:
    - `make fmt`
    - `make lint`
    - `make typecheck`
  - **Acceptance**:
    - All code passes ruff formatting
    - All code passes ruff linting
    - All code passes mypy type checking
    - No issues reported

#### Manual Testing

- [ ] T044 [P] Manual testing of segment duration and buffer-and-wait
  - **Complexity**: M
  - **Process**:
    - Start media-service: `make media-dev`
    - Publish test stream: `ffmpeg -re -i tests/e2e/fixtures/test_streams/1-min-nfl.mp4 -c copy -f rtsp rtsp://localhost:8554/stream`
    - Monitor segment production in logs
    - Verify segments are ~30s duration
    - Verify no av_offset_ns references in logs
    - Verify buffer-and-wait pairing messages in logs
  - **Acceptance**: Visual confirmation that segments are produced at 30s intervals with buffer-and-wait

- [ ] T045 Final verification of all requirements
  - **Complexity**: M
  - **Checklist**:
    - [ ] FR-001: VideoSegment.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000
    - [ ] FR-002: AudioSegment.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000
    - [ ] FR-003: SegmentBuffer.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000
    - [ ] FR-004: TOLERANCE_NS unchanged (100_000_000)
    - [ ] FR-005: MIN_SEGMENT_DURATION_NS unchanged (1_000_000_000)
    - [ ] FR-006: StreamConfig.chunk_duration_ms == 30000
    - [ ] FR-007: StreamSession.chunk_duration_ms == 30000
    - [ ] FR-008: StreamSession.timeout_ms == 60000
    - [ ] FR-009: TimeoutConfig.FRAGMENT_TIMEOUT == 60
    - [ ] FR-010: Video segments buffered until audio ready
    - [ ] FR-011: Output only when BOTH video and audio ready
    - [ ] FR-012: Output re-encoded with PTS=0 (not original PTS)
    - [ ] FR-013: Drift correction code removed
    - [ ] FR-014: StreamConfigPayload accepts chunk_duration_ms=30000
    - [ ] FR-015: StreamInitPayload accepts timeout_ms up to 120000
    - [ ] FR-016: ASR postprocessing accepts 30s audio
    - [ ] FR-017-022: All E2E configs and test values updated
    - [ ] SC-001: 60s fixture produces 2 segments
    - [ ] SC-002: Segment duration 30s +/- 100ms
    - [ ] SC-003: A/V sync < 100ms (from pairing)
    - [ ] SC-004: STS completes within 60s
    - [ ] SC-005-009: All tests pass
    - [ ] SC-010: Output PTS starts from 0 (ffprobe verified)
  - **Acceptance**: All FRs and SCs verified complete

---

### PHASE 7: GIT & PR

**Priority**: P3 - Integration
**Dependency**: All tests passing, documentation complete
**Success**: Code committed and PR created

#### Commit & Push

- [ ] T046 Stage all changes
  - **Complexity**: S
  - **Commands**: `git add -A`
  - **Acceptance**: `git status` shows all modified files staged

- [ ] T047 Create commit with feature branch
  - **Complexity**: S
  - **Commands**: `git commit -m "feat(021): increase fragment length from 6s to 30s (buffer-and-wait, PTS=0)"`
  - **Message Format**:
    ```
    feat(021): increase fragment length from 6s to 30s (buffer-and-wait, PTS=0)

    BREAKING CHANGE: A/V sync approach changed to buffer-and-wait with re-encoded output

    - Update segment duration constants from 6s to 30s across media-service
    - REMOVE av_offset_ns, needs_correction(), apply_slew_correction() (buffer-and-wait)
    - Output PTS reset to 0 for each segment (not original stream PTS)
    - Video re-encoded (not passthrough) to allow PTS reset
    - Update STS session timeout from 8s to 60s
    - Update validation constraints (chunk: le=30000, timeout: le=120000)
    - Update E2E test expectations (2 segments for 60s fixture)
    - All tests passing with new configuration
    - Peak memory now ~162MB (vs ~45MB) due to buffer-and-wait
    - Spec: specs/021-fragment-length-30s/spec.md
    ```
  - **Acceptance**: Commit created on feature branch

- [ ] T048 Push feature branch to remote
  - **Complexity**: S
  - **Commands**: `git push origin 021-fragment-length-30s`
  - **Acceptance**: Branch visible on remote, CI pipeline triggered

#### Pull Request

- [ ] T049 [P] Create pull request with full context
  - **Complexity**: S
  - **PR Title**: `feat: increase fragment length from 6s to 30s with buffer-and-wait A/V sync, PTS=0 (spec 021)`
  - **PR Body**:
    ```
    ## Summary
    - Increases audio/video fragment duration from 6 seconds to 30 seconds
    - **BREAKING**: Changes A/V sync from av_offset_ns to buffer-and-wait approach
    - **BREAKING**: Output PTS reset to 0 (re-encoded, not passthrough)
    - Video segments buffered until corresponding dubbed audio arrives
    - Extends STS processing timeout from 8s to 60s
    - Updates all validation constraints and E2E test expectations

    ## Architectural Change: Buffer and Wait with PTS Reset
    - **Removed**: av_offset_ns, needs_correction(), apply_slew_correction()
    - **Removed**: Original PTS preservation (PTS now resets to 0)
    - **Added**: Buffer-and-wait pairing (video waits for dubbed audio)
    - **Added**: Video re-encoding (required for PTS reset)
    - **Benefit**: Simpler code, naturally synchronized output, clean PTS
    - **Tradeoff**: Higher peak memory (~162MB vs ~45MB), CPU for re-encoding

    ## Testing
    - [ ] Unit tests pass: `make media-test-unit && make sts-test-unit`
    - [ ] Integration tests pass: `make media-test-integration`
    - [ ] E2E P1 tests pass: `make e2e-test-p1`
    - [ ] Output PTS=0 verified via ffprobe
    - [ ] Coverage >= 80%: `make media-test-coverage`
    - [ ] Code quality: `make fmt && make lint`

    ## Files Changed
    - Media Service (7 files): segments.py, segment_buffer.py, state.py (major), av_sync.py (major), output_pipeline.py (major), sts/models.py, worker/worker_runner.py
    - STS Service (3 files): session.py, echo/models/stream.py, asr/postprocessing.py
    - E2E Tests (1 file): config.py

    ## Config Changes
    | Setting | Old | New |
    |---------|-----|-----|
    | Segment Duration | 6s | 30s |
    | A/V Sync Approach | av_offset_ns (6s) | Buffer and Wait |
    | Output PTS | Original stream PTS | 0 (reset) |
    | Output Mode | Passthrough | Re-encoded |
    | STS Timeout | 8s | 60s |
    | Expected Segments (60s) | 10 | 2 |
    | Peak Memory | ~45MB | ~162MB |

    Spec: specs/021-fragment-length-30s/spec.md
    ```
  - **Acceptance**: PR created, all checks initiated

- [ ] T050 [P] Document review points for code reviewers
  - **Complexity**: S
  - **Changes**: Create review checklist comment on PR:
    - Verify all duration constants updated consistently
    - Confirm av_offset_ns completely removed (grep check)
    - Confirm drift correction code completely removed
    - Verify buffer-and-wait logic in AvSyncManager
    - Check that SyncPair.pts_ns is always 0 (PTS reset)
    - Verify output pipeline configured for re-encoding (not passthrough)
    - Verify output muxer starts PTS from 0
    - Validate timeout configuration (60s with 120s max)
    - Confirm no hardcoded references to "6 seconds" remain
    - Verify ffprobe shows PTS=0 in output segments
  - **Acceptance**: Review guidance provided to reviewers

---

## Parallel Task Groups

Tasks marked with `[P]` can be executed in parallel after their dependencies are satisfied:

### Group A: Initial Setup (can start immediately)
- T001, T002 (15 min)

### Group B: Test Infrastructure (Phase 1, after T002)
- T003-T012: Can run in parallel after feature branch created
- **Critical**: T011 must verify tests FAIL before moving to Phase 2

### Group C: Implementation (Phase 2-3, after T011 passes)
- Media service tasks (T013-T021): Can run in parallel
- STS service tasks (T022-T028): Can run in parallel with media service
- Both groups must complete before Phase 4

### Group D: E2E Configuration (Phase 4, after Phase 2-3)
- T029-T033: Can run in parallel once config structure is clear
- **Gate**: All unit tests must PASS before starting

### Group E: Validation (Phase 5, after Phases 2-4)
- T034-T040: Validation tests should run sequentially (integration, then E2E P1, then E2E full)

### Group F: Documentation (Phase 6, can start after Phase 2 complete)
- T041-T045: Documentation and verification can overlap with Phase 5 validation

### Group G: Integration (Phase 7, after all tests pass)
- T046-T050: Commit, push, and PR steps run sequentially

---

## Success Criteria Summary

| Category | Criteria | Verification |
|----------|----------|--------------|
| **Functionality (SC-001)** | 60s fixture -> 2 segments | `make e2e-test-p1` passes |
| **Accuracy (SC-002)** | Segment duration 30s +/-100ms | Integration test validates |
| **Sync (SC-003)** | A/V sync < 100ms (from pairing) | E2E test validates |
| **Timeout (SC-004)** | STS completes within 60s | E2E test validates |
| **Unit Tests (SC-005)** | All pass | `make media-test-unit && make sts-test-unit` |
| **Integration (SC-006)** | All pass | `make media-test-integration` |
| **E2E (SC-007)** | All P1 pass | `make e2e-test-p1` |
| **Validation (SC-008)** | chunk_duration_ms=30000 accepted | Unit tests verify |
| **Memory (SC-009)** | ~162MB peak within limits | Manual inspection |
| **PTS Reset (SC-010)** | Output PTS starts from 0 | ffprobe verification |

---

## Task Dependencies Map

```
T001-T002 (Setup)
    |
T003-T012 (Write Tests)
    |
T011 (Verify tests FAIL)
    +-- |
    +-- T013-T021 (Media Service + Buffer-and-Wait)
    +-- T022-T028 (STS Service)
    +-- T029-T033 (E2E Config)
        |
T034-T040 (Integration & E2E Validation)
    |
T041-T045 (Documentation & Verification)
    |
T046-T050 (Git & PR)
```

---

## Time Estimation

| Phase | Tasks | Est. Duration | Notes |
|-------|-------|---------------|-------|
| Setup | T001-T002 | 15 min | Quick prerequisite validation |
| Phase 1 (TDD) | T003-T012 | 1-2 hrs | Write tests before implementation |
| Phase 2 | T013-T021 | 2-3 hrs | Media service + buffer-and-wait refactor |
| Phase 3 | T022-T028 | 1-2 hrs | STS service timeout and validation |
| Phase 4 | T029-T033 | 1 hr | E2E test configuration updates |
| Phase 5 | T034-T040 | 2-3 hrs | Integration and E2E validation |
| Phase 6 | T041-T045 | 1 hr | Documentation and final checks |
| Phase 7 | T046-T050 | 30 min | Git commit and PR |
| **Total** | **50 tasks** | **9-14 hrs** | Depending on parallelization |

With effective parallelization (Groups A-G), total elapsed time: **4-6 hours**

---

## Rollback Checklist

If issues arise during or after implementation:

- [ ] Stop all active streams
- [ ] Revert commits: `git reset --hard HEAD~1` (or specific commit)
- [ ] Rebuild docker images: `docker compose -f apps/media-service/docker-compose.yml build --no-cache`
- [ ] Run tests to verify rollback: `make media-test-unit && make sts-test-unit`
- [ ] Notify deployment team if merged to main

---

## Notes

- **ARCHITECTURAL CHANGE**: Buffer-and-wait replaces av_offset_ns approach
- **PTS RESET**: Output PTS starts from 0 (re-encoded, not original stream PTS)
- **RE-ENCODING**: Video must be re-encoded (not passthrough) to allow PTS reset
- **Constitution Compliance**: This implementation strictly follows Principle VIII (Test-First Development). All tests are written in Phase 1, verified to fail, then implementation proceeds in Phases 2-4.
- **TDD Gateway**: T011 (verify tests fail) is a hard gate. Do not proceed to implementation (Phases 2-4) until tests exist and fail with current 6s values.
- **Parallelization**: Use task groups to run independent work in parallel, but respect phase dependencies.
- **Testing Commands**: Before committing, always run:
  ```bash
  make fmt && make lint && make media-test-unit && make sts-test-unit && make media-test-integration && make e2e-test-p1
  ```
- **PTS Verification**: After E2E tests, verify output PTS with:
  ```bash
  ffprobe -show_entries stream=start_time,start_pts -of json output_segment.mp4
  ```
- **Documentation**: Update docstrings alongside code changes; don't defer documentation to Phase 6.
- **Dead Code Check**: Verify av_offset_ns, needs_correction(), apply_slew_correction(), and original PTS preservation completely removed.
