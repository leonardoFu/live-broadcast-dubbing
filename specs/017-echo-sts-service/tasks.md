# Tasks: Echo STS Service for E2E Testing

**Input**: Design documents from `/specs/017-echo-sts-service/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/

**Tests**: Tests are MANDATORY per Constitution Principle VIII. Every user story MUST have tests written FIRST before implementation. The tasks below enforce a test-first workflow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This feature follows the monorepo structure:
- **Source**: `apps/sts-service/src/sts_service/echo/`
- **Unit Tests**: `apps/sts-service/tests/unit/echo/`
- **Integration Tests**: `apps/sts-service/tests/integration/echo/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, package structure, and dependencies

- [X] T001 Create echo service package structure at `apps/sts-service/src/sts_service/echo/__init__.py`
- [X] T002 [P] Create handlers subpackage at `apps/sts-service/src/sts_service/echo/handlers/__init__.py`
- [X] T003 [P] Create models subpackage at `apps/sts-service/src/sts_service/echo/models/__init__.py`
- [X] T004 Update `apps/sts-service/pyproject.toml` to add python-socketio>=5.0, uvicorn>=0.24.0, pydantic>=2.0 dependencies
- [X] T005 [P] Create unit test package at `apps/sts-service/tests/unit/echo/__init__.py`
- [X] T006 [P] Create integration test package at `apps/sts-service/tests/integration/echo/__init__.py`
- [X] T007 Create shared test fixtures at `apps/sts-service/tests/conftest.py` with sample PCM audio data

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Implement environment configuration in `apps/sts-service/src/sts_service/echo/config.py` (port, API key, processing delay, backpressure settings)
- [X] T009 [P] Implement Pydantic models for AudioData, FragmentMetadata in `apps/sts-service/src/sts_service/echo/models/fragment.py`
- [X] T010 [P] Implement Pydantic models for StreamInitPayload, StreamReadyPayload, StreamConfigPayload, StreamCompletePayload, StreamStatistics, ServerCapabilities in `apps/sts-service/src/sts_service/echo/models/stream.py`
- [X] T011 [P] Implement Pydantic models for ErrorPayload, ErrorSimulationConfig, ErrorSimulationRule in `apps/sts-service/src/sts_service/echo/models/error.py`
- [X] T012 Implement SessionStore class with create/get_by_sid/get_by_stream_id/delete methods in `apps/sts-service/src/sts_service/echo/session.py`
- [X] T013 Implement StreamSession dataclass with state transitions and SessionStatistics in `apps/sts-service/src/sts_service/echo/session.py`

**Checkpoint**: Foundation ready - user story implementation can now begin (automated tests verify, continue automatically)

---

## Phase 3: User Story 1 - Stream Worker Connects and Initializes Stream (Priority: P1)

**Goal**: Worker can connect and initialize a streaming session with stream:init/stream:ready exchange

**Note**: No authentication required - service accepts all connections.

**Independent Test**: Connect and send stream:init with various configurations

### Tests for User Story 1 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US1**: 95% (critical path - connection/initialization)

- [X] T014 [P] [US1] **Unit tests** for stream models in `apps/sts-service/tests/unit/echo/test_models.py`
  - `test_stream_init_payload_schema()` - validates stream:init structure matches spec 016
  - `test_stream_ready_payload_schema()` - validates stream:ready response structure
  - `test_stream_config_validation()` - validates config field constraints
- [X] T015 [P] [US1] **Unit tests** for session management in `apps/sts-service/tests/unit/echo/test_session.py`
  - `test_session_create()` - session created with correct initial state
  - `test_session_state_transition_to_active()` - initializing -> active on stream:ready
  - `test_session_store_get_by_sid()` - retrieve session by Socket.IO ID
  - `test_session_store_get_by_stream_id()` - retrieve session by stream ID
- [X] T016 [P] [US1] **Unit tests** for stream handlers in `apps/sts-service/tests/unit/echo/test_handlers_stream.py`
  - `test_stream_init_happy_path()` - valid init returns stream:ready
  - `test_stream_init_error_invalid_config()` - invalid config returns INVALID_CONFIG error
  - `test_stream_init_error_missing_required_fields()` - missing fields rejected
