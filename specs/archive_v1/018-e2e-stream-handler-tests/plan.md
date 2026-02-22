# Implementation Plan: E2E Stream Handler Tests

**Branch**: `018-e2e-stream-handler-tests` | **Date**: 2025-12-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-e2e-stream-handler-tests/spec.md`

## Summary

This plan implements comprehensive end-to-end (E2E) tests for the WorkerRunner pipeline orchestration with real MediaMTX RTSP/RTMP server and Echo STS Service. The tests validate the complete dubbing pipeline from RTSP input through STS processing to RTMP output, covering integration points that unit and component integration tests cannot validate.

Key deliverables:
1. E2E test infrastructure (docker-compose.yml, conftest.py fixtures)
2. Six test suites covering full pipeline, A/V sync, circuit breaker, backpressure, fragment tracking, and reconnection
3. Enhanced Echo STS Service with `simulate:disconnect` event for reconnection testing
4. Test fixtures and helper utilities for deterministic validation

## Technical Context

**Language/Version**: Python 3.10.x (per constitution and monorepo pyproject.toml requirement `>=3.10,<3.11`)
**Primary Dependencies**: pytest>=7.0, pytest-asyncio, python-socketio (client), prometheus_client, docker-compose
**Storage**: N/A (E2E tests use in-memory state, Docker volumes for MediaMTX streams)
**Testing**: pytest with Docker Compose orchestration, ffmpeg/ffprobe for stream analysis
**Target Platform**: Linux/macOS (local dev + CI environment)
**Project Type**: Cross-service E2E test suite (MediaMTX + media-service + echo-sts)
**Performance Goals**: 60-second test fixture completes in <90 seconds, tests run reliably in CI (95% pass rate)
**Constraints**: Tests must be deterministic, isolated (no shared state), fast cleanup on failure
**Scale/Scope**: 6 test files (P1: 2, P2: 3, P3: 1), ~15-20 test cases total, reusable fixtures for future test expansion

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all user stories (6 test suites mapped to spec user stories)
- [x] Mock patterns documented for STS events (Echo STS provides test-friendly event simulation)
- [x] Coverage targets specified (E2E tests validate integration, not code coverage)
- [x] Test infrastructure matches constitution requirements (pytest, Docker Compose isolation)
- [x] Test organization follows standard structure (tests/e2e/ per monorepo spec)

**Principle II - Testability Through Isolation**:
- [x] E2E tests use isolated Docker Compose environment (no external dependencies)
- [x] Test fixtures are deterministic (1-min-nfl.mp4, no random behavior)
- [x] Mock STS events provided by Echo STS Service (controlled error simulation)
- [x] Tests clean up resources in teardown (docker-compose down, process cleanup)

**Principle III - Spec-Driven Development**:
- [x] Spec created first (spec.md) with architectural decisions documented
- [x] Implementation plan follows spec (this document)
- [x] Contracts defined for Echo STS enhancement (simulate:disconnect event)

**Principle IV - Observability & Debuggability**:
- [x] Tests validate Prometheus metrics via /metrics endpoint
- [x] Tests capture and analyze container logs for assertions
- [x] Tests verify structured logging (streamId, fragment.id correlation)

**Principle V - Graceful Degradation**:
- [x] Circuit breaker E2E test validates fallback audio behavior
- [x] Reconnection E2E test validates in-flight fragment fallback

**Principle VI - A/V Sync Discipline**:
- [x] A/V sync E2E test validates PTS delta < 120ms throughout pipeline
- [x] Tests verify video passthrough preserves timestamps

**Principle VII - Incremental Delivery**:
- [x] Tests prioritized (P1, P2, P3) for incremental implementation
- [x] P1 tests (full pipeline, A/V sync) validate core functionality first

**Status**: All constitution gates PASSED. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/018-e2e-stream-handler-tests/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (test infrastructure patterns)
├── data-model.md        # Phase 1 output (test fixtures, Docker network model)
├── contracts/           # Phase 1 output (Echo STS simulate:disconnect schema)
│   └── sts-simulate-disconnect.json
├── quickstart.md        # Phase 1 output (how to run E2E tests)
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
tests/e2e/                              # Cross-service E2E tests (root level)
├── __init__.py
├── docker-compose.yml                  # MediaMTX + media-service + echo-sts
├── .env.e2e                            # E2E environment overrides
├── conftest.py                         # Shared fixtures (Docker, ffmpeg, cleanup)
├── helpers/                            # Test utilities
│   ├── __init__.py
│   ├── docker_manager.py               # Docker Compose lifecycle management
│   ├── stream_publisher.py             # ffmpeg RTSP publishing
│   ├── metrics_parser.py               # Prometheus metrics parsing
│   └── stream_analyzer.py              # ffprobe PTS analysis
├── fixtures/                           # Test data
│   └── test-streams/
│       └── 1-min-nfl.mp4               # 60s H.264 + AAC test fixture
├── test_full_pipeline.py               # P1: RTSP → Worker → STS → RTMP
├── test_av_sync.py                     # P1: A/V sync delta verification
├── test_circuit_breaker.py             # P2: Circuit breaker failure/recovery
├── test_backpressure.py                # P2: Backpressure handling
├── test_fragment_tracker.py            # P2: In-flight tracking
└── test_reconnection.py                # P3: Disconnect/reconnect resilience

apps/media-service/src/media_service/   # Echo STS enhancement (for reconnection test)
└── sts/
    └── echo_server.py                  # Add simulate:disconnect event handler

apps/media-service/deploy/              # Docker configuration updates
└── docker-compose.e2e.yml              # (deprecated - moved to tests/e2e/)
```

