# Feature Specification: MediaMTX Integration for Live Streaming Pipeline

**Feature Branch**: `001-mediamtx-integration`
**Created**: 2025-12-26
**Status**: Draft
**Input**: User description: "Help me integrate mediamtx into media service and make it runable"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local Development Environment Setup (Priority: P1)

As a developer, I need a single-command way to start the entire MediaMTX-based streaming pipeline locally so I can quickly test changes and debug issues without requiring production infrastructure.

**Why this priority**: This is the foundation for all development work. Without a working local environment, developers cannot implement or test any other features. It unblocks all subsequent work.

**Independent Test**: This can be tested by running the local environment and verifying all components start successfully.
- **Unit test**: `test_docker_compose_config_valid()` validates compose file syntax and service definitions
- **Contract test**: `test_mediamtx_config_schema()` validates MediaMTX configuration against expected schema
- **Integration test**: `test_local_environment_startup()` validates all services start and reach healthy state within 30s
- **Success criteria**: All services start successfully, MediaMTX accepts RTMP connections, APIs are reachable, 80% test coverage

**Acceptance Scenarios**:

1. **Given** a developer has cloned the repository, **When** they run `make dev`, **Then** MediaMTX, media-service, and dependent services start successfully within 30 seconds
2. **Given** the local environment is running, **When** a developer publishes an RTMP test stream to `rtmp://localhost:1935/live/test/in`, **Then** the stream appears in the MediaMTX Control API `/v3/paths/list` endpoint
3. **Given** the local environment is running, **When** a developer accesses `http://localhost:9997/v3/paths/list`, **Then** they receive a valid JSON response showing active paths
4. **Given** the local environment is running, **When** a developer runs `make logs`, **Then** they see log output from all running services
5. **Given** the local environment is running, **When** a developer runs `make down`, **Then** all services stop cleanly within 10 seconds

---

### User Story 2 - RTMP Ingest Triggers Worker Events (Priority: P1)

As a system operator, I need RTMP stream ingestion to automatically trigger downstream processing workers so that published streams are processed without manual intervention.

**Why this priority**: This is the core automation mechanism. Without automatic worker triggering, the system requires manual intervention for every stream, making it impractical for production use.

**Independent Test**: This can be tested by publishing a test stream and verifying hook events are received.
- **Unit test**: `test_hook_wrapper_parses_env_vars()` validates hook script correctly reads MTX_PATH, MTX_QUERY, etc.
- **Contract test**: `test_ready_event_schema()` validates `/v1/mediamtx/events/ready` payload structure
- **Integration test**: `test_rtmp_publish_triggers_ready_event()` validates end-to-end flow from RTMP publish to hook receiver
- **Success criteria**: Hook events fire within 1 second of stream state change, 100% event delivery, 80% test coverage

**Acceptance Scenarios**:

1. **Given** MediaMTX is running and configured with hooks, **When** a publisher starts streaming to `rtmp://localhost:1935/live/stream123/in`, **Then** the media-service service receives a `POST /v1/mediamtx/events/ready` request with `path: "live/stream123/in"` within 1 second
2. **Given** an active stream exists at `live/stream123/in`, **When** the publisher disconnects, **Then** the media-service service receives a `POST /v1/mediamtx/events/not-ready` request within 1 second
3. **Given** a stream is published with query parameters `?lang=es`, **When** MediaMTX triggers the ready hook, **Then** the hook payload includes `query: "lang=es"`
4. **Given** the hook receiver is temporarily unavailable, **When** MediaMTX attempts to call the hook, **Then** the hook wrapper fails immediately without retry and the failure is logged clearly in MediaMTX logs with the HTTP error code

---

### User Story 3 - Stream Worker Input/Output via MediaMTX (Priority: P2)

As a media processing service, I need to pull incoming streams via RTSP and publish processed output back to MediaMTX so that the media pipeline can transform streams reliably.

**Why this priority**: This enables the actual media processing functionality. While P1 stories establish the foundation, this story delivers the core value proposition of stream transformation.

