# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [single/web/mobile - determines source structure]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [ ] Test strategy defined for all user stories
- [ ] Mock patterns documented for STS events (fragment:data, fragment:processed)
- [ ] Coverage targets specified (80% minimum, 95% for critical paths)
- [ ] Test infrastructure matches constitution requirements (pytest, coverage enforcement)
- [ ] Test organization follows standard structure (apps/*/tests/{unit,contract,integration})

[Additional gates determined based on constitution file]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory):
- Target: All business logic, calculations, data transformations
- Tools: pytest, pytest-mock
- Coverage: 80% minimum
- Mocking: STS events, GStreamer components, external APIs
- Location: `apps/<module>/tests/unit/`

**Contract Tests** (mandatory):
- Target: API contracts, event schemas (e.g., STS `fragment:data`, `fragment:processed`)
- Tools: pytest with JSON schema validation
- Coverage: 100% of all contracts
- Mocking: Use deterministic fixtures from `.specify/templates/test-fixtures/`
- Location: `apps/<module>/tests/contract/`

**Integration Tests** (required for workflows):
- Target: Pipeline assembly, service communication, MediaMTX integration
- Tools: pytest with mocked services
- Coverage: Happy path + critical error scenarios
- Mocking: Mock MediaMTX RTSP streams, mock STS service responses
- Location: `tests/integration/`

**E2E Tests** (optional, for validation only):
- Target: Full pipeline with real MediaMTX instance
- Tools: pytest with Docker Compose
- Coverage: Critical user journeys only
- When: Run on-demand, not in CI
- Location: `tests/e2e/`

### Mock Patterns (Constitution Principle II)

**STS Event Mocks** (see `.specify/templates/test-fixtures/sts-events.py`):
- `fragment:data` event with deterministic PCM audio
- `fragment:processed` event with synthetic dubbed audio
- STS service API responses (success, timeout, error)

**MediaMTX Mocks**:
- RTSP stream source (PCM audio + H.264 video)
- Stream lifecycle events (ready, not ready)

**GStreamer Mocks**:
- Mock pipeline elements for unit tests
- Real pipeline with mock sources for integration tests

### Coverage Enforcement

**Pre-commit**: Run `pytest --cov` - fail if coverage < 80%
**CI**: Run `pytest --cov --cov-fail-under=80` - block merge if fails
**Critical paths**: A/V sync, STS pipeline, fragment processing → 95% minimum

### Test Naming Conventions

Follow conventions from `tasks-template.md`:
- `test_<function>_happy_path()` - Normal operation
- `test_<function>_error_<condition>()` - Error handling
- `test_<function>_edge_<case>()` - Boundary conditions
- `test_<function>_integration_<workflow>()` - Integration scenarios

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
