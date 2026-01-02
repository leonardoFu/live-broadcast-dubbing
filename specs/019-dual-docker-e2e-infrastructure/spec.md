# Feature Specification: Dual Docker-Compose E2E Test Infrastructure

**Feature Branch**: `019-dual-docker-e2e-infrastructure`
**Created**: 2026-01-01
**Status**: Draft
**Input**: User description: "I want to run media service and real STS service together using 2 separate docker-compose but invoke to each other via external port expose. It's a true comprehensive e2e test, cover from media publish(using fixture asset) to worker handler, to STS whole process and send back to media service, and remux to publish as a new stream. Make sure we test the whole process without any mocking or bypassing."

## Overview

This specification defines a comprehensive E2E test infrastructure using **two separate docker-compose configurations** to test the full live dubbing pipeline with real services. Unlike spec 018 (which uses the Echo STS Service), this infrastructure tests the complete integration: media-service + MediaMTX + **real STS service** (with ASR, Translation, and TTS modules).

The dual docker-compose approach provides:
- **Service isolation**: Each service (media-service, sts-service) maintains its own docker-compose.yml for independent development
- **True E2E validation**: No mocking or bypassing - real ASR, real translation, real TTS processing
- **Simple networking**: Services communicate via localhost + port exposure (no complex service discovery)
- **Production-like environment**: Tests validate the actual service integration that will run in production

**Key Design Decisions**:
- Two separate docker-compose files (one for media-service + MediaMTX, one for sts-service) using bridge networking with port exposure
- Services communicate internally via Docker container names, externally via `localhost:<port>`
- Media-service uses bridge networking (not host mode) for production-like isolation

**Related Specs**:
- [specs/018-e2e-stream-handler-tests](../018-e2e-stream-handler-tests/spec.md) - E2E tests with Echo STS (mocked)
- [specs/017-echo-sts-service](../017-echo-sts-service/spec.md) - Echo STS Service for fast testing
- [specs/003-gstreamer-stream-worker](../003-gstreamer-stream-worker/spec.md) - WorkerRunner implementation
- [specs/008-tts-module](../008-tts-module/spec.md) - TTS module with Coqui provider
- [specs/016-websocket-audio-protocol](../016-websocket-audio-protocol.md) - Socket.IO protocol between services

## User Scenarios & Testing

### User Story 1 - Full Pipeline E2E: Media Publish → STS Processing → Dubbed Output (Priority: P1)

An E2E test that validates the complete dubbing pipeline with real services: test fixture published to MediaMTX → WorkerRunner ingests RTSP → segments sent to real STS service → ASR + Translation + TTS processing → dubbed audio returns → A/V sync and remux → new RTMP stream output.

**Why this priority**: This is the ultimate validation of the entire system working together. It's the only test that verifies real ASR, translation, and TTS integration without mocking. Without this working, we cannot be confident the production system will function.

**Independent Test**: This can be tested with a pre-recorded test video fixture published to MediaMTX.
- **Unit test**: N/A (this is inherently an E2E integration test)
- **Contract test**: Verify media-service emits correct Socket.IO events to real STS service per spec 016 contracts
- **E2E test**: `test_full_pipeline_media_to_sts_to_output()` validates complete workflow with all real services
- **Success criteria**: 30-second test video processed end-to-end, 5 segments (6s each) sent to STS and received back with real dubbed audio, RTMP output playable without errors, pipeline completes within 120 seconds (allowing for real STS latency)

**Acceptance Scenarios**:

1. **Given** both docker-compose environments running (media-service + sts-service), **When** test fixture (30s English video) is published to `rtsp://localhost:8554/live/test/in`, **Then** WorkerRunner connects and starts ingesting within 5 seconds
2. **Given** WorkerRunner ingesting RTSP stream, **When** 6 seconds of audio accumulated, **Then** segment is sent to real STS service via Socket.IO at `http://localhost:3000`
3. **Given** real STS service receives audio fragment, **When** ASR + Translation + TTS pipeline completes, **Then** dubbed audio (Spanish) returns via `fragment:processed` event within 15 seconds (real processing time)
4. **Given** dubbed audio received, **When** video and audio segments are paired by A/V sync, **Then** sync delta is less than 120ms and output is remuxed
5. **Given** remuxed segment ready, **When** output pipeline publishes to RTMP, **Then** output stream is available at `rtmp://localhost:1935/live/test/out` within 1 second
6. **Given** full 30-second stream processed, **When** all segments complete, **Then** 5 segments were processed, RTMP output duration matches input duration (+/- 500ms), real transcripts and translations are recorded in logs