**Independent Test**: This can be tested with a mock worker that reads from RTSP and publishes to RTMP.
- **Unit test**: `test_rtsp_url_construction()` validates RTSP URL format for different stream IDs
- **Contract test**: `test_rtmp_publish_url_format()` validates RTMP output URL construction
- **Integration test**: `test_worker_passthrough_pipeline()` validates reading from `live/test/in` via RTSP and publishing to `live/test/out` via RTMP
- **Success criteria**: Worker successfully reads and publishes streams, latency <500ms, 80% test coverage

**Acceptance Scenarios**:

1. **Given** a stream is active at `live/stream456/in`, **When** a worker pulls from `rtsp://mediamtx:8554/live/stream456/in`, **Then** the worker receives the live video and audio data with less than 500ms latency
2. **Given** a worker has processed a stream, **When** it publishes to `rtmp://mediamtx:1935/live/stream456/out`, **Then** the processed stream appears at the `/out` path in MediaMTX
3. **Given** network instability causes UDP packet loss, **When** the worker uses RTSP over TCP (`protocols=tcp`), **Then** the stream remains stable without frame drops
4. **Given** a worker is reading a stream via RTSP, **When** the source stream disconnects, **Then** the worker detects the disconnection within 5 seconds, retries connection 3 times with exponential backoff (1s, 2s, 4s), and exits cleanly if reconnection fails

---

### User Story 4 - Observability and Debugging (Priority: P2)

As a system operator, I need access to real-time metrics, logs, and control APIs so I can monitor system health, troubleshoot issues, and understand stream processing status.

**Why this priority**: Essential for operations and debugging but can be added after core streaming functionality works. Critical for production readiness.

**Independent Test**: This can be tested by querying metrics and API endpoints.
- **Unit test**: `test_metrics_endpoint_format()` validates Prometheus metrics format
- **Contract test**: `test_control_api_response_schema()` validates API response structures
- **Integration test**: `test_end_to_end_observability()` validates metrics update when streams start/stop
- **Success criteria**: All observability endpoints return valid data within 1 second, 80% test coverage

**Acceptance Scenarios**:

1. **Given** MediaMTX is running, **When** an operator queries `http://localhost:9997/v3/paths/list`, **Then** they receive a JSON list of all active stream paths
2. **Given** an active stream exists, **When** an operator queries `http://localhost:9998/metrics?type=paths&path=live/stream123/in`, **Then** they receive Prometheus-format metrics showing bytes received, readers count, and stream state
3. **Given** MediaMTX is processing streams, **When** an operator views logs via `make logs`, **Then** they see structured log entries including hook execution results, connection events, and error messages
4. **Given** multiple streams are active, **When** an operator queries the Control API, **Then** they can identify which streams are being read by workers vs. sitting idle

---

### User Story 5 - Test Stream Publishing and Playback (Priority: P3)

As a developer, I need simple commands to publish test streams and verify playback so I can validate the pipeline without requiring external streaming software.

**Why this priority**: Nice-to-have for development convenience. Core functionality works without this, but it significantly improves developer experience.

**Independent Test**: This can be tested by running test commands and verifying output.
- **Unit test**: `test_ffmpeg_test_command_generation()` validates test stream command construction
- **Contract test**: N/A (test utilities, no contracts to validate)
- **Integration test**: `test_publish_and_playback_test_stream()` validates end-to-end test stream flow
- **Success criteria**: Test commands work on first try, documentation includes working examples, 80% test coverage

**Acceptance Scenarios**:

1. **Given** MediaMTX is running, **When** a developer runs the documented FFmpeg test publish command, **Then** a test stream with video and audio appears at the target path
2. **Given** a test stream is active, **When** a developer runs `ffplay rtsp://localhost:8554/live/test/in`, **Then** they see and hear the test pattern playing smoothly
3. **Given** the test documentation, **When** a developer copies the GStreamer RTSP→RTMP bypass command, **Then** they can republish a stream from `/in` to `/out` without errors
4. **Given** a developer is troubleshooting codec issues, **When** they examine the test stream commands, **Then** they can identify the expected codec configuration (H.264 + AAC)

