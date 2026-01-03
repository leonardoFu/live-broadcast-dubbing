# Feature Specification: Full Services E2E Testing

**Feature Branch**: `021-production-e2e-testing`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "Make test_full_pipeline.py pass using real media-service and STS-service via Docker Compose manager on localhost/macOS with CPU - no mocking"

## Overview

This specification defines E2E testing that validates the complete dubbing pipeline using **real, unmodified services** running locally via Docker Compose. The goal is simple: make `tests/e2e/test_full_pipeline.py` pass.

**Key principle: No mocking, real services only**

The only differences from production are environmental:
- **Environment**: localhost/macOS instead of cloud infrastructure (EC2 + RunPod)
- **Hardware**: CPU-only instead of GPU for STS-service
- **Orchestration**: Docker Compose (via `docker_compose_manager.py`) instead of production deployment tools

Everything else is **identical** to production:
- Same media-service code (GStreamer pipeline, segmentation, A/V sync)
- Same STS-service code (real Whisper ASR, real Translation, real Coqui TTS)
- Same Socket.IO protocol (spec 016)
- Same RTMP input/output flow
- Same error handling and resilience patterns

This approach validates the actual production code path without shortcuts, providing confidence that production deployment will work correctly.

**Related Specs**:
- [specs/003-gstreamer-stream-worker](../003-gstreamer-stream-worker/spec.md) - media-service architecture
- [specs/004-sts-pipeline-design.md](../004-sts-pipeline-design.md) - STS service architecture
- [specs/016-websocket-audio-protocol](../016-websocket-audio-protocol.md) - Socket.IO protocol

**Related Test Files**:
- [tests/e2e/test_full_pipeline.py](../../tests/e2e/test_full_pipeline.py) - Main E2E test (target to pass)
- [tests/e2e/helpers/docker_compose_manager.py](../../tests/e2e/helpers/docker_compose_manager.py) - Docker Compose lifecycle management

## User Scenarios & Testing

### User Story 1 - Docker Compose Service Management (Priority: P1)

The test infrastructure uses `DualComposeManager` from `docker_compose_manager.py` to start media-service and STS-service as separate Docker Compose environments. Each service runs with its dependencies (MediaMTX for media-service) and communicates via localhost port exposure.

**Why this priority**: This validates the core E2E test setup - services must start, become healthy, and communicate before pipeline testing can begin.

**Independent Test**: Test service startup and health checks
- **Unit test**: N/A (infrastructure configuration)
- **Contract test**: Validate `DualComposeManager` correctly starts both compositions and waits for health endpoints
- **Integration test**: `test_docker_compose_files_exist()` in test_full_pipeline.py validates compose files exist
- **Success criteria**: Both Docker Compose environments start successfully, health checks pass within 60 seconds, services expose required ports to localhost

**Acceptance Scenarios**:

1. **Given** `DualComposeManager` initialized with media and STS compose files, **When** `start_all()` is called, **Then** STS composition starts first, media composition starts second, both report healthy
2. **Given** both compositions running, **When** pytest queries health endpoints, **Then** media-service returns 200 OK at `http://localhost:8080/health` and STS-service returns 200 OK at `http://localhost:3000/health`
3. **Given** media-service configured with `STS_SERVICE_URL=http://host.docker.internal:3000`, **When** media-service attempts Socket.IO connection, **Then** connection succeeds via localhost port mapping
4. **Given** test completes or fails, **When** `stop_all()` is called, **Then** both compositions stop cleanly, volumes removed, logs collected if test failed

---

### User Story 2 - Full Pipeline E2E: test_full_pipeline_media_to_sts_to_output (Priority: P1)

The test `test_full_pipeline_media_to_sts_to_output()` in `test_full_pipeline.py` validates the complete dubbing pipeline with **real, unmodified services**: test fixture published to MediaMTX, media-service ingests RTMP, segments sent to real STS service (Whisper ASR + Translation + Coqui TTS), dubbed audio returns, A/V remux, RTMP output stream.

**Why this priority**: This is the test that must pass. It validates the entire system working together with production code on localhost.

**Independent Test**: Test with 1-min NFL fixture published via `publish_test_fixture` pytest fixture
- **Unit test**: N/A (end-to-end integration test)
- **Contract test**: Verify Socket.IO events match spec 016 schemas throughout pipeline (monitored via `sts_monitor` fixture)
- **Integration test**: `test_full_pipeline_media_to_sts_to_output()` validates complete workflow
- **Success criteria**: 60-second test video processed end-to-end, 10 segments (6s each) sent to STS and received back with real dubbed audio, RTMP output playable, pipeline completes within 300 seconds

