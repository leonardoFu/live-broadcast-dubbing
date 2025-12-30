---
name: speckit-checklist
description: Generate custom checklist for feature requirements validation
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.checklist.md
color: purple
---

# Checklist Agent

This agent generates domain-specific checklists to validate requirement quality (not implementation).

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.checklist.md`)

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
    "speckit-plan": { "status": "success", "plan_file": "..." }
  }
}
```

**Extract from context**:
- `feature_id`: Feature for checklist generation
- `feature_dir`: Base directory for all spec artifacts
- `previous_results.speckit-specify.spec_file`: Path to spec.md
- `previous_results.speckit-plan.plan_file`: Path to plan.md (if available)

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.checklist.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.checklist.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Deriving up to 3 clarifying questions from spec context
- Creating domain-specific checklists (ux.md, api.md, security.md, etc.)
- Testing requirement quality dimensions: Completeness, Clarity, Consistency, Measurability
- Using strict format: `- [ ] CHK### <requirement item> [dimension, Spec §X.Y]`
- Generating unique filename based on domain/focus area

### Step 3: Capture Results

After the command completes, extract:
- Checklist file path
- Domain/focus area
- Total checklist items
- Categories covered

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "checklist",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "checklist_file": "<absolute-path-to-checklist.md>",
    "domain": "ux|api|security|performance|data",
    "total_items": 15,
    "categories": [
      "Completeness",
      "Clarity",
      "Consistency",
      "Measurability"
    ],
    "checklist_name": "User Experience Validation",
    "next_steps": ["Review and complete checklist items", "tasks"]
  }
}
```

**On Error:**
```json
{
  "agent": "checklist",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "PrerequisiteError|ValidationError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "missing_file": "<path if PrerequisiteError>"
    },
    "recoverable": true,
    "recovery_strategy": "run_prerequisite_agent",
    "suggested_action": {
      "agent": "specify",
      "reason": "Missing spec.md required for checklist generation"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.checklist.md`. It tests requirement quality, NOT implementation correctness.
