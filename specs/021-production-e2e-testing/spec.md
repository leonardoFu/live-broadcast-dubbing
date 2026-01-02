# Feature Specification: Production-like E2E Testing Infrastructure

**Feature Branch**: `021-production-e2e-testing`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "Production-like E2E Testing Infrastructure with Separate Docker Services - media-service and STS-service as separate Docker containers to simulate production deployment and validate end-to-end dubbing pipeline"

## Overview

This specification defines a production-like E2E testing infrastructure that runs media-service and STS-service as **separate, independent Docker containers** (not docker-compose orchestration) to simulate the production deployment architecture where services run on different infrastructure (EC2 for media-service, RunPod for STS-service).

Unlike specs/018 (Echo STS with docker-compose) and specs/019 (dual docker-compose), this infrastructure tests the actual production deployment pattern:
- **Independent Docker containers**: Each service runs in its own container with no shared docker-compose
- **Network-based service discovery**: Services communicate over standard Docker bridge network via environment variables
- **Real STS processing**: Full ASR + Translation + TTS pipeline (not echo mode)
- **Production-like resilience**: Tests validate service isolation, network reliability, and failure recovery

This approach provides the highest confidence that the production deployment will work correctly, catching integration issues that simpler test setups cannot reveal.

**Related Specs**:
- [specs/018-e2e-stream-handler-tests](../018-e2e-stream-handler-tests/spec.md) - E2E tests with Echo STS (docker-compose)
- [specs/019-dual-docker-e2e-infrastructure](../019-dual-docker-e2e-infrastructure/spec.md) - Dual docker-compose approach
- [specs/003-gstreamer-stream-worker](../003-gstreamer-stream-worker/spec.md) - media-service architecture
- [specs/004-sts-pipeline-design.md](../004-sts-pipeline-design.md) - STS service architecture

## User Scenarios & Testing

### User Story 1 - Independent Docker Containers: True Service Isolation (Priority: P1)

The test infrastructure runs media-service and STS-service as completely independent Docker containers on a shared bridge network, simulating the production deployment pattern where services run on separate infrastructure and communicate over network.

**Why this priority**: This is the core requirement - testing with independent containers validates the production deployment model. Without this, we cannot be confident that services will communicate correctly in production.

**Independent Test**: Test service startup and network connectivity independently
- **Unit test**: N/A (infrastructure configuration)
- **Contract test**: Validate Docker container network configuration matches production
- **Integration test**: `test_independent_containers_can_communicate()` validates network connectivity between isolated containers
- **Success criteria**: Both containers start independently, network discovery succeeds, services can communicate via configured endpoints

**Acceptance Scenarios**:

1. **Given** media-service Docker container started with `STS_SERVICE_URL=http://sts-service:3000`, **When** media-service attempts to connect to STS, **Then** connection succeeds via Docker bridge network using container name resolution
2. **Given** STS-service Docker container started on bridge network with name `sts-service`, **When** media-service container queries DNS, **Then** `sts-service` resolves to correct container IP
3. **Given** both containers running on custom bridge network `e2e-dubbing-network`, **When** pytest queries health endpoints, **Then** both services return 200 OK within 30 seconds
4. **Given** media-service container stopped, **When** STS-service container status checked, **Then** STS-service remains running (no cascading failures from service isolation)

---

### User Story 2 - Full Pipeline E2E: RTMP Input to Dubbed Output (Priority: P1)

An E2E test validates the complete dubbing pipeline with real services: test fixture published to MediaMTX, media-service ingests RTMP, segments sent to real STS service, ASR + Translation + TTS processing, dubbed audio returns, A/V remux, RTMP output stream.

**Why this priority**: This validates the entire system working together in a production-like deployment. It's the ultimate integration test that proves the architecture works.

