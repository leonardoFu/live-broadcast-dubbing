# Implementation Plan: MediaMTX Integration for Live Streaming Pipeline

**Branch**: `001-mediamtx-integration` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-mediamtx-integration/spec.md`

**Note**: This plan implements the MediaMTX integration described in `specs/002-mediamtx.md` with a focus on local development environment, hook-based worker triggering, and TDD approach.

## Summary

Integrate MediaMTX as the media router for the live streaming pipeline, providing RTMP ingest as the entry point that triggers downstream stream workers via hooks. This implementation creates a runnable local development environment with Docker Compose, MediaMTX configuration for path-based stream routing (`live/<streamId>/in`, `live/<streamId>/out`), a hook wrapper script that notifies the media-service service, and comprehensive observability through Control API and Prometheus metrics. The media-service service receives hook events and manages worker lifecycle (covered in a future spec). This foundation enables developers to publish test streams, verify hook delivery, and debug the media pipeline without requiring production infrastructure.

## Technical Context

**Language/Version**: Python 3.10.x (media-service service), Shell/Bash (hook wrapper script)
**Primary Dependencies**: MediaMTX (bluenviron/mediamtx Docker image), Docker Compose, FFmpeg/GStreamer (test utilities), FastAPI or Flask (media-service HTTP service)
**Storage**: File system for logs (Docker log capture), MediaMTX recordings disabled in v0
**Testing**: pytest (Python service tests), bats or pytest (shell script tests), Docker Compose (integration tests)
**Target Platform**: Local development (macOS/Linux), containerized services (Docker Compose)
**Project Type**: Infrastructure integration (multi-service Docker Compose setup)
**Performance Goals**: Hook delivery <1s, RTSP latency <500ms, API response <100ms, startup time <30s
**Constraints**: No authentication in v0 (local dev only), no recording (disabled), 5 concurrent streams max
**Scale/Scope**: Local dev environment, 5 concurrent streams, 3 services (MediaMTX, media-service, future worker)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all user stories (5 user stories with unit/contract/integration tests specified in spec.md)
- [x] Mock patterns documented (mock RTMP streams, mock HTTP hooks, mock MediaMTX API responses)
- [x] Coverage targets specified (80% minimum per constitution, 100% for hook wrapper script)
- [x] Test infrastructure matches constitution requirements (pytest for Python, bats for shell, Docker Compose for integration)
- [x] Test organization follows standard structure (apps/media-service/tests/{unit,contract,integration}, tests/integration/ for end-to-end)

**Principle III - Spec-Driven Development**:
- [x] Architecture spec exists (`specs/002-mediamtx.md`, `specs/011-media-service.md`)
- [x] Feature spec created (`specs/001-mediamtx-integration/spec.md`) with 22 functional requirements
- [x] Implementation plan (this document) created before any code

**Principle II - Testability Through Isolation**:
- [x] Hook wrapper testable without MediaMTX (mock environment variables)
- [x] Stream-orchestration service testable without MediaMTX (mock HTTP POST requests)
- [x] Integration tests use deterministic test streams (FFmpeg testsrc)

**Principle IV - Observability & Debuggability**:
- [x] Structured logs required (FR-012, FR-014: JSON logs with correlation fields)
- [x] Metrics endpoint required (FR-009: Prometheus at :9998)
- [x] Control API required (FR-008: /v3/paths/list for debugging)

**All gates PASSED** - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-mediamtx-integration/
├── spec.md              # Feature specification (already exists)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (MediaMTX research, hook patterns)
├── data-model.md        # Phase 1 output (stream path model, hook event model)
├── quickstart.md        # Phase 1 output (local dev setup guide)
├── contracts/           # Phase 1 output (API contracts)
│   ├── hook-events.json     # Hook event payload schema
│   └── control-api.json     # MediaMTX Control API response schema
├── checklists/          # Quality validation checklists
│   └── requirements.md  # Spec quality checklist (already exists)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

This feature creates the MediaMTX integration infrastructure:

```text
live-broadcast-dubbing-cloud/
├── deploy/                                 # Docker and deployment configs
│   ├── docker-compose.yml                  # Multi-service compose (MediaMTX + orchestration)
│   ├── mediamtx/
│   │   ├── mediamtx.yml                    # MediaMTX configuration
│   │   └── hooks/
│   │       └── mtx-hook                    # Hook wrapper script (shell/Python)
│   └── media-service/
│       ├── Dockerfile                      # Stream-orchestration service image
│       ├── requirements.txt                # Python dependencies (FastAPI, uvicorn)
│       └── server.py                       # Minimal hook receiver (logs events)
│
├── apps/                                   # Service applications
│   └── media-service/               # Stream-orchestration service (hook receiver)
│       ├── pyproject.toml                  # Service-specific dependencies
│       ├── requirements.txt                # Locked dependencies
│       ├── requirements-dev.txt            # Dev/test dependencies
│       ├── src/
│       │   └── media_service/       # Python package namespace
│       │       ├── __init__.py
│       │       ├── api/                    # HTTP API endpoints
│       │       │   ├── __init__.py
│       │       │   └── hooks.py            # /v1/mediamtx/events/* endpoints
│       │       ├── models/                 # Data models
│       │       │   ├── __init__.py
│       │       │   └── events.py           # Hook event models
│       │       └── main.py                 # FastAPI app entry point
│       ├── tests/                          # Service-specific tests
│       │   ├── unit/
│       │   │   ├── __init__.py
│       │   │   └── test_hook_parsing.py    # Unit tests for event parsing
│       │   ├── contract/
│       │   │   ├── __init__.py
│       │   │   └── test_hook_schema.py     # Contract tests for hook payloads
│       │   └── integration/
│       │       ├── __init__.py
│       │       └── test_hook_receiver.py   # Integration tests for HTTP API
│       └── README.md                       # Service documentation
│
├── tests/                                  # End-to-end integration tests
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_mediamtx_startup.py        # MediaMTX startup and health check
│   │   ├── test_rtmp_publish_hook.py       # RTMP publish → hook event flow
│   │   └── test_control_api.py             # Control API endpoint tests
│   └── fixtures/
│       └── test-streams/                   # Test stream definitions
│           └── ffmpeg-test.sh              # FFmpeg test stream script
│
├── Makefile                                # Development workflow commands
└── README.md                               # Repository overview (update with MediaMTX setup)
```

**Structure Decision**: This feature extends the existing monorepo structure with MediaMTX integration components. The structure uses `deploy/` for containerized service configurations (MediaMTX config, Docker Compose), `apps/media-service/` for the hook receiver service (following existing monorepo pattern), and `tests/integration/` for end-to-end MediaMTX integration tests. The hook wrapper script lives in `deploy/mediamtx/hooks/` alongside MediaMTX configuration for clarity.

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory):
- Target: Hook wrapper script logic, event payload parsing, HTTP client in hook wrapper
- Tools: pytest with mock environment variables, bats for shell script testing
- Coverage: 100% for hook wrapper script (simple deterministic logic)
- Mocking: Mock `MTX_PATH`, `MTX_QUERY`, `MTX_SOURCE_TYPE`, `MTX_SOURCE_ID` environment variables
- Location: `deploy/mediamtx/hooks/test_mtx_hook.py` or `test_mtx_hook.bats`
- Examples:
  - `test_parse_mtx_env_vars_happy_path()` - Valid environment variables → JSON payload
  - `test_parse_mtx_env_vars_missing_path()` - Missing MTX_PATH → error
  - `test_construct_hook_url_from_orchestrator_url()` - ORCHESTRATOR_URL env → full endpoint

**Contract Tests** (mandatory):
- Target: Hook event payload schema, MediaMTX Control API response schema
- Tools: pytest with JSON schema validation (jsonschema library)
- Coverage: 100% of all hook event types (ready, not-ready)
- Mocking: Use deterministic fixtures from `contracts/hook-events.json`
- Location: `apps/media-service/tests/contract/test_hook_schema.py`
- Examples:
  - `test_ready_event_schema()` - POST /v1/mediamtx/events/ready payload matches schema
  - `test_not_ready_event_schema()` - POST /v1/mediamtx/events/not-ready payload matches schema
  - `test_control_api_paths_list_schema()` - GET /v3/paths/list response matches schema

**Integration Tests** (required for workflows):
- Target: Full RTMP publish → hook delivery → orchestration service flow
- Tools: pytest with Docker Compose, FFmpeg for test streams
- Coverage: All 5 user stories have integration tests
- Mocking: Use FFmpeg test sources (testsrc, sine wave), real MediaMTX instance
- Location: `tests/integration/test_rtmp_publish_hook.py`
- Examples:
  - `test_rtmp_publish_triggers_ready_event()` - RTMP publish → /v1/mediamtx/events/ready received within 1s
  - `test_rtmp_disconnect_triggers_not_ready_event()` - Disconnect → /v1/mediamtx/events/not-ready received within 1s
  - `test_control_api_shows_active_stream()` - RTMP publish → GET /v3/paths/list shows stream
  - `test_concurrent_streams()` - 5 concurrent RTMP publishes → all hooks delivered

**E2E Tests** (optional, for validation only):
- Target: Full local dev workflow (`make dev` → publish → playback)
- Tools: pytest with subprocess calls, manual validation
- Coverage: Success criteria SC-001 through SC-011
- When: Run manually before release
- Location: `tests/e2e/test_local_dev_workflow.py`

### Mock Patterns (Constitution Principle II)

**MediaMTX Hook Environment Variables** (unit tests):
```python
@pytest.fixture
def mock_mtx_env():
    return {
        "MTX_PATH": "live/test-stream/in",
        "MTX_QUERY": "lang=es",
        "MTX_SOURCE_TYPE": "rtmp",
        "MTX_SOURCE_ID": "1"
    }