---

### Edge Cases

- What happens when MediaMTX receives an RTMP connection but the hook receiver is down? (Hook call fails immediately without retry, failure is logged with HTTP error code, stream is still accepted by MediaMTX for playback, no worker is started)
- How does the system handle rapid connect/disconnect cycles (stream churn)? (Hook receiver should implement debouncing/grace period as per spec section 12, default 30s)
- What happens when a worker attempts to read from an RTSP path that doesn't exist yet? (Worker should retry 3 times with exponential backoff: 1s, 2s, 4s; log clear error messages for each attempt; exit cleanly after final retry failure)
- How does the system handle multiple workers trying to read the same stream? (MediaMTX supports multiple readers by default, should be allowed)
- What happens when a stream is published with special characters in the stream ID? (Path validation and URL encoding should be tested)
- What happens when the recordings directory fills up? (Not applicable in v0 since recording is disabled, but document future consideration)
- How does the system behave under high CPU load when MediaMTX is slow to respond? (Timeouts should be configured, hook wrapper should fail gracefully)
- What happens when a publisher sends invalid codec data? (MediaMTX should reject or log errors, worker should handle gracefully)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Docker Compose configuration that starts MediaMTX, media-service service, and any required dependencies with a single `make dev` command
- **FR-002**: MediaMTX MUST accept RTMP publish connections on port 1935 at paths matching `live/<streamId>/in`
- **FR-003**: MediaMTX MUST expose RTSP read endpoints on port 8554 for paths matching `live/<streamId>/in` and `live/<streamId>/out`
- **FR-004**: MediaMTX MUST trigger a `runOnReady` hook when a stream becomes available, calling the media-service service's `/v1/mediamtx/events/ready` endpoint
- **FR-005**: MediaMTX MUST trigger a `runOnNotReady` hook when a stream becomes unavailable, calling the media-service service's `/v1/mediamtx/events/not-ready` endpoint
- **FR-006**: Hook wrapper script MUST safely parse MediaMTX environment variables (MTX_PATH, MTX_QUERY, MTX_SOURCE_TYPE, MTX_SOURCE_ID) and construct valid JSON payloads
- **FR-006a**: Hook wrapper script MUST read the media-service service endpoint URL from the ORCHESTRATOR_URL environment variable
- **FR-007**: Hook wrapper script MUST make HTTP POST requests to the media-service service and exit with non-zero status on failure (no retries; fail immediately)
- **FR-008**: MediaMTX MUST expose a Control API on port 9997 with endpoints `/v3/paths/list` and `/v3/rtmpconns/list`
- **FR-009**: MediaMTX MUST expose Prometheus metrics on port 9998 at `/metrics` endpoint
- **FR-010**: MediaMTX MUST expose a Playback server on port 9996 (for future recording retrieval, even though recording is disabled in v0)
- **FR-011**: Stream-orchestration service MUST accept POST requests at `/v1/mediamtx/events/ready` and `/v1/mediamtx/events/not-ready` with JSON payloads containing path, query, sourceType, and sourceId
- **FR-011a**: Stream-orchestration service MUST expose its HTTP endpoint on a configurable port (default: 8080) accessible both within Docker Compose network and externally
- **FR-012**: Stream-orchestration service MUST log all received hook events with correlation fields (path, streamId, sourceId, timestamp)
- **FR-013**: MediaMTX configuration MUST set `record: no` to disable recording in v0
- **FR-014**: MediaMTX configuration MUST output logs to stdout in JSON or structured format for container environments
- **FR-015**: MediaMTX configuration MUST use `source: publisher` for path defaults to allow dynamic path creation
- **FR-016**: Documentation MUST include working test commands for publishing RTMP streams using FFmpeg and GStreamer
- **FR-017**: Documentation MUST include working test commands for reading streams via RTSP using FFmpeg and GStreamer
- **FR-018**: Makefile MUST provide targets: `dev` (start services), `logs` (view logs), `down` (stop services), `ps` (list services)
- **FR-019**: MediaMTX MUST prefer RTSP over TCP for worker connections to avoid UDP packet loss in containerized environments
- **FR-020**: System MUST support stream IDs containing alphanumeric characters, hyphens, and underscores (validation and URL encoding as needed)
- **FR-021**: Stream worker MUST retry RTSP connection failures exactly 3 times with exponential backoff intervals (1 second, 2 seconds, 4 seconds), logging each attempt, and exit cleanly after final failure
- **FR-022**: System MUST support at least 5 concurrent active streams with independent workers, maintaining performance targets for hook delivery, stream latency, and API response times