**Acceptance Scenarios** (from test_full_pipeline.py):

1. **Given** both compose environments started via `dual_compose_env` fixture, **When** 1-min NFL fixture published to MediaMTX RTMP, **Then** stream appears in MediaMTX API within 10 seconds
2. **Given** stream active in MediaMTX, **When** media-service WorkerRunner starts, **Then** worker metrics appear at `http://localhost:8080/metrics` within 10 seconds
3. **Given** WorkerRunner processing stream, **When** audio segments accumulate, **Then** `fragment:processed` events received via `sts_monitor` fixture (10 expected for 60s video)
4. **Given** `fragment:processed` events received, **When** event data inspected, **Then** each event contains `dubbed_audio`, `transcript`, and `translated_text` fields (real STS processing, not echo)
5. **Given** all 10 fragments processed, **When** output stream inspected via ffprobe, **Then** output available at `rtmp://localhost:1935/live/{stream_path}/out`, duration 60s ± 1s, codecs H.264 + AAC
6. **Given** output stream verified, **When** metrics checked, **Then** `media_service_worker_segments_processed_total` shows 10 audio segments processed, A/V sync delta < 120ms

---

### User Story 3 - Service Communication via Localhost Port Mapping (Priority: P1)

Services communicate via localhost port mapping: Docker Compose exposes service ports to host, media-service connects to STS-service using `http://host.docker.internal:3000` (or `http://localhost:3000` if running on host network).

**Why this priority**: Service communication must work for the pipeline to function. Localhost port mapping is the standard Docker Compose pattern for local development.

**Independent Test**: Test media-service can reach STS-service health endpoint
- **Unit test**: N/A (infrastructure configuration)
- **Contract test**: Validate media-service Socket.IO client can connect to STS-service on localhost
- **Integration test**: Part of `test_full_pipeline_media_to_sts_to_output()` - connection verified when fragments are processed
- **Success criteria**: media-service successfully connects to STS-service, Socket.IO handshake completes, fragments are sent and received

**Acceptance Scenarios**:

1. **Given** STS-service running with port 3000 exposed to localhost, **When** curl queries `http://localhost:3000/health`, **Then** STS-service returns 200 OK
2. **Given** media-service configured with `STS_SERVICE_URL=http://host.docker.internal:3000`, **When** media-service starts and attempts Socket.IO connection, **Then** connection succeeds within 5 seconds
3. **Given** Socket.IO connection established, **When** media-service emits `fragment:data` event, **Then** STS-service receives event and processes fragment
4. **Given** pytest test framework, **When** tests query `http://localhost:8080/metrics` and `http://localhost:3000/health`, **Then** both services respond successfully (validates port exposure)

---

### User Story 4 - Real STS Processing: No Mocking, CPU-based (Priority: P1)

The E2E test validates that **real, unmodified STS-service** (Whisper ASR + Translation + Coqui TTS) processes audio fragments and returns dubbed audio. No mocking, no shortcuts - same code as production, running on CPU instead of GPU.

**Why this priority**: This is the "no mocking" principle - we test the actual production code path to catch real integration issues.

**Independent Test**: Verify `fragment:processed` events contain real transcripts and dubbed audio
- **Unit test**: Tested in individual STS module specs (005-ASR, 006-Translation, 008-TTS)
- **Contract test**: Monitored via `sts_monitor` fixture in test_full_pipeline.py
- **Integration test**: Part of `test_full_pipeline_media_to_sts_to_output()` - validates each `fragment:processed` event
- **Success criteria**: All 10 fragments return with `dubbed_audio` (base64 audio), `transcript` (English text), and `translated_text` (Spanish text)

**Acceptance Scenarios** (from test assertions in test_full_pipeline.py):

1. **Given** `fragment:processed` event received, **When** event data inspected, **Then** `dubbed_audio` field exists, is not None, and has length > 0 (real TTS output, not empty/mock)
2. **Given** `fragment:processed` event data, **When** `transcript` field inspected, **Then** field contains English text (real Whisper ASR output)
3. **Given** `fragment:processed` event data, **When** `translated_text` field inspected, **Then** field contains Spanish text (real Translation output)
4. **Given** 10 fragments processed in test, **When** test completes, **Then** all 10 events have valid `dubbed_audio`, `transcript`, and `translated_text` (no failures, no echo responses)