---

### User Story 2 - Service Discovery via Port Exposure: Localhost Communication (Priority: P1)

The test infrastructure configures both docker-compose files to expose service ports to the host network. Services communicate via `localhost:<port>` URLs configured through environment variables, validating the simplest production deployment pattern.

**Why this priority**: Port-based service discovery is the simplest and most reliable approach for initial deployment. It validates that services can find each other without complex DNS or service mesh setups.

**Independent Test**: Test service connectivity and health checks before running full pipeline.
- **Unit test**: N/A (infrastructure configuration)
- **Contract test**: Verify health check endpoints return correct status codes
- **Integration test**: `test_services_can_communicate()` validates media-service can reach sts-service health endpoint and vice versa
- **Success criteria**: Health checks pass for all services within 30 seconds of startup, Socket.IO connection established successfully

**Acceptance Scenarios**:

1. **Given** media-service docker-compose started with `STS_SERVICE_URL=http://localhost:3000`, **When** media-service attempts to connect to STS, **Then** connection succeeds via exposed port 3000
2. **Given** sts-service docker-compose started with port 3000 exposed, **When** external client (media-service from host) connects, **Then** Socket.IO handshake completes successfully
3. **Given** MediaMTX started with RTSP port 8554 and RTMP port 1935 exposed, **When** WorkerRunner connects from media-service container, **Then** connection succeeds using host network mode or explicit localhost URLs
4. **Given** all services started, **When** pytest queries health endpoints, **Then** all services return 200 OK within 5 seconds

---

### User Story 3 - Real STS Processing: ASR → Translation → TTS Pipeline (Priority: P1)

The E2E test validates that real STS service components (ASR with Whisper, Translation, TTS with Coqui) process audio fragments correctly and return dubbed audio with accurate transcripts and translations.

**Why this priority**: This validates the core value proposition of the dubbing system - real speech processing without shortcuts. It's the only way to catch integration bugs between STS modules that mocks cannot reveal.

**Independent Test**: Test STS service in isolation by sending audio fragments via Socket.IO client.
- **Unit test**: Tested in individual module specs (005-ASR, 006-Translation, 008-TTS)
- **Contract test**: `test_sts_fragment_processing_contract()` validates fragment:data → fragment:processed event structure
- **E2E test**: `test_sts_processes_real_audio()` validates full ASR + Translation + TTS pipeline with real audio input
- **Success criteria**: Audio fragment with English speech returns Spanish dubbed audio, transcript shows accurate English text, translated_text shows accurate Spanish text, processing_time_ms is reasonable (<15s per 6s fragment)

**Acceptance Scenarios**:

1. **Given** audio fragment containing English speech "Hello world", **When** STS service processes it with source=en, target=es, **Then** transcript is "Hello world" (or close variant), translated_text is "Hola mundo" (or equivalent), dubbed_audio contains Spanish TTS output
2. **Given** audio fragment with background noise and speech, **When** STS service processes it, **Then** ASR extracts speech successfully, dubbed audio is returned without errors
3. **Given** audio fragment with no speech (silence), **When** STS service processes it, **Then** ASR returns empty or near-empty transcript, TTS returns minimal audio, no errors raised
4. **Given** STS service processing multiple fragments concurrently, **When** fragments arrive in sequence, **Then** all fragments are processed and returned in order, no fragments lost or duplicated

---

### User Story 4 - Test Fixture Management: Deterministic Input Assets (Priority: P2)

The test infrastructure provides deterministic test fixtures (pre-recorded videos with known properties) that are published to MediaMTX via ffmpeg or GStreamer scripts controlled by pytest fixtures.

**Why this priority**: Deterministic test fixtures enable reproducible tests and regression detection. Without predictable inputs, test failures become impossible to diagnose.

**Independent Test**: Test fixture validation can be done before pipeline tests.
- **Unit test**: `test_fixture_properties()` validates test fixture has expected video codec, audio codec, duration, sample rate
- **Contract test**: N/A (file validation)
- **Integration test**: `test_publish_fixture_to_mediamtx()` validates ffmpeg can publish fixture to MediaMTX RTSP endpoint
- **Success criteria**: Test fixture publishes successfully, MediaMTX reports stream active, stream metadata matches expected values

