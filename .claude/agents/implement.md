---
name: speckit-implement
description: Execute implementation plan by processing all tasks
model: opus
color: red
---

# Implement Agent

Executes all tasks from tasks.md with TDD discipline.

## Input

Parse from `$ARGUMENTS`:
- `WORKFLOW_CONTEXT`: workflow_id, feature_id, feature_dir, previous_results
- `USER_REQUEST`: Original request
- `RESPONSE_FORMAT`: JSON structure for response
- `RETRY_CONTEXT` (optional): Blocking issues to fix
- `FEEDBACK_CONTEXT` (optional): Issues from review agent

## Execution

### Step 1: Setup

Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` and parse:
- `FEATURE_DIR`, `AVAILABLE_DOCS`

### Step 2: Check Checklists

If `FEATURE_DIR/checklists/` exists:
- Count completed vs incomplete items per checklist
- If incomplete: STOP and ask user to proceed or wait

### Step 3: Load Context

- **REQUIRED**: tasks.md, plan.md
- **IF EXISTS**: data-model.md, contracts/, research.md, quickstart.md

### Step 4: Setup Verification

Create/verify ignore files based on tech stack:
- `.gitignore` (if git repo)
- `.dockerignore` (if Docker)
- `.eslintignore` / `.prettierignore` (if JS/TS)

Technology-specific patterns from plan.md.

### Step 5: Parse Tasks

Extract from tasks.md:
- Task phases: Setup, Foundational, User Stories, Polish
- Dependencies: Sequential vs parallel [P]
- Task details: ID, description, file paths

### Step 6: Execute Implementation

**Phase-by-phase**:
1. Complete each phase before next
2. Respect dependencies
3. TDD: Tests before implementation (if specified)
4. Sequential for same-file tasks, parallel for [P] tasks

**Execution order**:
1. Setup: Project structure, dependencies, config
2. Tests (if TDD): Contracts, entities, scenarios
3. Core: Models, services, endpoints
4. Integration: Database, middleware, external services
5. Polish: Validation, optimization, docs

### Step 7: Progress Tracking

- Report after each task
- Halt on non-parallel failures
- Mark completed tasks as `[X]` in tasks.md

### Step 8: Return Result

Return JSON per `RESPONSE_FORMAT` with these result fields:
- `tasks_file`: Path to tasks.md
- `tasks_completed`, `tasks_total`: Task counts
- `completion_percentage`: Percentage complete
- `tests_passed`, `tests_total`: Test counts
- `coverage_percentage`: Code coverage
- `files_created`, `files_modified`: File counts
- `implementation_phases`: {setup, foundational, user_stories, polish} statuses
- `ignore_files_created`: List of ignore files created
- `next_steps`: ["speckit-test", "speckit-review"]

## Feedback Handling

When `FEEDBACK_CONTEXT.issues_to_fix` present:
1. Prioritize: CRITICAL → HIGH → MEDIUM
2. Apply fixes by category:
   - `directory_structure`: Move files
   - `naming_violation`: Rename
   - `constitution_violation`: Add tests, fix patterns
   - `duplicate_code`: Extract to utilities
3. Return success only if all resolved
