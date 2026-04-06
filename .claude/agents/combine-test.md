---
name: speckit-combine-test
description: Execute integration test plan, verify module combinations, and fix issues until all tests pass
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.combine-test.md
color: green
---

# Combine Test Agent

This agent executes the integration test plan, runs E2E tests, analyzes failures, fixes issues, and iterates until all tests pass.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.combine-test.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "019-module-combination-testing",
  "feature_dir": "specs/019-module-combination-testing/",
  "previous_results": {
    "speckit-combine-plan": {
      "status": "success",
      "context_file": "specs/019-module-combination-testing/context.md",
      "total_tests": 38,
      "p1_tests": 13,
      "p2_tests": 19,
      "p3_tests": 6
    }
  }
}

USER_REQUEST: <original user request text>

FEEDBACK_CONTEXT (if max iterations reached):
{
  "feedback_from": "speckit-combine-test",
  "iteration": 10,
  "max_iterations": 10,
  "blocking_issues": [
    {
      "severity": "CRITICAL",
      "type": "test_failure",
      "test": "test_full_pipeline::test_rtsp_to_rtmp",
      "message": "Persistent timeout after 10 iterations",
      "recommendation": "Manual investigation required"
    }
  ]
}
```

**Extract from context**:
- `workflow_id`: Unique workflow identifier
- `feature_id`: Always "019-module-combination-testing" for this agent
- `feature_dir`: Directory for context.md file
- `previous_results.speckit-combine-plan`: Test plan results
- `USER_REQUEST`: Original user request for context
- `FEEDBACK_CONTEXT`: If present, indicates max iterations reached

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.combine-test.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.combine-test.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Running check-prerequisites.sh for paths
- Loading context.md with test plan
- Setting up test environment (Docker Compose)
- Verifying 3rd party library versions
- Running P1/P2/P3 tests with comprehensive logging
- Collecting Docker logs for failures
- Analyzing test results and categorizing issues
- Fixing issues (test/implementation/config/3rd party)
- Re-running failed tests
- Iterating until all tests pass (max 10 iterations)
- Updating context.md with execution log
- Generating final report

### Step 3: Capture Results

After the command completes, extract:
- Total tests run
- Tests passed/failed by priority
- Iterations required
- Issues found and fixed
- Final status (all passing or max iterations reached)

### Step 4: Return JSON Output

**On Success (All Tests Passing):**
```json
{
  "agent": "speckit-combine-test",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "context_file": "specs/019-module-combination-testing/context.md",
    "total_tests": 38,
    "tests_passed": 38,
    "tests_failed": 0,
    "p1_results": { "total": 13, "passed": 13, "failed": 0 },
    "p2_results": { "total": 19, "passed": 19, "failed": 0 },
    "p3_results": { "total": 6, "passed": 6, "failed": 0 },
    "iterations_required": 3,
    "issues_found": 5,
    "issues_fixed": 5,
    "third_party_issues": {
      "docker": 0,
      "socketio": 1,
      "gstreamer": 0,
      "pytest": 0
    },
    "all_tests_passing": true,
    "next_steps": ["Review context.md for detailed logs", "Consider creating PR for fixes"]
  }
}
```

**On Partial Success (Max Iterations Reached):**
```json
{
  "agent": "speckit-combine-test",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "context_file": "specs/019-module-combination-testing/context.md",
    "total_tests": 38,
    "tests_passed": 35,
    "tests_failed": 3,
    "iterations_required": 10,
    "issues_found": 8,
    "issues_fixed": 5
  },
  "error": {
    "type": "MaxIterationsReached",
    "code": "MAX_ITERATIONS",
    "message": "Reached maximum 10 iterations with 3 tests still failing",
    "details": {
      "remaining_failures": [
        "test_full_pipeline::test_rtsp_to_rtmp",
        "test_circuit_breaker::test_recovery",
        "test_reconnection::test_exponential_backoff"
      ]
    },
    "recoverable": true,
    "feedback_required": true,
    "recovery_strategy": "manual_investigation",
    "blocking_issues": [
      {
        "severity": "CRITICAL",
        "type": "test_failure",
        "test": "test_full_pipeline::test_rtsp_to_rtmp",
        "category": "Infrastructure Issue",
        "message": "Persistent timeout - may require infrastructure fix",
        "logs": "See context.md for full logs"
      }
    ]
  }
}
```

**On Error (Infrastructure/Environment):**
```json
{
  "agent": "speckit-combine-test",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "InfrastructureError|PrerequisiteError|ContextReadError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "docker_available": false,
      "pytest_available": true,
      "context_file_exists": true
    },
    "recoverable": false,
    "recovery_strategy": "fix_infrastructure",
    "suggested_action": {
      "user_action": "Ensure Docker is running and accessible"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.combine-test.md`. It delegates execution and adds JSON output formatting for orchestrator consumption.

Key characteristics:
- **Iterative execution**: Runs up to 10 iterations to fix issues
- **Comprehensive logging**: Captures pytest, Docker, and service logs
- **3rd party library analysis**: Identifies and documents library-related issues
- **Auto-fixing**: Fixes minor issues automatically, asks approval for major changes
- **Never stops**: Continues until 100% pass rate or max iterations reached
- **Context synchronization**: Updates context.md after each iteration