**Acceptance Scenarios**:

1. **Given** test fixture `30s-english-speech.mp4` (H.264 video, AAC audio, 30s duration), **When** ffmpeg publishes to `rtsp://localhost:8554/live/test/in`, **Then** MediaMTX reports stream active within 2 seconds
2. **Given** pytest fixture `publish_test_stream()`, **When** fixture is invoked, **Then** ffmpeg process starts, stream publishes, fixture yields control to test, and cleans up ffmpeg on teardown
3. **Given** multiple tests using same fixture, **When** tests run sequentially, **Then** fixture cleanup ensures no stream conflicts, each test gets fresh stream
4. **Given** test fixture with known speech content, **When** E2E test completes, **Then** output transcript matches expected text (allowing for ASR variance), validating end-to-end correctness

---

### User Story 5 - Separate Docker Compose Files: Independent Service Lifecycle (Priority: P2)

Each service (media-service, sts-service) has its own docker-compose.yml file for independent development and testing. Tests start both compositions and coordinate them through environment variables.

**Why this priority**: Separate docker-compose files enable independent service development and avoid monolithic configurations. Teams can develop and test services in isolation before integration.

**Independent Test**: Test each docker-compose file independently before full E2E.
- **Unit test**: N/A (infrastructure configuration)
- **Contract test**: Validate docker-compose files have required service definitions and port exposures
- **Integration test**: `test_media_service_compose_starts()` and `test_sts_service_compose_starts()` validate each composition starts successfully
- **Success criteria**: Each docker-compose can start independently, health checks pass, services are reachable on exposed ports

**Acceptance Scenarios**:

1. **Given** `apps/media-service/docker-compose.e2e.yml` exists, **When** docker-compose up is run, **Then** media-service and MediaMTX start, ports 8080 (media API), 8554 (RTSP), 1935 (RTMP) are exposed and accessible
2. **Given** `apps/sts-service/docker-compose.e2e.yml` exists, **When** docker-compose up is run, **Then** sts-service starts, port 3000 (Socket.IO) is exposed and accessible
3. **Given** both compositions running, **When** pytest test suite runs, **Then** tests coordinate both environments via environment variables, execute full pipeline, and clean up both compositions on teardown
4. **Given** sts-service composition down, **When** developer runs media-service tests with Echo STS, **Then** media-service composition still works independently (no hard dependency on sts-service composition)

---

### User Story 6 - Output Stream Validation: Playable Dubbed Stream (Priority: P2)

The E2E test validates that the output RTMP stream contains the dubbed audio correctly synchronized with video, and is playable via standard media players or ffprobe analysis.

**Why this priority**: The ultimate success criterion is a playable dubbed stream. Without validating output quality, tests can pass while producing unusable output.

**Independent Test**: Test output stream properties separately from input processing.
- **Unit test**: N/A (output validation)
- **Contract test**: N/A (output validation)
- **Integration test**: `test_output_stream_is_playable()` validates output RTMP stream using ffprobe inspection
- **Success criteria**: Output stream has valid video track (H.264), valid audio track (dubbed AAC), duration matches input (+/- 500ms), A/V sync delta < 120ms throughout

**Acceptance Scenarios**:

1. **Given** full pipeline completed, **When** ffprobe inspects output stream `rtmp://localhost:1935/live/test/out`, **Then** stream reports 2 streams (video + audio), video codec is H.264, audio codec is AAC
2. **Given** output stream active, **When** ffprobe extracts duration, **Then** duration is 30 seconds (+/- 500ms tolerance for segment boundaries)
3. **Given** output stream active, **When** ffprobe extracts audio language metadata, **Then** metadata shows target language (es for Spanish)
4. **Given** output stream recorded to file, **When** video player opens file, **Then** video plays smoothly, dubbed audio is audible and synchronized with video, no corruption or artifacts

---

### User Story 7 - Environment Configuration: Configurable Service Endpoints (Priority: P3)

Both docker-compose files use environment variables to configure service endpoints (MediaMTX URLs, STS service URL), making the infrastructure adaptable to different deployment scenarios.

**Why this priority**: Configuration flexibility enables testing different deployment patterns and makes the infrastructure reusable for CI/CD, local development, and production-like staging.