**Independent Test**: Test with pre-recorded video fixture published to MediaMTX
- **Unit test**: N/A (end-to-end integration test)
- **Contract test**: Verify Socket.IO events match spec 016 schemas throughout pipeline
- **Integration test**: `test_full_pipeline_rtmp_to_dubbed_output()` validates complete workflow
- **Success criteria**: 30-second test video processed end-to-end, 5 segments (6s each) sent to STS and received back with real dubbed audio, RTMP output playable, pipeline completes within 120 seconds

**Acceptance Scenarios**:

1. **Given** both containers running with MediaMTX accessible, **When** test fixture (30s English video) is published to `rtmp://localhost:1935/live/test/in`, **Then** media-service detects stream and starts processing within 5 seconds
2. **Given** media-service processing stream, **When** 6 seconds of audio accumulated, **Then** segment is sent to STS-service container via Socket.IO at `http://sts-service:3000`
3. **Given** STS-service receives audio fragment, **When** ASR + Translation + TTS pipeline completes, **Then** dubbed audio (Spanish) returns via `fragment:processed` event within 15 seconds
4. **Given** dubbed audio received, **When** media-service remuxes A/V segments, **Then** sync delta is less than 120ms and output publishes to RTMP
5. **Given** full 30-second stream processed, **When** all segments complete, **Then** 5 segments were processed, output duration matches input (+/- 500ms), real transcripts logged
6. **Given** output stream available, **When** ffprobe inspects `rtmp://localhost:1935/live/test/out`, **Then** stream is playable with H.264 video and dubbed AAC audio

---

### User Story 3 - Docker Bridge Network: Service Discovery via Container Names (Priority: P1)

The test infrastructure creates a custom Docker bridge network that both containers join, enabling service discovery via container names without hardcoded IPs or complex orchestration.

**Why this priority**: Proper networking is fundamental for service communication. Using Docker bridge networks with container name resolution matches production Kubernetes/ECS patterns.

**Independent Test**: Test network configuration and DNS resolution independently
- **Unit test**: N/A (infrastructure configuration)
- **Contract test**: Validate network configuration matches production networking patterns
- **Integration test**: `test_docker_network_service_discovery()` validates DNS resolution and connectivity
- **Success criteria**: Containers can resolve each other by name, network latency is acceptable (<5ms within bridge network), no network conflicts

**Acceptance Scenarios**:

1. **Given** custom bridge network `e2e-dubbing-network` created, **When** both containers join network with names `media-service` and `sts-service`, **Then** `docker network inspect` shows both containers connected
2. **Given** both containers on bridge network, **When** media-service container pings `sts-service`, **Then** DNS resolves to correct IP and ping succeeds with <5ms latency
3. **Given** network configured with `--internal=false`, **When** containers need external access (model downloads), **Then** containers can reach internet while maintaining internal connectivity
4. **Given** pytest test framework on host, **When** tests query services via published ports, **Then** localhost port mapping works correctly for external access

---

### User Story 4 - Real STS Processing: ASR + Translation + TTS Pipeline (Priority: P1)

The E2E test validates that real STS-service components (Whisper ASR, Translation, Coqui TTS) process audio fragments correctly and return dubbed audio with accurate transcripts and translations.

**Why this priority**: Testing with real STS processing is the core value proposition - it validates the actual speech processing pipeline without shortcuts or mocks.

**Independent Test**: Test STS-service processing independently with Socket.IO client
- **Unit test**: Tested in individual module specs (005-ASR, 006-Translation, 008-TTS)
- **Contract test**: `test_sts_real_processing_contract()` validates fragment:data to fragment:processed events with real processing
- **Integration test**: `test_sts_processes_real_english_audio()` validates full pipeline with English speech input
- **Success criteria**: Audio fragment with English speech returns Spanish dubbed audio, transcript shows accurate English text, processing time is reasonable (<15s per 6s fragment)

**Acceptance Scenarios**:

