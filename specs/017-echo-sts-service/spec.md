# Feature Specification: Echo STS Service for E2E Testing

**Feature Branch**: `017-echo-sts-service`
**Created**: 2025-12-28
**Status**: Draft
**Input**: User description: "Build an echo/mock service for sts-service to be used for E2E testing with full WebSocket Audio Fragment Protocol support"

## Overview

The Echo STS Service is a protocol-compliant mock implementation of the STS (Speech-to-Speech) Service designed for end-to-end testing. Rather than performing actual ASR (Automatic Speech Recognition), translation, and TTS (Text-to-Speech) processing, this service echoes received audio fragments back to the caller. This enables comprehensive E2E testing of the media-service integration without requiring GPU resources or complex ML model dependencies.

The service must fully implement the WebSocket Audio Fragment Protocol as defined in [specs/016-websocket-audio-protocol.md](../016-websocket-audio-protocol.md), acting as the Socket.IO server (STS role) while the media-service stream worker acts as the client.

---

## Clarifications

### Session 2025-12-28

- Q: How should error simulation be configured? A: Via Socket.IO events (`config:error_simulation`) sent by the test before fragments, providing maximum flexibility during E2E tests without service restarts.
- Q: Where should the Echo STS Service code be placed? A: In `apps/sts-service/src/sts_service/echo/` as a subpackage within the sts-service, allowing shared types and following the monorepo structure.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stream Worker Connects and Initializes Stream (Priority: P1)

An E2E test scenario where the media-service stream worker establishes a WebSocket connection to the Echo STS Service and initializes a streaming session. The worker authenticates with an API key and sends stream configuration. The Echo STS Service validates the connection and responds with session confirmation.

**Why this priority**: Connection establishment is the foundation of all protocol interactions. Without successful connection and initialization, no audio processing can occur. This is the critical path that must work first.

**Independent Test**: This can be tested by attempting to connect with valid and invalid API keys, and sending stream:init with various configurations.
- **Unit test**: `test_authentication_valid_key()` validates API key acceptance; `test_authentication_invalid_key()` validates rejection
- **Contract test**: `test_stream_init_payload_schema()` validates stream:init message structure matches spec 016
- **Integration test**: `test_worker_connects_and_initializes()` validates full connection flow from worker to echo service
- **Success criteria**: Valid API key accepts connection, invalid key rejects with AUTH_FAILED error, stream:ready response matches protocol schema

**Acceptance Scenarios**:

1. **Given** a configured Echo STS Service running with API key authentication enabled, **When** a worker connects with a valid API key and sends stream:init with valid configuration, **Then** the service responds with stream:ready containing session_id, max_inflight, and capabilities
2. **Given** a configured Echo STS Service running, **When** a worker connects with an invalid API key, **Then** the connection is rejected immediately with AUTH_FAILED error
3. **Given** a configured Echo STS Service running, **When** a worker sends stream:init with invalid configuration (missing required fields), **Then** the service responds with INVALID_CONFIG error

---

### User Story 2 - Audio Fragment Echo Processing (Priority: P1)

An E2E test scenario where the media-service stream worker sends audio fragments to the Echo STS Service. The service acknowledges receipt, "processes" the fragment (by echoing it), and returns the audio data in a fragment:processed event with dubbed_audio containing the original audio.

**Why this priority**: This is the core functionality of the echo service - receiving fragments and returning them. Without this working, the service cannot fulfill its purpose as an E2E testing tool.

**Independent Test**: Send audio fragments and verify they are echoed back correctly with proper sequencing.
- **Unit test**: `test_fragment_echo_preserves_audio()` validates audio data is returned unchanged; `test_fragment_response_structure()` validates response payload
- **Contract test**: `test_fragment_data_schema()` validates incoming fragment matches spec 016; `test_fragment_processed_schema()` validates outgoing response
- **Integration test**: `test_worker_sends_fragments_receives_echo()` validates full fragment round-trip
- **Success criteria**: Fragment audio echoed with less than 50ms processing overhead, sequence numbers preserved, all response fields populated correctly

**Acceptance Scenarios**:

1. **Given** an initialized stream session, **When** a worker sends fragment:data with valid audio payload, **Then** the service immediately responds with fragment:ack (status: queued), then sends fragment:processed with dubbed_audio containing the original audio data
2. **Given** an initialized stream session, **When** a worker sends multiple fragments in sequence, **Then** fragment:processed events are returned in sequence_number order
3. **Given** an initialized stream session, **When** a worker sends a fragment, **Then** fragment:processed includes processing_time_ms, transcript (mock text), and translated_text (mock text)

---

### User Story 3 - Stream Lifecycle Management (Priority: P2)

An E2E test scenario where the media-service stream worker manages the full stream lifecycle including pause, resume, and graceful end. The Echo STS Service responds appropriately to each lifecycle event.