**Independent Test**: Test environment variable substitution in docker-compose files.
- **Unit test**: N/A (infrastructure configuration)
- **Contract test**: Validate docker-compose files reference environment variables correctly
- **Integration test**: `test_env_config_overrides()` validates services use environment variables for endpoints
- **Success criteria**: Changing environment variables updates service endpoints without modifying docker-compose files

**Acceptance Scenarios**:

1. **Given** media-service docker-compose with `STS_SERVICE_URL=${STS_SERVICE_URL:-http://localhost:3000}`, **When** environment variable `STS_SERVICE_URL=http://sts-service:3000` is set, **Then** media-service connects to internal docker network endpoint instead of localhost
2. **Given** sts-service docker-compose with `PORT=${STS_PORT:-3000}`, **When** environment variable `STS_PORT=8000` is set, **Then** service listens on port 8000 and tests adjust accordingly
3. **Given** pytest test configuration file, **When** developer sets custom ports for conflict avoidance, **Then** docker-compose files respect custom ports without manual editing
4. **Given** CI/CD environment with non-standard ports, **When** tests run, **Then** services use CI-provided ports and tests pass without modification

---

### Edge Cases

- What happens when STS service is not reachable (port not exposed or service down)? Media-service retries 3 times with exponential backoff, then fails gracefully, E2E test fails with clear error message.
- What happens when test fixture has no audio track? WorkerRunner logs error "audio track required for dubbing" and exits, E2E test fails with assertion on error log.
- What happens when STS service processing is very slow (>30s per fragment)? Fragment timeout (default 30s) triggers, media-service uses passthrough audio (original segment) and continues pipeline, E2E test logs warning but passes if output stream is complete (validates graceful degradation per Constitution Principle V).
- What happens when MediaMTX RTSP stream disconnects mid-test? WorkerRunner detects stream end, completes in-flight fragments, publishes final output, E2E test validates partial output is still correct.
- What happens when docker-compose fails to start (port conflict)? Pytest fixture detects startup failure (health check timeout), skips test with clear message about port conflict.
- What happens when output RTMP publish fails (MediaMTX egress disabled)? WorkerRunner logs error and exits, E2E test fails with assertion on error log and missing output stream.
- What happens when both docker-compose files use same network name? Docker merges networks, services can communicate via container names directly (fallback to service discovery), tests still pass.
- What happens when test fixture file is missing? Pytest fixture fails during setup with FileNotFoundError, test is skipped with clear error message.

## Requirements

### Functional Requirements

**Dual Docker-Compose Infrastructure (P1)**

- **FR-001**: E2E test infrastructure MUST use two separate docker-compose files: `apps/media-service/docker-compose.e2e.yml` and `apps/sts-service/docker-compose.e2e.yml`
- **FR-002**: Both docker-compose files MUST expose service ports to host network for inter-service communication
- **FR-003**: Media-service composition MUST include MediaMTX (RTSP/RTMP server) and media-service worker host
- **FR-004**: STS-service composition MUST include real STS service with ASR, Translation, and TTS modules
- **FR-005**: Services MUST communicate via `localhost:<port>` URLs configured through environment variables

**Service Port Exposure (P1)**

- **FR-006**: Media-service composition MUST expose ports: 8080 (media API + metrics), 8554 (MediaMTX RTSP), 1935 (MediaMTX RTMP)
- **FR-007**: STS-service composition MUST expose port 3000 (Socket.IO server for fragment processing)
- **FR-008**: All exposed ports MUST be configurable via environment variables for conflict avoidance
- **FR-009**: Each docker-compose file MUST include health checks for all services (readiness validation)

**Full Pipeline E2E Testing (P1)**

- **FR-010**: E2E tests MUST validate complete pipeline: fixture publish → RTSP ingest → STS processing → A/V remux → RTMP output
- **FR-011**: E2E tests MUST use real STS service (no mocking of ASR, Translation, or TTS modules)
- **FR-012**: E2E tests MUST verify output RTMP stream is playable and contains dubbed audio
- **FR-013**: E2E tests MUST verify real transcripts and translations are produced by STS service
- **FR-014**: E2E tests MUST complete within 180 seconds for 30-second test fixture (allowing for real STS latency)

**Test Fixture Management (P2)**