```

**Hook Event Payloads** (contract tests):
```json
{
  "path": "live/test-stream/in",
  "query": "lang=es",
  "sourceType": "rtmp",
  "sourceId": "1"
}
```

**MediaMTX Control API Responses** (integration tests):
```python
@pytest.fixture
def mock_paths_list_response():
    return {
        "items": [
            {
                "name": "live/test-stream/in",
                "ready": True,
                "tracks": ["H264", "AAC"]
            }
        ]
    }
```

**FFmpeg Test Streams** (integration tests):
```bash
# Deterministic test stream (720p H.264 + AAC)
ffmpeg -re \
  -f lavfi -i testsrc=size=1280x720:rate=30 \
  -f lavfi -i sine=frequency=440:sample_rate=44100 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -c:a aac -ar 44100 \
  -f flv rtmp://localhost:1935/live/test-stream/in
```

### Coverage Enforcement

**Pre-commit**: Run `pytest --cov=media_service --cov=deploy/mediamtx/hooks --cov-fail-under=80` - fail if coverage < 80%
**CI**: Run `pytest --cov --cov-fail-under=80` - block merge if fails
**Critical paths**: Hook wrapper script, event parsing → 100% coverage (no exceptions - simple deterministic code)

### Test Naming Conventions

Follow conventions from `tasks-template.md`:
- `test_parse_mtx_env_happy_path()` - Normal environment variable parsing
- `test_parse_mtx_env_error_missing_path()` - Missing MTX_PATH error
- `test_hook_receiver_error_invalid_payload()` - Invalid JSON payload
- `test_rtmp_publish_integration_hook_delivery()` - Full RTMP → hook flow

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**No violations** - This feature aligns with all constitution principles.

---

## Phase 0: Research & Technology Decisions

### Research Questions

1. **MediaMTX Hook Mechanisms**: How does MediaMTX trigger hooks? What environment variables are available? What are the failure semantics?
2. **Hook Wrapper Implementation**: Should the hook wrapper be shell script or Python? What are the trade-offs?
3. **Docker Compose Networking**: How to configure service discovery between MediaMTX and media-service?
4. **MediaMTX Configuration**: What are the minimum required settings for RTMP ingest, RTSP read, hooks, and observability?
5. **Stream-Orchestration Service Framework**: FastAPI vs Flask vs minimal HTTP server for hook receiver?
6. **Test Stream Generation**: What FFmpeg/GStreamer commands produce reliable test streams with H.264 + AAC?

### Research Tasks

*These will be resolved in `research.md` (Phase 0 output)*

1. **Task**: Research MediaMTX hook documentation and environment variables
   - **Output**: Complete list of MTX_* environment variables available to hooks
   - **Decision criteria**: Official documentation accuracy, version compatibility (MediaMTX v1.0+)
   - **Sources**: bluenviron/mediamtx GitHub docs, specs/002-mediamtx.md

2. **Task**: Compare shell vs Python for hook wrapper script
   - **Output**: Chosen implementation language with justification
   - **Decision criteria**: Simplicity, error handling, JSON construction safety, testability
   - **Recommendation**: Python (safer JSON handling, easier testing, better error messages)

3. **Task**: Research Docker Compose service networking patterns
   - **Output**: Docker Compose networking configuration for MediaMTX → media-service communication
   - **Decision criteria**: Service name resolution, port exposure, network isolation
   - **Recommendation**: Single custom network, service name `media-service:8080`

4. **Task**: Research MediaMTX configuration for local development
   - **Output**: Minimal `mediamtx.yml` template with hooks, API, metrics, RTMP, RTSP enabled
   - **Decision criteria**: Minimal config, clear defaults, easy debugging
   - **Reference**: specs/002-mediamtx.md section 7

5. **Task**: Compare FastAPI vs Flask for media-service service
   - **Output**: Chosen framework with justification
   - **Decision criteria**: Async support (not required in v0), simplicity, type safety, testing support
   - **Recommendation**: FastAPI (type safety, automatic OpenAPI docs, better for future async)

6. **Task**: Research FFmpeg test stream commands for RTMP publish
   - **Output**: Working FFmpeg and GStreamer commands for test streams
   - **Decision criteria**: Reliable H.264 + AAC output, low latency, easy to customize
   - **Reference**: specs/002-mediamtx.md section 8.2

---

## Phase 1: Design Artifacts

### Data Model (`data-model.md`)

The data model for this feature focuses on stream paths and hook events:

1. **Stream Path Entity**: Represents a unique stream location in MediaMTX
   - Attributes: `path` (string, e.g., "live/stream123/in"), `state` (ready/not-ready), `source_type` (rtmp/rtsp), `source_id` (string), `creation_time` (datetime)
   - Relationships: `readers` (List[Reader]), `hook_events` (List[HookEvent])
   - Validation: Path must match pattern `live/<streamId>/(in|out)`

2. **Hook Event Entity**: Represents a state change notification from MediaMTX
   - Attributes: `event_type` (ready/not-ready), `path` (string), `query` (string), `source_type` (string), `source_id` (string), `timestamp` (datetime), `correlation_id` (UUID)
   - Relationships: `stream_path` (StreamPath)
   - Validation: Must include path, source_type, source_id; query and timestamp optional

3. **Stream Worker Entity** (placeholder for future implementation):
   - Attributes: `stream_id` (string), `input_url` (RTSP string), `output_url` (RTMP string), `state` (starting/running/stopping/stopped), `start_time` (datetime)
   - Relationships: `stream_path` (StreamPath), `hook_events` (List[HookEvent])
   - Note: Worker lifecycle management is out of scope for this feature (see specs/011-media-service.md)

4. **Stream-Orchestration Service Entity**: Represents the HTTP service that receives hooks
   - Attributes: `endpoint_url` (string, e.g., "http://media-service:8080"), `hook_receiver_endpoints` (List[string])
   - Relationships: `received_events` (List[HookEvent])
   - Validation: Endpoint URL must be accessible from MediaMTX container network

### Contracts (`contracts/`)

#### Hook Event Schema (`contracts/hook-events.json`)

JSON Schema defining hook event payloads:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MediaMTX Hook Event",
  "type": "object",
  "required": ["path", "sourceType", "sourceId"],
  "properties": {
    "path": {
      "type": "string",
      "pattern": "^live/[a-zA-Z0-9_-]+/(in|out)$",
      "description": "Stream path in MediaMTX (e.g., live/stream123/in)"
    },
    "query": {
      "type": "string",
      "description": "Query string from RTMP URL (e.g., lang=es)"
    },
    "sourceType": {
      "type": "string",
      "enum": ["rtmp", "rtsp", "webrtc"],
      "description": "Source protocol type"
    },
    "sourceId": {
      "type": "string",
      "description": "Unique identifier for the source connection"
    }
  }
}
```