---

### User Story 5 - Test Fixture Validation (Priority: P1)

The test validates that the test fixture (`1-min-nfl.mp4`) exists and has expected properties before running the pipeline test.

**Why this priority**: The test cannot run without a valid fixture - this is a prerequisite check.

**Independent Test**: `test_test_fixture_exists()` in test_full_pipeline.py
- **Unit test**: N/A (file validation)
- **Contract test**: Validates fixture has H.264 video, AAC audio, 60s duration
- **Integration test**: `test_test_fixture_exists()` uses ffprobe to inspect fixture
- **Success criteria**: Fixture exists at `tests/e2e/fixtures/test-streams/1-min-nfl.mp4`, duration 60s ± 1s, correct codecs

**Acceptance Scenarios** (from test_test_fixture_exists):

1. **Given** test suite starts, **When** `test_test_fixture_exists()` runs, **Then** fixture file exists at expected path
2. **Given** fixture file exists, **When** ffprobe inspects file, **Then** duration is 59-61 seconds
3. **Given** ffprobe output, **When** streams inspected, **Then** 1 video stream (H.264) and 1 audio stream (AAC @ 44.1kHz) present
4. **Given** fixture validated, **When** main pipeline test runs, **Then** fixture is published to MediaMTX via `publish_test_fixture` fixture

---

### User Story 6 - Output Stream Validation (Priority: P1)

The test validates that the output RTMP stream is playable and contains dubbed audio (not original audio passthrough).

**Why this priority**: This proves the dubbing pipeline actually worked end-to-end.

**Independent Test**: Part of `test_full_pipeline_media_to_sts_to_output()` - output validation steps
- **Unit test**: N/A (end-to-end output validation)
- **Contract test**: N/A (output validation)
- **Integration test**: ffprobe inspection + metrics validation in test_full_pipeline.py
- **Success criteria**: Output stream playable, duration matches input (60s ± 1s), codecs correct (H.264 + AAC), A/V sync < 120ms

**Acceptance Scenarios** (from test output validation steps):

1. **Given** all fragments processed, **When** ffprobe inspects `rtmp://localhost:1935/live/{stream_path}/out`, **Then** stream info contains valid format and streams
2. **Given** stream info retrieved, **When** streams inspected, **Then** 1 video stream (H.264) and 1 audio stream (AAC) present
3. **Given** stream duration checked, **When** compared to input, **Then** duration is 59-61 seconds (matches 60s input ± tolerance)
4. **Given** metrics queried, **When** A/V sync metric inspected, **Then** `worker_av_sync_delta_ms` < 120ms (if metric available)

---

### Edge Cases

- **What happens when STS-service is not reachable?** media-service retries Socket.IO connection, uses fallback audio for in-flight fragments. E2E test should fail if unable to connect (validates connectivity requirement).
- **What happens when test fixture is missing?** `test_test_fixture_exists()` fails, subsequent tests are skipped.
- **What happens when STS processing is very slow (>15s per fragment)?** Test may timeout at 300s total. This validates timeout handling - if STS is too slow, test fails (expected behavior).
- **What happens when MediaMTX is not running?** Stream publish fails, test fails fast with clear error message from `publish_test_fixture` fixture.
- **What happens when port conflicts occur (1935, 3000, 8080 already in use)?** Docker Compose fails to start, `DualComposeManager` reports error, test is skipped with clear message.
- **What happens when Docker Compose files are missing/invalid?** `test_docker_compose_files_exist()` fails, subsequent tests are skipped.

## Requirements

### Functional Requirements

**Goal: Make test_full_pipeline.py pass (P1)**

- **FR-001**: Test `test_full_pipeline_media_to_sts_to_output()` MUST pass, validating complete pipeline end-to-end
- **FR-002**: Test fixtures `test_docker_compose_files_exist()` and `test_test_fixture_exists()` MUST pass as prerequisites

**Docker Compose Service Management (P1)**

- **FR-003**: `DualComposeManager` MUST start media-service compose (MediaMTX + media-service) and STS-service compose separately
- **FR-004**: Both compose environments MUST expose required ports to localhost (MediaMTX: 1935, 8889; media-service: 8080; STS-service: 3000)
- **FR-005**: `DualComposeManager` MUST wait for health checks to pass before running tests (timeout: 60 seconds)
- **FR-006**: `DualComposeManager` MUST clean up both compose environments after tests (even on failure)

