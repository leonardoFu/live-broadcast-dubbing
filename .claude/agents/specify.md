---
name: speckit-specify
description: Create feature specification from natural language description
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.specify.md
color: blue
---

# Specify Agent

This agent creates feature specifications from natural language descriptions.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.specify.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "<feature-id>",
  "feature_dir": "specs/<feature-id>/",
  "previous_results": {}
}

USER_REQUEST: <original user request text>

FEEDBACK_CONTEXT (if feedback from analyze agent):
{
  "feedback_from": "speckit-analyze",
  "iteration": 1,
  "max_iterations": 2,
  "issues_to_fix": [
    {
      "severity": "CRITICAL",
      "type": "spec_ambiguity",
      "message": "Requirement REQ-3 is ambiguous",
      "location": "spec.md:45",
      "recommendation": "Clarify authentication scope"
    }
  ]
}
```

**Extract from context**:
- `workflow_id`: Unique identifier for this workflow run
- `feature_id`: Feature being created (may be auto-generated if not provided)
- `USER_REQUEST`: Original user request to understand intent
- `FEEDBACK_CONTEXT`: If present, fix issues reported by analyze agent

**Note**: As the first agent in the workflow, `specify` typically receives minimal context. It establishes the feature_id and feature_dir that subsequent agents will use.

## Handling Feedback from Analyze Agent

When `FEEDBACK_CONTEXT` is present in the input, the specify agent must:

1. **Parse the feedback issues** from `issues_to_fix` array
2. **Identify spec-related issues**: `spec_ambiguity`, `missing_requirement`, `unclear_scope`
3. **Update spec.md** to address each issue:
   - Add missing requirements
   - Clarify ambiguous language
   - Add detail to underspecified sections
4. **Return success** only if all feedback issues are resolved

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.specify.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.specify.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

### Step 3: Capture Results

After the command completes, extract the following information:
- Branch name created
- Spec file path
- Feature number
- Clarifications needed (count of [NEEDS CLARIFICATION] markers)
- Checklist status
- Any errors encountered

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "specify",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "branch_name": "<branch-name>",
    "spec_file": "<absolute-path-to-spec.md>",
    "feature_number": <number>,
    "short_name": "<short-name>",
    "clarifications_needed": <count>,
    "clarification_markers": [
      "<clarification question 1>",
      "<clarification question 2>"
    ],
    "sections_generated": [
      "Overview",
      "User Scenarios & Testing",
      "Functional Requirements",
      "Success Criteria",
      "Key Entities"
    ],
    "checklist_status": "complete|incomplete",
    "checklist_file": "<path-to-requirements.md>",
    "next_steps": ["clarify", "plan"]
  }
}
```

**On Error:**
```json
{
  "agent": "specify",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "ValidationError|BranchExistsError|PermissionError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "context": "<additional error context>"
    },
    "recoverable": true|false,
    "recovery_strategy": "ask_user|invoke_clarify_agent|manual_resolution",
    "suggested_action": {
      "agent": "<next-agent-to-run>",
      "reason": "<why this will help>"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around the original command in `.claude/commands/speckit.specify.md`. The wrapper:
1. Delegates execution to the original command logic
2. Captures the results
3. Formats output as structured JSON
4. Provides error handling with recovery suggestions
