# Tasks: RTMP Stream Pull Migration

**Feature**: 020-rtmp-stream-pull | **Branch**: `020-rtmp-stream-pull`
**Generated**: 2026-01-01 | **Status**: In Progress (T001-T011 Complete)

## Task Metadata

- **Total Tasks**: 24
- **Phases**: Setup (3) → Foundational (8) → User Stories (10) → Polish (3)
- **Parallelizable Tasks**: 12 (tasks with no dependencies can run in parallel)
- **Estimated Duration**: 2-3 days (with TDD workflow)

## Dependency Graph

```
Setup Phase:
T001 (no deps) → T002 (no deps) → T003 (depends on T002)

Foundational Phase:
T004 (depends on T003) → T005 (depends on T004) → T006 (depends on T005)
T007 (depends on T003) ─┐
T008 (depends on T003) ─┼→ T009 (depends on T007, T008)
T010 (depends on T003) ─┘
T011 (depends on T006, T009, T010)

User Stories Phase:
T012 (depends on T011) → T013 (depends on T012) → T014 (depends on T013)
T015 (depends on T011) → T016 (depends on T015) → T017 (depends on T016)
T018 (depends on T011) → T019 (depends on T018)
T020 (depends on T014, T017, T019)
T021 (depends on T020)

Polish Phase:
T022 (depends on T021)
T023 (depends on T021)
T024 (depends on T022, T023)
```

---

## Phase 0: Setup (3 tasks)

### T001: Create feature branch and verify environment
- **Priority**: P1
- **Type**: Setup
- **Dependencies**: None
- **Estimated Time**: 15 minutes

**Description**: Create feature branch `020-rtmp-stream-pull` and verify GStreamer RTMP elements availability.

**Steps**:
1. Create and checkout feature branch: `git checkout -b 020-rtmp-stream-pull`
2. Verify GStreamer installation: `gst-inspect-1.0 rtmpsrc`
3. Verify flvdemux availability: `gst-inspect-1.0 flvdemux`
4. Verify MediaMTX RTMP support: Check `deploy/mediamtx/mediamtx.yml` for RTMP configuration
5. Document environment prerequisites in branch notes

**Acceptance Criteria**:
- [X] Feature branch created and checked out
- [X] `rtmpsrc` element available in GStreamer (via Docker)
- [X] `flvdemux` element available in GStreamer (via Docker)
- [X] MediaMTX configuration includes RTMP settings

**Test**: Manual verification only (no automated tests required)
**Status**: COMPLETE

---

### T002: Update MediaMTX configuration for RTMP
- **Priority**: P1
- **Type**: Configuration
- **Dependencies**: None
- **Estimated Time**: 15 minutes

**Description**: Configure MediaMTX to enable RTMP on port 1935 and ensure paths accept RTMP streams.

**Steps**:
1. Open `apps/media-service/deploy/mediamtx/mediamtx.yml`
2. Ensure RTMP is enabled:
   ```yaml
   rtmpAddress: :1935
   rtmpEncryption: "no"
   ```
3. Update paths configuration to accept RTMP:
   ```yaml
   paths:
     live:
       source: publisher
       # Remove RTSP-specific constraints
   ```
4. Update `apps/media-service/docker-compose.yml` to expose port 1935:
   ```yaml
   ports:
     - "1935:1935"  # RTMP
   ```
5. Update `docker-compose.e2e.yml` similarly

**Acceptance Criteria**:
- [X] RTMP enabled on port 1935 in mediamtx.yml
- [X] Docker Compose files expose port 1935
- [X] No RTSP-specific path constraints remain

**Test**: Manual verification - `docker-compose up` and check MediaMTX logs for RTMP listener
**Status**: COMPLETE

---

### T003: Update test fixtures for RTMP publishing
- **Priority**: P1
- **Type**: Test Infrastructure
- **Dependencies**: T002
- **Estimated Time**: 30 minutes

**Description**: Update integration/E2E test fixtures to publish streams via RTMP instead of RTSP.

**Steps**:
1. Open `apps/media-service/tests/integration/conftest.py`
2. Update `publish_test_stream()` fixture to use RTMP:
   ```python
   ffmpeg -re -i tests/fixtures/test-30s.mp4 \
       -c:v copy -c:a copy \
       -f flv rtmp://mediamtx:1935/live/test/in
   ```