1. **Given** audio fragment containing English speech "One two three four five six", **When** STS-service processes with source=en, target=es, **Then** transcript is accurate, translated_text is Spanish equivalent, dubbed_audio contains Spanish TTS output
2. **Given** STS-service running in Docker container, **When** multiple fragments arrive in sequence, **Then** all fragments are processed and returned in order, no fragments lost or duplicated
3. **Given** STS processing latency varies (5-15s), **When** media-service receives dubbed audio, **Then** A/V sync mechanism compensates for latency variance, output sync remains <120ms
4. **Given** STS-service processing under load, **When** backpressure event emitted, **Then** media-service respects backpressure and adjusts sending rate

---

### User Story 5 - Container Lifecycle Management: Independent Start/Stop (Priority: P2)

Each container (media-service, STS-service, MediaMTX) can be started, stopped, and restarted independently without affecting the test infrastructure or other containers.

**Why this priority**: Independent lifecycle management enables resilience testing and matches production operations where services are deployed and scaled independently.

**Independent Test**: Test container start/stop/restart independently
- **Unit test**: N/A (infrastructure operations)
- **Contract test**: Validate health check endpoints survive container restarts
- **Integration test**: `test_container_restart_recovery()` validates services recover after restart
- **Success criteria**: Services can restart independently, reconnection logic works, no data loss during graceful shutdown

**Acceptance Scenarios**:

1. **Given** all containers running and pipeline processing, **When** STS-service container is stopped, **Then** media-service detects disconnect, uses fallback audio, logs reconnection attempts
2. **Given** STS-service container stopped, **When** STS-service container restarted, **Then** media-service reconnects via Socket.IO, pipeline resumes with next segment
3. **Given** media-service container restarted during processing, **When** container restarts, **Then** stream processing resumes from last checkpoint (segment boundary)
4. **Given** MediaMTX container restarted, **When** input stream restored, **Then** media-service detects stream, reconnects, and resumes processing

---

### User Story 6 - Test Fixture Management: Deterministic RTMP Publishing (Priority: P2)

The test infrastructure provides deterministic test fixtures (pre-recorded videos with known properties) that are published to MediaMTX via ffmpeg, controlled by pytest fixtures with proper cleanup.

**Why this priority**: Deterministic test fixtures enable reproducible tests and regression detection. Without predictable inputs, test failures are impossible to diagnose.

**Independent Test**: Test fixture publishing can be validated independently
- **Unit test**: `test_fixture_properties()` validates test fixture has expected video/audio codecs and duration
- **Contract test**: N/A (file validation)
- **Integration test**: `test_publish_fixture_to_mediamtx()` validates ffmpeg can publish fixture to MediaMTX RTMP endpoint
- **Success criteria**: Test fixture publishes successfully, MediaMTX reports stream active, stream metadata matches expected values

**Acceptance Scenarios**:

1. **Given** test fixture `30s-english-counting.mp4` (H.264 video, AAC audio, 30s duration with counting phrases), **When** ffmpeg publishes to `rtmp://localhost:1935/live/test/in`, **Then** MediaMTX reports stream active within 2 seconds
2. **Given** pytest fixture `publish_rtmp_stream()`, **When** fixture is invoked, **Then** ffmpeg process starts, stream publishes, fixture yields control to test, and kills ffmpeg on teardown
3. **Given** test fixture with known speech content (counting "One, two, three..."), **When** E2E test completes, **Then** output transcript matches expected text (allowing for ASR variance)
4. **Given** multiple tests using fixtures, **When** tests run sequentially, **Then** fixture cleanup ensures no stream conflicts, each test gets fresh stream with unique name

---

### User Story 7 - Environment Configuration: Configurable Service Endpoints (Priority: P3)

The test infrastructure uses environment variables to configure service endpoints (MediaMTX URLs, STS service URL, network names), making the setup adaptable to different deployment scenarios.

**Why this priority**: Configuration flexibility enables testing different deployment patterns and makes the infrastructure reusable for CI/CD environments.