#### Control API Schema (`contracts/control-api.json`)

JSON Schema for MediaMTX Control API `/v3/paths/list` response:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MediaMTX Paths List Response",
  "type": "object",
  "required": ["items"],
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "ready"],
        "properties": {
          "name": {
            "type": "string",
            "description": "Path name (e.g., live/stream123/in)"
          },
          "ready": {
            "type": "boolean",
            "description": "Whether the path has an active source"
          },
          "tracks": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Available tracks (e.g., H264, AAC)"
          }
        }
      }
    }
  }
}
```

### Quick Start Guide (`quickstart.md`)

Developer onboarding guide covering:

1. **Prerequisites**: Docker and Docker Compose installed, FFmpeg or GStreamer for testing
2. **Initial Setup**: Clone repository, run `make dev`
3. **Publishing Test Streams**: Use documented FFmpeg/GStreamer commands
4. **Verifying Hook Delivery**: Check media-service logs for hook events
5. **Debugging**: Use Control API (`curl http://localhost:9997/v3/paths/list`), check metrics
6. **Common Tasks**: Start/stop services, view logs, publish/playback streams
7. **Troubleshooting**: Common errors (port conflicts, hook delivery failures, codec issues)

---

## Phase 2: Task Breakdown

*Tasks will be generated by `/speckit.tasks` command (not part of this plan)*

