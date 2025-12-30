---
name: speckit-tasks
description: Generate actionable, dependency-ordered task list
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.tasks.md
color: yellow
---

# Tasks Agent

This agent generates a complete, dependency-ordered task list from the implementation plan.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.tasks.md`)

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
    "speckit-plan": { "status": "success", "plan_file": "...", "data_model_file": "..." }
  }
}
```

**Extract from context**:
- `feature_id`: Feature for task generation
- `feature_dir`: Base directory for all spec artifacts
- `previous_results.speckit-plan.plan_file`: Path to plan.md
- `previous_results.speckit-plan.data_model_file`: Path to data-model.md
- `previous_results.speckit-specify.spec_file`: Path to spec.md

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.tasks.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.tasks.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Loading spec.md, plan.md, data-model.md, contracts/
- Extracting requirements by priority (P1, P2, P3)
- Mapping entities and contracts to tasks
- Organizing tasks in phases: Setup → Foundational → User Stories → Polish
- Generating strict checklist format with Task IDs
- Creating dependency graph

### Step 3: Capture Results

After the command completes, extract:
- Tasks file path
- Total task count
- Tasks by phase
- Parallelizable tasks count
- Task IDs generated

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "tasks",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "tasks_file": "<absolute-path-to-tasks.md>",
    "task_count": 23,
    "phases": {
      "setup": 3,
      "foundational": 8,
      "user_stories": 10,
      "polish": 2
    },
    "parallelizable_tasks": 12,
    "task_ids": ["T001", "T002", "T003", "..."],
    "dependencies_mapped": true,
    "next_steps": ["analyze", "implement"]
  }
}
```

**On Error:**
```json
{
  "agent": "tasks",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "PrerequisiteError|ValidationError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "missing_file": "<path if PrerequisiteError>",
      "invalid_requirements": ["<list if ValidationError>"]
    },
    "recoverable": true,
    "recovery_strategy": "run_prerequisite_agent",
    "suggested_action": {
      "agent": "plan",
      "reason": "Missing plan.md required for task generation"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.tasks.md`. It delegates execution and adds JSON output formatting for orchestrator consumption.
