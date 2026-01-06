---
description: Analyze implemented modules and E2E tests to generate a comprehensive integration test plan
handoffs:
  - label: Execute Test Plan
    agent: speckit.combine-test
    prompt: Execute the test plan and verify module combinations
    send: true
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. **Setup**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse paths. All paths must be absolute. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").
   - Parse JSON output to get repository root and paths
   - Set context file location: `specs/019-module-combination-testing/context.md`
   - Load existing context if present, or initialize new one
   - Extract WORKFLOW_CONTEXT if provided by orchestrator (contains workflow_id, feature_id, previous_results)

2. **Analyze Implemented Modules**:
   - **Services**: Read all specs in `specs/` directory to understand:
     - Service purposes and capabilities
     - Module interfaces and contracts
     - Integration points between services
     - Expected behaviors and user stories
   - **Libraries**: Identify shared libraries in `libs/`
   - **Dependencies**: Map service dependencies and communication protocols
   - Document findings in context.md under "Implemented Modules Analysis"

3. **Analyze Existing E2E Tests**:
   - **Test Coverage**: Read all E2E tests in `tests/e2e/`
     - List all test files and test functions
     - Extract test priorities (P1/P2/P3 markers)
     - Identify what module combinations each test covers
     - Note test fixtures and helpers used
   - **Test Infrastructure**: Review `tests/e2e/helpers/`
     - docker_compose_manager.py
     - stream_publisher.py
     - stream_analyzer.py
     - socketio_monitor.py
     - metrics_parser.py
   - Document findings in context.md under "E2E Test Coverage Analysis"

4. **Identify Module Combination Scenarios**:
   Based on specs and current tests, identify:
   - **Critical Combinations (P1)**: Core user journeys
     - RTSP ingestion → media-service → STS → RTMP output
     - Real ASR → Translation → TTS pipeline
     - Service discovery and health checks
   - **Important Combinations (P2)**: Resilience features
     - Circuit breaker with fallback
     - Backpressure handling
     - Fragment tracking
   - **Edge Cases (P3)**: Error scenarios
     - Reconnection after failures
     - Network interruptions
     - Invalid input handling
   - Document in context.md under "Module Combination Scenarios"

5. **Generate Test Execution Plan**:
   Create a structured plan with:
   - **Phase 1**: Setup and Environment Verification
     - Docker Compose services start successfully
     - All services reach healthy state
     - Network connectivity verified
   - **Phase 2**: P1 Tests (Critical Path)
     - List all P1 test files and functions
     - Expected outcomes for each test
     - Dependencies between tests
   - **Phase 3**: P2 Tests (Important Features)
     - List all P2 test files and functions
     - Expected outcomes
   - **Phase 4**: P3 Tests (Edge Cases)
     - List all P3 test files and functions
     - Expected outcomes
   - **Success Criteria**: Define what "all tests passing" means
     - 100% of P1 tests must pass
     - 100% of P2 tests must pass
     - 100% of P3 tests must pass
     - No regressions in unit/integration tests
   - Document in context.md under "Test Execution Plan"

6. **Create Test Priority Matrix**:
   Generate a table mapping tests to priorities and module combinations:
   ```
   | Test File | Function | Priority | Modules | Expected Result |
   |-----------|----------|----------|---------|-----------------|
   | test_full_pipeline.py | test_rtsp_to_rtmp | P1 | media+sts+mediamtx | Stream output in 90s |
   ```
   - Document in context.md under "Test Priority Matrix"

7. **Expected Behaviors Documentation**:
   For each module combination, document:
   - Input conditions
   - Expected outputs
   - Success criteria
   - Known limitations
   - Document in context.md under "Expected Behaviors"

8. **Update Context File**:
   - Save all analysis and planning to `specs/019-module-combination-testing/context.md`
   - Update status to "Plan Ready"
   - Set "Next Steps" to point to speckit.combine-test execution

