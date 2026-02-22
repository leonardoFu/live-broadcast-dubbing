# Feature Specification: E2E Stream Handler Tests

**Feature Branch**: `018-e2e-stream-handler-tests`
**Created**: 2025-12-30
**Status**: Draft
**Input**: User description: "Add more E2E tests to verify the stream handler implementation with MediaMTX and echo-sts server."

## Overview

This specification defines comprehensive end-to-end (E2E) tests for the WorkerRunner pipeline orchestration with real MediaMTX RTSP/RTMP server and Echo STS Service. These tests verify the complete dubbing pipeline from RTSP input through STS processing to RTMP output, validating integration points that unit and component integration tests cannot cover.

The tests fill a critical gap: while existing unit tests verify individual components and integration tests verify service-to-service communication, no tests currently validate the full WorkerRunner orchestration with real external dependencies (MediaMTX + Echo STS).

**Related Specs**:
- [specs/003-gstreamer-stream-worker](../003-gstreamer-stream-worker/spec.md) - WorkerRunner implementation spec
- [specs/017-echo-sts-service](../017-echo-sts-service/spec.md) - Echo STS Service for testing
- [specs/001-mediamtx-integration](../001-mediamtx-integration/spec.md) - MediaMTX integration

## User Scenarios & Testing

### User Story 1 - Full Pipeline Flow: RTSP → Worker → Echo STS → RTMP (Priority: P1)

An E2E test that validates the complete dubbing pipeline orchestration: MediaMTX publishes RTSP stream, WorkerRunner ingests via input pipeline, segments are buffered, audio is sent to Echo STS, dubbed audio returns, A/V sync pairs segments, and output publishes to RTMP on MediaMTX.

**Why this priority**: This is the core end-to-end workflow that the entire system is designed to perform. Without this working, no dubbing pipeline exists. This test provides the highest confidence that all components integrate correctly in a production-like environment.

**Independent Test**: This can be tested with a pre-recorded test video fixture published to MediaMTX.
- **Unit test**: N/A (this is inherently an E2E integration test)
- **Contract test**: Verify WorkerRunner emits correct Socket.IO events to Echo STS per spec 017 contracts
- **E2E test**: `test_full_pipeline_rtsp_to_rtmp()` validates complete workflow with MediaMTX + Echo STS + test fixture
- **Success criteria**: 60-second test video processed end-to-end, 10 segments (6s each) sent to STS and received back, RTMP output playable without errors, pipeline completes within 90 seconds

**Acceptance Scenarios**:

1. **Given** MediaMTX running and Echo STS Service running, **When** test fixture (1-min-nfl.mp4) is published to `rtsp://localhost:8554/live/test/in`, **Then** WorkerRunner connects and starts ingesting within 5 seconds
2. **Given** WorkerRunner ingesting RTSP stream, **When** 6 seconds of video/audio accumulated, **Then** segment is written to disk and audio is sent to Echo STS via Socket.IO
3. **Given** Echo STS receives audio fragment, **When** fragment is processed, **Then** dubbed audio returns via `fragment:processed` event within 1 second
4. **Given** dubbed audio received, **When** video and audio segments are paired by A/V sync, **Then** sync delta is less than 120ms
5. **Given** A/V sync completes pairing, **When** output pipeline publishes to RTMP, **Then** output stream is available at `rtmp://localhost:1935/live/test/out` within 1 second of first segment pair
6. **Given** full 60-second stream processed, **When** all segments complete, **Then** 10 segments were processed, RTMP output duration matches input duration (+/- 500ms), and no errors logged

---

### User Story 2 - A/V Sync Verification: Sync Delta < 120ms (Priority: P1)

An E2E test that specifically validates A/V synchronization remains within acceptable threshold (120ms) throughout the full pipeline despite asynchronous STS processing latency.

**Why this priority**: A/V sync is critical for user experience. Lip sync errors are immediately noticeable and ruin the dubbing experience. This test ensures the pipeline maintains tight synchronization under real-world conditions with network latency and processing delays.

