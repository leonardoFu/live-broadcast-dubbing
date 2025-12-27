---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are MANDATORY per Constitution Principle VIII. Every user story MUST have tests written FIRST before implementation. The tasks below enforce a test-first workflow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

<!-- 
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.
  
  The /speckit.tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Feature requirements from plan.md
  - Entities from data-model.md
  - Endpoints from contracts/
  
  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment
  
  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize [language] project with [framework] dependencies
- [ ] T003 [P] Configure linting and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Examples of foundational tasks (adjust based on your project):

- [ ] T004 Setup database schema and migrations framework
- [ ] T005 [P] Implement authentication/authorization framework
- [ ] T006 [P] Setup API routing and middleware structure
- [ ] T007 Create base models/entities that all stories depend on
- [ ] T008 Configure error handling and logging infrastructure
- [ ] T009 Setup environment configuration management

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel (automated tests verify, continue automatically)

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Test Naming Conventions**:
- Unit tests: `test_<function>_<scenario>.py` (e.g., `test_chunk_audio_happy_path.py`)
- Contract tests: `test_<contract>_<event>.py` (e.g., `test_sts_fragment_processed.py`)
- Integration tests: `test_<workflow>_<scenario>.py` (e.g., `test_pipeline_assembly_valid_stream.py`)

**Coverage Target for US1**: 80% minimum (95% for critical paths)

- [ ] T010 [P] [US1] **Unit tests** for [specific functions] in `apps/<module>/tests/unit/test_<name>.py`
  - Test happy path: valid inputs → expected outputs
  - Test error cases: invalid inputs → proper exceptions
  - Test edge cases: boundary conditions, empty inputs, etc.
- [ ] T011 [P] [US1] **Contract tests** for STS events in `apps/<module>/tests/contract/test_sts_<event>.py`
  - Mock `fragment:data` event → validate processing
  - Mock `fragment:processed` event → validate output schema
  - Validate event serialization/deserialization
- [ ] T012 [P] [US1] **Integration tests** for [user journey] in `tests/integration/test_<workflow>.py`
  - Mock MediaMTX stream → validate end-to-end flow
  - Validate A/V sync preservation
  - Validate fallback behavior on STS failure

**Verification**: Run `pytest apps/<module>/tests` - ALL tests MUST FAIL with "NotImplementedError" or similar

### Implementation for User Story 1

- [ ] T012 [P] [US1] Create [Entity1] model in src/models/[entity1].py
- [ ] T013 [P] [US1] Create [Entity2] model in src/models/[entity2].py
- [ ] T014 [US1] Implement [Service] in src/services/[service].py (depends on T012, T013)
- [ ] T015 [US1] Implement [endpoint/feature] in src/[location]/[file].py
- [ ] T016 [US1] Add validation and error handling
- [ ] T017 [US1] Add logging for user story 1 operations

**Checkpoint**: User Story 1 should be fully functional and testable independently (run automated tests, continue automatically)

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US2**: 80% minimum (95% for critical paths)

- [ ] T018 [P] [US2] **Unit tests** for [specific functions] in `apps/<module>/tests/unit/test_<name>.py`
- [ ] T019 [P] [US2] **Contract tests** for [API/events] in `apps/<module>/tests/contract/test_<name>.py`
- [ ] T020 [P] [US2] **Integration tests** for [user journey] in `tests/integration/test_<workflow>.py`

**Verification**: Run `pytest apps/<module>/tests` - ALL tests MUST FAIL before implementation

### Implementation for User Story 2

- [ ] T020 [P] [US2] Create [Entity] model in src/models/[entity].py
- [ ] T021 [US2] Implement [Service] in src/services/[service].py
- [ ] T022 [US2] Implement [endpoint/feature] in src/[location]/[file].py
- [ ] T023 [US2] Integrate with User Story 1 components (if needed)

**Checkpoint**: User Stories 1 AND 2 should both work independently (run automated tests, continue automatically)

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US3**: 80% minimum (95% for critical paths)

- [ ] T024 [P] [US3] **Unit tests** for [specific functions] in `apps/<module>/tests/unit/test_<name>.py`
- [ ] T025 [P] [US3] **Contract tests** for [API/events] in `apps/<module>/tests/contract/test_<name>.py`
- [ ] T026 [P] [US3] **Integration tests** for [user journey] in `tests/integration/test_<workflow>.py`