**Structure Decision**: E2E tests placed at repository root `tests/e2e/` per monorepo spec: "E2E tests spanning multiple services (media-service + sts-service)". This separates cross-service tests from service-specific integration tests in `apps/<service>/tests/integration/`.

## Test Strategy

### Test Levels for This Feature

**E2E Tests** (primary focus):
- Target: Full pipeline integration (MediaMTX + WorkerRunner + Echo STS)
- Tools: pytest, Docker Compose, ffmpeg, ffprobe, python-socketio client
- Coverage: 6 user stories from spec (full pipeline, A/V sync, circuit breaker, backpressure, fragment tracker, reconnection)
- Mocking: Use Echo STS Service for controlled STS responses (not pure mocks)
- Location: `tests/e2e/`
- Validation: Metrics endpoint, log analysis, output stream inspection, PTS verification

**Unit/Integration Tests** (reference only - not created in this feature):
- Unit tests for Echo STS enhancement (simulate:disconnect handler) already covered by existing echo-sts test suite
- Integration tests for WorkerRunner already exist in `apps/media-service/tests/integration/`

### Test Fixtures

**Primary Fixture**:
- File: `tests/e2e/fixtures/test-streams/1-min-nfl.mp4`
- Duration: 60 seconds
- Video: H.264, 1280x720, 30fps
- Audio: AAC, 48kHz stereo
- Expected Segments: 10 (6 seconds each)
- Purpose: Deterministic input for all E2E tests

**Docker Environment**:
- MediaMTX: RTSP server (port 8554), RTMP server (port 1935)
- Echo STS: Socket.IO server (port 8080)
- media-service: WorkerRunner with metrics endpoint (port 8000)
- Shared network: `e2e-test-network` for inter-service communication

**Helper Fixtures** (conftest.py):
- `docker_services`: Starts/stops docker-compose.yml
- `stream_publisher`: Publishes test fixture to MediaMTX RTSP
- `metrics_client`: Queries /metrics endpoint
- `log_capture`: Captures container logs for assertions
- `cleanup_resources`: Ensures teardown even on test failure

### Mock Patterns (Echo STS Service)

