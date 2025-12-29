# Implementation Plan: Echo STS Service for E2E Testing

**Branch**: `017-echo-sts-service` | **Date**: 2025-12-28 | **Spec**: [specs/017-echo-sts-service/spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-echo-sts-service/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a protocol-compliant echo/mock STS service that fully implements the WebSocket Audio Fragment Protocol (spec 016) for E2E testing. The service acts as a Socket.IO server, receives audio fragments from the media-service stream worker, and echoes them back with mock metadata. This enables comprehensive E2E testing without GPU resources or ML model dependencies.

**Key Technical Approach**:
- Use `python-socketio` AsyncServer with ASGI mode for high-performance async Socket.IO
- Implement as subpackage in `apps/sts-service/src/sts_service/echo/`
- Support dynamic error simulation via `config:error_simulation` Socket.IO event
- Maintain in-order fragment delivery via output buffer
- Full protocol compliance with spec 016 message types

## Technical Context

**Language/Version**: Python 3.10.x (per constitution and pyproject.toml requirement `>=3.10,<3.11`)
**Primary Dependencies**: python-socketio>=5.0, uvicorn>=0.24.0, pydantic>=2.0
**Storage**: N/A (stateless, in-memory session state only)
**Testing**: pytest>=7.0, pytest-asyncio, pytest-cov
**Target Platform**: Linux server (Docker container for E2E testing with media-service)
**Project Type**: Monorepo subpackage (apps/sts-service/src/sts_service/echo/)
**Performance Goals**: <100ms echo latency, 10+ concurrent sessions, <2s startup
**Constraints**: <100ms processing overhead per fragment, preserve sequence ordering
**Scale/Scope**: E2E testing only - 10 concurrent streams sufficient

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I - Real-Time First**:
- [x] Echo service designed for continuous streaming, not batch
- [x] Immediate fragment:ack upon receipt
- [x] In-order delivery via output buffer (not blocking)

**Principle II - Testability Through Isolation**:
- [x] Echo service IS the mock for real STS - enables isolated testing
- [x] Service can be tested without live RTMP endpoints
- [x] Deterministic echo behavior (no ML randomness)

**Principle III - Spec-Driven Development (NON-NEGOTIABLE)**:
- [x] Feature spec created: specs/017-echo-sts-service/spec.md
- [x] Implementation follows protocol spec 016 exactly
- [x] Plan created before implementation

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all user stories (5 stories with unit/contract/integration tests)
- [x] Mock patterns documented for STS events (fragment:data, fragment:processed)
- [x] Coverage targets specified (80% minimum, 95% for fragment processing critical path)
- [x] Test infrastructure matches constitution requirements (pytest, coverage enforcement)
- [x] Test organization follows standard structure (apps/sts-service/tests/{unit,integration})

**Additional Gates**:
- [x] Principle V - Graceful Degradation: Error simulation allows testing fallback scenarios
- [x] Principle VII - Incremental Delivery: Echo service is a testable, independent milestone

## Project Structure

### Documentation (this feature)

```text
specs/017-echo-sts-service/
├── spec.md              # Feature specification (exists)
├── plan.md              # This file
├── research.md          # Phase 0 output - technology decisions
├── data-model.md        # Phase 1 output - entity definitions
├── quickstart.md        # Phase 1 output - usage guide
├── contracts/           # Phase 1 output - Socket.IO event schemas
│   ├── stream-events.json
│   ├── fragment-events.json
│   └── error-events.json
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
apps/sts-service/
├── pyproject.toml                    # Updated with python-socketio dependency
├── src/
│   └── sts_service/
│       ├── __init__.py
│       ├── echo/                     # NEW: Echo service subpackage
│       │   ├── __init__.py           # Package exports
│       │   ├── server.py             # AsyncServer setup, ASGI app
│       │   ├── handlers/             # Event handlers
│       │   │   ├── __init__.py
│       │   │   ├── stream.py         # stream:init, stream:pause, stream:resume, stream:end
│       │   │   ├── fragment.py       # fragment:data, fragment:ack
│       │   │   └── config.py         # config:error_simulation
│       │   ├── models/               # Pydantic models for events
│       │   │   ├── __init__.py
│       │   │   ├── stream.py         # StreamInitPayload, StreamReadyPayload, etc.
│       │   │   ├── fragment.py       # FragmentDataPayload, FragmentProcessedPayload
│       │   │   └── error.py          # ErrorPayload, ErrorSimulationConfig
│       │   ├── session.py            # StreamSession state management
│       │   └── config.py             # Environment-based configuration
│       ├── asr/                      # Existing ASR module
│       ├── translation/              # Existing translation module
│       └── tts/                      # Existing TTS module
├── tests/
│   ├── unit/
│   │   └── echo/                     # NEW: Unit tests for echo service
│   │       ├── __init__.py
│   │       ├── test_session.py
│   │       ├── test_handlers_stream.py
│   │       ├── test_handlers_fragment.py
│   │       └── test_models.py
│   └── integration/
│       └── echo/                     # NEW: Integration tests
│           ├── __init__.py
│           ├── test_connection_lifecycle.py
│           ├── test_fragment_echo.py
│           ├── test_backpressure.py
│           └── test_error_simulation.py
├── docker-compose.yml                # Updated for echo service
└── README.md
```

**Structure Decision**: Subpackage approach (`apps/sts-service/src/sts_service/echo/`) chosen per clarification decision. This allows:
- Shared types with real STS service (Pydantic models, error codes)
- Single deployment unit for testing
- Clear separation of echo vs. real implementation
- Follows existing sts-service structure (asr/, translation/, tts/ subpackages)

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory):
- Target: Session management, event handlers, model validation
- Tools: pytest, pytest-asyncio, pytest-mock
- Coverage: 80% minimum (95% for fragment processing)
- Mocking: Socket.IO sid, emit callbacks, session store
- Location: `apps/sts-service/tests/unit/echo/`