The task breakdown will follow the 5 user story priorities (P1-P5) and create implementation tasks for:

1. **P1 Tasks (Local Development Environment)**:
   - Create Docker Compose configuration
   - Configure MediaMTX service with volume mounts
   - Add Makefile targets (dev, logs, down, ps)
   - Write integration tests for service startup

2. **P1 Tasks (RTMP Ingest Triggers Worker Events)**:
   - Implement hook wrapper script (Python)
   - Create media-service service skeleton (FastAPI)
   - Implement /v1/mediamtx/events/ready endpoint
   - Implement /v1/mediamtx/events/not-ready endpoint
   - Write contract tests for hook payloads
   - Write integration tests for hook delivery

3. **P2 Tasks (Stream Worker Input/Output)**:
   - Document RTSP read URL construction
   - Document RTMP publish URL construction
   - Add test utilities for passthrough pipeline (GStreamer bypass)
   - Write integration tests for RTSP → RTMP flow

4. **P2 Tasks (Observability and Debugging)**:
   - Configure MediaMTX Control API
   - Configure MediaMTX Prometheus metrics
   - Add Makefile targets for querying API/metrics
   - Write integration tests for API endpoints
   - Document log correlation fields

5. **P3 Tasks (Test Stream Publishing and Playback)**:
   - Document FFmpeg test publish commands
   - Document GStreamer test publish commands
   - Document playback commands (ffplay, GStreamer)
   - Create test stream scripts in `tests/fixtures/`