**Echo STS Event Simulation** (existing functionality):
- `fragment:data` → `fragment:processed` (immediate echo response)
- `config:error_simulation` → Configure TIMEOUT, MODEL_ERROR, etc.
- `config:backpressure` → Emit backpressure events (pause, slow_down, none)

**New Enhancement for Reconnection Testing**:
- `simulate:disconnect` → Force Socket.IO disconnect from server side
- Event payload: `{ "delay_ms": 0 }` (immediate disconnect)
- Response: Server closes connection, triggers client reconnection flow

### Coverage Enforcement

**E2E Test Success Criteria**:
- All P1 tests pass (full pipeline, A/V sync)
- All P2 tests pass (circuit breaker, backpressure, fragment tracker)
- P3 test passes (reconnection) for production readiness
- Tests run reliably in CI (95% pass rate over 20 runs)
- Test suite completes in <10 minutes total

**No Code Coverage Metrics**:
E2E tests validate integration behavior, not line coverage. Unit tests already provide coverage for WorkerRunner components.

### Test Naming Conventions

Follow spec user story mapping:
- `test_full_pipeline_rtsp_to_rtmp()` - User Story 1 (P1)
- `test_av_sync_within_threshold()` - User Story 2 (P1)
- `test_circuit_breaker_opens_on_sts_failures()` - User Story 3 (P2)
- `test_worker_respects_backpressure()` - User Story 4 (P2)
- `test_fragment_tracker_respects_max_inflight()` - User Story 5 (P2)
- `test_worker_reconnects_after_sts_disconnect()` - User Story 6 (P3)

## Complexity Tracking

No constitution violations. E2E test suite aligns with:
- Principle II (isolated test environment via Docker)
- Principle VIII (test strategy defined before implementation)
- Spec-driven development (spec.md created first)

No additional complexity introduced.

## Phase 0: Research & Unknowns

**Research Tasks**:

1. **Docker Compose Test Patterns**: How to manage Docker Compose lifecycle in pytest fixtures?
   - Research pytest-docker plugin vs. subprocess-based management
   - Find patterns for health checks and service readiness

2. **Prometheus Metrics Parsing**: How to parse /metrics endpoint in tests?
   - Research prometheus_client.parser library
   - Find patterns for metric assertions (gauge values, counter increments)

3. **ffprobe PTS Analysis**: How to extract and compare PTS from output stream?
   - Research ffprobe JSON output format for stream analysis
   - Find patterns for A/V sync delta calculation

4. **Socket.IO Server-Side Disconnect**: How does Echo STS force disconnect from server?
   - Research python-socketio server disconnect methods (emit, disconnect)
   - Find patterns for reconnection testing

5. **Test Fixture Acquisition**: Where to get deterministic 60s video file?
   - Research copyright-free test video sources (Big Buck Bunny, Blender Foundation)
   - Alternative: Generate synthetic test video with ffmpeg

**Output**: research.md documenting decisions for each research task

## Phase 1: Design & Implementation Structure

### Data Model (Test Fixtures & Docker Network)

**Entities** (see data-model.md):

1. **E2E Test Environment**
   - Services: MediaMTX, media-service, echo-sts
   - Network: Shared Docker network (e2e-test-network)
   - Lifecycle: Start in setup, stop in teardown

2. **Test Fixture**
   - File: 1-min-nfl.mp4
   - Properties: H.264 video, AAC audio, 60s duration
   - Publishing: ffmpeg subprocess to MediaMTX RTSP

3. **Pipeline Metrics Snapshot**
   - Source: /metrics HTTP endpoint
   - Parsed metrics: worker_audio_fragments_total, worker_inflight_fragments, worker_av_sync_delta_ms, etc.
   - Assertions: Counter increments, gauge values, state transitions

4. **A/V Sync Measurement**
   - Source: ffprobe JSON output from RTMP stream
   - Video PTS, Audio PTS per segment
   - Delta calculation: |video_pts - audio_pts|

