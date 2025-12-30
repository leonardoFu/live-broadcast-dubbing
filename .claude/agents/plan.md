---
name: speckit-plan
description: Execute implementation planning workflow using plan template
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.plan.md
color: green
---

# Plan Agent

This agent executes the implementation planning workflow, generating technical design artifacts.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.plan.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "<feature-id>",
  "feature_dir": "specs/<feature-id>/",
  "previous_results": {
    "speckit-specify": { "status": "success", "spec_file": "..." },
    "speckit-clarify": { "status": "success", "clarifications_resolved": 3 }
  }
}
```

**Extract from context**:
- `feature_id`: Feature being planned
- `feature_dir`: Base directory for all spec artifacts
- `previous_results.speckit-specify.spec_file`: Path to spec.md to load

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.plan.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.plan.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Running setup script: `.specify/scripts/bash/setup-plan.sh --json`
- Loading spec and constitution
- Executing Phase 0: Research (resolve unknowns)
- Executing Phase 1: Design (data-model, contracts, quickstart)
- Updating agent context

### Step 3: Capture Results

After the command completes, extract:
- Plan file path
- Research file path (if created)
- Data model file path (if created)
- Contracts directory (if created)
- Quickstart file path (if created)
- Technologies identified
- Constitution violations (if any)

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "plan",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "plan_file": "<absolute-path-to-plan.md>",
    "research_file": "<absolute-path-to-research.md>",
    "data_model_file": "<absolute-path-to-data-model.md>",
    "contracts_dir": "<absolute-path-to-contracts/>",
    "quickstart_file": "<absolute-path-to-quickstart.md>",
    "technologies": [
      "Python 3.10",
      "FastAPI",
      "PostgreSQL"
    ],
    "constitution_violations": [],
    "artifacts_created": [
      "plan.md",
      "research.md",
      "data-model.md",
      "contracts/",
      "quickstart.md"
    ],
    "next_steps": ["checklist", "tasks"]
  }
}
```

**On Error:**
```json
{
  "agent": "plan",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "PrerequisiteError|ValidationError|ConstitutionViolationError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "missing_file": "<path if PrerequisiteError>",
      "violations": ["<list if ConstitutionViolationError>"]
    },
    "recoverable": true|false,
    "recovery_strategy": "run_prerequisite_agent|manual_resolution",
    "suggested_action": {
      "agent": "specify",
      "reason": "Missing spec.md required for planning"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.plan.md`. It delegates execution and adds JSON output formatting for orchestrator consumption.