- [X] T017 [US1] **Integration tests** for connection lifecycle in `apps/sts-service/tests/e2e/echo/test_connection_lifecycle.py`
  - `test_worker_connects_and_initializes()` - full connection flow with Socket.IO client
  - `test_multiple_concurrent_sessions()` - 10 concurrent sessions

**Verification**: Run `pytest apps/sts-service/tests/unit/echo/test_handlers_stream.py -v` - ALL tests MUST FAIL

### Implementation for User Story 1

- [X] T018 [US1] Implement stream:init handler in `apps/sts-service/src/sts_service/echo/handlers/stream.py`
- [X] T019 [US1] Implement Socket.IO AsyncServer setup with ASGI app in `apps/sts-service/src/sts_service/echo/server.py`
- [X] T020 [US1] Wire connect event and stream:init handler to server in `apps/sts-service/src/sts_service/echo/server.py`

**Checkpoint**: User Story 1 fully functional - workers can connect and initialize streams (run automated tests, continue automatically)

---

## Phase 4: User Story 2 - Audio Fragment Echo Processing (Priority: P1)

**Goal**: Worker sends audio fragments and receives them echoed back with mock metadata in fragment:processed events

**Independent Test**: Send audio fragments and verify they are echoed back with proper sequencing and all required fields

### Tests for User Story 2 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US2**: 95% (critical path - core echo functionality)

- [X] T023 [P] [US2] **Unit tests** for fragment models in `apps/sts-service/tests/unit/echo/test_models.py`
  - `test_fragment_data_payload_schema()` - validates fragment:data matches spec 016
  - `test_fragment_processed_payload_schema()` - validates fragment:processed matches spec 016
  - `test_fragment_ack_payload_schema()` - validates fragment:ack structure
  - `test_audio_data_base64_validation()` - validates audio data constraints
- [X] T024 [P] [US2] **Unit tests** for fragment handlers in `apps/sts-service/tests/unit/echo/test_handlers_fragment.py`
  - `test_fragment_echo_preserves_audio()` - audio data unchanged in response
  - `test_fragment_ack_immediate()` - fragment:ack sent immediately with status queued
  - `test_fragment_response_structure()` - all required fields populated
  - `test_fragment_mock_transcript()` - transcript field contains mock text
  - `test_fragment_mock_translated_text()` - translated_text field contains mock text
  - `test_fragment_processing_time_recorded()` - processing_time_ms populated
  - `test_fragment_stage_timings_included()` - stage_timings with mock values
- [X] T025 [P] [US2] **Unit tests** for sequence ordering in `apps/sts-service/tests/unit/echo/test_handlers_fragment.py`
  - `test_fragment_ordering_preserved()` - fragments delivered in sequence_number order
  - `test_fragment_out_of_order_processing()` - out-of-order input still delivers in-order
  - `test_fragment_before_stream_init_rejected()` - STREAM_NOT_FOUND error
  - `test_fragment_too_large_rejected()` - FRAGMENT_TOO_LARGE error for >10MB
- [X] T026 [US2] **Integration tests** for fragment round-trip in `apps/sts-service/tests/integration/echo/test_fragment_echo.py`
  - `test_worker_sends_fragments_receives_echo()` - full round-trip with Socket.IO
  - `test_multiple_fragments_in_sequence()` - 10 fragments processed in order
  - `test_fragment_worker_ack()` - worker acknowledgment handled correctly

**Verification**: Run `pytest apps/sts-service/tests/unit/echo/test_handlers_fragment.py -v` - ALL tests MUST FAIL

### Implementation for User Story 2

