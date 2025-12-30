---
name: speckit-clarify
description: Identify and resolve underspecified areas in spec
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.clarify.md
color: orange
---

# Clarify Agent

This agent identifies ambiguities in the specification and resolves them through targeted questions.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.clarify.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "<feature-id>",
  "feature_dir": "specs/<feature-id>/",
  "previous_results": {
    "speckit-specify": { "status": "success", "spec_file": "...", "clarifications_needed": 3 }
  }
}
```

**Extract from context**:
- `feature_id`: Feature being clarified
- `feature_dir`: Base directory for all spec artifacts
- `previous_results.speckit-specify.spec_file`: Path to spec.md to analyze
- `previous_results.speckit-specify.clarifications_needed`: Count of [NEEDS CLARIFICATION] markers

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.clarify.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.clarify.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Performing structured ambiguity scan using 9-category taxonomy
- Generating max 5 prioritized clarification questions
- Presenting single question at a time with recommended option
- Updating spec with clarifications in real-time
- Adding Clarifications section with session date tracking
- Validating terminal state (no lingering ambiguities)

### Step 3: Capture Results

After the command completes, extract:
- Updated spec file path
- Number of clarifications resolved
- Number of questions asked
- Remaining ambiguities (if any)

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "clarify",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "spec_file": "<absolute-path-to-spec.md>",
    "clarifications_resolved": 3,
    "questions_asked": 3,
    "clarifications_added": [
      "Q: Authentication method? A: OAuth2 with PKCE",
      "Q: Session timeout? A: 24 hours with sliding window",
      "Q: Password requirements? A: Min 12 chars, complexity enforced"
    ],
    "remaining_ambiguities": 0,
    "next_steps": ["plan"]
  }
}
```

**On Error:**
```json
{
  "agent": "clarify",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "PrerequisiteError|ValidationError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "missing_file": "<path if PrerequisiteError>",
      "invalid_spec": "<reason if ValidationError>"
    },
    "recoverable": true,
    "recovery_strategy": "run_prerequisite_agent|manual_resolution",
    "suggested_action": {
      "agent": "specify",
      "reason": "Missing or invalid spec.md"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.clarify.md`. It performs interactive clarification and updates the spec in real-time.