### Key Entities

- **Stream Path**: Represents a unique stream location in MediaMTX, with naming convention `live/<streamId>/in` for ingest or `live/<streamId>/out` for processed output
  - Attributes: path name, state (ready/not-ready), source type (rtmp/rtsp), creation time
  - Relationships: Each stream path can have multiple readers (workers, playback clients)

- **Hook Event**: Represents a state change notification from MediaMTX to the media-service service
  - Attributes: event type (ready/not-ready), path, query string, source type, source ID, timestamp
  - Relationships: Triggered by stream path state changes, consumed by media-service service

- **Stream Worker**: Represents a media processing component that reads from MediaMTX via RTSP and publishes processed output back via RTMP
  - Attributes: stream ID, input URL (RTSP), output URL (RTMP), processing state, start time
  - Relationships: One worker per stream (as per spec decision 3), triggered by hook events

- **Stream-Orchestration Service**: Represents the HTTP service that receives hook events and manages worker lifecycle
  - Attributes: service endpoint URL, hook receiver endpoints, worker management policy
  - Relationships: Receives hook events from MediaMTX, starts/stops stream workers

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developer can start the full local environment with a single command and see all services healthy within 30 seconds
- **SC-002**: RTMP stream publish triggers hook event delivery to media-service service within 1 second of stream becoming ready
- **SC-003**: Stream disconnection triggers hook event delivery within 1 second of stream becoming unavailable
- **SC-004**: Worker can successfully read live stream data via RTSP with end-to-end latency less than 500 milliseconds
- **SC-005**: Worker can successfully publish processed stream via RTMP and the output appears in MediaMTX within 1 second
- **SC-006**: Control API responds to queries within 100 milliseconds and returns accurate stream state information
- **SC-007**: Prometheus metrics endpoint returns data within 100 milliseconds and includes active path counts and byte counters
- **SC-008**: Test commands documented in README work without modification on macOS and Linux with FFmpeg/GStreamer installed
- **SC-009**: System logs include sufficient detail to debug stream connection issues, including hook execution results and error messages
- **SC-010**: All test suites (unit, contract, integration) pass with at least 80% code coverage
- **SC-011**: System successfully handles 5 concurrent streams without degradation in hook delivery time, stream latency, or API response time

### Qualitative Outcomes

- Developer feedback confirms local setup is straightforward and well-documented
- System operators can troubleshoot stream issues using available logs and metrics without requiring access to MediaMTX internals
- Documentation clearly explains the data flow: RTMP publish → MediaMTX → hook → orchestrator → worker → RTSP read → processing → RTMP publish → MediaMTX

## Clarifications

### Session 2025-12-26

