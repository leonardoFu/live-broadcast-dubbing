# Tasks: E2E Stream Handler Tests

**Input**: Design documents from `/specs/018-e2e-stream-handler-tests/`
**Prerequisites**: plan.md, spec.md

**Tests**: Tests are MANDATORY per Constitution Principle VIII. This feature IS the test suite itself - E2E tests for WorkerRunner pipeline validation.

**Organization**: Tasks are grouped by implementation phase to enable incremental delivery and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Infrastructure Setup (P0 - Prerequisites for All Tests)

**Purpose**: Establish E2E test environment with Docker Compose, shared fixtures, and helper utilities

**⚠️ CRITICAL**: No E2E tests can be written until this phase is complete

- [X] T001 Create E2E test directory structure at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/__init__.py`
- [X] T002 Create Docker Compose configuration at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/docker-compose.yml` with MediaMTX, media-service, and echo-sts services on shared network `e2e-test-network`
- [X] T003 Create E2E environment configuration at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/config.py` with RTSP/RTMP URLs, Socket.IO endpoint, metrics endpoint
- [X] T004 [P] Create test helpers directory at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/helpers/__init__.py`
- [X] T005 [P] Create Docker manager helper at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/helpers/docker_manager.py` for docker-compose lifecycle management (start, stop, health checks)
- [X] T006 [P] Create stream publisher helper at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/helpers/stream_publisher.py` for ffmpeg RTSP publishing via subprocess
- [X] T007 [P] Create metrics parser helper at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/helpers/metrics_parser.py` for Prometheus /metrics endpoint parsing using prometheus_client
- [X] T008 [P] Create stream analyzer helper at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/helpers/stream_analyzer.py` for ffprobe PTS analysis and A/V delta calculation
- [X] T009 Create pytest conftest at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/conftest.py` with shared fixtures: docker_services, stream_publisher, metrics_client, log_capture, cleanup_resources

**Checkpoint**: E2E infrastructure ready - test files can now be created

---

## Phase 2: Test Fixture Acquisition and Validation

**Purpose**: Acquire deterministic test video fixture for consistent E2E test results

- [X] T010 Create test fixtures directory at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/fixtures/test-streams/`
- [ ] T011 Acquire or generate 60-second H.264 + AAC test video (1-min-nfl.mp4 or equivalent) at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/fixtures/test-streams/1-min-nfl.mp4` with properties: 1280x720, 30fps, 48kHz stereo, 60s duration (see fixtures/README.md for instructions)
- [ ] T012 Validate test fixture properties using ffprobe: verify duration=60s, video_codec=H.264, audio_codec=AAC, fps=30, resolution=1280x720, audio_sample_rate=48000Hz
- [X] T013 Create fixture documentation at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/fixtures/README.md` describing fixture properties and expected segments (10 segments x 6s)

**Checkpoint**: Test fixture validated - ready for E2E test development

---

## Phase 3: P1 Tests - Full Pipeline & A/V Sync (MVP E2E Tests)

**Purpose**: Validate core end-to-end functionality - RTSP ingestion → STS processing → RTMP output with A/V sync verification

### User Story 1 - Full Pipeline Flow: RTSP → Worker → Echo STS → RTMP (P1) 🎯 MVP

**Goal**: Validate complete dubbing pipeline orchestration end-to-end

**Independent Test**: Run with test fixture published to MediaMTX, verify RTMP output playable

- [X] T014 [US1] Create E2E test file at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/test_full_pipeline.py`
- [X] T015 [US1] Write test `test_full_pipeline_rtsp_to_rtmp()` that:
  - Starts Docker Compose services (MediaMTX + media-service + echo-sts)
  - Publishes 1-min-nfl.mp4 to rtsp://localhost:8554/live/test/in using stream_publisher helper
  - Starts WorkerRunner with RTSP input and RTMP output configuration
  - Waits for 10 segments to be processed (monitor logs or metrics)
  - Verifies RTMP output stream exists at rtmp://localhost:1935/live/test/out using ffprobe
  - Validates output duration matches input duration (+/- 500ms) using stream_analyzer
  - Asserts no errors in container logs
  - Validates test completes within 90 seconds
- [X] T016 [US1] Add metrics validation to `test_full_pipeline_rtsp_to_rtmp()`: query /metrics endpoint and verify worker_audio_fragments_total=10, worker_fallback_total=0
- [X] T017 [US1] Add cleanup logic to `test_full_pipeline_rtsp_to_rtmp()`: ensure docker-compose down executes even on test failure using pytest fixtures

**Checkpoint**: Full pipeline E2E test passing - core workflow validated

### User Story 2 - A/V Sync Verification: Sync Delta < 120ms (P1)

**Goal**: Validate A/V synchronization remains within 120ms threshold throughout pipeline

**Independent Test**: Analyze output stream PTS deltas, verify 95% of segments within threshold

- [X] T018 [US2] Create E2E test file at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/test_av_sync.py`
- [X] T019 [US2] Write test `test_av_sync_within_threshold()` that:
  - Starts Docker Compose services and publishes test fixture (reuse conftest fixtures)
  - Starts WorkerRunner with A/V sync monitoring enabled
  - Captures all segment pairs during processing
  - Uses stream_analyzer to extract video PTS and audio PTS from output RTMP stream
  - Calculates A/V delta for each segment: |video_pts - audio_pts|
  - Asserts 95% of segments have delta < 120ms
  - Validates worker_av_sync_delta_ms metric is updated correctly