5. **Circuit Breaker State Log**
   - Source: Container logs (media-service)
   - Events: State transitions (closed → open → half-open → closed)
   - Metrics: worker_sts_breaker_state gauge

6. **Backpressure Event Log**
   - Source: Container logs + metrics
   - Events: severity, action (pause, slow_down, none), recommended_delay_ms
   - Metrics: worker_backpressure_events_total counter

7. **Reconnection Attempt Log**
   - Source: Container logs
   - Events: Disconnect, reconnection attempts with backoff timestamps
   - Metrics: worker_reconnection_total counter

### API Contracts

**Echo STS Enhancement** (see contracts/sts-simulate-disconnect.json):

New event from test client to Echo STS server:
```json
{
  "event": "simulate:disconnect",
  "payload": {
    "delay_ms": 0
  }
}
```

Server behavior:
- Receives `simulate:disconnect` event
- Waits `delay_ms` milliseconds
- Calls `socketio.disconnect(sid)` to force client disconnect
- Client triggers reconnection flow

### Test Implementation Phases

**Phase 1: Infrastructure Setup** (P0 - prerequisite for all tests)
- Create tests/e2e/docker-compose.yml with 3 services
- Create tests/e2e/conftest.py with shared fixtures
- Create helpers/ for Docker, ffmpeg, metrics, stream analysis
- Validate environment startup/teardown

**Phase 2: P1 Tests** (core functionality)
- test_full_pipeline.py: Validate RTSP → STS → RTMP end-to-end
- test_av_sync.py: Validate A/V sync delta < 120ms

**Phase 3: P2 Tests** (resilience & flow control)
- test_circuit_breaker.py: Validate failure → fallback → recovery
- test_backpressure.py: Validate pause/resume/slow_down
- test_fragment_tracker.py: Validate max_inflight enforcement

**Phase 4: P3 Tests** (reconnection)
- Enhance Echo STS with simulate:disconnect event
- test_reconnection.py: Validate disconnect → backoff → reconnect

**Phase 5: CI Integration** (production readiness)
- Add E2E test suite to CI pipeline
- Validate 95% pass rate over 20 runs
- Document flakiness mitigation (timeouts, retries)

### Quickstart Guide

See quickstart.md for:
- Prerequisites (Docker, Docker Compose, ffmpeg)
- Running E2E tests locally
- Debugging test failures
- Adding new E2E tests

## Dependencies

**External Services**:
- MediaMTX (containerized via docker-compose.yml)
- Echo STS Service (containerized, enhanced with simulate:disconnect)

**Python Libraries**:
- pytest>=7.0
- pytest-asyncio
- python-socketio[client]>=5.0
- prometheus_client (for metrics parsing)
- PyYAML (for docker-compose parsing if needed)

**Infrastructure**:
- Docker Engine
- Docker Compose v2
- ffmpeg (for stream publishing)
- ffprobe (for PTS analysis)

**Specifications**:
- specs/003-gstreamer-stream-worker/spec.md (WorkerRunner behavior)
- specs/017-echo-sts-service/spec.md (Echo STS event protocol)
- specs/017-echo-sts-service/contracts/ (Socket.IO schemas)

## Out of Scope

- Performance benchmarking (latency percentiles, throughput limits)
- Load testing (multiple concurrent streams)
- GPU STS service testing (only Echo STS for E2E)
- Multi-worker orchestration (only single worker instance)
- MediaMTX configuration tuning (use defaults)
- Custom error scenarios beyond spec 017 error codes
- Production deployment automation (E2E tests for validation only)

## Next Steps

After /speckit.plan completion:
1. Execute Phase 0 research (see research.md)
2. Generate data-model.md (test fixtures, Docker network entities)
3. Generate contracts/sts-simulate-disconnect.json (Echo STS enhancement schema)
4. Generate quickstart.md (E2E test execution guide)
5. Run /speckit.tasks to break down implementation into tasks
6. Run /speckit.checklist to generate validation checklist