- **FR-015**: E2E tests MUST use deterministic test fixtures from `tests/fixtures/test_streams/`
- **FR-016**: Primary test fixture MUST be 30-second video with English speech (counting phrases "One, two, three... thirty" at ~1 number/second), H.264 video, AAC audio, 48kHz sample rate
- **FR-016a**: Test fixture audio content enables deterministic ASR validation (known expected transcripts for each segment)
- **FR-017**: Pytest fixtures MUST publish test fixtures to MediaMTX RTSP using ffmpeg subprocess
- **FR-018**: Pytest fixtures MUST clean up ffmpeg processes and streams in teardown even if test fails

**Real STS Processing Validation (P2)**

- **FR-019**: E2E tests MUST verify ASR produces accurate transcripts (compare to known test fixture content)
- **FR-020**: E2E tests MUST verify Translation produces target language text (Spanish for primary test fixture)
- **FR-021**: E2E tests MUST verify TTS produces dubbed audio in target language (not original audio)
- **FR-022**: E2E tests MUST verify fragment:processed events include transcript, translated_text, and dubbed_audio fields

**Output Stream Validation (P2)**

- **FR-023**: E2E tests MUST verify output stream using ffprobe inspection (video codec, audio codec, duration)
- **FR-024**: E2E tests MUST verify output audio is dubbed (not original) using dual validation: (1) monitor Socket.IO fragment:processed events confirm dubbed_audio received for all segments, (2) extract output audio and compute spectral fingerprint/hash to confirm audio differs from original
- **FR-025**: E2E tests MUST verify A/V sync delta remains < 120ms throughout output stream
- **FR-026**: E2E tests MUST verify output stream duration matches input duration (+/- 500ms)

**Environment Configuration (P3)**

- **FR-027**: Docker-compose files MUST use environment variables for all service endpoints (MediaMTX URLs, STS URL)
- **FR-028**: Docker-compose files MUST provide sensible defaults for environment variables (localhost ports)
- **FR-029**: Pytest configuration MUST allow overriding service URLs and ports for CI/CD environments
- **FR-030**: E2E tests MUST validate environment variable substitution works correctly

**Test Lifecycle Management (P3)**

- **FR-031**: Pytest fixtures MUST start both docker-compose environments before tests and stop them after, using session scope (start once for all tests, tear down at end)
- **FR-031a**: Pytest fixtures MUST use unique stream names per test (e.g., `/live/test1/in`, `/live/test2/in`) to avoid conflicts between tests sharing the same docker-compose session
- **FR-032**: Pytest fixtures MUST wait for health checks to pass before allowing tests to run
- **FR-033**: Pytest fixtures MUST collect docker-compose logs on test failure for debugging
- **FR-034**: Pytest fixtures MUST ensure cleanup even if test is interrupted (SIGINT, SIGTERM)

### Key Entities

- **Media Service Docker Compose**: `apps/media-service/docker-compose.e2e.yml` - defines MediaMTX + media-service + environment config
- **STS Service Docker Compose**: `apps/sts-service/docker-compose.e2e.yml` - defines real STS service + environment config
- **Test Fixture**: 30-second video file with known properties (H.264, AAC, English speech) for deterministic testing
- **E2E Test Suite**: `tests/e2e/test_dual_compose_full_pipeline.py` - orchestrates both compositions and validates full pipeline
- **Service Configuration**: Environment variables for endpoints (MEDIAMTX_RTSP_URL, MEDIAMTX_RTMP_URL, STS_SERVICE_URL)
- **Output Stream**: RTMP stream at `rtmp://localhost:1935/live/test/out` containing dubbed video + audio

## Success Criteria

### Measurable Outcomes

- **SC-001**: Full pipeline E2E test passes with 30-second test fixture completing in under 180 seconds
- **SC-002**: Real STS service processes all fragments successfully, returning transcripts + translations + dubbed audio
- **SC-003**: Output RTMP stream is playable via ffprobe and contains dubbed audio in target language
- **SC-004**: A/V sync delta remains < 120ms throughout output stream (measured via PTS analysis)
- **SC-005**: Both docker-compose files start independently and together without conflicts
- **SC-006**: Health checks for all services pass within 30 seconds of docker-compose up
- **SC-007**: E2E test suite executes reliably in CI/CD environment without flakiness (95% pass rate over 10 runs)
- **SC-008**: Services communicate successfully via localhost + port exposure without complex networking

## Architecture Decisions

Based on user requirements and clarification:

