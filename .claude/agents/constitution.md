---
name: speckit-constitution
description: Create or update project constitution
model: opus
type: command-wrapper
command: .claude/commands/speckit.constitution.md
color: gold
---

# Constitution Agent

This agent creates or updates the project constitution, which defines foundational governance principles.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.constitution.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": null,
  "feature_dir": null,
  "previous_results": {}
}

USER_REQUEST: <original user request text>
```

**Extract from context**:
- `workflow_id`: Unique identifier for this workflow run
- `USER_REQUEST`: User's constitution update request

**Note**: The constitution agent operates at the project level, not feature level. It does not require `feature_id` or `feature_dir`. The constitution applies globally to all features.

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.constitution.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.constitution.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Loading template with placeholder tokens [ALL_CAPS_IDENTIFIER]
- Collecting/deriving values for all placeholders
- Updating version following semantic versioning
- Propagating changes across dependent templates
- Validating all templates in consistency check
- Generating Sync Impact Report

### Step 3: Capture Results

After the command completes, extract:
- Constitution file path
- Version number
- Templates updated
- Sync impact report details

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "constitution",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "constitution_file": "<path-to-constitution.md>",
    "version": "1.2.0",
    "version_type": "minor",
    "principles_updated": ["Principle VIII: Test-Driven Development"],
    "templates_synchronized": [
      "plan-template.md",
      "spec-template.md",
      "tasks-template.md"
    ],
    "commands_validated": [
      "speckit.specify.md",
      "speckit.plan.md",
      "speckit.tasks.md"
    ],
    "sync_impact_report": "<path-to-sync-report.md>",
    "breaking_changes": false,
    "next_steps": ["Review constitution changes", "Communicate to team"]
  }
}
```

**On Error:**
```json
{
  "agent": "constitution",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "ValidationError|ConflictError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "invalid_principle": "<principle with validation error>",
      "conflicting_files": ["<files with conflicts>"]
    },
    "recoverable": false,
    "recovery_strategy": "manual_resolution",
    "suggested_action": {
      "action": "manual_fix",
      "reason": "Constitution conflicts require manual review"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.constitution.md`. It manages foundational governance and propagates changes to dependent templates.