**Verification**: Run `pytest apps/<module>/tests` - ALL tests MUST FAIL before implementation

### Implementation for User Story 3

- [ ] T026 [P] [US3] Create [Entity] model in src/models/[entity].py
- [ ] T027 [US3] Implement [Service] in src/services/[service].py
- [ ] T028 [US3] Implement [endpoint/feature] in src/[location]/[file].py

**Checkpoint**: All user stories should now be independently functional (run automated tests, continue automatically)

---

[Add more user story phases as needed, following the same pattern]

---

## Test Organization Standards

### Directory Structure
```
apps/<module>/
├── src/
│   ├── __init__.py
│   ├── models/
│   ├── services/
│   └── pipeline/
└── tests/
    ├── __init__.py
    ├── conftest.py          # Shared fixtures
    ├── unit/
    │   ├── __init__.py
    │   ├── test_models.py
    │   ├── test_services.py
    │   └── test_pipeline.py
    ├── contract/
    │   ├── __init__.py
    │   ├── test_sts_events.py
    │   └── test_api_schema.py
    └── integration/
        ├── __init__.py
        └── test_workflow.py

tests/                        # Root-level integration/e2e
├── __init__.py
├── conftest.py              # Global fixtures
├── integration/
│   ├── test_mediamtx_integration.py
│   └── test_worker_lifecycle.py
└── e2e/
    └── test_full_pipeline.py (optional)
```

### Naming Conventions

**Test Files**:
- `test_<module>.py` - Tests for a specific module
- `test_<feature>_<scenario>.py` - Tests for specific scenarios

**Test Functions**:
- `test_<function>_happy_path()` - Normal operation
- `test_<function>_error_<condition>()` - Error handling
- `test_<function>_edge_<case>()` - Boundary conditions
- `test_<function>_integration_<workflow>()` - Integration scenarios

**Examples**:
```python
# Unit test
def test_chunk_audio_happy_path():
    """Test audio chunking with valid PCM input."""
    pass

# Error case
def test_chunk_audio_error_invalid_sample_rate():
    """Test audio chunking raises ValueError for invalid sample rate."""
    pass

# Edge case
def test_chunk_audio_edge_zero_duration():
    """Test audio chunking handles zero-duration input."""
    pass

# Integration test
def test_pipeline_assembly_integration_valid_stream():
    """Test GStreamer pipeline assembles correctly with mocked RTSP stream."""
    pass
```

### Fixture Organization

**apps/<module>/tests/conftest.py**:
```python
"""Module-level test fixtures."""
import pytest

@pytest.fixture
def sample_pcm_audio():
    """Provide deterministic PCM audio for testing."""
    # 1 second of silence at 16kHz, S16LE
    return b'\x00\x00' * 16000

@pytest.fixture
def mock_sts_fragment():
    """Provide mock STS fragment event."""
    return {
        "fragment_id": "test-frag-001",
        "stream_id": "test-stream",
        "sequence_number": 1,
        "audio_data": "base64encodedpcm...",
        "duration_ms": 1000,
        "sample_rate": 16000,
        "channels": 1
    }
```

**tests/conftest.py** (global):
```python
"""Global test fixtures for integration tests."""
import pytest

@pytest.fixture
def mock_mediamtx_stream():
    """Provide mock MediaMTX RTSP stream."""
    pass

@pytest.fixture
def mock_sts_service():
    """Provide mock STS service API for integration tests."""
    pass
```

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and refactoring
- [ ] TXXX Performance optimization across all stories
- [ ] TXXX [P] Additional unit tests (if requested) in tests/unit/
- [ ] TXXX Security hardening
- [ ] TXXX Run quickstart.md validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (if tests requested):
Task: "Contract test for [endpoint] in tests/contract/test_[name].py"
Task: "Integration test for [user journey] in tests/integration/test_[name].py"

# Launch all models for User Story 1 together:
Task: "Create [Entity1] model in src/models/[entity1].py"
Task: "Create [Entity2] model in src/models/[entity2].py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Checkpoints are informational - run automated tests to validate, then continue automatically unless manual verification is explicitly required
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