- [X] T027 [P] [US2] Implement FragmentDataPayload and FragmentProcessedPayload models in `apps/sts-service/src/sts_service/echo/models/fragment.py`
- [X] T028 [US2] Implement fragment:data handler with echo logic in `apps/sts-service/src/sts_service/echo/handlers/fragment.py`
- [X] T029 [US2] Implement fragment:ack handler (worker->STS) in `apps/sts-service/src/sts_service/echo/handlers/fragment.py`
- [X] T030 [US2] Implement in-order delivery via pending_fragments buffer in `apps/sts-service/src/sts_service/echo/handlers/fragment.py`
- [X] T031 [US2] Wire fragment handlers to server in `apps/sts-service/src/sts_service/echo/server.py`

**Checkpoint**: User Stories 1 AND 2 fully functional - core echo loop working (run automated tests, continue automatically)

---

## Phase 5: User Story 3 - Stream Lifecycle Management (Priority: P2)

**Goal**: Worker can pause, resume, and gracefully end streams with proper state management and statistics

**Independent Test**: Test pause/resume flow and verify stream:complete returns accurate statistics

### Tests for User Story 3 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US3**: 80% minimum

- [X] T032 [P] [US3] **Unit tests** for session state transitions in `apps/sts-service/tests/unit/echo/test_session.py`
  - `test_session_state_active_to_paused()` - transition on stream:pause
  - `test_session_state_paused_to_active()` - transition on stream:resume
  - `test_session_state_active_to_ending()` - transition on stream:end
  - `test_session_state_paused_to_ending()` - transition on stream:end from paused
  - `test_session_state_ending_to_completed()` - transition when all fragments done
  - `test_session_statistics_tracking()` - statistics updated correctly
- [X] T033 [P] [US3] **Unit tests** for lifecycle handlers in `apps/sts-service/tests/unit/echo/test_handlers_stream.py`
  - `test_stream_pause_stops_new_fragments()` - new fragments rejected when paused
  - `test_stream_pause_completes_inflight()` - in-flight fragments complete
  - `test_stream_resume_allows_fragments()` - fragments accepted after resume
  - `test_stream_end_returns_statistics()` - stream:complete with accurate stats
  - `test_stream_complete_payload_structure()` - validates stream:complete schema
- [X] T034 [US3] **Integration tests** for lifecycle in `apps/sts-service/tests/integration/echo/test_connection_lifecycle.py`
  - `test_worker_pause_resume_end_lifecycle()` - full lifecycle flow
  - `test_stream_complete_auto_disconnect()` - connection closes after 5 seconds

**Verification**: Run `pytest apps/sts-service/tests/unit/echo/test_handlers_stream.py::test_stream_pause* -v` - ALL tests MUST FAIL

### Implementation for User Story 3

- [X] T035 [US3] Implement stream:pause handler in `apps/sts-service/src/sts_service/echo/handlers/stream.py`
- [X] T036 [US3] Implement stream:resume handler in `apps/sts-service/src/sts_service/echo/handlers/stream.py`
- [X] T037 [US3] Implement stream:end handler with statistics calculation in `apps/sts-service/src/sts_service/echo/handlers/stream.py`
- [X] T038 [US3] Implement auto-disconnect after stream:complete (5 second delay) in `apps/sts-service/src/sts_service/echo/handlers/stream.py`
- [X] T039 [US3] Wire lifecycle handlers to server in `apps/sts-service/src/sts_service/echo/server.py`

**Checkpoint**: User Stories 1, 2, AND 3 functional - full stream lifecycle working (run automated tests, continue automatically)

---

## Phase 6: User Story 4 - Backpressure Simulation (Priority: P2)

**Goal**: Echo service can emit backpressure events to test worker flow control handling

**Independent Test**: Configure backpressure thresholds and verify events emitted at correct severity levels

### Tests for User Story 4 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US4**: 80% minimum

- [X] T040 [P] [US4] **Unit tests** for backpressure models in `apps/sts-service/tests/unit/echo/test_models.py`
  - `test_backpressure_payload_schema()` - validates backpressure message matches spec 016
  - `test_backpressure_severity_levels()` - low, medium, high values accepted
  - `test_backpressure_action_values()` - slow_down, pause, none values accepted