- [X] T020 [US2] Add test `test_av_sync_with_variable_sts_latency()` that configures Echo STS to introduce variable latency (0-500ms) and verifies A/V sync buffers absorb variation without drift
- [X] T021 [US2] Add test `test_av_sync_correction_gradual_slew()` that triggers sync drift and verifies correction uses gradual slew (not hard jump) by analyzing consecutive PTS deltas

**Checkpoint**: A/V sync E2E tests passing - sync discipline validated

---

## Phase 4: P2 Tests - Circuit Breaker, Backpressure, Fragment Tracking

**Purpose**: Validate resilience, flow control, and in-flight tracking mechanisms

### User Story 3 - Circuit Breaker Integration: Fallback on STS Failure (P2)

**Goal**: Validate circuit breaker protection during STS failures and recovery workflow

**Independent Test**: Configure Echo STS error simulation, verify breaker opens/closes correctly

- [X] T022 [US3] Create E2E test file at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/test_circuit_breaker.py`
- [X] T023 [US3] Write test `test_circuit_breaker_opens_on_sts_failures()` that:
  - Starts Docker Compose services and publishes test fixture
  - Configures Echo STS to return 5 consecutive TIMEOUT errors via config:error_simulation event
  - Starts WorkerRunner and processes stream
  - Verifies circuit breaker opens after 5 failures (check logs and worker_sts_breaker_state metric)
  - Asserts subsequent fragments use fallback audio (worker_fallback_total increments)
  - Waits 30s for cooldown period
  - Verifies breaker enters half-open state (sends 1 probe fragment)
  - Configures Echo STS to succeed on probe
  - Verifies breaker closes and normal processing resumes
- [X] T024 [US3] Add test `test_circuit_breaker_ignores_non_retryable_errors()` that sends INVALID_CONFIG error and verifies breaker failure counter NOT incremented (breaker stays closed)
- [X] T025 [US3] Add test `test_circuit_breaker_state_transitions_logged()` that validates all state transitions (closed → open → half-open → closed) are logged with correct timestamps and reflected in metrics

**Checkpoint**: Circuit breaker E2E tests passing - fault tolerance validated

### User Story 4 - Backpressure Handling: Worker Handles STS Backpressure (P2)

**Goal**: Validate WorkerRunner responds correctly to backpressure events from Echo STS

**Independent Test**: Configure Echo STS backpressure simulation, monitor fragment sending rate

- [X] T026 [US4] Create E2E test file at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/test_backpressure.py`
- [X] T027 [US4] Write test `test_worker_respects_backpressure_pause()` that:
  - Starts Docker Compose services and publishes test fixture
  - Starts WorkerRunner sending fragments normally
  - Configures Echo STS to emit backpressure with action="pause"
  - Verifies worker stops sending new fragments (monitor logs and metrics)
  - Configures Echo STS to emit backpressure with action="none"
  - Verifies worker resumes sending fragments
  - Validates worker_backpressure_events_total counter shows correct counts
- [X] T028 [US4] Add test `test_worker_respects_backpressure_slow_down()` that:
  - Configures Echo STS to emit backpressure with action="slow_down" and recommended_delay_ms=500
  - Measures time between fragment sends (using log timestamps)
  - Asserts worker inserts 500ms delay between fragments
- [X] T029 [US4] Add test `test_backpressure_metrics_updated()` that validates worker_backpressure_events_total is incremented correctly by action type (pause, slow_down, none)

**Checkpoint**: Backpressure E2E tests passing - flow control validated

### User Story 5 - Fragment Tracker E2E: In-Flight Tracking Across Services (P2)

**Goal**: Validate FragmentTracker correctly tracks in-flight fragments and enforces max_inflight limit

**Independent Test**: Send fragments and verify in-flight count updates correctly across full pipeline