**Why this priority**: Lifecycle management ensures proper resource cleanup and allows for graceful handling of stream state changes. This is essential for robust E2E tests but secondary to core fragment processing.

**Independent Test**: Test pause/resume flow and graceful stream termination.
- **Unit test**: `test_stream_pause_stops_new_fragments()` validates pause behavior; `test_stream_resume_allows_fragments()` validates resume; `test_stream_end_completes()` validates end
- **Contract test**: `test_stream_pause_payload()`, `test_stream_resume_payload()`, `test_stream_end_payload()` validate message structures
- **Integration test**: `test_worker_pause_resume_end_lifecycle()` validates full lifecycle from worker perspective
- **Success criteria**: Pause prevents new fragment processing, resume re-enables processing, stream:complete returns accurate statistics

**Acceptance Scenarios**:

1. **Given** an initialized stream with fragments in flight, **When** a worker sends stream:pause, **Then** the service completes in-flight fragments but accepts no new fragments until resumed
2. **Given** a paused stream, **When** a worker sends stream:resume, **Then** the service accepts new fragments normally
3. **Given** an initialized stream, **When** a worker sends stream:end, **Then** the service completes all in-flight fragments and responds with stream:complete containing statistics (total_fragments, success_count, avg_processing_time_ms)
4. **Given** a stream that has received stream:complete, **Then** the connection auto-closes after 5 seconds

---

### User Story 4 - Backpressure Simulation (Priority: P2)

An E2E test scenario where the Echo STS Service simulates backpressure conditions to test the media-service worker's flow control handling. The service can be configured to trigger backpressure events.

**Why this priority**: Backpressure testing is important for production resilience, but the echo service can still be useful without this feature. It enables testing of edge cases in the worker's flow control logic.

**Independent Test**: Configure backpressure simulation and verify worker responds correctly.
- **Unit test**: `test_backpressure_event_emission()` validates backpressure event structure; `test_backpressure_severity_levels()` validates low/medium/high configurations
- **Contract test**: `test_backpressure_payload_schema()` validates backpressure message matches spec 016
- **Integration test**: `test_worker_handles_backpressure()` validates worker slows down or pauses when backpressure received
- **Success criteria**: Backpressure events emitted at configured thresholds, worker responds to action recommendations

**Acceptance Scenarios**:

1. **Given** an initialized stream with backpressure simulation enabled, **When** the in-flight fragment count exceeds the configured threshold, **Then** the service emits a backpressure event with appropriate severity and action recommendation
2. **Given** a backpressure event with action "pause" was sent, **When** the queue clears below threshold, **Then** the service emits backpressure with severity "low" and action "none"

---

### User Story 5 - Error Simulation for Testing (Priority: P3)

An E2E test scenario where the Echo STS Service can be configured to simulate various error conditions to test the media-service worker's error handling.

**Why this priority**: Error simulation is valuable for comprehensive testing but is an enhancement beyond core echo functionality. Tests can be run without error simulation initially.

**Independent Test**: Configure error simulation and verify error responses match protocol.
- **Unit test**: `test_error_event_structure()` validates error payload; `test_error_codes_valid()` validates all error codes from spec 016
- **Contract test**: `test_error_payload_schema()` validates error message matches spec 016
- **Integration test**: `test_worker_handles_timeout_error()`, `test_worker_handles_model_error()` validate worker error recovery
- **Success criteria**: Configured errors emitted correctly, retryable flag accurate, worker can recover from retryable errors

**Acceptance Scenarios**:

1. **Given** an initialized stream with error simulation configured for fragment N, **When** fragment N is received, **Then** the service responds with fragment:processed status "failed" and appropriate error details
2. **Given** error simulation configured for TIMEOUT error, **When** the error is returned, **Then** the retryable flag is set to true
3. **Given** error simulation configured for AUTH_FAILED, **When** a connection attempt is made, **Then** the connection is rejected with AUTH_FAILED error

---

### Edge Cases

- What happens when a fragment is received before stream:init? The service responds with STREAM_NOT_FOUND error.
- How does the system handle fragments larger than 10MB (base64-encoded)? The service responds with FRAGMENT_TOO_LARGE error.
- What happens when sequence numbers have gaps? The service responds with INVALID_SEQUENCE error.
- How does the system handle ping timeout? Connection is closed after ping timeout (10s without response).
- What happens when max_inflight is exceeded? The service emits backpressure warning.
- How does the system handle duplicate fragment_ids? The service rejects with appropriate error.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Connection & Authentication
- **FR-001**: Service MUST act as a Socket.IO server accepting WebSocket connections on a configurable port
- **FR-002**: Service MUST validate API key authentication on connection handshake using the `auth.token` field
- **FR-003**: Service MUST reject unauthorized connections immediately with AUTH_FAILED error
- **FR-004**: Service MUST support `X-Stream-ID` and `X-Worker-ID` extra headers for connection identification
- **FR-005**: Service MUST implement Socket.IO ping/pong with 25s interval and 10s timeout