- Q: What should the worker do when it detects the RTSP source stream has disconnected? → A: Retry connection 3 times with exponential backoff (1s, 2s, 4s), then exit cleanly
- Q: What is the maximum number of concurrent streams the system should support in v0? → A: 5 streams (small-scale concurrent testing)
- Q: When the media-service service is down, should MediaMTX retry the hook call? → A: No retry - log failure and continue (stream accepted by MediaMTX, no worker started)
- Q: How should the hook wrapper discover the media-service service endpoint URL? → A: Environment variable (ORCHESTRATOR_URL) configured in Docker Compose, pointing to service name (e.g., http://media-service:8080); service port exposed for external access

## Assumptions & Dependencies *(optional)*

### Assumptions

- Developers have Docker and Docker Compose installed (or equivalent container runtime)
- Developers have basic familiarity with RTMP/RTSP protocols and streaming concepts
- Local development will use default ports (1935, 8554, 8080, 9997, 9998, 9996) without conflicts
- FFmpeg or GStreamer is available locally for testing stream publish/playback
- Stream IDs will be determined by the publisher (via path naming) and do not require validation against an external registry in v0
- Network latency between MediaMTX and workers is negligible (same host or low-latency container network)
- Hook receiver (media-service) will be implemented in Python (implied by repository context, but not specified here)
- Development machines have sufficient resources to run 5 concurrent streams (estimated ~2GB RAM, 2 CPU cores minimum)

### Dependencies

- **External**: MediaMTX container image (official bluenviron/mediamtx or equivalent)
- **External**: Docker/Docker Compose runtime
- **Internal**: Stream-orchestration service implementation (referenced but not fully defined in this spec)
- **Internal**: Stream worker implementation (referenced in specs/003-gstreamer-stream-worker.md)
- **Configuration**: MediaMTX configuration file (`deploy/mediamtx/mediamtx.yml`)
- **Configuration**: Docker Compose file (`deploy/docker-compose.yml`)
- **Scripts**: Hook wrapper script (`deploy/mediamtx/hooks/mtx-hook`)

### Out of Scope

- Production deployment configuration (Kubernetes, ECS, cloud-specific setup)
- Stream authentication and access control (v0 is unauthenticated)
- Recording functionality (explicitly disabled in v0 per spec decision 5)
- Worker implementation details (covered in separate spec)
- Stream encryption/DRM
- CDN integration or multi-region distribution
- User-facing playback UI (only MediaMTX playback endpoint)
- Metrics persistence or alerting infrastructure
- Advanced features like transcoding, ABR (adaptive bitrate), or multi-quality outputs

## Open Questions

*No open questions remaining. All decisions documented in specs/002-mediamtx.md section 12 have been applied:*
- Stream identity via path naming: `live/<streamId>/in` and `live/<streamId>/out`
- Hook receiver: HTTP-based media-service service
- Worker lifecycle: one worker per stream with grace period
- Forwarding: separate egress forwarder (not part of this integration spec)
- Recording: disabled in v0
- Access control: unauthenticated in v0
- Observability: logs to filesystem, metrics at :9998
- Ports: no conflicts assumed (1935 RTMP, 8554 RTSP, 8080 orchestration, 9997 API, 9998 metrics, 9996 playback)

## Risk Assessment *(optional)*

### Technical Risks

- **Risk**: Hook wrapper script failures could prevent worker triggering
  - **Mitigation**: Comprehensive unit tests for hook wrapper, clear error logging, hook wrapper should be simple shell/Python script with minimal dependencies

- **Risk**: RTSP over UDP packet loss in containerized environments
  - **Mitigation**: Force RTSP over TCP in worker configuration (`protocols=tcp` in GStreamer/FFmpeg)

- **Risk**: Port conflicts on developer machines
  - **Mitigation**: Document required ports clearly, provide configuration options to override defaults

- **Risk**: MediaMTX version changes could break hook behavior
  - **Mitigation**: Pin MediaMTX container image to specific version tag, document tested version in README

### Operational Risks

- **Risk**: Developers unfamiliar with streaming concepts may struggle with debugging
  - **Mitigation**: Provide comprehensive debugging guide with common failure scenarios (section 9 of specs/002-mediamtx.md)

- **Risk**: Hook receiver downtime causes missed worker triggers
  - **Mitigation**: Document this as expected behavior in v0, plan for retry logic in future iterations

## Notes

This specification focuses on the integration layer between MediaMTX and the media service. Implementation details for the stream worker (media processing logic) and media-service service (worker management) are covered in separate specifications:
- Stream worker: `specs/003-gstreamer-stream-worker.md` (referenced in specs/002-mediamtx.md)
- Stream-orchestration: To be specified separately

The specification is based on the detailed technical spec in `specs/002-mediamtx.md` but focuses on user-facing value and testable requirements rather than implementation details.