3. Create `publish_video_only_stream()` fixture for audio validation tests:
   ```python
   ffmpeg -re -i tests/fixtures/test-30s.mp4 \
       -c:v copy -an \
       -f flv rtmp://mediamtx:1935/live/video-only/in
   ```
4. Update E2E fixtures in `tests/e2e/conftest.py` similarly
5. Document fixture changes in conftest.py docstrings

**Acceptance Criteria**:
- [ ] Integration test fixtures use RTMP URLs
- [ ] Video-only stream fixture created
- [ ] E2E test fixtures updated
- [ ] All fixtures use port 1935 and FLV format

**Test**: Run fixtures manually to verify stream publishing works

---

## Phase 1: Foundational - RTMP URL Validation (5 tasks)

### T004: Write failing unit tests for RTMP URL validation
- **Priority**: P1
- **Type**: Test (TDD)
- **Dependencies**: T003
- **Estimated Time**: 30 minutes

**Description**: Write comprehensive unit tests for RTMP URL validation in InputPipeline (MUST fail initially per TDD).

**Steps**:
1. Open `apps/media-service/tests/unit/test_input_pipeline.py`
2. Add test class `TestRTMPURLValidation`
3. Implement tests per contracts/test-expectations.md:
   - `test_rtmp_url_validation_happy_path()` - Valid RTMP URLs
   - `test_rtmp_url_validation_error_empty()` - Empty URL rejection
   - `test_rtmp_url_validation_error_none()` - None URL rejection
   - `test_rtmp_url_validation_error_wrong_protocol()` - Non-RTMP protocol rejection
4. Add assertions for error messages (must be descriptive)
5. Run tests and VERIFY they fail (no implementation yet)

**Acceptance Criteria**:
- [ ] At least 4 URL validation tests written
- [ ] Tests cover happy path and 3+ error conditions
- [ ] Tests initially FAIL (implementation not done)
- [ ] Error message assertions included

**Test Output Expected**:
```
FAILED test_input_pipeline.py::TestRTMPURLValidation::test_rtmp_url_validation_happy_path
FAILED test_input_pipeline.py::TestRTMPURLValidation::test_rtmp_url_validation_error_empty
```

---

### T005: Implement RTMP URL validation in InputPipeline.__init__
- **Priority**: P1
- **Type**: Implementation
- **Dependencies**: T004
- **Estimated Time**: 20 minutes

**Description**: Add RTMP URL validation logic to InputPipeline constructor to make T004 tests pass.

**Steps**:
1. Open `apps/media-service/src/media_service/pipeline/input.py`
2. Update `__init__` signature: Replace `rtsp_url` with `rtmp_url`
3. Add validation logic:
   ```python
   if not rtmp_url:
       raise ValueError("RTMP URL cannot be empty")
   if not rtmp_url.startswith("rtmp://"):
       raise ValueError("RTMP URL must start with 'rtmp://'")
   ```
4. Store `self.rtmp_url = rtmp_url`
5. Run tests from T004 and VERIFY they now PASS

**Acceptance Criteria**:
- [ ] `__init__` parameter changed from `rtsp_url` to `rtmp_url`
- [ ] URL validation raises ValueError with descriptive messages
- [ ] All T004 tests now PASS
- [ ] No RTSP-specific code remains in `__init__`

**Test**: `make media-test-unit -k TestRTMPURLValidation` → All tests PASS

---

### T006: Write failing unit tests for RTMP element creation
- **Priority**: P1
- **Type**: Test (TDD)
- **Dependencies**: T005
- **Estimated Time**: 45 minutes

**Description**: Write unit tests for GStreamer RTMP element creation (rtmpsrc, flvdemux, parsers, appsinks).

**Steps**:
1. Add test class `TestRTMPElementCreation` to `test_input_pipeline.py`
2. Implement tests with GStreamer mocking:
   - `test_build_rtmp_elements_happy_path()` - Verify 8 elements created (rtmpsrc, flvdemux, h264parse, aacparse, 2 queues, 2 appsinks)
   - `test_build_rtmp_elements_no_rtspsrc()` - Verify rtspsrc NOT created
   - `test_build_rtmp_elements_no_depayloaders()` - Verify rtph264depay/rtpmp4gdepay NOT created
   - `test_rtmpsrc_location_property()` - Verify rtmpsrc.location set to RTMP URL
   - `test_flvdemux_max_buffers_property()` - Verify flvdemux.max-buffers configured