**Independent Test**: This can be tested by measuring PTS deltas between video and audio in output stream.
- **Unit test**: `test_av_sync_manager_delta_measurement()` validates sync delta calculation logic
- **Contract test**: N/A (purely time-based verification)
- **E2E test**: `test_av_sync_within_threshold()` validates sync delta < 120ms throughout full pipeline
- **Success criteria**: A/V sync delta measured at output pipeline remains < 120ms for 95% of segments, no sync corrections required beyond initial offset

**Acceptance Scenarios**:

1. **Given** WorkerRunner processing stream with Echo STS, **When** each segment pair is output, **Then** A/V sync delta metric reports < 120ms
2. **Given** Echo STS introduces variable latency (0-500ms), **When** audio returns at different times, **Then** A/V sync buffers absorb latency variation without drift
3. **Given** 10 segments processed end-to-end, **When** output RTMP stream is analyzed, **Then** video PTS and audio PTS deltas are within 120ms for all segments
4. **Given** A/V sync delta exceeds threshold temporarily, **When** sync manager detects drift, **Then** correction is applied via gradual slew (not hard jump) and logged

---

### User Story 3 - Circuit Breaker Integration: Fallback on STS Failure (Priority: P2)

An E2E test that validates circuit breaker protection when Echo STS is configured to simulate failures. The test verifies that after consecutive failures, the circuit breaker opens and original audio is used as fallback, then recovers after cooldown.

**Why this priority**: Production resilience is critical for a streaming service that must remain operational even when STS service has issues. This validates fault tolerance under realistic failure scenarios.

**Independent Test**: Configure Echo STS to simulate errors via `config:error_simulation` event.
- **Unit test**: `test_circuit_breaker_state_transitions()` validates breaker state machine (closed → open → half-open → closed)
- **Contract test**: Verify circuit breaker only counts retryable errors per spec 003 (TIMEOUT, MODEL_ERROR, GPU_OOM, QUEUE_FULL, RATE_LIMIT)
- **E2E test**: `test_circuit_breaker_opens_on_sts_failures()` validates full failure → fallback → recovery workflow
- **Success criteria**: Circuit breaker opens after 5 consecutive failures, fallback audio used (original audio in output), breaker recovers after 30s cooldown, normal processing resumes

**Acceptance Scenarios**:

1. **Given** WorkerRunner processing stream normally, **When** Echo STS is configured to return 5 consecutive TIMEOUT errors, **Then** circuit breaker opens and subsequent fragments use original audio fallback
2. **Given** circuit breaker is open, **When** fragments arrive, **Then** STS calls are skipped, original audio is written directly to output, and metrics show `worker_fallback_total` incrementing
3. **Given** circuit breaker is open, **When** 30 seconds elapse (cooldown), **Then** breaker enters half-open state and sends 1 probe fragment to STS
4. **Given** breaker is half-open and probe succeeds, **When** next fragment arrives, **Then** breaker closes and normal dubbing resumes
5. **Given** Echo STS returns non-retryable error (INVALID_CONFIG), **When** error is received, **Then** circuit breaker failure counter is NOT incremented (error logged but breaker stays closed)

---

### User Story 4 - Backpressure Handling: Worker Handles STS Backpressure (Priority: P2)

An E2E test that validates WorkerRunner responds correctly to backpressure events from Echo STS. The test configures Echo STS to emit backpressure with various actions (pause, slow_down, none) and verifies worker flow control.

**Why this priority**: Backpressure is essential for preventing buffer overflows and GPU overload in production STS service. This validates the worker respects STS capacity limits and adjusts sending rate dynamically.

**Independent Test**: Configure Echo STS backpressure simulation and monitor fragment sending rate.
- **Unit test**: `test_backpressure_handler_pause_resume()` validates pause/resume logic; `test_backpressure_handler_slow_down_delay()` validates delay insertion
- **Contract test**: Verify backpressure events match spec 017 schema (severity, action, recommended_delay_ms)
- **E2E test**: `test_worker_respects_backpressure()` validates worker adjusts sending rate based on backpressure events
- **Success criteria**: Worker pauses on `action: pause`, resumes on `action: none`, inserts delay on `action: slow_down`, metrics show backpressure events recorded

