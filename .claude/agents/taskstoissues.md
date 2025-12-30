---
name: speckit-taskstoissues
description: Convert tasks into actionable GitHub issues
model: haiku
type: command-wrapper
command: .claude/commands/speckit.taskstoissues.md
color: pink
---

# Tasks to Issues Agent

This agent converts the task list into GitHub issues for team collaboration and tracking.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.taskstoissues.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "<feature-id>",
  "feature_dir": "specs/<feature-id>/",
  "previous_results": {
    "speckit-tasks": { "status": "success", "tasks_file": "...", "task_count": 23 }
  }
}
```

**Extract from context**:
- `feature_id`: Feature for issue creation
- `feature_dir`: Base directory for all spec artifacts
- `previous_results.speckit-tasks.tasks_file`: Path to tasks.md
- `previous_results.speckit-tasks.task_count`: Number of tasks to convert

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.taskstoissues.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.taskstoissues.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Validating Git remote is a GitHub URL
- Loading tasks.md
- Creating one GitHub issue per task using `gh` CLI
- Maintaining task order and dependencies in issues
- Linking issues to feature branch
- Setting appropriate labels and milestones

### Step 3: Capture Results

After the command completes, extract:
- Number of issues created
- Issue URLs
- Milestone URL (if created)
- Any creation failures

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "taskstoissues",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "issues_created": 23,
    "issue_urls": [
      "https://github.com/owner/repo/issues/145",
      "https://github.com/owner/repo/issues/146",
      "https://github.com/owner/repo/issues/147"
    ],
    "milestone_url": "https://github.com/owner/repo/milestone/5",
    "milestone_title": "Feature: User Authentication",
    "labels_applied": ["feature", "user-auth", "P1"],
    "feature_branch": "005-user-authentication",
    "next_steps": ["Assign issues to team members", "Track progress via milestone"]
  }
}
```

**On Error:**
```json
{
  "agent": "taskstoissues",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "ExternalServiceError|PrerequisiteError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "service": "GitHub API",
      "http_status": 403,
      "missing_file": "<path if PrerequisiteError>"
    },
    "recoverable": true,
    "recovery_strategy": "exponential_backoff_retry|run_prerequisite_agent",
    "suggested_action": {
      "agent": "tasks",
      "reason": "Missing tasks.md required for issue creation"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.taskstoissues.md`. It uses the `gh` CLI to create GitHub issues from tasks.