#### Stream Initialization
- **FR-006**: Service MUST respond to stream:init with stream:ready containing session_id, max_inflight, and capabilities
- **FR-007**: Service MUST validate stream:init configuration and respond with INVALID_CONFIG error for invalid payloads
- **FR-008**: Service MUST support all stream:init configuration fields: source_language, target_language, voice_profile, chunk_duration_ms, sample_rate_hz, channels, format

#### Fragment Processing (Echo)
- **FR-009**: Service MUST respond to fragment:data with immediate fragment:ack (status: queued)
- **FR-010**: Service MUST echo received audio back in fragment:processed with dubbed_audio containing the original audio data
- **FR-011**: Service MUST emit fragment:processed events in sequence_number order (in-order delivery)
- **FR-012**: Service MUST populate processing_time_ms in fragment:processed (actual echo processing time)
- **FR-013**: Service MUST include mock transcript and translated_text fields in fragment:processed (e.g., "[ECHO] Original audio")
- **FR-014**: Service MUST accept fragment:ack from worker confirming receipt of processed fragments

#### Stream Lifecycle
- **FR-015**: Service MUST handle stream:pause by completing in-flight fragments and rejecting new ones
- **FR-016**: Service MUST handle stream:resume by accepting new fragments again
- **FR-017**: Service MUST respond to stream:end with stream:complete containing accurate statistics
- **FR-018**: Service MUST auto-close connection 5 seconds after stream:complete

#### Flow Control
- **FR-019**: Service MUST support configurable backpressure simulation (threshold, severity, action)
- **FR-020**: Service MUST emit backpressure events when configured thresholds are exceeded
- **FR-021**: Service MUST respect max_inflight configuration from stream:init

#### Error Handling
- **FR-022**: Service MUST support error simulation configured via `config:error_simulation` Socket.IO event, allowing tests to dynamically configure which errors to trigger (by sequence_number or fragment_id) without service restart
- **FR-023**: Service MUST emit error events with proper structure (error_id, code, message, severity, retryable)
- **FR-024**: Service MUST reject fragments exceeding 10MB (base64-encoded) with FRAGMENT_TOO_LARGE error
- **FR-025**: Service MUST reject fragments received before stream:init with STREAM_NOT_FOUND error
- **FR-026**: Service MUST emit disconnect event with reason on connection close

#### Configuration
- **FR-027**: Service MUST be configurable via environment variables (port, API key, simulation settings)
- **FR-028**: Service MUST support a configurable processing delay to simulate real STS latency

### Key Entities *(include if feature involves data)*

- **Stream Session**: Represents an active streaming session with configuration, state (initializing, active, paused, ending), and statistics
- **Fragment**: Audio fragment with unique ID, sequence number, timestamp, and audio payload
- **Backpressure State**: Current backpressure severity and action for flow control
- **Error Simulation Config**: Configuration for which errors to simulate and when

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: E2E tests can establish connection and complete stream lifecycle in under 5 seconds for a 10-fragment session
- **SC-002**: Echo service echoes audio fragments with less than 100ms added latency (excluding configurable delay)
- **SC-003**: All message types from spec 016 are implemented and pass contract validation tests
- **SC-004**: Fragment ordering is preserved - fragments are always delivered in sequence_number order
- **SC-005**: Service can handle at least 10 concurrent stream sessions for parallel E2E testing
- **SC-006**: 100% of E2E test scenarios can be executed without requiring GPU resources or ML models
- **SC-007**: Service starts up and is ready to accept connections in under 2 seconds
- **SC-008**: All error codes from spec 016 are implemented and can be simulated for testing

---

## Assumptions

- The service will be implemented in `apps/sts-service/src/sts_service/echo/` as a subpackage of the sts-service
- The service will run in Docker alongside the media-service for E2E tests
- Python 3.10.x will be used consistent with the project constitution
- python-socketio library will be used for Socket.IO server implementation
- The service will be stateless between stream sessions (no persistence required)
- Mock transcript and translation text are fixed strings (no actual processing needed)
- Configurable delay for simulating processing latency defaults to 0ms (instant echo)

---

## Dependencies

- [specs/016-websocket-audio-protocol.md](../016-websocket-audio-protocol.md) - Defines the complete WebSocket Audio Fragment Protocol that this service must implement
- [specs/015-deployment-architecture.md](../015-deployment-architecture.md) - Deployment context for the STS service
- [specs/004-sts-pipeline-design.md](../004-sts-pipeline-design.md) - Original STS pipeline design reference

---

## Out of Scope

- Actual ASR, translation, or TTS processing
- GPU utilization or ML model loading
- Persistent storage of audio or session data
- Production deployment configuration
- Load testing beyond basic concurrent session support
- WebSocket transport fallback to HTTP polling (WebSocket only)