### Decision 1: Two Separate Docker-Compose Files
**Choice**: `apps/media-service/docker-compose.e2e.yml` and `apps/sts-service/docker-compose.e2e.yml`
**Rationale**: Enables independent service development and testing. Each team can work on their service without modifying a monolithic compose file. Matches real-world deployment where services are deployed independently.

### Decision 2: Bridge Networking with Port Exposure
**Choice**: Use Docker bridge networking (default), expose ports to host, services communicate internally via container names (`mediamtx:8554`), externally via `localhost:<port>`
**Rationale**: Production-like isolation and standard Docker patterns. Internal communication uses container names for efficiency, external access via localhost for pytest validation. Avoids host networking complexities while maintaining simplicity.

### Decision 3: Real STS Service (No Mocking)
**Choice**: Use actual ASR + Translation + TTS modules in E2E tests
**Rationale**: Only way to validate real integration and catch bugs that mocks cannot reveal. Spec 018 already provides fast tests with Echo STS - this spec provides comprehensive tests with real processing.

### Decision 4: Pytest Fixtures for Lifecycle Management
**Choice**: Use pytest fixtures to start/stop docker-compose, publish fixtures, and validate output
**Rationale**: Pytest fixtures provide proper setup/teardown guarantees, enable test isolation, and integrate cleanly with existing test suite. Python-based control allows programmatic validation of services.

### Decision 5: 30-Second Test Fixture with Counting Phrases
**Choice**: Primary test fixture is 30 seconds (5 segments @ 6s each) with English counting phrases "One, two, three... thirty" (~1 number/second)
**Rationale**: Short enough for fast iteration (< 3 minutes total test time with real STS), long enough to validate multi-segment processing and A/V sync over time. Counting phrases provide deterministic content for ASR validation (known expected transcripts) and test continuous speech across segments.

### Decision 6: Environment Variable Configuration
**Choice**: All service endpoints configurable via environment variables with defaults
**Rationale**: Enables flexible deployment (localhost for local dev, service names for docker networks, external IPs for distributed setups). Avoids hardcoded values that break in different environments.

### Decision 7: Session-Scoped Pytest Fixtures
**Choice**: Docker-compose environments use session scope - start once for all E2E tests, tear down at end
**Rationale**: Balances speed and isolation. STS model loading is expensive (30s+), session scope amortizes this cost across all tests. MediaMTX and STS are stateless between streams, so unique stream names per test (`/live/test1/in`, `/live/test2/in`) provide sufficient isolation without restart overhead.

### Decision 8: 30-Second Timeout with Passthrough Fallback
**Choice**: Media-service waits 30s max per fragment for STS response, then uses passthrough audio (original segment) and continues pipeline
**Rationale**: Validates graceful degradation per Constitution Principle V. E2E test logs warning but passes if output stream completes, confirming the system can handle STS latency without complete failure. Better than hard failure which would hide fallback logic bugs.

## Test Infrastructure Design

### Docker Compose Files

#### `apps/media-service/docker-compose.e2e.yml`

```yaml
version: '3.8'

services:
  # MediaMTX Media Server (RTSP/RTMP)
  mediamtx:
    image: bluenviron/mediamtx:latest-ffmpeg
    container_name: e2e-media-mediamtx
    restart: "no"
    ports:
      - "${MEDIAMTX_RTSP_PORT:-8554}:8554"     # RTSP
      - "${MEDIAMTX_RTMP_PORT:-1935}:1935"     # RTMP
      - "${MEDIAMTX_API_PORT:-9997}:9997"      # Control API
    environment:
      - MTX_RTSPADDRESS=:8554
      - MTX_RTMPADDRESS=:1935
      - MTX_APIADDRESS=:9997
      - MTX_PROTOCOLS=tcp
      - MTX_LOGLEVEL=warn
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:9997/v3/paths/list"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s

  # Media Service (WorkerRunner host)
  media-service:
    build:
      context: .
      dockerfile: deploy/Dockerfile
    container_name: e2e-media-service
    restart: "no"
    ports:
      - "${MEDIA_SERVICE_PORT:-8080}:8080"  # Expose metrics/API
    environment:
      - PORT=8080
      - LOG_LEVEL=DEBUG
      - MEDIAMTX_RTSP_URL=rtsp://mediamtx:8554  # Internal: use container name
      - MEDIAMTX_RTMP_URL=rtmp://mediamtx:1935  # Internal: use container name
      - STS_SERVICE_URL=${STS_SERVICE_URL:-http://host.docker.internal:3000}  # External: STS on host
      - STS_SOCKETIO_PATH=/socket.io
      - SEGMENT_DIR=/tmp/segments
      - METRICS_ENABLED=true
    extra_hosts:
      - "host.docker.internal:host-gateway"  # Enable access to host network for STS
    volumes:
      - segments-data:/tmp/segments
    depends_on:
      mediamtx:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:8080/health"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 10s

volumes:
  segments-data:
    driver: local
```