9. **Return JSON Response**:
   Output JSON response following the Agent Response Contract:
   ```json
   {
     "agent": "speckit-combine-plan",
     "status": "success",
     "timestamp": "<ISO8601 timestamp>",
     "result": {
       "context_file": "specs/019-module-combination-testing/context.md",
       "total_tests": <number>,
       "p1_tests": <number>,
       "p2_tests": <number>,
       "p3_tests": <number>,
       "module_combinations": <number>,
       "test_files_analyzed": <number>,
       "specs_analyzed": <number>,
       "ready_for_execution": true
     },
     "error": null
   }
   ```

10. **Display Summary to User**:
    After JSON response, display human-readable summary:
    - Total E2E tests identified: X tests across Y files
    - P1 tests: X critical tests
    - P2 tests: X important tests
    - P3 tests: X edge case tests
    - Module combinations identified: X combinations
    - Test execution plan generated: specs/019-module-combination-testing/context.md
    - Ready to execute: Run `speckit.combine-test` to begin testing

## Planning Rules

**CRITICAL**: The test plan must be exhaustive and systematic.

### Analysis Requirements

1. **Spec Analysis**:
   - Read ALL specs in `specs/` directory
   - Extract user stories and acceptance criteria
   - Identify service contracts and APIs
   - Map data models and entities
   - Note configuration requirements

2. **Test Coverage Analysis**:
   - Read ALL test files in `tests/e2e/`
   - Count total test functions
   - Extract pytest markers (@pytest.mark.p1, etc.)
   - Identify test fixtures used
   - Map tests to user stories from specs

3. **Gap Analysis**:
   - Compare spec user stories with test coverage
   - Identify untested module combinations
   - Note missing test scenarios
   - Document in context.md for future work

### Test Plan Structure

The test execution plan MUST include:

1. **Environment Setup Phase**:
   - Docker Compose startup procedure
   - Health check verification steps
   - Pre-test validation checklist

2. **Test Execution Phases** (by priority):
   - Phase order: P1 → P2 → P3
   - For each phase:
     - List of tests to run
     - Expected duration
     - Success criteria
     - Failure handling strategy

3. **Test Dependencies**:
   - Identify tests that must run in sequence
   - Identify tests that can run in parallel
   - Document blocking dependencies

4. **Success Criteria**:
   - Define pass/fail thresholds
   - Specify metrics to collect
   - Define what constitutes "complete"

### Context File Format

The context.md file should follow this structure:

```markdown
# Module Combination Testing Context

**Status**: [Planning/Ready/In Progress/Complete]
**Last Updated**: [Timestamp]

## Overview
[High-level summary]

## Implemented Modules Analysis
[Detailed analysis from step 2]

## E2E Test Coverage Analysis
[Detailed analysis from step 3]

## Module Combination Scenarios
[Scenarios from step 4]

## Test Execution Plan
[Plan from step 5]

## Test Priority Matrix
[Matrix from step 6]

## Expected Behaviors
[Behaviors from step 7]

## Test Execution Log
[Updated by combine-test agent]

## Issues Tracker
[Updated by combine-test agent]

## Next Steps
[Next actions]
```

## Output Requirements

After completing the plan:

1. **Context File Updated**: All analysis saved to context.md
2. **JSON Response**: Following Agent Response Contract format
3. **Summary Displayed**: Clear summary shown to user
4. **Next Action Clear**: User knows to run speckit.combine-test next
5. **Handoff Ready**: Context contains all information needed by combine-test agent

## Error Handling

If errors occur during planning, return JSON error response:

```json
{
  "agent": "speckit-combine-plan",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "result": {},
  "error": {
    "type": "MissingTestsError|SpecReadError|ContextWriteError",
    "message": "Detailed error message",
    "recoverable": true,
    "feedback_required": false,
    "suggested_action": {
      "agent": "speckit-combine-plan",
      "retry": true
    }
  }
}
```

**Error Types**:
- `MissingTestsError`: No E2E tests found in tests/e2e/
- `SpecReadError`: Cannot read specs from specs/ directory
- `ContextWriteError`: Cannot write to context.md file
- `PrerequisiteError`: check-prerequisites.sh failed

This agent focuses ONLY on planning and analysis. It does NOT execute tests.