**Service Communication (P1)**

- **FR-007**: media-service MUST connect to STS-service via localhost port mapping (e.g., `http://host.docker.internal:3000` or `http://localhost:3000`)
- **FR-008**: Socket.IO connection MUST establish successfully between media-service and STS-service
- **FR-009**: Health check endpoints MUST be accessible from pytest via localhost (`http://localhost:8080/health`, `http://localhost:3000/health`)

**Real Services - No Mocking (P1)**

- **FR-010**: STS-service MUST use real Whisper ASR (not mocked/echo)
- **FR-011**: STS-service MUST use real Translation module (not mocked/echo)
- **FR-012**: STS-service MUST use real Coqui TTS (not mocked/echo)
- **FR-013**: media-service MUST use real GStreamer pipeline (not mocked)
- **FR-014**: The ONLY environmental differences from production are: CPU vs GPU, localhost vs cloud, Docker Compose vs production orchestration

**Pipeline Validation (P1)**

- **FR-015**: Test MUST publish 1-min NFL fixture to MediaMTX via `publish_test_fixture` pytest fixture
- **FR-016**: Test MUST verify stream appears in MediaMTX API within 10 seconds
- **FR-017**: Test MUST verify media-service WorkerRunner connects and starts processing (metrics appear at `/metrics`)
- **FR-018**: Test MUST receive 10 `fragment:processed` events (for 60s video @ 6s segments) via `sts_monitor` fixture
- **FR-019**: Each `fragment:processed` event MUST contain `dubbed_audio`, `transcript`, and `translated_text` fields (validates real STS processing)
- **FR-020**: Test MUST verify output stream at `rtmp://localhost:1935/live/{stream_path}/out` using ffprobe
- **FR-021**: Output stream MUST have H.264 video and AAC audio, duration 60s ± 1s
- **FR-022**: Metrics MUST show 10 processed audio segments
- **FR-023**: Test MUST complete within 300 seconds total

**Test Fixture (P1)**

- **FR-024**: Test fixture MUST exist at `tests/e2e/fixtures/test-streams/1-min-nfl.mp4`
- **FR-025**: Fixture MUST be 60-second video with H.264 video and AAC audio @ 44.1kHz
- **FR-026**: `test_test_fixture_exists()` MUST validate fixture before pipeline test runs

### Key Entities

- **DualComposeManager**: Python class from `docker_compose_manager.py` managing two separate Docker Compose environments
- **media-service Docker Compose**: Runs MediaMTX + media-service containers (from `apps/media-service/docker-compose.yml`)
- **STS-service Docker Compose**: Runs STS-service container (from `apps/sts-service/docker-compose.yml`)
- **Test Fixture**: `1-min-nfl.mp4` - 60-second video with H.264 video and AAC audio @ 44.1kHz
- **E2E Test Suite**: `tests/e2e/test_full_pipeline.py` - orchestrates service lifecycle and validates full pipeline
- **Test Helpers**: `sts_monitor` (Socket.IO monitoring), `publish_test_fixture` (RTMP publishing), `stream_analyzer` (ffprobe wrapper), `metrics_parser` (Prometheus metrics)

## Success Criteria

### Measurable Outcomes

The ultimate success criterion is simple: **`test_full_pipeline_media_to_sts_to_output()` passes**.

Specifically:

- **SC-001**: Test completes successfully within 300 seconds
- **SC-002**: All 10 `fragment:processed` events received with valid `dubbed_audio`, `transcript`, and `translated_text` (real STS processing verified)
- **SC-003**: Output RTMP stream exists and is playable (H.264 video + AAC audio)
- **SC-004**: Output duration matches input (60s ± 1s tolerance)
- **SC-005**: Metrics show 10 processed audio segments
- **SC-006**: No mocking used - real Whisper ASR, real Translation, real Coqui TTS, real GStreamer pipeline
- **SC-007**: Test runs reliably on localhost/macOS with CPU (no GPU required)
- **SC-008**: Test infrastructure (`DualComposeManager`, fixtures, helpers) is reusable for additional E2E tests

## Architecture Decisions

### Decision 1: Use Existing DualComposeManager (Not Independent Docker Containers)

**Choice**: Use `DualComposeManager` from `docker_compose_manager.py` to manage two separate Docker Compose environments
**Rationale**: Infrastructure already exists and works. Simpler than managing individual containers with `docker run`. Reuses existing compose files (`docker-compose.yml`) for both services.