Each task will include:
- Test requirements (unit, contract, integration from spec.md)
- Acceptance criteria from spec
- Dependencies on previous tasks
- Estimated complexity

---

## Implementation Notes

### Design Decisions

1. **Hook Wrapper Language**: Python chosen over shell for safer JSON construction, better error handling, and easier testing. The script will be simple (<100 lines) and have 100% test coverage.

2. **Stream-Orchestration Framework**: FastAPI chosen over Flask for type safety (Pydantic models), automatic OpenAPI documentation, and better alignment with future async requirements. Initial implementation will be synchronous.

3. **Docker Compose Networking**: Single custom network (`dubbing-network`) with service name resolution. MediaMTX hooks will use `ORCHESTRATOR_URL=http://media-service:8080` environment variable.

4. **MediaMTX Configuration**: Minimal configuration from specs/002-mediamtx.md section 7, with recording disabled (`record: no`), structured logs to stdout (`logDestinations: [stdout]`), and all observability endpoints enabled.

5. **Test Stream Generation**: Use FFmpeg testsrc and sine wave generators for deterministic test streams. Document both FFmpeg and GStreamer commands for developer flexibility.

6. **Error Handling in Hooks**: Hook wrapper fails immediately without retry (per specs/002-mediamtx.md section 4.2). Failure is logged with clear error message and HTTP status code. MediaMTX will log hook failures, but stream ingestion continues.