- [X] T030 [US5] Create E2E test file at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/test_fragment_tracker.py`
- [X] T031 [US5] Write test `test_fragment_tracker_respects_max_inflight()` that:
  - Starts Docker Compose services and publishes test fixture
  - Configures WorkerRunner with max_inflight=3
  - Starts processing with 5+ segments ready
  - Monitors worker_inflight_fragments metric during processing
  - Verifies worker never exceeds max_inflight=3 (sample metric every 100ms)
  - Verifies in-flight count increases on fragment:data send and decreases on fragment:processed
  - Validates all fragments are tracked and completed (no leaks)
- [X] T032 [US5] Add test `test_fragment_tracker_timeout_triggers_fallback()` that:
  - Configures Echo STS to delay response beyond 8s timeout
  - Verifies fragment is removed from in-flight tracking after timeout
  - Asserts fallback audio is used for timed-out fragment
  - Validates worker can send next fragment (in-flight slot freed)
- [X] T033 [US5] Add test `test_fragment_tracker_correlation_across_events()` that validates fragment_id correlation between fragment:data, fragment:ack, and fragment:processed events

**Checkpoint**: Fragment tracking E2E tests passing - in-flight management validated

---

## Phase 5: P3 Tests - Reconnection Resilience (Optional but Recommended)

**Purpose**: Validate WorkerRunner handles Socket.IO disconnection and reconnects with exponential backoff

**Prerequisites**: Echo STS enhancement with simulate:disconnect event

### Echo STS Enhancement for Reconnection Testing

- [X] T034 Create Echo STS contract definition at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/specs/018-e2e-stream-handler-tests/contracts/sts-simulate-disconnect.json` with schema for simulate:disconnect event
- [X] T035 Enhance Echo STS server at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/apps/sts-service/src/sts_service/echo/handlers/simulate.py` to handle simulate:disconnect event by calling socketio.disconnect(sid) after optional delay_ms

### User Story 6 - Reconnection Resilience: Recovery After STS Disconnection (P3)

**Goal**: Validate WorkerRunner handles Socket.IO disconnection and successfully reconnects

**Independent Test**: Force Echo STS disconnect, verify reconnection with exponential backoff

- [X] T036 [US6] Create E2E test file at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/tests/e2e/test_reconnection.py`
- [X] T037 [US6] Write test `test_worker_reconnects_after_sts_disconnect()` that:
  - Starts Docker Compose services and publishes test fixture
  - Starts WorkerRunner with 2 fragments in-flight
  - Sends simulate:disconnect event to Echo STS via Socket.IO client
  - Verifies worker immediately uses fallback audio for 2 in-flight fragments
  - Monitors logs for reconnection attempts with exponential backoff: 2s, 4s, 8s, 16s, 32s (verify timestamps)
  - Validates worker re-sends stream:init after reconnection succeeds
  - Verifies stream resumes from next segment boundary with fresh sequence_number=0
  - Asserts worker_reconnection_total counter increments by 1
- [X] T038 [US6] Add test `test_worker_exits_after_max_reconnection_attempts()` that:
  - Forces Echo STS to stay offline (stop container)
  - Verifies worker attempts 5 reconnections with correct backoff timing
  - Asserts worker exits with non-zero code after final attempt fails
- [X] T039 [US6] Add test `test_reconnection_preserves_pipeline_state()` that validates after successful reconnection: circuit breaker state is preserved (worker_sts_breaker_state), stream configuration is re-initialized, processing continues without data loss

**Checkpoint**: Reconnection E2E tests passing - network resilience validated

---

## Phase 6: Documentation and CI Integration

**Purpose**: Document E2E test execution and integrate into CI pipeline

