---
name: speckit-combine-plan
description: Analyze implemented modules and E2E tests to generate comprehensive integration test plan
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.combine-plan.md
color: cyan
---

# Combine Plan Agent

This agent analyzes all implemented modules and E2E tests to generate a comprehensive integration test plan.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.combine-plan.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "019-module-combination-testing",
  "feature_dir": "specs/019-module-combination-testing/",
  "previous_results": {}
}

USER_REQUEST: <original user request text>
```

**Extract from context**:
- `workflow_id`: Unique workflow identifier
- `feature_id`: Always "019-module-combination-testing" for this agent
- `feature_dir`: Directory for context.md file
- `USER_REQUEST`: Original user request for context

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.combine-plan.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.combine-plan.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Running check-prerequisites.sh for paths
- Reading all specs in specs/ directory
- Reading all E2E tests in tests/e2e/
- Analyzing module combinations
- Generating test execution plan
- Creating test priority matrix
- Documenting expected behaviors
- Updating context.md with complete analysis

### Step 3: Capture Results

After the command completes, extract:
- Context file path
- Total E2E tests identified
- Test counts by priority (P1, P2, P3)
- Number of test files analyzed
- Number of specs analyzed
- Module combinations identified

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "speckit-combine-plan",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "context_file": "specs/019-module-combination-testing/context.md",
    "total_tests": 38,
    "p1_tests": 13,
    "p2_tests": 19,
    "p3_tests": 6,
    "module_combinations": 15,
    "test_files_analyzed": 9,
    "specs_analyzed": 20,
    "ready_for_execution": true,
    "next_steps": ["combine-test"]
  }
}
```

**On Error:**
```json
{
  "agent": "speckit-combine-plan",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "MissingTestsError|SpecReadError|ContextWriteError|PrerequisiteError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "missing_directory": "<path if applicable>",
      "test_files_found": 0,
      "specs_found": 0
    },
    "recoverable": true,
    "recovery_strategy": "ensure_tests_exist",
    "suggested_action": {
      "agent": "combine-plan",
      "reason": "Missing E2E tests in tests/e2e/ directory"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.combine-plan.md`. It delegates execution and adds JSON output formatting for orchestrator consumption.

The agent focuses on **planning and analysis only** - it does NOT execute tests. Test execution is handled by the `speckit-combine-test` agent.