**Acceptance Scenarios**:

1. **Given** WorkerRunner sending fragments to Echo STS, **When** Echo STS emits backpressure with `action: "pause"`, **Then** worker stops sending new fragments until backpressure clears (subsequent event with `action: "none"`)
2. **Given** worker is paused due to backpressure, **When** Echo STS emits backpressure with `action: "none"`, **Then** worker resumes sending fragments normally
3. **Given** Echo STS emits backpressure with `action: "slow_down"` and `recommended_delay_ms: 500`, **When** worker has next fragment ready, **Then** worker waits 500ms before sending each new fragment
4. **Given** backpressure handled correctly, **When** metrics endpoint is queried, **Then** `worker_backpressure_events_total` shows correct count by action type (pause, slow_down, none)

---

### User Story 5 - Fragment Tracker E2E: In-Flight Tracking Across Services (Priority: P2)

An E2E test that validates FragmentTracker correctly tracks in-flight fragments across the full pipeline: fragment sent to STS, tracked as in-flight, fragment:ack received, fragment:processed received, tracking completed. Validates max_inflight limit enforcement.

**Why this priority**: Fragment tracking is essential for flow control and preventing queue overflows. In-flight tracking ensures the worker doesn't send more fragments than STS can handle (max_inflight limit).

**Independent Test**: Send fragments and verify in-flight count updates correctly.
- **Unit test**: `test_fragment_tracker_inflight_count()` validates tracking add/complete; `test_fragment_tracker_max_inflight()` validates limit enforcement
- **Contract test**: Verify fragment_id correlation between fragment:data, fragment:ack, and fragment:processed events
- **E2E test**: `test_fragment_tracker_respects_max_inflight()` validates worker enforces max_inflight=3 across full pipeline
- **Success criteria**: Worker never exceeds max_inflight=3, metrics show correct in-flight count, all fragments are tracked and completed

**Acceptance Scenarios**:

1. **Given** WorkerRunner configured with max_inflight=3, **When** 5 segments are ready, **Then** worker sends only 3 fragments and waits for completions before sending more
2. **Given** 3 fragments in-flight, **When** Echo STS returns fragment:processed for fragment 1, **Then** in-flight count drops to 2 and worker sends fragment 4
3. **Given** fragments being tracked, **When** metrics endpoint is queried, **Then** `worker_inflight_fragments` gauge shows current in-flight count (0-3)
4. **Given** fragment sent but no response for 8 seconds (timeout), **When** timeout occurs, **Then** fragment is removed from in-flight tracking, fallback audio used, and worker can send next fragment

---

### User Story 6 - Reconnection Resilience: Recovery After STS Disconnection (Priority: P3)

An E2E test that validates WorkerRunner handles unexpected Socket.IO disconnection from Echo STS and successfully reconnects with exponential backoff. In-flight fragments fallback to original audio, and pipeline resumes with fresh sequence numbering.

**Why this priority**: Network resilience is important for production but less critical than core functionality. This validates the worker can recover from transient network failures without manual intervention.

**Independent Test**: Force Echo STS disconnect and verify reconnection behavior.
- **Unit test**: `test_sts_client_reconnection_backoff()` validates exponential backoff timing (2s, 4s, 8s, 16s, 32s); `test_reconnection_discards_inflight()` validates in-flight handling
- **Contract test**: Verify stream:init is re-sent after reconnection with fresh session
- **E2E test**: `test_worker_reconnects_after_sts_disconnect()` validates full disconnect → fallback → reconnect → resume workflow
- **Success criteria**: Worker attempts 5 reconnections with correct backoff timing, in-flight fragments use fallback audio, after reconnection stream resumes from next segment boundary with sequence_number=0

**Acceptance Scenarios**:

1. **Given** WorkerRunner processing stream normally with 2 fragments in-flight, **When** Echo STS connection drops unexpectedly, **Then** worker immediately uses fallback audio for 2 in-flight fragments and logs disconnect
2. **Given** STS disconnected, **When** worker starts reconnection, **Then** worker attempts reconnection with exponential backoff: 2s, 4s, 8s, 16s, 32s (up to 5 attempts)
3. **Given** reconnection succeeds, **When** connection is re-established, **Then** worker re-sends stream:init, waits for stream:ready, and resumes from next complete 6-second segment boundary with fresh sequence_number starting from 0
4. **Given** reconnection fails after 5 attempts, **When** final attempt fails, **Then** worker transitions to permanent failure state, logs error, and exits with non-zero code (for orchestrator restart)
5. **Given** reconnection succeeded and stream resumed, **When** metrics endpoint is queried, **Then** `worker_reconnection_total` counter shows 1, `worker_sts_breaker_state` shows 0 (closed), pipeline continues normally

---

### Edge Cases

- What happens when MediaMTX RTSP stream is not available at startup? Worker retries 3 times with exponential backoff (1s, 2s, 4s), then exits with error if connection fails.
- What happens when Echo STS returns audio with different duration than expected? Worker sanitizes (trim/pad) if within 10% tolerance, else uses fallback audio and logs warning.
- What happens when RTMP publish to MediaMTX fails? Worker logs error and exits with non-zero code (orchestrator restarts worker).
- What happens when test fixture has no audio track? Worker logs error "audio track required for dubbing" and exits immediately.
- What happens when all segments use fallback audio (STS never responds)? Pipeline completes with original audio, metrics show 100% fallback rate, circuit breaker opens after 5 failures.
- What happens when video buffers arrive but audio is delayed? Video is buffered up to av_offset_ns (6 seconds default) before first output, then waits for audio pairs.
- What happens when Socket.IO ping timeout occurs during processing? Connection closes, worker triggers reconnection flow per User Story 6.
- What happens when Echo STS session is lost during pause? On resume, worker detects missing session, re-initializes stream, and continues processing.

## Requirements

### Functional Requirements

**E2E Test Infrastructure (P1)**

- **FR-001**: E2E tests MUST use Docker Compose to start MediaMTX and Echo STS Service in isolated environment
- **FR-002**: E2E tests MUST use test fixtures from `tests/fixtures/test-streams/` (e.g., 1-min-nfl.mp4)
- **FR-003**: E2E tests MUST publish test fixtures to MediaMTX RTSP using ffmpeg or GStreamer scripts
- **FR-004**: E2E tests MUST verify output RTMP stream availability and playback via ffprobe inspection
- **FR-005**: E2E tests MUST clean up all resources (workers, streams, containers) in teardown even if test fails

**Full Pipeline E2E (P1)**

- **FR-006**: E2E test MUST validate complete RTSP → Worker → STS → RTMP flow with 60-second test fixture
- **FR-007**: E2E test MUST verify 10 segments (6s each) are created, sent to STS, and received back
- **FR-008**: E2E test MUST verify RTMP output stream duration matches input duration (+/- 500ms)
- **FR-009**: E2E test MUST verify no errors logged during full pipeline execution
- **FR-010**: E2E test MUST complete within 90 seconds for 60-second input fixture

**A/V Sync E2E (P1)**

- **FR-011**: E2E test MUST measure A/V sync delta at output pipeline for each segment pair
- **FR-012**: E2E test MUST verify 95% of segments have sync delta < 120ms
- **FR-013**: E2E test MUST verify A/V sync metrics are updated correctly in Prometheus metrics
- **FR-014**: E2E test MUST verify sync corrections (if any) use gradual slew, not hard jumps

**Circuit Breaker E2E (P2)**

- **FR-015**: E2E test MUST configure Echo STS to simulate 5 consecutive retryable errors (TIMEOUT)
- **FR-016**: E2E test MUST verify circuit breaker opens after 5 failures and uses fallback audio
- **FR-017**: E2E test MUST verify circuit breaker enters half-open after 30s cooldown
- **FR-018**: E2E test MUST verify circuit breaker closes on successful probe in half-open state
- **FR-019**: E2E test MUST verify non-retryable errors (INVALID_CONFIG) do NOT increment failure counter
- **FR-020**: E2E test MUST verify circuit breaker state transitions are logged and reflected in metrics

**Backpressure E2E (P2)**