**Independent Test**: Test environment variable substitution independently
- **Unit test**: N/A (infrastructure configuration)
- **Contract test**: Validate environment variables are correctly applied to container configurations
- **Integration test**: `test_env_config_overrides()` validates services use environment variables for endpoints
- **Success criteria**: Changing environment variables updates service endpoints without modifying test code, configuration is clearly documented

**Acceptance Scenarios**:

1. **Given** pytest configuration with `MEDIAMTX_RTMP_PORT=1935`, **When** environment variable `MEDIAMTX_RTMP_PORT=1936` is set, **Then** pytest uses port 1936 for MediaMTX RTMP, avoiding port conflicts
2. **Given** Docker network name `E2E_NETWORK_NAME=e2e-dubbing-network`, **When** environment variable changed to `E2E_NETWORK_NAME=ci-dubbing-net`, **Then** containers join custom network name
3. **Given** STS service URL `STS_SERVICE_URL=http://sts-service:3000`, **When** environment variable `STS_SERVICE_URL=http://sts-prod:8000` is set, **Then** media-service connects to custom endpoint
4. **Given** CI/CD environment with unique network names per build, **When** tests run, **Then** tests use CI-provided network names and run without conflicts

---

### User Story 8 - Output Validation: Playable Dubbed Stream Quality (Priority: P2)

The E2E test validates that the output RTMP stream contains dubbed audio correctly synchronized with video, is playable via standard tools, and meets quality thresholds.

**Why this priority**: The ultimate success criterion is a playable, high-quality dubbed stream. Without validating output quality, tests can pass while producing unusable output.

**Independent Test**: Test output stream properties separately
- **Unit test**: N/A (output validation)
- **Contract test**: N/A (output validation)
- **Integration test**: `test_output_stream_quality_validation()` validates output using ffprobe and audio analysis
- **Success criteria**: Output stream has valid video/audio tracks, duration matches input, A/V sync <120ms, dubbed audio differs from original

**Acceptance Scenarios**:

1. **Given** full pipeline completed, **When** ffprobe inspects output stream `rtmp://localhost:1935/live/test/out`, **Then** stream has H.264 video and AAC audio, duration is 30s (+/- 500ms)
2. **Given** output stream active, **When** Socket.IO events monitored, **Then** all segments received `fragment:processed` with dubbed_audio field populated
3. **Given** output audio extracted, **When** spectral fingerprint computed and compared to original, **Then** audio differs significantly (confirming dubbing occurred, not passthrough)
4. **Given** output stream recorded to file, **When** video player opens file, **Then** video plays smoothly, dubbed audio is audible and synchronized, no corruption artifacts

---

### Edge Cases

- What happens when STS-service container is not reachable (stopped or network issue)? media-service retries Socket.IO connection 5 times with exponential backoff (2s, 4s, 8s, 16s, 32s), uses fallback audio for in-flight fragments, E2E test logs warning but passes if output stream is complete.
- What happens when test fixture has no audio track? media-service logs error "audio track required for dubbing" and exits, E2E test fails with assertion on error log.
- What happens when STS processing is very slow (>30s per fragment)? Fragment timeout (30s) triggers, media-service uses passthrough audio (original segment) and continues, E2E test logs warning but passes (validates graceful degradation).
- What happens when MediaMTX container stops mid-stream? media-service detects stream end, completes in-flight fragments, publishes final output, E2E test validates partial output is correct.
- What happens when Docker network does not exist? pytest fixture detects network creation failure, creates network automatically, retries container start.
- What happens when port conflicts occur (1935 already in use)? pytest fixture detects port conflict, either fails fast with clear error or uses dynamic port allocation if configured.
- What happens when both containers use same exposed ports? Docker prevents port conflicts - second container fails to start, pytest fixture detects failure and skips test with clear error message.
- What happens when test fixture file is missing? pytest fixture fails during setup with FileNotFoundError, test is skipped with clear error message.

## Requirements

### Functional Requirements

**Independent Docker Containers (P1)**