- [X] T040 [P] Create quickstart guide at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/specs/018-e2e-stream-handler-tests/quickstart.md` with:
  - Prerequisites (Docker, Docker Compose, ffmpeg, pytest)
  - Running E2E tests locally: `docker-compose -f tests/e2e/docker-compose.yml up -d && pytest tests/e2e/ -v`
  - Debugging test failures (container logs, metrics inspection)
  - Adding new E2E tests (template and best practices)
- [ ] T041 [P] Update root README at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/README.md` with E2E test section linking to quickstart guide
- [X] T042 Add E2E test suite to Makefile at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/stream-handler/Makefile` with targets: `e2e-up`, `e2e-down`, `e2e-test`, `e2e-test-full`, `e2e-test-p1`, `e2e-test-p2`, `e2e-test-p3`
- [ ] T043 Validate E2E test suite reliability by running 20 consecutive executions and measuring pass rate (target: 95% pass rate)
- [ ] T044 Document flakiness mitigation strategies in quickstart.md (timeout tuning, Docker health checks, cleanup procedures)

**Checkpoint**: E2E test suite documented and CI-ready

---

## Dependencies & Execution Order

### Phase Dependencies

- **Infrastructure Setup (Phase 1)**: No dependencies - can start immediately
- **Test Fixture Acquisition (Phase 2)**: Depends on Phase 1 completion (needs fixtures directory)
- **P1 Tests (Phase 3)**: Depends on Phase 1 + Phase 2 completion
- **P2 Tests (Phase 4)**: Depends on Phase 1 + Phase 2 completion (can run in parallel with Phase 3)
- **P3 Tests (Phase 5)**: Depends on Phase 1 + Phase 2 + Echo STS enhancement (T034-T035)
- **Documentation (Phase 6)**: Depends on all test phases completion

### Task Dependencies Within Phases

**Phase 1 (Infrastructure)**:
- T001 → T002, T003, T004 (directory must exist first)
- T004 → T005, T006, T007, T008 (helpers directory must exist)
- T005, T006, T007, T008 can run in parallel (different files)
- T009 depends on T005, T006, T007, T008 (imports helpers)

**Phase 2 (Fixture)**:
- T010 → T011 (directory must exist)
- T011 → T012, T013 (fixture must exist)
- T012, T013 can run in parallel

**Phase 3 (P1 Tests)**:
- T014 → T015, T016, T017 (file must exist)
- T015 → T016 (metrics validation extends test)
- T016, T017 can run in parallel
- T018 → T019, T020, T021 (file must exist)
- T019, T020, T021 can run in parallel (different test functions)

**Phase 4 (P2 Tests)**:
- T022 → T023, T024, T025 (file must exist)
- T023, T024, T025 can run in parallel
- T026 → T027, T028, T029 (file must exist)
- T027, T028, T029 can run in parallel
- T030 → T031, T032, T033 (file must exist)
- T031, T032, T033 can run in parallel

**Phase 5 (P3 Tests)**:
- T034, T035 must complete before T036 (Echo STS enhancement required)
- T034, T035 can run in parallel (different files)
- T036 → T037, T038, T039 (file must exist)
- T037, T038, T039 can run in parallel

**Phase 6 (Documentation)**:
- T040, T041, T042 can run in parallel (different files)
- T043 depends on all test phases completion
- T044 depends on T043 (documents findings)

### Parallel Opportunities

- Phase 3 (P1 tests) and Phase 4 (P2 tests) can run in parallel after Phase 2 completes
- Within each test file: multiple test functions can be written in parallel
- Helper utilities (T005, T006, T007, T008) can be developed in parallel
- Documentation tasks (T040, T041, T042) can be completed in parallel

---

## Implementation Strategy

### MVP First (P1 Tests Only)

1. Complete Phase 1: Infrastructure Setup (T001-T009)
2. Complete Phase 2: Test Fixture Acquisition (T010-T013)
3. Complete Phase 3: P1 Tests (T014-T021)
4. **STOP and VALIDATE**: Run P1 E2E tests, verify full pipeline and A/V sync working
5. Ready for production validation

### Incremental Delivery

1. Complete Infrastructure + Fixture → Foundation ready (Phase 1-2)
2. Add P1 Tests → Validate core workflow (Phase 3) → **MVP E2E suite!**
3. Add P2 Tests → Validate resilience (Phase 4) → Production-ready E2E suite
4. Add P3 Tests → Validate reconnection (Phase 5) → Full E2E coverage
5. Add Documentation → CI-ready (Phase 6)

### Parallel Team Strategy

With multiple developers:

1. Team completes Infrastructure + Fixture together (Phase 1-2)
2. Once foundation ready:
   - Developer A: Full Pipeline Test (T014-T017)
   - Developer B: A/V Sync Test (T018-T021)
   - Developer C: Circuit Breaker Test (T022-T025)
   - Developer D: Backpressure Test (T026-T029)
   - Developer E: Fragment Tracker Test (T030-T033)
3. Tests complete and validate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability (US1-US6 from spec.md)
- All E2E tests use Docker Compose for isolation and deterministic behavior
- Test fixtures are pre-validated for consistent properties (60s, H.264, AAC)
- Helper utilities provide reusable abstractions for Docker, ffmpeg, metrics, stream analysis
- Each test file should be independently runnable (use conftest.py shared fixtures)
- Cleanup logic (docker-compose down) MUST execute even on test failure using pytest fixtures
- Metrics validation uses Prometheus text format parsing via prometheus_client library
- PTS analysis uses ffprobe JSON output for A/V delta calculation
- Echo STS enhancement (simulate:disconnect) enables reconnection testing without container restarts
- Tests should complete within reasonable time: full suite <10 minutes, individual tests <90 seconds
- CI integration targets 95% pass rate over 20 consecutive runs (validate reliability)