- [X] T041 [P] [US4] **Unit tests** for backpressure logic in `apps/sts-service/tests/unit/echo/test_handlers_fragment.py`
  - `test_backpressure_event_emission()` - event emitted when threshold exceeded
  - `test_backpressure_severity_low()` - 50% threshold -> low severity
  - `test_backpressure_severity_medium()` - 70% threshold -> medium severity
  - `test_backpressure_severity_high()` - 90% threshold -> high severity
  - `test_backpressure_clear()` - low severity with action none when queue clears
- [X] T042 [US4] **Integration tests** for backpressure in `apps/sts-service/tests/integration/echo/test_backpressure.py`
  - `test_worker_receives_backpressure()` - backpressure event received via Socket.IO
  - `test_backpressure_triggers_at_threshold()` - event emitted at correct inflight count

**Verification**: Run `pytest apps/sts-service/tests/unit/echo/test_handlers_fragment.py::test_backpressure* -v` - ALL tests MUST FAIL

### Implementation for User Story 4

- [X] T043 [P] [US4] Implement BackpressurePayload model in `apps/sts-service/src/sts_service/echo/models/fragment.py`
- [X] T044 [US4] Implement backpressure calculation and emission logic in `apps/sts-service/src/sts_service/echo/handlers/fragment.py`
- [X] T045 [US4] Add backpressure configuration to session from environment in `apps/sts-service/src/sts_service/echo/config.py`

**Checkpoint**: User Stories 1-4 functional - backpressure simulation working (run automated tests, continue automatically)

---

## Phase 7: User Story 5 - Error Simulation for Testing (Priority: P3)

**Goal**: E2E tests can configure error injection via config:error_simulation Socket.IO event

**Independent Test**: Configure error rules and verify specific fragments return expected errors

### Tests for User Story 5 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US5**: 80% minimum

- [X] T046 [P] [US5] **Unit tests** for error simulation models in `apps/sts-service/tests/unit/echo/test_models.py`
  - `test_error_simulation_config_schema()` - validates config:error_simulation payload
  - `test_error_simulation_rule_schema()` - validates rule structure
  - `test_error_codes_valid()` - all 10 error codes from spec 016 accepted
  - `test_error_event_structure()` - validates error event payload
- [X] T047 [P] [US5] **Unit tests** for config handler in `apps/sts-service/tests/unit/echo/test_handlers_config.py`
  - `test_config_error_simulation_enable()` - simulation enabled via event
  - `test_config_error_simulation_ack()` - ack response with rules_count
  - `test_config_error_simulation_invalid()` - invalid config returns error status
- [X] T048 [P] [US5] **Unit tests** for error injection in `apps/sts-service/tests/unit/echo/test_handlers_fragment.py`
  - `test_error_injection_by_sequence_number()` - error triggered on specific sequence
  - `test_error_injection_by_fragment_id()` - error triggered on specific fragment
  - `test_error_injection_by_nth_fragment()` - error triggered on every Nth fragment
  - `test_error_retryable_flag_timeout()` - TIMEOUT error has retryable=true
  - `test_error_retryable_flag_auth_failed()` - AUTH_FAILED has retryable=false
- [X] T049 [US5] **Integration tests** for error simulation in `apps/sts-service/tests/integration/echo/test_error_simulation.py`
  - `test_worker_configures_error_simulation()` - config accepted via Socket.IO
  - `test_worker_handles_timeout_error()` - timeout error returned correctly
  - `test_worker_handles_model_error()` - model error returned correctly
  - `test_error_simulation_multiple_rules()` - multiple rules trigger correctly

**Verification**: Run `pytest apps/sts-service/tests/unit/echo/test_handlers_config.py -v` - ALL tests MUST FAIL

### Implementation for User Story 5

- [X] T050 [US5] Implement config:error_simulation handler in `apps/sts-service/src/sts_service/echo/handlers/config.py`
- [X] T051 [US5] Implement error injection logic in fragment handler in `apps/sts-service/src/sts_service/echo/handlers/fragment.py`
- [X] T052 [US5] Wire config handler to server in `apps/sts-service/src/sts_service/echo/server.py`

