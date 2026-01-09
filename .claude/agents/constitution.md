---
name: speckit-constitution
description: Create or update project constitution
model: opus
type: command-wrapper
command: .claude/commands/speckit.constitution.md
color: gold
---

# Constitution Agent

Creates or updates the project constitution, which defines foundational governance principles.

**Command**: `.claude/commands/speckit.constitution.md`

## Execution

1. Parse `WORKFLOW_CONTEXT`, `USER_REQUEST`, and `RESPONSE_FORMAT` from input
2. Execute `.claude/commands/speckit.constitution.md` with `$ARGUMENTS`
3. Return JSON per `RESPONSE_FORMAT` with result fields below

**Note**: Operates at project level, not feature level. No `feature_id` required.

## Result Fields

Return these in `result`:
- `constitution_file`: Path to constitution.md
- `version`: Version number (semver)
- `version_type`: "major", "minor", or "patch"
- `principles_updated`: List of updated principles
- `templates_synchronized`: List of synced templates
- `commands_validated`: List of validated commands
- `sync_impact_report`: Path to sync report
- `breaking_changes`: Boolean
- `next_steps`: ["Review constitution changes", "Communicate to team"]

## Sync Behavior

Changes propagate to:
- plan-template.md
- spec-template.md
- tasks-template.md