- **FR-001**: E2E test infrastructure MUST run media-service and STS-service as separate, independent Docker containers (not docker-compose orchestration)
- **FR-002**: Each container MUST be started and stopped independently via `docker run` and `docker stop` commands
- **FR-003**: Containers MUST communicate over a custom Docker bridge network created by test infrastructure
- **FR-004**: Container names MUST be deterministic for DNS resolution (e.g., `e2e-media-service`, `sts-service`, `e2e-mediamtx`)
- **FR-005**: Containers MUST expose required ports to host network for pytest access (MediaMTX: 1935, 8554; media-service: 8080; STS-service: 3000)

**Docker Bridge Network Configuration (P1)**

- **FR-006**: Test infrastructure MUST create a custom Docker bridge network (default name: `e2e-dubbing-network`) before starting containers
- **FR-007**: Bridge network MUST allow external internet access (not internal-only) for model downloads and external dependencies
- **FR-008**: All containers MUST join the bridge network with static container names for DNS resolution
- **FR-009**: Containers MUST be able to resolve each other by name (e.g., `ping sts-service` from media-service container succeeds)
- **FR-010**: Network MUST be cleaned up after tests complete, even if tests fail

**Service Discovery and Communication (P1)**

- **FR-011**: media-service container MUST be configured with `STS_SERVICE_URL=http://sts-service:3000` to connect to STS-service via container name
- **FR-012**: media-service container MUST be configured with `MEDIAMTX_RTMP_URL=rtmp://e2e-mediamtx:1935` for internal RTMP communication
- **FR-013**: Services MUST communicate using container names on bridge network (not localhost or hardcoded IPs)
- **FR-014**: Health check endpoints MUST be accessible from host via published ports (e.g., `http://localhost:8080/health` for media-service)

**Full Pipeline E2E Testing (P1)**

- **FR-015**: E2E tests MUST validate complete pipeline: RTMP fixture publish, media-service ingest, STS processing, A/V remux, RTMP output
- **FR-016**: E2E tests MUST use real STS-service (Whisper ASR + Translation + Coqui TTS) without mocking
- **FR-017**: E2E tests MUST verify output RTMP stream is playable and contains dubbed audio
- **FR-018**: E2E tests MUST verify real transcripts and translations are produced by STS-service
- **FR-019**: E2E tests MUST complete within 180 seconds for 30-second test fixture (allowing for real STS latency)

**Container Lifecycle Management (P2)**

- **FR-020**: Pytest fixtures MUST start containers before tests and stop containers after tests, with proper cleanup on failure
- **FR-021**: Pytest fixtures MUST wait for health checks to pass before allowing tests to run (timeout: 60 seconds for STS model loading)
- **FR-022**: Pytest fixtures MUST collect container logs on test failure for debugging
- **FR-023**: Containers MUST support graceful shutdown (SIGTERM) with cleanup of in-progress work
- **FR-024**: Containers MUST support restart without data loss (state checkpointing at segment boundaries)

**Test Fixture Management (P2)**

- **FR-025**: E2E tests MUST use deterministic test fixtures from `tests/fixtures/test_streams/`
- **FR-026**: Primary test fixture MUST be 30-second video with English counting phrases ("One, two, three... thirty" at ~1 number/second), H.264 video, AAC audio 48kHz
- **FR-027**: Pytest fixtures MUST publish test fixtures to MediaMTX RTMP using ffmpeg subprocess
- **FR-028**: Pytest fixtures MUST clean up ffmpeg processes and streams in teardown even if test fails
- **FR-029**: Test fixtures MUST use unique stream names per test to avoid conflicts (e.g., `/live/test_{timestamp}/in`)

**Real STS Processing Validation (P2)**

- **FR-030**: E2E tests MUST verify ASR produces accurate transcripts (compare to known test fixture content with tolerance for ASR variance)
- **FR-031**: E2E tests MUST verify Translation produces target language text (Spanish for primary test fixture)
- **FR-032**: E2E tests MUST verify TTS produces dubbed audio in target language (not original audio)
- **FR-033**: E2E tests MUST verify `fragment:processed` events include transcript, translated_text, and dubbed_audio fields