#### `apps/sts-service/docker-compose.e2e.yml`

```yaml
version: '3.8'

services:
  # Real STS Service (ASR + Translation + TTS)
  sts-service:
    build:
      context: .
      dockerfile: deploy/Dockerfile
    container_name: e2e-sts-service
    restart: "no"
    ports:
      - "${STS_PORT:-3000}:3000"
    environment:
      - PORT=3000
      - HOST=0.0.0.0
      - LOG_LEVEL=INFO
      - ASR_MODEL=whisper-small  # Balance accuracy and speed
      - TRANSLATION_PROVIDER=google
      - TTS_PROVIDER=coqui
      - TTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC
      - DEVICE=cpu  # Use CPU for E2E tests (no GPU required)
      - MAX_INFLIGHT=3
      - PROCESSING_TIMEOUT=30
    volumes:
      - model-cache:/root/.cache  # Cache models across runs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 30s  # Allow time for model loading

volumes:
  model-cache:
    driver: local
```

### Test Directory Structure

```
tests/e2e/
├── __init__.py
├── conftest.py                                    # Shared pytest fixtures
├── docker_utils.py                                # Docker compose lifecycle helpers
├── test_dual_compose_full_pipeline.py             # P1: Full pipeline E2E
├── test_dual_compose_service_communication.py     # P1: Service connectivity
├── test_dual_compose_real_sts_processing.py       # P1: Real STS validation
├── test_dual_compose_output_validation.py         # P2: Output stream quality
└── test_dual_compose_env_configuration.py         # P3: Config flexibility
```

### Key Pytest Fixtures

```python
# tests/e2e/conftest.py

@pytest.fixture(scope="session")
def media_compose_env():
    """Start media-service docker-compose and wait for health checks.

    Session scope: Starts once for all tests, tears down at end.
    Uses bridge networking with port exposure.
    """
    env = {
        "MEDIAMTX_RTSP_PORT": "8554",
        "MEDIAMTX_RTMP_PORT": "1935",
        "MEDIA_SERVICE_PORT": "8080",
        "STS_SERVICE_URL": "http://host.docker.internal:3000"
    }
    # Start composition, wait for health, yield, cleanup
    ...

@pytest.fixture(scope="session")
def sts_compose_env():
    """Start sts-service docker-compose and wait for health checks.

    Session scope: Starts once, model loading (30s+) happens once.
    """
    env = {"STS_PORT": "3000"}
    # Start composition, wait for health (including model load), yield, cleanup
    ...

@pytest.fixture(scope="session")
def dual_compose_env(media_compose_env, sts_compose_env):
    """Combined fixture ensuring both environments are running.

    Session scope: Both compositions stay up for all tests.
    Tests use unique stream names to avoid conflicts.
    """
    return {"media": media_compose_env, "sts": sts_compose_env}

@pytest.fixture
def publish_test_fixture(request):
    """Publish 30s test fixture to MediaMTX RTSP, cleanup on teardown.

    Test fixture: 30s video with counting phrases "One, two, three... thirty"
    (H.264 video, AAC audio 48kHz, ~1 number/second for deterministic ASR).

    Uses unique stream name per test to avoid conflicts in session-scoped compose.
    """
    test_name = request.node.name
    stream_name = f"test_{test_name}_{int(time.time())}"
    rtsp_url = f"rtsp://localhost:8554/live/{stream_name}/in"
    # ffmpeg publish subprocess, yield stream_name, kill process
    ...
```

## Assumptions