- **FR-021**: E2E test MUST configure Echo STS to emit backpressure events (pause, slow_down, none)
- **FR-022**: E2E test MUST verify worker pauses sending on `action: "pause"` and resumes on `action: "none"`
- **FR-023**: E2E test MUST verify worker inserts delay on `action: "slow_down"` with `recommended_delay_ms`
- **FR-024**: E2E test MUST verify backpressure events are recorded in metrics by action type

**Fragment Tracking E2E (P2)**

- **FR-025**: E2E test MUST verify worker enforces max_inflight limit (default 3)
- **FR-026**: E2E test MUST verify in-flight count increases on fragment:data send and decreases on fragment:processed
- **FR-027**: E2E test MUST verify metrics show correct in-flight count during pipeline execution
- **FR-028**: E2E test MUST verify fragment timeout (8s) removes fragment from tracking and triggers fallback

**Reconnection E2E (P3)**

- **FR-029**: E2E test MUST force STS disconnect and verify reconnection with exponential backoff (2s, 4s, 8s, 16s, 32s)
- **FR-030**: E2E test MUST verify in-flight fragments use fallback audio on disconnect
- **FR-031**: E2E test MUST verify stream resumes with fresh stream:init and sequence_number=0 after reconnection
- **FR-032**: E2E test MUST verify worker exits with non-zero code after 5 failed reconnection attempts

**Metrics Validation (P3)**

- **FR-033**: E2E tests MUST verify Prometheus metrics endpoint (/metrics) returns valid Prometheus format
- **FR-034**: E2E tests MUST verify key metrics are updated correctly: `worker_audio_fragments_total`, `worker_fallback_total`, `worker_inflight_fragments`, `worker_av_sync_delta_ms`, `worker_sts_breaker_state`, `worker_backpressure_events_total`, `worker_reconnection_total`

### Key Entities

- **E2E Test Environment**: Docker Compose configuration with MediaMTX (RTSP/RTMP server) + Echo STS Service + test fixtures
- **Test Fixture**: Pre-recorded video file (1-min-nfl.mp4) with known properties (H.264 video, AAC audio, 60s duration)
- **Pipeline Metrics Snapshot**: Captured Prometheus metrics at test completion for validation
- **A/V Sync Measurement**: PTS delta between video and audio at each output segment pair
- **Circuit Breaker State Log**: Captured state transitions (closed → open → half-open → closed) during test
- **Backpressure Event Log**: Captured backpressure events (severity, action, recommended_delay_ms) during test
- **Reconnection Attempt Log**: Captured reconnection attempts with timestamps for backoff validation

## Success Criteria

### Measurable Outcomes

- **SC-001**: All P1 E2E tests pass with 60-second test fixture completing in under 90 seconds
- **SC-002**: A/V sync delta remains < 120ms for 95% of segments in full pipeline E2E test
- **SC-003**: Circuit breaker correctly opens after 5 failures, recovers after cooldown, verified via metrics and logs
- **SC-004**: Worker correctly handles backpressure pause/resume cycle with Echo STS simulation
- **SC-005**: Worker enforces max_inflight=3 throughout full pipeline execution
- **SC-006**: Worker successfully reconnects after STS disconnect with correct exponential backoff timing
- **SC-007**: All Prometheus metrics are correctly updated and exposed via /metrics endpoint
- **SC-008**: E2E test suite executes reliably in CI/CD environment without flakiness (95% pass rate over 20 runs)

## Architecture Decisions

Based on clarification questions resolved during specification:

### Decision 1: Test Location
**Choice**: `tests/e2e/` (root directory)
**Rationale**: These are true cross-service E2E tests spanning MediaMTX + media-service + echo-sts. The root `tests/e2e/` directory is "reserved for full dubbing pipeline tests" per monorepo structure.

### Decision 2: Docker Compose Configuration
**Choice**: New dedicated `tests/e2e/docker-compose.yml`
**Rationale**: A dedicated E2E compose file provides test isolation, predictable networking (single shared network), and doesn't affect dev environments for individual services.

### Decision 3: Test Fixture Publishing
**Choice**: Python subprocess in pytest fixtures
**Rationale**: Direct control from tests using subprocess gives proper cleanup on test failure, test lifecycle control, and doesn't require shell script modifications.