**Checkpoint**: All user stories functional - full echo service complete (run automated tests, continue automatically)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Docker setup, documentation, and final validation

- [X] T053 [P] Create Dockerfile for echo service at `apps/sts-service/deploy/Dockerfile.echo`
- [X] T054 [P] Update `apps/sts-service/docker-compose.yml` to add echo service container
- [X] T055 [P] Create entrypoint script at `apps/sts-service/src/sts_service/echo/__main__.py` for running standalone
- [X] T056 [P] Export public API in `apps/sts-service/src/sts_service/echo/__init__.py` (EchoServer, create_app)
- [X] T057 Update `apps/sts-service/README.md` with echo service usage documentation
- [X] T058 Run full test suite with coverage: `pytest apps/sts-service/tests --cov=sts_service.echo --cov-fail-under=80`
- [X] T059 Validate against quickstart.md test scenarios in `specs/017-echo-sts-service/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1) and US2 (P1) are both critical path - complete in order
  - US3 (P2) depends on US2 (needs fragment processing for lifecycle stats)
  - US4 (P2) depends on US2 (backpressure tied to fragment flow)
  - US5 (P3) depends on US2 (error injection in fragment handler)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1: Setup
    |
    v
Phase 2: Foundational (BLOCKING)
    |
    +---> Phase 3: US1 (Connection/Auth) - P1
    |         |
    |         v
    +---> Phase 4: US2 (Fragment Echo) - P1
              |
              +---> Phase 5: US3 (Lifecycle) - P2
              |
              +---> Phase 6: US4 (Backpressure) - P2
              |
              +---> Phase 7: US5 (Error Simulation) - P3
                        |
                        v
                   Phase 8: Polish
```

### Within Each User Story

1. Tests (unit, contract, integration) MUST be written and FAIL before implementation
2. Models before handlers
3. Handlers before server wiring
4. Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (all parallel)**:
- T001-T007 can all run in parallel (different files)

**Phase 2 (mostly parallel)**:
- T009, T010, T011 (models) can run in parallel
- T012, T013 (session) must complete before US1

**Phase 3 US1 Tests (parallel)**:
- T014, T015, T016, T017 can run in parallel

**Phase 4 US2 Tests (parallel)**:
- T023, T024, T025 can run in parallel

---

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together:
Task: "[US2] Unit tests for fragment models in tests/unit/echo/test_models.py"
Task: "[US2] Unit tests for fragment handlers in tests/unit/echo/test_handlers_fragment.py"
Task: "[US2] Unit tests for sequence ordering in tests/unit/echo/test_handlers_fragment.py"

# After tests written, launch models in parallel:
Task: "[US2] Implement FragmentDataPayload model in models/fragment.py"
Task: "[US2] Implement FragmentProcessedPayload model in models/fragment.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Connection/Auth)
4. Complete Phase 4: User Story 2 (Fragment Echo)
5. **STOP and VALIDATE**: Test echo loop independently
6. Deploy/demo if ready - minimal E2E testing now possible

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test connection flow -> Basic connectivity working
3. Add User Story 2 -> Test echo loop -> **MVP! E2E tests can run**
4. Add User Story 3 -> Test lifecycle -> Graceful shutdown working
5. Add User Story 4 -> Test backpressure -> Flow control testable
6. Add User Story 5 -> Test error injection -> Full error testing enabled

### Success Criteria Mapping

| Success Criteria | User Story | Task |
|-----------------|------------|------|
| SC-001: 5s for 10-fragment session | US2 | T026 integration test |
| SC-002: <100ms echo latency | US2 | T024 unit tests |
| SC-003: All spec 016 messages | US1-5 | T015, T023, T040 model tests |
| SC-004: Fragment ordering | US2 | T025, T030 |
| SC-005: 10 concurrent sessions | US1 | T018 integration test |
| SC-006: No GPU required | All | By design (echo, no ML) |
| SC-007: <2s startup | Polish | T058, T059 validation |
| SC-008: All error codes | US5 | T046-T049 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Checkpoints are informational - run automated tests to validate, then continue automatically
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