**Output Stream Validation (P2)**

- **FR-034**: E2E tests MUST verify output stream using ffprobe inspection (video codec H.264, audio codec AAC, duration matches input)
- **FR-035**: E2E tests MUST verify output audio is dubbed (not original) using dual validation: (1) monitor Socket.IO events confirm dubbed_audio received, (2) extract audio and compute spectral fingerprint to confirm audio differs from original
- **FR-036**: E2E tests MUST verify A/V sync delta remains <120ms throughout output stream (measured via PTS analysis)
- **FR-037**: E2E tests MUST verify output stream duration matches input duration (+/- 500ms)

**Environment Configuration (P3)**

- **FR-038**: Test infrastructure MUST use environment variables for all configurable values (network name, ports, service URLs)
- **FR-039**: Test infrastructure MUST provide sensible defaults for all environment variables
- **FR-040**: Pytest configuration MUST allow overriding service URLs and ports for CI/CD environments
- **FR-041**: All configuration MUST be documented in test README with examples

**Observability and Debugging (P3)**

- **FR-042**: Pytest fixtures MUST collect and save container logs to `tests/e2e/logs/` directory on test failure
- **FR-043**: E2E tests MUST log key events (container start/stop, stream publish, segment processing) with timestamps
- **FR-044**: E2E tests MUST verify Prometheus metrics are updated correctly (fragment count, fallback count, processing time)
- **FR-045**: Test output MUST include clear error messages with debugging hints when failures occur

### Key Entities

- **Docker Bridge Network**: Custom network (`e2e-dubbing-network`) connecting all containers with DNS resolution
- **media-service Container**: Independent Docker container running media-service worker with GStreamer pipeline
- **STS-service Container**: Independent Docker container running real STS-service (ASR + Translation + TTS)
- **MediaMTX Container**: Independent Docker container running MediaMTX RTSP/RTMP server
- **Test Fixture**: 30-second video file with English counting phrases, known properties for deterministic testing
- **E2E Test Suite**: `tests/e2e/test_production_e2e.py` - orchestrates container lifecycle and validates full pipeline
- **Service Configuration**: Environment variables for endpoints, ports, and network settings

## Success Criteria

### Measurable Outcomes

- **SC-001**: Full pipeline E2E test passes with 30-second test fixture completing in under 180 seconds
- **SC-002**: All three containers (media-service, STS-service, MediaMTX) start independently and communicate successfully
- **SC-003**: Real STS-service processes all fragments successfully, returning transcripts + translations + dubbed audio
- **SC-004**: Output RTMP stream is playable via ffprobe and contains dubbed audio in target language (verified via fingerprint analysis)
- **SC-005**: A/V sync delta remains <120ms throughout output stream (measured via PTS analysis)
- **SC-006**: Services can restart independently without cascading failures or data loss
- **SC-007**: E2E test suite executes reliably in CI/CD environment without flakiness (95% pass rate over 10 runs)
- **SC-008**: Container logs are automatically collected and saved on test failure for debugging

## Architecture Decisions

### Decision 1: Independent Docker Containers (Not docker-compose)

**Choice**: Use separate `docker run` commands for each container, managed by pytest fixtures
**Rationale**: Matches production deployment where services run on different infrastructure (EC2 vs RunPod). Enables testing of true service isolation, independent lifecycle management, and network-based discovery. Avoids docker-compose orchestration overhead.

### Decision 2: Custom Docker Bridge Network with Container Name Resolution

**Choice**: Create custom bridge network, containers join with static names (e.g., `sts-service`, `e2e-mediamtx`)
**Rationale**: Provides production-like service discovery via DNS without hardcoded IPs. Standard Docker pattern that translates well to Kubernetes/ECS. Simple, reliable, no external dependencies.

### Decision 3: Real STS-service (No Mocking)