3. Mock `Gst.ElementFactory.make` to return MagicMock elements
4. Run tests and VERIFY they fail (build() not updated yet)

**Acceptance Criteria**:
- [ ] At least 5 element creation tests written
- [ ] Tests verify RTMP elements created, RTSP elements NOT created
- [ ] Tests verify element property configuration
- [ ] Tests initially FAIL

**Test Output Expected**:
```
FAILED test_input_pipeline.py::TestRTMPElementCreation::test_build_rtmp_elements_happy_path
```

---

### T007: Write failing unit tests for WorkerRunner RTMP URL construction
- **Priority**: P1
- **Type**: Test (TDD)
- **Dependencies**: T003
- **Estimated Time**: 30 minutes

**Description**: Write unit tests for WorkerRunner constructing RTMP URLs from configuration.

**Steps**:
1. Open `apps/media-service/tests/unit/test_worker_runner.py`
2. Add test class `TestRTMPURLConstruction`
3. Implement tests:
   - `test_worker_runner_builds_rtmp_url()` - Verify URL format `rtmp://{host}:{port}/{app}/{stream}/in`
   - `test_worker_runner_uses_port_1935()` - Verify RTMP port used (not 8554)
   - `test_worker_runner_no_rtsp_url()` - Verify RTSP URL NOT constructed
4. Mock InputPipeline and verify constructor call arguments
5. Run tests and VERIFY they fail

**Acceptance Criteria**:
- [ ] At least 3 WorkerRunner URL tests written
- [ ] Tests verify RTMP URL construction from config
- [ ] Tests verify port 1935 used
- [ ] Tests initially FAIL

**Test Output Expected**:
```
FAILED test_worker_runner.py::TestRTMPURLConstruction::test_worker_runner_builds_rtmp_url
```

---

### T008: Write failing unit tests for audio track validation
- **Priority**: P1
- **Type**: Test (TDD)
- **Dependencies**: T003
- **Estimated Time**: 30 minutes

**Description**: Write unit tests for audio track presence validation during pipeline startup.

**Steps**:
1. Add test class `TestAudioTrackValidation` to `test_input_pipeline.py`
2. Implement tests:
   - `test_audio_validation_success()` - Both video and audio pads present
   - `test_audio_validation_error_missing_audio()` - Only video pad present (should raise RuntimeError)
   - `test_audio_validation_timeout()` - Validation exceeds 2 seconds (should raise TimeoutError)
3. Mock flvdemux pad signals and pipeline state transitions
4. Run tests and VERIFY they fail

**Acceptance Criteria**:
- [ ] At least 3 audio validation tests written
- [ ] Tests verify RuntimeError raised when audio missing
- [ ] Tests verify descriptive error messages
- [ ] Tests initially FAIL

**Test Output Expected**:
```
FAILED test_input_pipeline.py::TestAudioTrackValidation::test_audio_validation_error_missing_audio
```

---

## Phase 2: Foundational - Implementation (3 tasks)

### T009: Implement RTMP element creation in InputPipeline.build()
- **Priority**: P1
- **Type**: Implementation
- **Dependencies**: T006, T007, T008
- **Estimated Time**: 60 minutes

**Description**: Replace RTSP pipeline elements with RTMP elements in InputPipeline.build() method.

**Steps**:
1. Open `apps/media-service/src/media_service/pipeline/input.py`
2. Update `__init__` to accept `max_buffers` parameter (default 10)
3. In `build()` method, replace element creation:
   - REMOVE: `rtspsrc`, `rtph264depay`, `rtpmp4gdepay`, `rtpmp4adepay`
   - ADD: `rtmpsrc`, `flvdemux`
4. Update pipeline structure:
   ```python
   rtmpsrc = Gst.ElementFactory.make("rtmpsrc", "rtmpsrc")
   flvdemux = Gst.ElementFactory.make("flvdemux", "flvdemux")
   h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
   aacparse = Gst.ElementFactory.make("aacparse", "aacparse")
   # ... queues and appsinks
   ```
5. Configure element properties:
   ```python
   rtmpsrc.set_property("location", self.rtmp_url)
   flvdemux.set_property("max-buffers", self.max_buffers)
   ```
6. Update element linking (remove RTP-specific pad handling)
7. Run T006 tests and VERIFY they now PASS

**Acceptance Criteria**:
- [ ] RTMP elements created (rtmpsrc, flvdemux)
- [ ] All RTSP/RTP elements removed
- [ ] Element properties configured correctly
- [ ] T006 tests now PASS
- [ ] No RTSP-specific code remains in build()

