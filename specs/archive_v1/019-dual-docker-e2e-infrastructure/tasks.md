# Tasks: Dual Docker-Compose E2E Test Infrastructure

**Input**: Design documents from `/specs/019-dual-docker-e2e-infrastructure/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), contracts/media-service-env.json, contracts/sts-service-env.json

**Tests**: Tests are MANDATORY per Constitution Principle VIII. Every user story MUST have tests written FIRST before implementation. The tasks below enforce a test-first workflow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. This feature is primarily E2E infrastructure, so most implementation creates test files and Docker configurations.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for dual Docker Compose E2E tests

- [ ] T001 [P] Create directory structure `tests/e2e/helpers/` with `__init__.py`
- [ ] T002 [P] Create directory structure `tests/e2e/fixtures/test_streams/` for video fixtures
- [ ] T003 [P] Create `tests/e2e/pytest.ini` with pytest configuration for E2E tests (markers, asyncio settings)
- [ ] T004 [P] Create `.env.dual-compose.example` in `tests/e2e/` documenting all environment variables from contracts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story tests can run

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create test fixture: Generate or add `tests/e2e/fixtures/test_streams/30s-counting-english.mp4` (30s H.264 video with AAC audio, counting phrases "One, two, three... thirty")
- [ ] T006 Validate test fixture properties with ffprobe: duration=30s, video_codec=h264, audio_codec=aac, sample_rate=48000
- [ ] T007 [P] Create `apps/media-service/docker-compose.e2e.yml` with MediaMTX + media-service services (bridge networking, port exposure per contract)
- [ ] T008 [P] Create `apps/media-service/.env.e2e.example` documenting environment variables from contracts/media-service-env.json
- [ ] T009 [P] Create `apps/sts-service/docker-compose.e2e.yml` with real STS service (ASR + Translation + TTS, CPU mode)
- [ ] T010 [P] Create `apps/sts-service/.env.e2e.example` documenting environment variables from contracts/sts-service-env.json
- [ ] T011 [P] Create helper `tests/e2e/helpers/docker_compose_manager.py` with DockerComposeManager class (start, stop, health_check, logs methods)
- [ ] T012 [P] Create helper `tests/e2e/helpers/stream_publisher.py` with StreamPublisher class (ffmpeg RTSP publishing, process cleanup)
- [ ] T013 [P] Create helper `tests/e2e/helpers/metrics_parser.py` with PrometheusMetricsParser class (parse /metrics endpoint)
- [ ] T014 [P] Create helper `tests/e2e/helpers/stream_analyzer.py` with StreamAnalyzer class (ffprobe inspection, PTS extraction, audio fingerprinting)
- [ ] T015 [P] Create helper `tests/e2e/helpers/socketio_monitor.py` with SocketIOMonitor class (capture fragment:processed events)
- [ ] T016 Create `tests/e2e/conftest.py` with session-scoped fixtures: media_compose_env, sts_compose_env, dual_compose_env, publish_test_fixture

**Checkpoint**: Foundation ready - user story tests can now be written and run (automated validation with docker-compose up/down)

---

## Phase 3: User Story 1 - Full Pipeline E2E (Priority: P1) 🎯 MVP

**Goal**: Validate complete dubbing pipeline: test fixture → MediaMTX → WorkerRunner → real STS → dubbed output

**Independent Test**: Publish 30s counting fixture, verify all 5 segments processed by real STS, output stream playable

### Tests for User Story 1 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before infrastructure is fully implemented**

**Coverage Target for US1**: E2E integration validation (full pipeline correctness)

- [ ] T017 [US1] Create `tests/e2e/test_dual_compose_full_pipeline.py` with test_full_pipeline_media_to_sts_to_output()
  - Test setup: Start dual_compose_env fixture
  - Test action: Publish 30s counting fixture to unique RTSP stream (rtsp://localhost:8554/live/test_us1/in)
  - Test validation: Verify WorkerRunner connects within 5s, 5 segments sent to STS, all fragments return with dubbed_audio, output RTMP stream available (rtmp://localhost:1935/live/test_us1/out)
  - Test validation: Verify pipeline completes within 180 seconds (allowing real STS latency)
  - Test teardown: Stop ffmpeg, verify cleanup

**Verification**: Run `pytest tests/e2e/test_dual_compose_full_pipeline.py` - test MUST FAIL if docker-compose files incomplete or services not started

### Implementation for User Story 1

- [ ] T018 [US1] Add MediaMTX health check to apps/media-service/docker-compose.e2e.yml (wget http://localhost:9997/v3/paths/list)
- [ ] T019 [US1] Add media-service health check to apps/media-service/docker-compose.e2e.yml (wget http://localhost:8080/health)
- [ ] T020 [US1] Configure MediaMTX environment variables in apps/media-service/docker-compose.e2e.yml (RTSP port 8554, RTMP port 1935)
- [ ] T021 [US1] Configure media-service environment in apps/media-service/docker-compose.e2e.yml (STS_SERVICE_URL=http://host.docker.internal:3000, LOG_LEVEL=DEBUG)
- [ ] T022 [US1] Add extra_hosts for host.docker.internal in apps/media-service/docker-compose.e2e.yml (enable media-service → STS connection)
- [ ] T023 [US1] Add STS service health check to apps/sts-service/docker-compose.e2e.yml (curl http://localhost:3000/health, start_period=30s for model load)
- [ ] T024 [US1] Configure STS service environment in apps/sts-service/docker-compose.e2e.yml (ASR_MODEL=whisper-small, TTS_PROVIDER=coqui, DEVICE=cpu)
- [ ] T025 [US1] Add model-cache volume to apps/sts-service/docker-compose.e2e.yml (persist Whisper + TTS models across runs)
- [ ] T026 [US1] Update test_full_pipeline_media_to_sts_to_output() to assert 5 segments processed (monitor metrics endpoint worker_audio_fragments_total)
- [ ] T027 [US1] Update test_full_pipeline_media_to_sts_to_output() to verify output stream duration matches input (ffprobe, +/- 500ms tolerance)

**Checkpoint**: User Story 1 E2E test passes - full pipeline validated with real STS (run `pytest tests/e2e/test_dual_compose_full_pipeline.py -v`)

---

## Phase 4: User Story 2 - Service Discovery via Port Exposure (Priority: P1)

**Goal**: Validate services communicate via localhost:<port> URLs, health checks pass before tests run

**Independent Test**: Query health endpoints for all services, verify Socket.IO connection established

### Tests for User Story 2 (MANDATORY - Test-First) ✅

**Coverage Target for US2**: Service connectivity and health validation

- [ ] T028 [P] [US2] Create `tests/e2e/test_dual_compose_service_communication.py` with test_services_can_communicate()
  - Test setup: Start dual_compose_env fixture
  - Test action: Query MediaMTX health (GET http://localhost:9997/v3/paths/list)
  - Test action: Query media-service health (GET http://localhost:8080/health)
  - Test action: Query sts-service health (GET http://localhost:3000/health)
  - Test validation: All services return 200 OK within 30 seconds of startup
- [ ] T029 [P] [US2] Add test_socketio_connection_established() to test_dual_compose_service_communication.py
  - Test setup: Start dual_compose_env fixture
  - Test action: Create python-socketio client, connect to http://localhost:3000
  - Test validation: Socket.IO handshake completes successfully
  - Test teardown: Disconnect client

**Verification**: Run `pytest tests/e2e/test_dual_compose_service_communication.py` - tests MUST FAIL if ports not exposed or health checks not configured

### Implementation for User Story 2

- [ ] T030 [US2] Update DockerComposeManager.wait_for_health() in tests/e2e/helpers/docker_compose_manager.py to poll health check endpoints with retries
- [ ] T031 [US2] Update dual_compose_env fixture in tests/e2e/conftest.py to validate all health checks before yielding to tests
- [ ] T032 [US2] Add timeout configuration to dual_compose_env fixture (HEALTH_CHECK_TIMEOUT=30s, MAX_RETRIES=10)

**Checkpoint**: User Story 2 tests pass - services reachable via localhost ports (run `pytest tests/e2e/test_dual_compose_service_communication.py -v`)

---

## Phase 5: User Story 3 - Real STS Processing (Priority: P1)

**Goal**: Validate real ASR → Translation → TTS pipeline produces accurate transcripts, translations, dubbed audio

**Independent Test**: Send audio fragment via Socket.IO client, verify fragment:processed event contains real transcript + translation + dubbed_audio

### Tests for User Story 3 (MANDATORY - Test-First) ✅

**Coverage Target for US3**: Real STS module integration (no mocking)

- [ ] T033 [P] [US3] Create `tests/e2e/test_dual_compose_real_sts_processing.py` with test_sts_processes_real_audio()
  - Test setup: Start sts_compose_env fixture (STS service only, no media-service)
  - Test action: Create Socket.IO client, connect to http://localhost:3000
  - Test action: Extract 6-second audio from test fixture (segment with "One, two, three, four, five, six")
  - Test action: Emit fragment:data event with audio_data (base64 PCM), source=en, target=es
  - Test validation: Wait for fragment:processed event (timeout 20s for real STS latency)
  - Test validation: Verify transcript contains expected text (ASR accuracy check)
  - Test validation: Verify translated_text is Spanish (Translation check)
  - Test validation: Verify dubbed_audio field is present and non-empty (TTS check)
- [ ] T034 [P] [US3] Add test_sts_fragment_processing_contract() to test_dual_compose_real_sts_processing.py
  - Test setup: Start sts_compose_env fixture
  - Test action: Send fragment:data event with known audio segment
  - Test validation: Verify fragment:processed event schema matches spec 016 (fragment_id, transcript, translated_text, dubbed_audio, processing_time_ms)
  - Test validation: Verify processing_time_ms is reasonable (<15000ms for 6s fragment on CPU)

**Verification**: Run `pytest tests/e2e/test_dual_compose_real_sts_processing.py` - tests MUST FAIL if STS service not running or modules not configured

### Implementation for User Story 3

- [ ] T035 [US3] Implement SocketIOMonitor.capture_events() in tests/e2e/helpers/socketio_monitor.py (async queue for event collection)
- [ ] T036 [US3] Implement SocketIOMonitor.wait_for_event() in tests/e2e/helpers/socketio_monitor.py (wait for specific event type with timeout)
- [ ] T037 [US3] Add audio extraction utility to tests/e2e/helpers/stream_analyzer.py (extract 6s segment from test fixture using ffmpeg)
- [ ] T038 [US3] Update test_sts_processes_real_audio() to validate transcript content against expected counting phrases (ASR accuracy assertion)

**Checkpoint**: User Story 3 tests pass - real STS processing validated (run `pytest tests/e2e/test_dual_compose_real_sts_processing.py -v`)

---

## Phase 6: User Story 4 - Test Fixture Management (Priority: P2)

**Goal**: Validate deterministic test fixtures are published correctly and cleaned up after tests

**Independent Test**: Publish fixture to MediaMTX, verify stream active, verify cleanup on teardown

### Tests for User Story 4 (MANDATORY - Test-First) ✅

**Coverage Target for US4**: Fixture publishing and lifecycle management

- [ ] T039 [P] [US4] Create `tests/e2e/test_dual_compose_fixture_management.py` with test_fixture_properties()
  - Test action: Load 30s-counting-english.mp4 with ffprobe
  - Test validation: Verify duration=30s (+/- 100ms), video_codec=h264, audio_codec=aac, sample_rate=48000
  - Test validation: Verify file exists and is readable
- [ ] T040 [P] [US4] Add test_publish_fixture_to_mediamtx() to test_dual_compose_fixture_management.py
  - Test setup: Start media_compose_env fixture (MediaMTX only)
  - Test action: Use publish_test_fixture() fixture to publish stream to rtsp://localhost:8554/live/test_fixture/in
  - Test action: Query MediaMTX API for active streams (GET http://localhost:9997/v3/paths/list)
  - Test validation: Verify stream "test_fixture/in" is active within 2 seconds
  - Test validation: Verify MediaMTX reports correct stream metadata
  - Test teardown: Verify ffmpeg process terminated and stream removed after fixture cleanup
- [ ] T041 [P] [US4] Add test_fixture_cleanup_on_failure() to test_dual_compose_fixture_management.py
  - Test setup: Start media_compose_env fixture
  - Test action: Start publish_test_fixture(), then raise exception mid-test
  - Test validation: Verify ffmpeg process is killed even when test fails (no orphaned processes)

**Verification**: Run `pytest tests/e2e/test_dual_compose_fixture_management.py` - tests MUST FAIL if fixture missing or StreamPublisher not implemented

### Implementation for User Story 4

- [ ] T042 [US4] Implement StreamPublisher.start() in tests/e2e/helpers/stream_publisher.py (ffmpeg subprocess publishing RTSP stream)
- [ ] T043 [US4] Implement StreamPublisher.stop() in tests/e2e/helpers/stream_publisher.py (SIGTERM to ffmpeg, verify process exit)
- [ ] T044 [US4] Update publish_test_fixture() in tests/e2e/conftest.py to use StreamPublisher with unique stream names (f"test_{request.node.name}_{int(time.time())}")
- [ ] T045 [US4] Add cleanup handler to publish_test_fixture() using pytest finalizer (ensure ffmpeg killed even on test failure)

**Checkpoint**: User Story 4 tests pass - fixture management validated (run `pytest tests/e2e/test_dual_compose_fixture_management.py -v`)

---

## Phase 7: User Story 5 - Separate Docker Compose Files (Priority: P2)

**Goal**: Validate each docker-compose file starts independently and together without conflicts

**Independent Test**: Start media-service compose alone, then sts-service compose alone, then both together

### Tests for User Story 5 (MANDATORY - Test-First) ✅

**Coverage Target for US5**: Independent composition lifecycle management

- [ ] T046 [P] [US5] Create `tests/e2e/test_dual_compose_compose_lifecycle.py` with test_media_service_compose_starts()
  - Test action: Start media_compose_env fixture (media-service + MediaMTX only)
  - Test validation: Verify MediaMTX container running (docker ps | grep e2e-media-mediamtx)
  - Test validation: Verify media-service container running (docker ps | grep e2e-media-service)
  - Test validation: Verify ports exposed: 8554 (RTSP), 1935 (RTMP), 8080 (metrics)
  - Test teardown: Stop media_compose_env, verify containers stopped
- [ ] T047 [P] [US5] Add test_sts_service_compose_starts() to test_dual_compose_compose_lifecycle.py
  - Test action: Start sts_compose_env fixture (sts-service only)
  - Test validation: Verify sts-service container running (docker ps | grep e2e-sts-service)
  - Test validation: Verify port 3000 exposed and Socket.IO server reachable
  - Test validation: Verify model-cache volume created
  - Test teardown: Stop sts_compose_env, verify container stopped
- [ ] T048 [P] [US5] Add test_dual_compose_starts_together() to test_dual_compose_compose_lifecycle.py
  - Test action: Start dual_compose_env fixture (both compositions)
  - Test validation: Verify all 3 containers running (MediaMTX, media-service, sts-service)
  - Test validation: Verify no port conflicts (all services healthy)
  - Test validation: Verify services can communicate (media-service → STS health check succeeds)

**Verification**: Run `pytest tests/e2e/test_dual_compose_compose_lifecycle.py` - tests MUST FAIL if docker-compose files have errors or dependencies misconfigured

### Implementation for User Story 5

- [ ] T049 [US5] Implement DockerComposeManager.start() in tests/e2e/helpers/docker_compose_manager.py (docker-compose up -d with project naming)
- [ ] T050 [US5] Implement DockerComposeManager.stop() in tests/e2e/helpers/docker_compose_manager.py (docker-compose down -v)
- [ ] T051 [US5] Implement DockerComposeManager.get_logs() in tests/e2e/helpers/docker_compose_manager.py (docker-compose logs for debugging)
- [ ] T052 [US5] Update media_compose_env in tests/e2e/conftest.py to use DockerComposeManager with apps/media-service/docker-compose.e2e.yml
- [ ] T053 [US5] Update sts_compose_env in tests/e2e/conftest.py to use DockerComposeManager with apps/sts-service/docker-compose.e2e.yml
- [ ] T054 [US5] Add project name separation to avoid network conflicts (media_compose: project="e2e-media", sts_compose: project="e2e-sts")

**Checkpoint**: User Story 5 tests pass - compositions start independently and together (run `pytest tests/e2e/test_dual_compose_compose_lifecycle.py -v`)

---

## Phase 8: User Story 6 - Output Stream Validation (Priority: P2)

**Goal**: Validate output RTMP stream is playable, contains dubbed audio (not original), A/V sync preserved

**Independent Test**: Run full pipeline, inspect output stream with ffprobe and audio fingerprinting

### Tests for User Story 6 (MANDATORY - Test-First) ✅

**Coverage Target for US6**: Output quality validation (playability, dubbed audio verification, A/V sync)

- [ ] T055 [P] [US6] Create `tests/e2e/test_dual_compose_output_validation.py` with test_output_stream_is_playable()
  - Test setup: Start dual_compose_env, run full pipeline (publish 30s fixture)
  - Test action: Wait for pipeline completion (180s timeout)
  - Test action: Inspect output stream with ffprobe (rtmp://localhost:1935/live/test_output/out)
  - Test validation: Verify stream has 2 tracks (video + audio)
  - Test validation: Verify video codec is h264, audio codec is aac
  - Test validation: Verify duration matches input (30s +/- 500ms)
- [ ] T056 [P] [US6] Add test_output_audio_is_dubbed() to test_dual_compose_output_validation.py
  - Test setup: Start dual_compose_env, run full pipeline with Socket.IO monitor
  - Test validation (primary): Verify all 5 fragment:processed events received with dubbed_audio field
  - Test action (secondary): Extract output audio, compute spectral fingerprint
  - Test action (secondary): Extract original audio, compute spectral fingerprint
  - Test validation (secondary): Verify fingerprints differ (audio is not identical to original)
- [ ] T057 [P] [US6] Add test_output_av_sync_preserved() to test_dual_compose_output_validation.py
  - Test setup: Start dual_compose_env, run full pipeline
  - Test action: Extract PTS values from output stream using ffprobe (video + audio tracks)
  - Test validation: Verify A/V sync delta < 120ms throughout stream
  - Test validation: Query metrics endpoint for worker_av_sync_delta_ms, verify < 120ms

**Verification**: Run `pytest tests/e2e/test_dual_compose_output_validation.py` - tests MUST FAIL if output stream invalid or audio not dubbed

### Implementation for User Story 6

- [ ] T058 [US6] Implement StreamAnalyzer.inspect_stream() in tests/e2e/helpers/stream_analyzer.py (ffprobe wrapper, return codec, duration, track info)
- [ ] T059 [US6] Implement StreamAnalyzer.extract_pts() in tests/e2e/helpers/stream_analyzer.py (ffprobe PTS extraction for A/V sync analysis)
- [ ] T060 [US6] Implement StreamAnalyzer.compute_audio_fingerprint() in tests/e2e/helpers/stream_analyzer.py (spectral hash using numpy FFT or chromaprint)
- [ ] T061 [US6] Update test_output_audio_is_dubbed() to use SocketIOMonitor for primary validation (fragment:processed events)
- [ ] T062 [US6] Add PrometheusMetricsParser.get_av_sync_delta() in tests/e2e/helpers/metrics_parser.py (parse worker_av_sync_delta_ms metric)

**Checkpoint**: User Story 6 tests pass - output stream validated for quality and dubbing (run `pytest tests/e2e/test_dual_compose_output_validation.py -v`)

---

## Phase 9: User Story 7 - Environment Configuration (Priority: P3)

**Goal**: Validate environment variables configure service endpoints correctly, enable flexible deployment

**Independent Test**: Override environment variables, verify services use custom ports and URLs

### Tests for User Story 7 (MANDATORY - Test-First) ✅

**Coverage Target for US7**: Configuration flexibility and environment variable substitution

- [ ] T063 [P] [US7] Create `tests/e2e/test_dual_compose_env_configuration.py` with test_env_config_overrides()
  - Test setup: Override environment variables (MEDIAMTX_RTSP_PORT=9554, STS_PORT=4000)
  - Test action: Start dual_compose_env with custom env
  - Test validation: Verify MediaMTX RTSP listening on port 9554 (not 8554)
  - Test validation: Verify STS service listening on port 4000 (not 3000)
  - Test validation: Verify media-service connects to STS at custom port
  - Test teardown: Stop compositions, restore default env
- [ ] T064 [P] [US7] Add test_default_env_values() to test_dual_compose_env_configuration.py
  - Test setup: Start dual_compose_env without env overrides
  - Test validation: Verify default ports used (8554 RTSP, 1935 RTMP, 3000 STS, 8080 media)
  - Test validation: Verify STS_SERVICE_URL defaults to http://host.docker.internal:3000
- [ ] T065 [P] [US7] Add test_env_file_loading() to test_dual_compose_env_configuration.py
  - Test setup: Create .env.dual-compose in tests/e2e/ with custom values
  - Test action: Start dual_compose_env (should load .env.dual-compose)
  - Test validation: Verify custom values applied from env file
  - Test teardown: Remove .env.dual-compose

**Verification**: Run `pytest tests/e2e/test_dual_compose_env_configuration.py` - tests MUST FAIL if docker-compose files don't support environment variable substitution

### Implementation for User Story 7

- [ ] T066 [US7] Update apps/media-service/docker-compose.e2e.yml to use environment variable defaults (${MEDIAMTX_RTSP_PORT:-8554})
- [ ] T067 [US7] Update apps/sts-service/docker-compose.e2e.yml to use environment variable defaults (${STS_PORT:-3000})
- [ ] T068 [US7] Update DockerComposeManager to support env parameter (pass custom env dict to docker-compose)
- [ ] T069 [US7] Update dual_compose_env fixture to accept env_overrides parameter (pytest.mark.parametrize support)

**Checkpoint**: User Story 7 tests pass - environment configuration validated (run `pytest tests/e2e/test_dual_compose_env_configuration.py -v`)

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories, CI integration, documentation

- [ ] T070 [P] Create `tests/e2e/README.md` documenting dual-compose E2E test execution (prerequisites, running tests, debugging)
- [ ] T071 [P] Add pytest markers to tests/e2e/pytest.ini (e2e, slow, requires_docker, requires_sts)
- [ ] T072 [P] Create Makefile target `make e2e-test-dual-compose` for running dual-compose E2E suite
- [ ] T073 [P] Add CI configuration for dual-compose E2E tests (.github/workflows/e2e-dual-compose.yml or equivalent)
- [ ] T074 [P] Update root README.md with link to dual-compose E2E tests (tests/e2e/README.md)
- [ ] T075 Document troubleshooting common issues in tests/e2e/README.md (port conflicts, model download failures, timeout tuning)
- [ ] T076 Add pytest timeout plugin configuration (default 300s per test, 600s for full pipeline test)
- [ ] T077 Validate all tests pass reliably (run suite 10 times, verify 95% pass rate)
- [ ] T078 Create quickstart.md validation checklist (verify all commands work, all paths valid)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-9)**: All depend on Foundational phase completion
  - US1 (Full Pipeline): Can start after Foundational - no dependencies on other stories
  - US2 (Service Communication): Can start after Foundational - no dependencies on other stories (can run parallel with US1)
  - US3 (Real STS Processing): Can start after Foundational - no dependencies on other stories (can run parallel with US1/US2)
  - US4 (Fixture Management): Can start after Foundational - no dependencies on other stories (can run parallel with US1/US2/US3)
  - US5 (Compose Lifecycle): Depends on US1 (docker-compose files must be complete) - can run after US1
  - US6 (Output Validation): Depends on US1 (full pipeline must work) - can run after US1
  - US7 (Env Configuration): Depends on US1 (compositions must start) - can run after US1
- **Polish (Phase 10)**: Depends on all user stories P1 + P2 being complete

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Helper utilities before test implementation
- Docker compose configuration before test validation
- Story tests pass before moving to next priority

### Parallel Opportunities

- All Setup tasks (T001-T004) can run in parallel
- Most Foundational tasks (T007-T015) can run in parallel (docker-compose files + helpers)
- US1, US2, US3, US4 test creation (T017, T028, T033, T039) can run in parallel
- US2, US3, US4 implementation can proceed in parallel with US1
- US5, US6, US7 can run in parallel after US1 completes
- All Polish tasks (T070-T078) can run in parallel

---

## Implementation Strategy

### MVP First (P1 User Stories Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T016) - CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T017-T027) - Full pipeline E2E
4. Complete Phase 4: User Story 2 (T028-T032) - Service communication
5. Complete Phase 5: User Story 3 (T033-T038) - Real STS processing
6. **STOP and VALIDATE**: Run full P1 test suite (`pytest tests/e2e/ -m "not slow"`)
7. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP - full pipeline works!)
3. Add User Stories 2-3 → Test independently → Deploy/Demo (P1 complete)
4. Add User Stories 4-6 → Test independently → Deploy/Demo (P2 complete - output validation)
5. Add User Story 7 → Test independently → Deploy/Demo (P3 complete - production ready)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T016)
2. Once Foundational is done:
   - Developer A: User Story 1 (T017-T027) - Full pipeline
   - Developer B: User Story 2 + 3 (T028-T038) - Service validation
   - Developer C: User Story 4 (T039-T045) - Fixture management
3. After US1 complete:
   - Developer A: User Story 5 (T046-T054) - Compose lifecycle
   - Developer B: User Story 6 (T055-T062) - Output validation
   - Developer C: User Story 7 (T063-T069) - Env configuration
4. Polish phase: All developers collaborate on documentation + CI (T070-T078)

---

## Notes

- [P] tasks = different files, no dependencies, safe to parallelize
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests MUST fail before implementation (verify with `pytest --collect-only`)
- Session-scoped fixtures (dual_compose_env) mean tests share Docker environments - use unique stream names
- Real STS processing takes 10-17s per fragment (5 fragments = ~1min total, plan for 180s timeout)
- Checkpoints are informational - run automated tests to validate, continue automatically
- Docker Compose v2 required (docker-compose or docker compose command)
- ffmpeg required for fixture publishing and stream inspection
- Test fixture (30s-counting-english.mp4) can be generated if not provided (see plan.md fixture creation strategy)
