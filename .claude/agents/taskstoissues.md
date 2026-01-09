---
name: speckit-taskstoissues
description: Convert tasks into actionable GitHub issues
model: haiku
type: command-wrapper
command: .claude/commands/speckit.taskstoissues.md
color: pink
---

# Tasks to Issues Agent

Converts the task list into GitHub issues for team collaboration and tracking.

**Command**: `.claude/commands/speckit.taskstoissues.md`

## Execution

1. Parse `WORKFLOW_CONTEXT`, `USER_REQUEST`, and `RESPONSE_FORMAT` from input
2. Execute `.claude/commands/speckit.taskstoissues.md` with `$ARGUMENTS`
3. Return JSON per `RESPONSE_FORMAT` with result fields below

## Result Fields

Return these in `result`:
- `issues_created`: Number of issues created
- `issues`: List with number, title, url, task_id
- `milestone_url`: URL to milestone (if created)
- `milestone_title`: Milestone name
- `labels_applied`: List of labels applied
- `feature_branch`: Branch name
- `next_steps`: ["Assign issues to team members", "Track progress via milestone"]

## Prerequisites

- Git remote must be a GitHub URL
- `gh` CLI must be authenticated
- tasks.md must exist
