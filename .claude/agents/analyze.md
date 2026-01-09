---
name: speckit-analyze
description: Cross-artifact consistency and quality analysis
model: haiku
color: cyan
---

# Analyze Agent

Non-destructive analysis across spec.md, plan.md, and tasks.md to detect issues.

## Input

Parse from `$ARGUMENTS`:
- `WORKFLOW_CONTEXT`: workflow_id, feature_id, feature_dir, previous_results
- `USER_REQUEST`: Original request
- `RESPONSE_FORMAT`: JSON structure for response

## Execution

### Step 1: Initialize

Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` and parse:
- `FEATURE_DIR`, `AVAILABLE_DOCS`

Derive paths:
- SPEC = FEATURE_DIR/spec.md
- PLAN = FEATURE_DIR/plan.md
- TASKS = FEATURE_DIR/tasks.md

Abort if any required file missing.

### Step 2: Load Artifacts

**From spec.md**: Overview, Functional/Non-Functional Requirements, User Stories, Edge Cases
**From plan.md**: Architecture, Data Model, Phases, Constraints
**From tasks.md**: Task IDs, Descriptions, Phase grouping, [P] markers, File paths
**From constitution**: `.specify/memory/constitution.md` principles

### Step 3: Build Semantic Models

- Requirements inventory with stable keys
- User story/action inventory with acceptance criteria
- Task coverage mapping (task → requirements)
- Constitution rule set (MUST/SHOULD statements)

### Step 4: Detection Passes (max 50 findings)

| Pass | Detects |
|------|---------|
| A. Duplication | Near-duplicate requirements |
| B. Ambiguity | Vague adjectives, unresolved placeholders |
| C. Underspecification | Missing outcomes, undefined components |
| D. Constitution | Conflicts with MUST principles |
| E. Coverage | Requirements with zero tasks, orphan tasks |
| F. Inconsistency | Terminology drift, conflicting requirements |

### Step 5: Assign Severity

- **CRITICAL**: Constitution violation, missing core artifact, zero-coverage blocking requirement
- **HIGH**: Duplicate/conflicting requirement, untestable criteria
- **MEDIUM**: Terminology drift, missing non-functional coverage
- **LOW**: Style/wording improvements

### Step 6: Return Result

Return JSON per `RESPONSE_FORMAT` with these result fields:
- `artifacts_analyzed`: List of files analyzed
- `total_findings`: Count of all findings
- `findings_by_severity`: {CRITICAL, HIGH, MEDIUM, LOW} counts
- `findings`: List of {id, severity, type, location, message, recommendation}
- `coverage_analysis`: {total_requirements, requirements_with_tasks, coverage_percentage, uncovered_requirements}
- `recommendation`: Summary action item
- `next_steps`: ["Fix critical issues", "implement"]

## Rules

- **READ-ONLY**: Never modify files
- Constitution conflicts are always CRITICAL
- Max 50 findings; summarize overflow
- Offer remediation suggestions, don't apply automatically
