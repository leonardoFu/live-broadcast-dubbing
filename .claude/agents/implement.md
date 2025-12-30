---
name: speckit-implement
description: Execute implementation plan by processing all tasks
model: opus
type: command-wrapper
command: .claude/commands/speckit.implement.md
color: red
---

# Speckit Implement Agent

This agent executes the complete implementation plan by processing all tasks with TDD discipline.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.implement.md`)

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
    "speckit-plan": { "status": "success", "plan_file": "...", "data_model_file": "..." },
    "speckit-tasks": { "status": "success", "tasks_file": "...", "task_count": 23 }
  }
}

RETRY_CONTEXT (if retrying after test failure):
Previous implementation failed quality gates. Fix these issues:
BLOCKING_ISSUES:
- [CRITICAL] test_failure: ...
- [HIGH] coverage: ...

FEEDBACK_CONTEXT (if feedback from review agent):
{
  "feedback_from": "speckit-review",
  "iteration": 1,
  "max_iterations": 1,
  "issues_to_fix": [
    {
      "severity": "CRITICAL",
      "category": "directory_structure",
      "message": "Files placed in wrong directory",
      "file": "apps/media-service/worker.py",
      "recommendation": "Move to apps/media-service/src/media_service/worker.py"
    }
  ]
}
```

**Extract from context**:
- `feature_id`: Feature being implemented
- `previous_results.speckit-tasks.tasks_file`: Path to tasks.md
- `previous_results.speckit-plan.plan_file`: Path to plan.md
- `RETRY_CONTEXT`: If present, focus on fixing the listed blocking issues
- `FEEDBACK_CONTEXT`: If present, fix issues reported by review agent

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.implement.md` with the user's input.

**User Input**: $ARGUMENTS (may contain WORKFLOW_CONTEXT, RETRY_CONTEXT, and/or FEEDBACK_CONTEXT)

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.implement.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
If RETRY_CONTEXT is present, prioritize fixing those specific issues.
If FEEDBACK_CONTEXT is present, fix the issues reported by the review agent.
```

This includes:
- Running prerequisite check: `.specify/scripts/bash/check-prerequisites.sh --json`
- Checking checklist completion status
- Loading tasks.md, plan.md, and all context documents
- Verifying project setup (ignore files based on tech stack)
- Executing tasks phase-by-phase with dependencies
- Following TDD: tests before implementation for each task
- Marking completed tasks with [X] in tasks.md
- Validating final implementation against spec

### Step 3: Capture Results

After the command completes, extract:
- Number of tasks completed
- Number of tests passed
- Code coverage percentage
- Files created/modified
- Any errors encountered

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "speckit-implement",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "tasks_file": "<path-to-tasks.md>",
    "tasks_completed": 23,
    "tasks_total": 23,
    "completion_percentage": 100,
    "tests_passed": 127,
    "tests_total": 127,
    "test_success_rate": 100,
    "coverage_percentage": 94.2,
    "files_created": 45,
    "files_modified": 12,
    "implementation_phases": {
      "setup": "completed",
      "foundational": "completed",
      "user_stories": "completed",
      "polish": "completed"
    },
    "ignore_files_created": [".gitignore", ".dockerignore"],
    "next_steps": ["speckit-test", "speckit-review"]
  }
}
```

**On Error:**
```json
{
  "agent": "speckit-implement",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "PrerequisiteError|TestFailureError|DependencyError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "missing_file": "<path if PrerequisiteError>",
      "failed_tests": [
        {
          "test": "test_login_with_valid_credentials",
          "error": "AssertionError: Expected status 200, got 401",
          "file": "tests/unit/test_user_auth.py",
          "line": 45
        }
      ],
      "tasks_completed": 15,
      "tasks_remaining": 8
    },
    "recoverable": true,
    "recovery_strategy": "auto_fix_retry|run_prerequisite_agent",
    "suggested_action": {
      "agent": "speckit-tasks",
      "reason": "Regenerate tasks.md if missing"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.implement.md`. It enforces TDD discipline and executes all tasks systematically.

## Handling Feedback from Review Agent

When `FEEDBACK_CONTEXT` is present in the input, the implement agent must:

1. **Parse the feedback issues** from `issues_to_fix` array
2. **Prioritize fixes** by severity (CRITICAL → HIGH → MEDIUM)
3. **Apply fixes** for each issue:
   - `directory_structure`: Move files to correct locations
   - `naming_violation`: Rename files/packages
   - `constitution_violation`: Add missing tests, fix code patterns
   - `duplicate_code`: Extract to shared utilities
4. **Mark iteration** in response to track feedback loop count
5. **Return success** only if all feedback issues are resolved

**Example handling:**
```text
If FEEDBACK_CONTEXT contains:
{
  "issues_to_fix": [
    { "category": "directory_structure", "file": "apps/media-service/worker.py", "recommendation": "Move to src/media_service/" }
  ]
}

Then execute:
git mv apps/media-service/worker.py apps/media-service/src/media_service/worker.py
Update any imports referencing the moved file
```