### Risk Mitigation

1. **Risk**: Hook delivery failures prevent worker triggering
   - **Mitigation**: Comprehensive unit tests for hook wrapper, clear error logging, hook wrapper kept simple (<100 lines)

2. **Risk**: RTSP over UDP packet loss in Docker
   - **Mitigation**: Document `protocols=tcp` for GStreamer rtspsrc (specs/002-mediamtx.md section 3.2), test with TCP-only configuration

3. **Risk**: Port conflicts on developer machines
   - **Mitigation**: Document all required ports in README (1935, 8554, 8080, 9997, 9998, 9996), provide configuration options to override

4. **Risk**: MediaMTX version changes break hook behavior
   - **Mitigation**: Pin MediaMTX container image to specific version tag in docker-compose.yml, document tested version

5. **Risk**: Developers unfamiliar with streaming concepts struggle with debugging
   - **Mitigation**: Comprehensive debugging guide in quickstart.md, document common failure scenarios (from specs/002-mediamtx.md section 9)

6. **Risk**: Hook receiver downtime causes missed worker triggers
   - **Mitigation**: Document this as expected behavior in v0, log clearly in MediaMTX logs with HTTP error code

### Success Metrics

All 11 success criteria from spec must pass:

- **SC-001**: Single command (`make dev`) starts all services within 30 seconds
- **SC-002**: RTMP publish triggers hook delivery within 1 second
- **SC-003**: Stream disconnect triggers hook delivery within 1 second
- **SC-004**: Worker can read via RTSP with <500ms latency
- **SC-005**: Worker can publish via RTMP with <1s delay
- **SC-006**: Control API responds within 100ms
- **SC-007**: Prometheus metrics respond within 100ms
- **SC-008**: Test commands work without modification
- **SC-009**: Logs include correlation fields for debugging
- **SC-010**: All test suites pass with 80% coverage
- **SC-011**: 5 concurrent streams work without degradation

---

## Deployment Considerations

### Local Development

- **Environment**: Docker Compose with 2-3 services (MediaMTX, media-service, future worker)
- **Storage**: Logs to stdout (captured by Docker), no persistent storage (recordings disabled)
- **Networking**: Single custom bridge network for service name resolution
- **Secrets**: None required in v0 (unauthenticated local dev)

### Production (Future)

*Out of scope for v0, but documented for future reference:*

- **Platform**: Kubernetes, ECS, or similar container orchestration
- **Authentication**: Implement access control for RTMP publish, RTSP read, Control API, metrics
- **Observability**: Centralized logging (ELK, Loki), Prometheus scraping, alerting rules
- **Scaling**: Horizontal scaling of workers (one worker per stream), stateless orchestration service
- **Recording**: Enable `record: yes` with retention policies, S3/object storage for segments
- **Network**: Internal-only RTSP, external RTMP ingest with CDN/load balancer

---

## Agent Context Update

After Phase 1 completion, update agent context with:
- MediaMTX integration patterns (hooks, Control API, metrics)
- Stream path naming conventions (`live/<streamId>/in`, `live/<streamId>/out`)
- Docker Compose service configuration
- Hook event payload structure
- Stream-orchestration service API endpoints

This will be used by `/speckit.tasks` and `/speckit.implement` commands.
