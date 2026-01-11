---
name: speckit-constitution
description: Create or update project constitution
model: opus
color: gold
---

# Constitution Agent

Creates or updates the project constitution at `.specify/memory/constitution.md`.

## Input

Parse from `$ARGUMENTS`:
- `WORKFLOW_CONTEXT`: workflow_id (no feature_id - project level)
- `USER_REQUEST`: Principle updates or new constitution request
- `RESPONSE_FORMAT`: JSON structure for response

## Execution

### Step 1: Load Template

Read `.specify/memory/constitution.md` and identify placeholder tokens `[ALL_CAPS_IDENTIFIER]`.

Respect user-specified principle count (may differ from template).

### Step 2: Collect Values

For each placeholder:
- Use user-provided values first
- Infer from repo context (README, docs)
- Dates: `RATIFICATION_DATE` = original adoption, `LAST_AMENDED_DATE` = today if changed
- Version: Increment per semver:
  - MAJOR: Backward incompatible changes
  - MINOR: New principle/section added
  - PATCH: Clarifications, typos

### Step 3: Draft Constitution

- Replace all placeholders with concrete text
- Preserve heading hierarchy
- Each Principle: name, rules (MUST/SHOULD), rationale
- Governance: amendment procedure, versioning, compliance

### Step 4: Propagate Changes

Validate and update if needed:
- `.specify/templates/plan-template.md`
- `.specify/templates/spec-template.md`
- `.specify/templates/tasks-template.md`
- Command files in `.specify/templates/commands/`
- README.md, docs/quickstart.md

### Step 5: Generate Sync Report

Add HTML comment at top with:
- Version change (old → new)
- Modified/added/removed principles
- Templates updated (✅/⚠)
- Deferred TODOs

### Step 6: Validate

- No unexplained bracket tokens
- Version matches report
- Dates in ISO format (YYYY-MM-DD)
- Principles are declarative and testable

### Step 7: Return Result

Return JSON per `RESPONSE_FORMAT` with these result fields:
- `constitution_file`: Path to constitution.md
- `version`: New version (semver)
- `version_type`: "major", "minor", or "patch"
- `principles_updated`: List of updated principles
- `templates_synchronized`: List of synced templates
- `sync_impact_report`: Path to report
- `breaking_changes`: Boolean
- `next_steps`: ["Review constitution changes", "Communicate to team"]
