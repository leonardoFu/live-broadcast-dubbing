# Module Combination Testing Context

**Feature ID**: 019-module-combination-testing
**Created**: 2026-01-01
**Status**: Planning
**Last Updated**: 2026-01-01

## Overview

This feature implements specialized agents for systematically combining and testing previously implemented modules to verify they work together as expected according to specifications.

## Goals

1. Create a `speckit.combine-plan` agent that:
   - Analyzes existing specs and E2E tests
   - Identifies module combinations to test
   - Generates a comprehensive test plan
   - Tracks progress in a context file

2. Create a `speckit.combine-test` agent that:
   - Executes the test plan systematically
   - Runs existing E2E tests to verify module integration
   - Identifies and reports issues
   - Updates test results in the context file

3. Integrate with orchestrator:
   - Add new "combine" workflow to orchestrator
   - Enable continuous iteration until all tests pass
   - Never stop until component combination is complete

## Current Implementation Status

### Implemented Modules (from codebase exploration)

**Apps/Services:**
- **media-service**: CPU-based stream processing
  - Worker orchestration (WorkerManager, StreamWorker, WorkerRunner)
  - GStreamer pipeline (input/output)
  - STS integration (Socket.IO client, circuit breaker, reconnection, backpressure)
  - Buffer management
  - A/V synchronization
  - Metrics endpoint

- **sts-service**: GPU-based speech-to-speech translation
  - Echo STS Service (testing)
  - ASR module (speech recognition)
  - Translation module (DeepL provider)
  - TTS module (Coqui provider, duration matching)

**Libs:**
- dubbing-common: Shared utilities
- dubbing-contracts: API contracts and event schemas

### Existing E2E Tests

Located in `/tests/e2e/` - 9 test files, 38 test functions:

| Test File | Tests | Priority | Focus |
|-----------|-------|----------|-------|
| test_full_pipeline.py | 5 | P1 | RTSP→STS→RTMP workflow |
| test_av_sync.py | 5 | P1 | A/V synchronization |
| test_fragment_tracker.py | 6 | P2 | Fragment tracking |
| test_reconnection.py | 6 | P3 | Reconnection resilience |
| test_circuit_breaker.py | 4 | P2 | Circuit breaker |
| test_backpressure.py | 5 | P2 | Backpressure handling |
| test_dual_compose_full_pipeline.py | 3 | P1 | Real STS integration |
| test_dual_compose_real_sts_processing.py | 2 | P1 | Real ASR+Translation+TTS |
| test_dual_compose_service_communication.py | 2 | P1 | Service discovery |

## Implemented Modules Analysis

_This section will be populated by speckit.combine-plan agent_

**Status**: Pending analysis

The combine-plan agent will analyze:
- All specs in `specs/` directory
- Service purposes and capabilities
- Module interfaces and contracts
- Integration points between services
- Expected behaviors and user stories

## E2E Test Coverage Analysis

_This section will be populated by speckit.combine-plan agent_

**Status**: Pending analysis

The combine-plan agent will analyze:
- All test files in `tests/e2e/`
- Test priorities (P1/P2/P3 markers)
- Module combinations each test covers
- Test fixtures and helpers used
- Test infrastructure utilities

## Module Combination Scenarios

_This section will be populated by speckit.combine-plan agent_

**Status**: Pending analysis

Expected scenario categories:
- **Critical Combinations (P1)**: Core user journeys
- **Important Combinations (P2)**: Resilience features
- **Edge Cases (P3)**: Error scenarios

## Test Execution Plan

_This section will be populated by speckit.combine-plan agent_

**Status**: Pending plan generation

Expected plan structure:
- **Phase 1**: Setup and Environment Verification
- **Phase 2**: P1 Tests (Critical Path)
- **Phase 3**: P2 Tests (Important Features)
- **Phase 4**: P3 Tests (Edge Cases)
- **Success Criteria**: Definition of "all tests passing"

## Test Priority Matrix

_This section will be populated by speckit.combine-plan agent_

**Status**: Pending matrix generation

Expected format:
```
| Test File | Function | Priority | Modules | Expected Result |
|-----------|----------|----------|---------|-----------------|
| ... | ... | ... | ... | ... |
```

## Expected Behaviors

_This section will be populated by speckit.combine-plan agent_

**Status**: Pending documentation

For each module combination:
- Input conditions
- Expected outputs
- Success criteria
- Known limitations

## Test Execution Log

_This section will be updated by speckit.combine-test agent_

### Test Run: Not Started
- Status: Awaiting execution
- Tests Run: 0/38
- Passed: 0
- Failed: 0
- Skipped: 0

**Iterations**: None

## Issues Tracker

_This section will be updated by speckit.combine-test agent_

### Active Issues
- None

### Resolved Issues
- None

## Next Steps

1. Run `speckit.combine-plan` to analyze modules and generate detailed test plan
2. Run `speckit.combine-test` to execute test plan and verify module integration
3. Iterate until all tests pass

**How to Execute**:
```bash
# Via orchestrator (recommended)
/speckit-orchestrator
combine

# Or direct invocation
/speckit.combine-plan
/speckit.combine-test
```

## References

- Specs: `/specs/` (all feature specifications)
- E2E Tests: `/tests/e2e/` (existing test suite)
- Test Infrastructure: `/tests/e2e/helpers/` (test utilities)
- Media Service: `/apps/media-service/`
- STS Service: `/apps/sts-service/`
- Documentation: `specs/019-module-combination-testing/README.md`