**Choice**: Use actual Whisper ASR + Translation + Coqui TTS in E2E tests
**Rationale**: Only way to validate real integration and catch bugs that mocks cannot reveal. Specs 018 and 019 already provide fast tests with echo/mocked STS - this spec provides comprehensive production-like validation.

### Decision 4: Pytest Fixtures for Container Lifecycle

**Choice**: Use pytest fixtures to manage `docker run`, health checks, log collection, and `docker stop` cleanup
**Rationale**: Pytest fixtures provide proper setup/teardown guarantees, enable test isolation, and integrate cleanly with existing test suite. Python-based control allows programmatic validation and error handling.

### Decision 5: 30-Second Test Fixture with Counting Phrases

**Choice**: Primary test fixture is 30 seconds (5 segments @ 6s each) with English counting phrases "One, two, three... thirty"
**Rationale**: Short enough for fast iteration (<3 minutes total test time), long enough to validate multi-segment processing and A/V sync. Counting phrases provide deterministic content for ASR validation and test continuous speech across segments.

### Decision 6: Session-Scoped Fixtures with Model Preloading

**Choice**: Docker containers use session scope - start once for all E2E tests, tear down at end
**Rationale**: STS model loading is expensive (30s+), session scope amortizes cost across all tests. Containers are stateless between streams, so unique stream names per test provide sufficient isolation without restart overhead.

### Decision 7: Environment Variable Configuration

**Choice**: All service endpoints, ports, and network names configurable via environment variables with defaults
**Rationale**: Enables flexible deployment (local dev, CI/CD, staging). Avoids hardcoded values that break in different environments. Standard practice for containerized applications.

### Decision 8: Dual Validation for Dubbed Audio

**Choice**: Verify dubbing via (1) Socket.IO events monitoring + (2) spectral fingerprint comparison of output audio
**Rationale**: Socket.IO events confirm STS processing occurred, fingerprint comparison confirms dubbed audio was applied to output (not bypassed). Dual approach provides high confidence that dubbing happened correctly.

## Assumptions

- Docker Engine is installed and running on test host
- Python docker SDK is available (`pip install docker`)
- Test fixtures include 30-second video with English counting phrases
- STS-service can run on CPU (no GPU required for E2E tests)
- ffmpeg is available in test environment for fixture publishing and stream inspection
- Test execution environment has sufficient resources (4 CPU cores, 8GB RAM minimum)
- E2E tests run in isolated environment (not production)
- Model downloads (Whisper, TTS models) are cached in Docker volumes

## Dependencies

- **External Services**: MediaMTX (RTSP/RTMP server), real STS-service (ASR + Translation + TTS)
- **Python Libraries**: pytest, docker (Docker SDK), requests, python-socketio (client), prometheus_client
- **Infrastructure**: Docker Engine, Docker networks, ffmpeg (fixture publishing + inspection)
- **Test Fixtures**: `tests/fixtures/test_streams/30s-english-counting.mp4` (to be created)
- **Specifications**:
  - [specs/003-gstreamer-stream-worker](../003-gstreamer-stream-worker/spec.md) - media-service implementation
  - [specs/016-websocket-audio-protocol](../016-websocket-audio-protocol.md) - Socket.IO protocol
  - [specs/005-audio-transcription-module](../005-audio-transcription-module/spec.md) - ASR module
  - [specs/006-translation-component](../006-translation-component/spec.md) - Translation module
  - [specs/008-tts-module](../008-tts-module/spec.md) - TTS module

## Out of Scope

- GPU-based STS-service testing (CPU-only for E2E simplicity)
- Performance benchmarking (latency optimization, throughput limits)
- Multi-worker orchestration (only single worker instance)
- Production deployment configuration (Kubernetes, Terraform, etc.)
- Load testing with multiple concurrent streams
- Real-time streaming from live sources (only pre-recorded fixtures)
- Multiple language combinations (primary test fixture is English to Spanish)
- Docker Compose orchestration (intentionally avoided for true service isolation)