### Decision 4: Metrics Validation
**Choice**: Query HTTP `/metrics` endpoint and parse Prometheus text format
**Rationale**: Tests the full observability stack. Use `prometheus_client.parser` to parse responses into structured data for assertions.

### Decision 5: Reconnection Simulation
**Choice**: Add `simulate:disconnect` event to Echo STS Service
**Rationale**: Provides precise test control, matches existing `config:error_simulation` pattern, more reliable than container restarts or network manipulation.

## Test Fixtures and Verification

### Primary Test Fixture

- **File**: `tests/fixtures/test-streams/1-min-nfl.mp4`
- **Duration**: 60 seconds
- **Video**: H.264, 1280x720, 30fps
- **Audio**: AAC, 48kHz stereo
- **Expected Segments**: 10 segments (6 seconds each)

### Test Environment Setup

```bash
# Start all services via dedicated E2E Docker Compose
docker-compose -f tests/e2e/docker-compose.yml up -d

# Run E2E tests (fixture publishing handled by pytest fixtures)
pytest tests/e2e/ -v --log-cli-level=INFO

# Cleanup
docker-compose -f tests/e2e/docker-compose.yml down
```

### Test Directory Structure

```
tests/e2e/
├── __init__.py
├── docker-compose.yml          # MediaMTX + media-service + echo-sts on shared network
├── conftest.py                 # Shared fixtures (docker startup, ffmpeg publishing, cleanup)
├── test_full_pipeline.py       # P1: RTSP → Worker → STS → RTMP
├── test_av_sync.py             # P1: A/V sync delta verification
├── test_circuit_breaker.py     # P2: Circuit breaker failure/recovery
├── test_backpressure.py        # P2: Backpressure handling
├── test_fragment_tracker.py    # P2: In-flight tracking and max_inflight
└── test_reconnection.py        # P3: Disconnect/reconnect resilience
```

### Verification Methods

- **RTMP Output Playback**: Use ffprobe via subprocess to verify output stream properties
- **Metrics Validation**: Query /metrics HTTP endpoint and parse with `prometheus_client.parser`
- **Log Analysis**: Capture container logs via docker-compose logs for assertions
- **PTS Analysis**: Use ffprobe to extract PTS from output stream and calculate A/V deltas

## Assumptions

- MediaMTX is accessible at `localhost:8554` (RTSP) and `localhost:1935` (RTMP)
- Echo STS Service is accessible at `localhost:8080` via Socket.IO
- Test fixture 1-min-nfl.mp4 contains valid H.264 video and AAC audio (verified beforehand)
- Docker and Docker Compose are available in test environment
- Python 3.10.x environment per monorepo constitution
- GStreamer 1.x with Python bindings installed (gi.repository)
- E2E tests run in isolated environment (not production)
- Test execution environment has sufficient resources (2 CPU cores, 4GB RAM minimum)

## Dependencies

- **External Services**: MediaMTX (RTSP/RTMP server), Echo STS Service (Socket.IO server)
- **Python Libraries**: pytest, pytest-asyncio, python-socketio (client), prometheus_client
- **Infrastructure**: Docker, Docker Compose
- **Test Fixtures**: tests/fixtures/test-streams/1-min-nfl.mp4, ffmpeg or GStreamer CLI tools
- **Specifications**:
  - [specs/003-gstreamer-stream-worker/spec.md](../003-gstreamer-stream-worker/spec.md) - WorkerRunner implementation
  - [specs/017-echo-sts-service/spec.md](../017-echo-sts-service/spec.md) - Echo STS Service protocol
  - [specs/017-echo-sts-service/contracts/](../017-echo-sts-service/contracts/) - Socket.IO event schemas

## Out of Scope

- Performance testing (latency benchmarks, throughput limits)
- GPU STS service testing (only Echo STS for E2E tests)
- Multi-worker orchestration (only single worker instance)
- Production deployment configuration
- Load testing with multiple concurrent streams
- MediaMTX configuration tuning (use defaults)
- Custom error scenarios beyond spec 017 error codes