- Both services (media-service, sts-service) have working Dockerfiles and can run in containers
- Test fixtures include 30-second video with English speech (clear audio for ASR accuracy)
- Docker and Docker Compose v2 are available in test environment
- Python 3.10.x environment per monorepo constitution
- STS service can run on CPU (no GPU required for E2E tests, accepting slower processing)
- ffmpeg is available in test environment for fixture publishing and stream inspection
- Test execution environment has sufficient resources (4 CPU cores, 8GB RAM minimum for real STS)
- E2E tests run in isolated environment (not production)
- Model downloads (Whisper, TTS models) are cached in docker volumes to speed up subsequent runs

## Dependencies

- **External Services**: MediaMTX (RTSP/RTMP server), real STS service (ASR + Translation + TTS)
- **Python Libraries**: pytest, pytest-asyncio, python-socketio (client), prometheus_client, docker-py
- **Infrastructure**: Docker, Docker Compose v2, ffmpeg (fixture publishing + stream inspection)
- **Test Fixtures**: `tests/fixtures/test_streams/30s-english-speech.mp4` (to be created)
- **Specifications**:
  - [specs/003-gstreamer-stream-worker/spec.md](../003-gstreamer-stream-worker/spec.md) - WorkerRunner implementation
  - [specs/016-websocket-audio-protocol](../016-websocket-audio-protocol.md) - Socket.IO protocol
  - [specs/005-audio-transcription-module](../005-audio-transcription-module/spec.md) - ASR module
  - [specs/006-translation-component](../006-translation-component/spec.md) - Translation module
  - [specs/008-tts-module](../008-tts-module/spec.md) - TTS module
  - [specs/017-echo-sts-service](../017-echo-sts-service/spec.md) - Echo STS for fast tests (complementary)
  - [specs/018-e2e-stream-handler-tests](../018-e2e-stream-handler-tests/spec.md) - E2E tests with Echo STS

## Out of Scope

- GPU-based STS service testing (CPU-only for E2E simplicity)
- Performance benchmarking (latency optimization, throughput limits)
- Multi-worker orchestration (only single worker instance)
- Production deployment configuration (K8s, service mesh, etc.)
- Load testing with multiple concurrent streams
- Custom error injection beyond natural service failures
- Real-time streaming from live sources (only pre-recorded fixtures)
- Multiple language combinations (primary test fixture is English → Spanish)

---

## Clarifications

### Session: 2026-01-01

**Q1: Docker Networking Mode for Media Service**
- **Question**: Should media-service use `network_mode: "host"` or bridge networking with port exposure?
- **Answer**: Bridge networking (Option A) - both services use bridge networking with port exposure. Media-service communicates with MediaMTX via container names (`rtsp://mediamtx:8554`), with STS via `host.docker.internal:3000`. More production-like, better isolation, standard Docker patterns.

**Q2: Test Fixture Audio Content Specification**
- **Question**: What exact English speech content should the 30-second test fixture contain?
- **Answer**: Counting phrases (Option A) - "One, two, three... thirty" over 30 seconds (~1 number/second). Provides deterministic content for ASR validation, clear segmentation testing, easy to validate output with known expected transcripts, tests continuous speech across multiple segments.

**Q3: STS Service Processing Timeout and Retry Behavior**
- **Question**: What should happen when STS processing exceeds 30-second timeout?
- **Answer**: 30s timeout with passthrough fallback (Option A) - media-service waits 30s max per fragment, then uses passthrough audio (original segment) and continues pipeline. E2E test logs warning but passes if output stream is complete. Validates graceful degradation per Constitution Principle V.

**Q4: Output Stream Validation - How to Verify "Dubbed Audio" vs "Original Audio"?**
- **Question**: How should E2E tests verify output contains Spanish dubbed audio instead of English original?
- **Answer**: Socket.IO events + fingerprint comparison (Option C + A) - Primary: monitor Socket.IO events to verify all fragments received `fragment:processed` with dubbed_audio field. Secondary: extract audio from output stream, compute spectral hash/fingerprint, compare against original to confirm audio differs. Dual approach validates both that dubbing occurred (events) AND was applied to output (fingerprint).

**Q5: Pytest Fixture Scope and Docker Compose Lifecycle**
- **Question**: Should docker-compose environments use session scope (start once) or function scope (restart per test)?
- **Answer**: Session scope for both (Option A) - start once, run all E2E tests, tear down at end. Balances speed (STS model loading happens once, 30s+) and isolation (unique stream names per test like `/live/test1/in`, `/live/test2/in`). MediaMTX and STS are stateless between streams, so session scope is safe and efficient.