**Test**: `make media-test-unit -k TestRTMPElementCreation` → All tests PASS

---

### T010: Implement WorkerRunner RTMP URL construction
- **Priority**: P1
- **Type**: Implementation
- **Dependencies**: T007
- **Estimated Time**: 30 minutes

**Description**: Update WorkerRunner to construct RTMP URLs and initialize InputPipeline with RTMP parameters.

**Steps**:
1. Open `apps/media-service/src/media_service/worker/worker_runner.py`
2. Update configuration model (if needed):
   - `mediamtx_rtsp_port` → `mediamtx_rtmp_port` (default 1935)
3. Update URL construction in `initialize()`:
   ```python
   rtmp_url = f"rtmp://{self.config.mediamtx_host}:{self.config.mediamtx_rtmp_port}/{self.config.app_path}/{self.config.stream_id}/in"
   ```
4. Update InputPipeline initialization:
   ```python
   self.input_pipeline = InputPipeline(
       rtmp_url=rtmp_url,
       on_video_buffer=self._on_video_buffer,
       on_audio_buffer=self._on_audio_buffer,
       max_buffers=10
   )
   ```
5. Run T007 tests and VERIFY they now PASS

**Acceptance Criteria**:
- [ ] WorkerRunner constructs RTMP URLs (rtmp://host:1935/app/stream/in)
- [ ] Port 1935 used instead of 8554
- [ ] InputPipeline initialized with rtmp_url parameter
- [ ] T007 tests now PASS

**Test**: `make media-test-unit -k TestRTMPURLConstruction` → All tests PASS

---

### T011: Simplify _on_pad_added callback for FLV demuxing
- **Priority**: P1
- **Type**: Implementation
- **Dependencies**: T009, T010
- **Estimated Time**: 45 minutes

**Description**: Replace dynamic RTP pad detection with simplified FLV demux pad handling (video/x-h264 and audio/mpeg).

**Steps**:
1. Open `apps/media-service/src/media_service/pipeline/input.py`
2. Locate `_on_pad_added(self, element, pad)` callback
3. Replace RTP encoding detection logic with FLV caps detection:
   ```python
   caps = pad.get_current_caps()
   struct = caps.get_structure(0)
   name = struct.get_name()

   if name.startswith("video/x-h264"):
       # Link to h264parse
       sink_pad = self.h264parse.get_static_pad("sink")
       pad.link(sink_pad)
       self.has_video_pad = True
   elif name.startswith("audio/mpeg"):
       # Link to aacparse
       sink_pad = self.aacparse.get_static_pad("sink")
       pad.link(sink_pad)
       self.has_audio_pad = True
   ```
4. Remove RTP-specific codec detection (rtpmap, encoding-name checks)
5. Remove dynamic depayloader creation logic
6. Add logging for pad detection
7. Write unit test for simplified pad handling
8. Run tests and verify PASS

**Acceptance Criteria**:
- [ ] _on_pad_added simplified (no RTP-specific logic)
- [ ] FLV video/audio pads linked correctly
- [ ] No dynamic element creation in pad callback
- [ ] has_video_pad and has_audio_pad flags set
- [ ] Unit tests pass

**Test**: `make media-test-unit -k test_on_pad_added` → All tests PASS

---

## Phase 3: User Stories - Integration Tests (10 tasks)

### T012: Write failing integration test for RTMP stream consumption
- **Priority**: P1
- **Type**: Test (TDD)
- **Dependencies**: T011
- **Estimated Time**: 45 minutes

**Description**: Write integration test validating InputPipeline pulls RTMP stream from MediaMTX.

**Steps**:
1. Open `apps/media-service/tests/integration/test_segment_pipeline.py`
2. Add test `test_input_pipeline_rtmp_integration()`
3. Implement test flow:
   - Start MediaMTX via Docker Compose
   - Publish test stream via RTMP using T003 fixture
   - Create InputPipeline with RTMP URL
   - Collect video and audio buffers for 5 seconds
   - Assert buffers received, PTS valid, both media types present
4. Run test and VERIFY it fails (pipeline not fully integrated yet)

**Acceptance Criteria**:
- [ ] Integration test written with Docker Compose setup
- [ ] Test publishes RTMP stream and consumes via InputPipeline
- [ ] Assertions for buffer counts, PTS validity, media types
- [ ] Test initially FAILS

**Test Output Expected**:
```
FAILED test_segment_pipeline.py::test_input_pipeline_rtmp_integration
```

---

### T013: Implement audio track validation in InputPipeline.start()
- **Priority**: P1
- **Type**: Implementation
- **Dependencies**: T012
- **Estimated Time**: 45 minutes

**Description**: Add audio track validation to InputPipeline.start() to reject video-only streams.

**Steps**:
1. Open `apps/media-service/src/media_service/pipeline/input.py`
2. Add `_validate_audio_track()` method:
   ```python
   def _validate_audio_track(self, timeout_ms=2000):
       start = time.time()
       while (time.time() - start) * 1000 < timeout_ms:
           if self.has_audio_pad and self.has_video_pad:
               return True
           time.sleep(0.1)

       if not self.has_audio_pad:
           raise RuntimeError("Audio track required for dubbing pipeline - stream rejected")
       return True
   ```
3. Call validation in `start()` after PAUSED state:
   ```python
   self.pipeline.set_state(Gst.State.PAUSED)
   self._validate_audio_track()
   self.pipeline.set_state(Gst.State.PLAYING)
   ```
4. Run T008 tests and VERIFY they now PASS
5. Run T012 integration test and verify progress

**Acceptance Criteria**:
- [ ] _validate_audio_track() method implemented
- [ ] RuntimeError raised if audio missing after 2 seconds
- [ ] Descriptive error message included
- [ ] T008 unit tests now PASS
- [ ] T012 integration test progresses

**Test**: `make media-test-unit -k TestAudioTrackValidation` → All tests PASS

---

### T014: Fix integration test failures and verify RTMP pipeline
- **Priority**: P1
- **Type**: Bug Fix / Integration
- **Dependencies**: T013
- **Estimated Time**: 60 minutes

**Description**: Debug and fix integration test failures to achieve full RTMP pipeline functionality.

**Steps**:
1. Run `make media-test-integration`
2. Identify failure points (element linking, caps negotiation, buffer flow)
3. Add debug logging to InputPipeline (element states, pad events, buffer callbacks)
4. Fix identified issues (may include):
   - Element linking order corrections
   - Caps filter adjustments
   - Callback signal connections
5. Re-run integration tests until PASS
6. Verify both video and audio buffers received

**Acceptance Criteria**:
- [ ] T012 integration test now PASSES
- [ ] Video buffers received with valid PTS
- [ ] Audio buffers received with valid PTS
- [ ] No caps negotiation errors in logs
- [ ] Pipeline transitions to PLAYING state

**Test**: `make media-test-integration -k test_input_pipeline_rtmp_integration` → PASS

---

### T015: Write failing integration test for video-only stream rejection
- **Priority**: P1
- **Type**: Test (TDD)
- **Dependencies**: T011
- **Estimated Time**: 30 minutes

**Description**: Write integration test verifying pipeline rejects video-only streams (no audio track).

**Steps**:
1. Add test `test_input_pipeline_rejects_video_only_stream()` to `test_segment_pipeline.py`
2. Use video-only fixture from T003 (ffmpeg with `-an` flag)
3. Implement test:
   - Publish video-only stream via RTMP
   - Create InputPipeline
   - Assert start() raises RuntimeError with "Audio track required" message
   - Assert pipeline state is ERROR
4. Run test and VERIFY it fails initially

**Acceptance Criteria**:
- [ ] Integration test written for video-only stream
- [ ] Test publishes stream without audio track
- [ ] Assertions for RuntimeError and error message
- [ ] Test initially FAILS

**Test Output Expected**:
```
FAILED test_segment_pipeline.py::test_input_pipeline_rejects_video_only_stream
```

---

### T016: Fix audio validation to pass video-only rejection test
- **Priority**: P1
- **Type**: Bug Fix
- **Dependencies**: T015
- **Estimated Time**: 30 minutes

**Description**: Ensure audio validation correctly detects and rejects video-only streams.

**Steps**:
1. Run T015 test and observe failure mode
2. Adjust `_validate_audio_track()` if needed:
   - Ensure timeout is sufficient for pad detection
   - Verify has_audio_pad flag correctly set in _on_pad_added
   - Check error message clarity
3. Add logging for pad detection events
4. Re-run test until PASS

**Acceptance Criteria**:
- [ ] T015 test now PASSES
- [ ] Video-only streams rejected with RuntimeError
- [ ] Error message is descriptive
- [ ] Pipeline state set to ERROR on rejection

**Test**: `make media-test-integration -k test_input_pipeline_rejects_video_only_stream` → PASS

---

### T017: Verify integration test coverage and edge cases
- **Priority**: P2
- **Type**: Test Coverage
- **Dependencies**: T016
- **Estimated Time**: 45 minutes

**Description**: Run integration tests with coverage analysis and add missing edge case tests.

**Steps**:
1. Run `make media-test-integration` with coverage:
   ```bash
   pytest apps/media-service/tests/integration/ \
       --cov=media_service.pipeline.input \
       --cov-report=term-missing
   ```
2. Identify uncovered lines in InputPipeline
3. Add edge case tests as needed:
   - Pipeline stop during RTMP streaming
   - Network interruption simulation (if feasible)
   - Invalid RTMP stream format
4. Ensure 80% minimum coverage for InputPipeline

**Acceptance Criteria**:
- [ ] Integration tests achieve 80%+ coverage for InputPipeline
- [ ] Edge case tests added for critical paths
- [ ] Coverage report shows no untested error paths
- [ ] All integration tests PASS

**Test**: `make media-test-coverage` → 80%+ for InputPipeline

---

### T018: Write failing E2E test for RTMP-based full pipeline
- **Priority**: P1
- **Type**: Test (TDD)
- **Dependencies**: T011
- **Estimated Time**: 60 minutes

**Description**: Write E2E test validating complete RTMP flow from stream publish to STS processing.

**Steps**:
1. Open `tests/e2e/test_dual_compose_full_pipeline.py`
2. Add test `test_dual_compose_full_pipeline_rtmp()`
3. Implement E2E flow per contracts/test-expectations.md:
   - Start docker-compose.e2e.yml (MediaMTX + media-service + STS)
   - Publish stream via RTMP (port 1935)
   - Wait for pipeline startup (5 seconds)
   - Verify media-service logs show rtmpsrc/flvdemux (NOT rtspsrc)
   - Verify segments written to disk
   - Verify STS received audio fragments
4. Run test and VERIFY it fails initially

**Acceptance Criteria**:
- [ ] E2E test written for full RTMP pipeline
- [ ] Test publishes via RTMP (not RTSP)
- [ ] Assertions for logs, segments, STS fragments
- [ ] Test initially FAILS

**Test Output Expected**:
```
FAILED test_dual_compose_full_pipeline.py::test_dual_compose_full_pipeline_rtmp
```

---

### T019: Fix E2E test failures and verify end-to-end RTMP flow
- **Priority**: P1
- **Type**: Bug Fix / Integration
- **Dependencies**: T018
- **Estimated Time**: 90 minutes

**Description**: Debug and fix E2E test failures to achieve full end-to-end RTMP functionality.

**Steps**:
1. Run `make e2e-test -k test_dual_compose_full_pipeline_rtmp`
2. Identify failure points (Docker networking, stream publishing, segment writing, STS integration)
3. Fix issues (may include):
   - Docker Compose port mappings
   - MediaMTX RTMP configuration
   - Stream URL construction in E2E test
   - STS Socket.IO connection issues
4. Add debug logging to E2E test (service logs, stream status)
5. Re-run test until PASS

**Acceptance Criteria**:
- [ ] E2E test now PASSES
- [ ] RTMP stream successfully published and consumed
- [ ] Segments written to expected directories
- [ ] STS service receives audio fragments
- [ ] No RTSP references in logs

**Test**: `make e2e-test -k test_dual_compose_full_pipeline_rtmp` → PASS

---

### T020: Remove all RTSP-specific tests and code
- **Priority**: P1
- **Type**: Cleanup
- **Dependencies**: T014, T017, T019
- **Estimated Time**: 60 minutes

**Description**: Complete RTSP removal by deleting all RTSP-specific tests, code, and configuration.

**Steps**:
1. Search codebase for RTSP references:
   ```bash
   grep -r "rtsp" apps/media-service/ tests/
   grep -r "rtspsrc" apps/media-service/ tests/
   grep -r "rtph264depay" apps/media-service/ tests/
   ```
2. Delete RTSP-specific tests:
   - Any tests with "rtsp" in name or description
   - Tests for RTP depayloader selection
   - Tests for RTSP latency configuration
3. Remove RTSP code:
   - Remove `rtsp_url` parameter references
   - Remove RTP encoding detection logic
   - Remove dynamic depayloader creation
4. Remove RTSP configuration:
   - Remove `mediamtx_rtsp_port` from config models
   - Remove RTSP port 8554 from Docker Compose
5. Run full test suite to verify no broken references

**Acceptance Criteria**:
- [ ] No RTSP-specific tests remain
- [ ] No RTSP-specific code remains
- [ ] No RTSP port 8554 references in configs
- [ ] Full test suite passes (unit + integration + E2E)
- [ ] grep searches return no RTSP matches

**Test**: `make media-test && make e2e-test` → All tests PASS

---

### T021: Update existing E2E tests to use RTMP
- **Priority**: P1
- **Type**: Test Migration
- **Dependencies**: T020
- **Estimated Time**: 45 minutes

**Description**: Update all remaining E2E tests to publish streams via RTMP instead of RTSP.

**Steps**:
1. Review all tests in `tests/e2e/` directory
2. For each test that publishes streams:
   - Replace `rtsp://` URLs with `rtmp://` URLs
   - Change port 8554 to 1935
   - Update ffmpeg `-f rtsp` to `-f flv`
3. Update test assertions:
   - Replace expectations for rtspsrc with rtmpsrc
   - Replace RTP depayloader expectations with flvdemux
4. Run each updated test individually to verify
5. Run full E2E suite to verify all pass

**Acceptance Criteria**:
- [ ] All E2E tests use RTMP URLs
- [ ] No E2E tests reference port 8554 or RTSP
- [ ] All E2E tests pass
- [ ] Test execution time within 10% of baseline

**Test**: `make e2e-test` → All tests PASS

---

## Phase 4: Polish - Documentation and Verification (3 tasks)

### T022: Update documentation for RTMP migration
- **Priority**: P2
- **Type**: Documentation
- **Dependencies**: T021
- **Estimated Time**: 60 minutes

**Description**: Update all documentation to reflect RTMP as the standard stream pull protocol.

**Steps**:
1. Update `apps/media-service/README.md`:
   - Replace RTSP examples with RTMP examples
   - Update architecture diagrams (if any)
   - Document RTMP URL format and port 1935
   - Update quickstart instructions
2. Update `specs/020-rtmp-stream-pull/quickstart.md` (if exists):
   - Verify implementation matches quickstart guide
   - Add troubleshooting section for RTMP issues
3. Update root `README.md`:
   - Update system architecture description
   - Replace RTSP references with RTMP
4. Update `CLAUDE.md` (if needed):
   - Update build/test commands if changed
   - Add RTMP-specific development notes

**Acceptance Criteria**:
- [ ] All README files updated with RTMP references
- [ ] No RTSP references remain in documentation
- [ ] RTMP URL format documented
- [ ] Quickstart guide accurate

**Test**: Manual review - documentation is clear and accurate

---

### T023: Run full test suite with coverage verification
- **Priority**: P1
- **Type**: Verification
- **Dependencies**: T021
- **Estimated Time**: 30 minutes

**Description**: Run complete test suite (unit + integration + E2E) with coverage analysis to verify 80% minimum.

**Steps**:
1. Run unit tests with coverage:
   ```bash
   make media-test-unit
   pytest apps/media-service/tests/unit/ \
       --cov=media_service \
       --cov-report=term-missing \
       --cov-fail-under=80
   ```
2. Run integration tests with coverage:
   ```bash
   make media-test-integration
   ```
3. Run E2E tests:
   ```bash
   make e2e-test
   ```
4. Verify InputPipeline critical path has 95%+ coverage:
   ```bash
   pytest --cov=media_service.pipeline.input --cov-fail-under=95
   ```
5. Generate HTML coverage report:
   ```bash
   pytest --cov=media_service --cov-report=html
   ```
6. Review coverage report and add tests for any critical uncovered lines

**Acceptance Criteria**:
- [ ] Unit tests pass with 80%+ overall coverage
- [ ] InputPipeline has 95%+ coverage
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Coverage report generated
- [ ] No critical paths untested

**Test**: `make media-test-coverage` → 80%+ overall, 95%+ for InputPipeline

---

### T024: Final verification and PR preparation
- **Priority**: P1
- **Type**: Verification
- **Dependencies**: T022, T023
- **Estimated Time**: 45 minutes

**Description**: Final end-to-end verification and PR preparation checklist.

**Steps**:
1. Run all quality checks:
   ```bash
   make fmt
   make lint
   make typecheck
   make media-test
   make e2e-test
   ```
2. Verify no RTSP references remain:
   ```bash
   grep -r "rtsp" apps/media-service/src/ || echo "No RTSP found - PASS"
   grep -r "8554" apps/media-service/ || echo "No port 8554 found - PASS"
   ```
3. Test manual workflow:
   - Start services: `make media-dev`
   - Publish test stream via RTMP
   - Verify stream processing in logs
   - Stop services cleanly
4. Prepare commit message with spec reference:
   ```
   feat: migrate stream pull from RTSP to RTMP for lower complexity

   - Replace rtspsrc with rtmpsrc + flvdemux
   - Remove RTP depayloaders (rtph264depay, rtpmp4gdepay)
   - Add audio track validation (reject video-only streams)
   - Update all tests to use RTMP URLs
   - Complete RTSP removal (no backward compatibility)

   Spec: specs/020-rtmp-stream-pull/spec.md
   Reduces pipeline element count by 3+
   Simplifies caps negotiation, improves audio reliability
   Maintains <300ms latency budget

   🤖 Generated with Claude Code
   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
   ```
5. Create PR with testing evidence

**Acceptance Criteria**:
- [ ] All quality checks pass (fmt, lint, typecheck)
- [ ] All tests pass (unit, integration, E2E)
- [ ] No RTSP references in source code
- [ ] Manual workflow tested successfully
- [ ] Commit message prepared with spec reference
- [ ] Ready for PR submission

**Test**: All automated checks pass, manual verification successful

---

## Success Criteria Mapping

| Success Criteria | Tasks Addressing |
|------------------|------------------|
| SC-001: Pull RTMP streams within 2s | T009, T011, T012-T014 |
| SC-002: 80% test coverage | T004-T008, T012, T015, T018, T023 |
| SC-003: Video & audio segments written | T014, T017, T019 |
| SC-004: Audio fragments reach STS | T019, T021 |
| SC-005: 3+ elements removed | T009, T011, T020 |
| SC-006: <300ms latency maintained | T009, T014, T019 (verified in integration) |
| SC-007: No RTSP code remains | T020 |
| SC-008: Test execution time within 10% | T021, T023 |
| SC-009: Documentation updated | T022 |
| SC-010: All E2E steps pass | T019, T021 |

---

## Risk Mitigation

### Critical Path
T003 → T004 → T005 → T006 → T009 → T011 → T012 → T013 → T014 → T019 → T020 → T021 → T023 → T024

**Mitigation**: If critical path blocked, parallelize non-dependent tasks (T007-T008, T015-T016, T018, T022)

### High-Risk Tasks
- **T014**: Integration test debugging (may reveal unforeseen GStreamer issues)
  - Mitigation: Allocate extra time, add comprehensive logging, use gst-launch-1.0 for manual testing
- **T019**: E2E test debugging (multi-service coordination complexity)
  - Mitigation: Test services independently first, use docker logs for debugging, verify network connectivity

### Blocking Issues
- **GStreamer rtmpsrc not available**: Check GStreamer version, install gst-plugins-bad if missing
- **MediaMTX RTMP disabled**: Verify mediamtx.yml configuration, check MediaMTX version supports RTMP
- **Audio validation flaky**: Increase timeout, add retry logic, verify test fixture has audio track

---

## Parallelization Opportunities

**Phase 1 (Foundational)**: T007, T008 can run in parallel with T004-T006 sequence
**Phase 2 (Implementation)**: T010 can run in parallel with T009
**Phase 3 (Testing)**: T015-T016 can run in parallel with T012-T014 sequence, T018 can start after T011
**Phase 4 (Polish)**: T022 can run in parallel with T023

**Estimated parallel execution**: 1.5-2 days with parallelization vs. 2-3 days sequential

---

## Completion Checklist

- [ ] All 24 tasks completed
- [ ] All tests passing (unit, integration, E2E)
- [ ] Coverage >= 80% overall, >= 95% for InputPipeline
- [ ] No RTSP references in codebase
- [ ] Documentation updated
- [ ] Quality checks passing (fmt, lint, typecheck)
- [ ] Manual workflow tested
- [ ] PR prepared with spec reference
- [ ] Success criteria SC-001 through SC-010 achieved

---

**Next Steps**: Start with T001 (branch creation) and proceed through Setup phase. Follow TDD workflow: write failing tests, implement features, verify tests pass. Maintain 80% coverage minimum throughout.