**Contract Tests** (mandatory):
- Target: All Socket.IO event payloads match spec 016 schemas
- Tools: pytest with Pydantic model validation
- Coverage: 100% of all event types
- Fixtures: Deterministic audio fragments (base64-encoded M4A)
- Location: `apps/sts-service/tests/unit/echo/test_models.py`

**Integration Tests** (required):
- Target: Full Socket.IO connection lifecycle, fragment round-trip
- Tools: pytest-asyncio with python-socketio AsyncClient
- Coverage: Happy path + error scenarios for each user story
- Location: `apps/sts-service/tests/integration/echo/`

**E2E Tests** (target use case):
- Target: Media-service + Echo STS in Docker Compose
- Tools: pytest with Docker Compose setup
- Coverage: Full stream lifecycle with real audio fragments
- Location: `tests/e2e/`

### Mock Patterns (Constitution Principle II)

**Socket.IO Server Mocks**:
- Mock `sio.emit()` to capture outgoing events
- Mock `sio.enter_room()` / `sio.leave_room()` for room management

**Fragment Mocks** (from spec 016):
- `fragment:data` with deterministic 1-second M4A audio (48kHz, mono)
- `fragment:processed` with echoed audio + mock transcript
- Error simulation payloads for timeout, model error, etc.

**Session Mocks**:
- Pre-configured StreamSession with known state
- Backpressure state mocks for threshold testing

### Coverage Enforcement

**Pre-commit**: Run `pytest --cov=sts_service.echo --cov-fail-under=80`
**CI**: Block merge if coverage < 80%
**Critical paths**: Fragment echo processing, session lifecycle → 95% minimum

### Test Naming Conventions

- `test_stream_init_happy_path()` - Normal stream initialization
- `test_stream_init_error_invalid_config()` - Config validation error
- `test_fragment_echo_preserves_audio()` - Fragment data integrity
- `test_fragment_ordering_preserved()` - Sequence number ordering
- `test_backpressure_emission()` - Flow control behavior
- `test_error_simulation_timeout()` - Error injection testing

## Complexity Tracking

> No constitution violations. Echo service is a straightforward mock implementation within existing monorepo structure.

| Aspect | Decision | Justification |
|--------|----------|---------------|
| Subpackage location | `apps/sts-service/src/sts_service/echo/` | Clarification answer, shared types, single deployment |
| Socket.IO library | python-socketio | Official Python implementation, AsyncServer support, ASGI integration |
| Error simulation | Socket.IO event | Clarification answer, max test flexibility |
