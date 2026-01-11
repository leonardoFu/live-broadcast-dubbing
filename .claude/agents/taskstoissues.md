---
name: speckit-taskstoissues
description: Convert tasks into actionable GitHub issues
model: haiku
color: pink
---

# Tasks to Issues Agent

Converts task list into GitHub issues for team collaboration.

## Input

Parse from `$ARGUMENTS`:
- `WORKFLOW_CONTEXT`: workflow_id, feature_id, feature_dir, previous_results
- `USER_REQUEST`: Original request
- `RESPONSE_FORMAT`: JSON structure for response

## Execution

### Step 1: Setup

Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` and parse:
- `FEATURE_DIR`, `AVAILABLE_DOCS`, tasks path

### Step 2: Validate GitHub Remote

```bash
git config --get remote.origin.url
```

**STOP** if remote is not a GitHub URL.

### Step 3: Create Issues

For each task in tasks.md:
- Use GitHub MCP server to create issue
- Map task ID to issue number
- Apply appropriate labels

**CRITICAL**: Only create issues in repositories matching the remote URL.

### Step 4: Return Result

Return JSON per `RESPONSE_FORMAT` with these result fields:
- `issues_created`: Number of issues created
- `issues`: List of {number, title, url, task_id}
- `milestone_url`: URL to milestone (if created)
- `milestone_title`: Milestone name
- `labels_applied`: List of labels
- `feature_branch`: Branch name
- `next_steps`: ["Assign issues to team members", "Track progress via milestone"]

## Prerequisites

- Git remote must be GitHub URL
- `gh` CLI must be authenticated
- tasks.md must exist