### Decision 2: Localhost Port Mapping (Not Bridge Networks)

**Choice**: Services communicate via localhost port exposure (media-service → `http://host.docker.internal:3000` → STS-service)
**Rationale**: Standard Docker Compose pattern for local development. No custom networks needed - services expose ports to localhost, pytest and containers access via localhost/host.docker.internal.

### Decision 3: No Mocking Whatsoever

**Choice**: Use real, unmodified services for E2E testing - same code as production
**Rationale**: The ONLY way to validate production code path is to test production code. Environmental differences (CPU vs GPU, localhost vs cloud) are acceptable - code must be identical. This catches real integration bugs that mocks hide.

### Decision 4: 60-Second Test Fixture (1-min-nfl.mp4)

**Choice**: Use existing 1-minute NFL video fixture (10 segments @ 6s each)
**Rationale**: Fixture already exists in `tests/e2e/fixtures/test-streams/`. Long enough to validate multi-segment processing and A/V sync. Real audio content validates ASR/Translation/TTS pipeline end-to-end.

### Decision 5: CPU-only STS Processing

**Choice**: Run STS-service on CPU (not GPU) for E2E tests
**Rationale**: Enables testing on developer machines (macOS) without GPU. Slower (5-15s per fragment vs <1s on GPU) but acceptable for E2E validation. Production uses GPU - this is an environmental difference only, code is identical.

### Decision 6: Session-Scoped Fixtures

**Choice**: Docker Compose environments use session scope - start once for all E2E tests
**Rationale**: STS model loading is expensive (30s+), session scope amortizes cost. Services are stateless between tests, so unique stream names per test provide isolation without restart overhead.

### Decision 7: Single Target Test

**Choice**: Focus on making `test_full_pipeline_media_to_sts_to_output()` pass
**Rationale**: Simplicity. One clear goal makes success criteria unambiguous. Additional E2E tests can be added later using the same infrastructure (DualComposeManager, fixtures, helpers).

## Assumptions

- Docker Engine and Docker Compose are installed on test host (macOS)
- Test fixture `1-min-nfl.mp4` exists at `tests/e2e/fixtures/test-streams/1-min-nfl.mp4`
- STS-service can run on CPU without GPU (slower but functional)
- ffmpeg is available for stream publishing and inspection
- Sufficient resources available: 4 CPU cores, 8GB RAM minimum
- Model downloads (Whisper, TTS models) are cached in Docker volumes (or downloaded on first run)
- Ports 1935, 3000, 8080, 8889 are available on localhost

## Dependencies

- **Docker Compose Files**:
  - `apps/media-service/docker-compose.yml` (media-service + MediaMTX)
  - `apps/sts-service/docker-compose.yml` (STS-service)
- **Python Test Infrastructure**:
  - `tests/e2e/helpers/docker_compose_manager.py` (DualComposeManager)
  - `tests/e2e/conftest.py` (pytest fixtures: dual_compose_env, publish_test_fixture, sts_monitor)
  - `tests/e2e/helpers/stream_analyzer.py` (ffprobe wrapper)
  - `tests/e2e/helpers/metrics_parser.py` (Prometheus metrics parser)
  - `tests/e2e/helpers/socketio_monitor.py` (Socket.IO event monitor)
- **Python Libraries**: pytest, pytest-asyncio, httpx, python-socketio[client], prometheus_client
- **Test Fixtures**: `tests/e2e/fixtures/test-streams/1-min-nfl.mp4`
- **Specifications**:
  - [specs/003-gstreamer-stream-worker](../003-gstreamer-stream-worker/spec.md) - media-service implementation
  - [specs/016-websocket-audio-protocol](../016-websocket-audio-protocol.md) - Socket.IO protocol
  - [specs/005-audio-transcription-module](../005-audio-transcription-module/spec.md) - Whisper ASR
  - [specs/006-translation-component](../006-translation-component/spec.md) - Translation module
  - [specs/008-tts-module](../008-tts-module/spec.md) - Coqui TTS

## Out of Scope

- GPU-based STS testing (CPU-only for local development simplicity)
- Performance benchmarking or latency optimization
- Multi-worker orchestration (single worker instance only)
- Production deployment (this is local E2E testing only)
- Load testing with multiple concurrent streams
- Real-time streaming from live sources (pre-recorded fixtures only)
- Multiple language combinations (fixture is English audio, translated to Spanish)
- Resilience testing (covered by separate test_resilience.py - not part of this spec)
