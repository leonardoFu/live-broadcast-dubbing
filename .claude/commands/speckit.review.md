---
description: Post-implementation review and cleanup agent - validates constitution compliance, refactors code, fixes directory structure, removes redundant tests/code
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The input may include:
- `story_scope`: Limit review to files modified for a specific story (e.g., "US1", "US2")
- Other constraints or focus areas

## Goal

Post-implementation cleanup: validate constitution compliance, fix directory structure, remove redundant code, and ensure codebase quality.

**Mode: ACTIVE CLEANUP** - This command WILL modify the codebase.

## Execution Steps

### Phase 1: Analysis (Read-Only)

1. **Get feature scope** by running `.specify/scripts/bash/check-prerequisites.sh --json --paths-only` from repo root and parse JSON for:
   - `FEATURE_DIR`: Feature directory path
   - `FEATURE_SPEC`: Path to spec.md
   - `TASKS`: Path to tasks.md

   Output file: `review.md` in FEATURE_DIR.

   For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

2. **Read context files**:
   - `FEATURE_DIR/spec.md` - Feature specification
   - `FEATURE_DIR/tasks.md` - Task list (for story scope filtering)
   - `FEATURE_DIR/plan.md` - Implementation plan

3. **Load rules**:
   - `.specify/memory/constitution.md` - Project principles
   - `CLAUDE.md` - Project-specific AI guidance (if exists)

4. **Scan files** based on scope:
   - **If `story_scope` provided**: Only scan files mentioned in `[<story_scope>]` tasks in tasks.md
   - **If no scope**: Scan `apps/**/*.py`, `libs/**/*.py`, `tests/**/*.py` (adjust patterns based on project type)

### Phase 2: Directory Cleanup (Active)

**Expected Structure** (Python monorepo example - adapt based on project):
```
apps/<service>/src/<package>/     → Implementation
apps/<service>/tests/unit/        → Unit tests
apps/<service>/tests/integration/ → Integration tests
libs/<lib>/src/dubbing_<lib>/     → Libraries (with prefix if required)
tests/e2e/                        → E2E tests
```

**Actions**:
- `git mv` misplaced files to correct locations
- Create missing `__init__.py` files (Python) or index files (JS/TS)
- Rename files violating naming conventions (e.g., snake_case for Python, camelCase for JS)

### Phase 3: Test Cleanup (Active)

- **Find duplicates**: Search for `def test_` (Python) or `it(` / `test(` (JS/TS) across test directories
- **Delete duplicate tests**: Remove exact or near-duplicate test functions
- **Consolidate similar tests**: Merge into parametrized versions where appropriate
- **Remove out-of-scope tests**: Delete tests unrelated to feature scope

### Phase 4: Code Cleanup (Active)

- **Run linters with auto-fix** (adapt to project):
  - Python: `ruff check --fix --select F401,F841 apps/ libs/` for unused imports/vars
  - JavaScript/TypeScript: `eslint --fix` or equivalent
- **Extract duplicates**: Move duplicate utility functions to shared location (e.g., `libs/common/`)
- **Delete deprecated files**: Remove unrelated or deprecated code

### Phase 5: Validation (Read-Only)

- Re-scan to verify structure is correct
- Check constitution compliance for all modified files
- Run test suite: `make test` or equivalent (adapt to project)
- Verify nothing broke

### Phase 6: Completion Report

Save the following report to `FEATURE_DIR/review.md`:

```markdown
## Review & Cleanup Report

### Overall Status
[APPROVED | APPROVED_WITH_WARNINGS | NEEDS_MANUAL_REVIEW]

### Changes Made

| Category | Count | Details |
|----------|-------|---------|
| Files moved | N | [list] |
| Files deleted | N | [list] |
| Files created | N | [list] |
| Files modified | N | [list] |

### Constitution Compliance

| Check | Status | Notes |
|-------|--------|-------|
| [principle] | ✓ PASS / ✗ FAIL | [details] |

### Cleanup Summary

- Tests removed: N
- Files moved: N
- Dead code lines removed: N
- Duplicate functions consolidated: N

### Blocking Issues (if any)
[List issues requiring manual intervention]

### Feedback & Action Items

Items requiring attention (check when resolved):

- [ ] [CATEGORY] Description of issue - `path/to/file.py:line`
- [ ] [CATEGORY] Description of issue - `path/to/file.py:line`

Categories: `[CODE]`, `[TEST]`, `[STRUCTURE]`, `[CONSTITUTION]`, `[PERFORMANCE]`, `[SECURITY]`

### Suggested Next Steps
[Recommendations for follow-up actions]
```

After saving `review.md`, report the absolute path to the saved file.

## Safety Rules

**SAFE TO DELETE** (no confirmation needed):
- Exact duplicates of existing files
- Empty files (0 bytes)
- Deprecated code marked for removal
- Unused imports and variables
- Tests for out-of-scope features (when scope is defined)
- `.pyc`, `__pycache__`, `.DS_Store`, etc.

**ASK BEFORE DELETING**:
- Files >100 lines of code
- Files with cross-feature references
- Configuration files
- Any file not clearly redundant

**NEVER DELETE**:
- `specs/*` - Specification files
- `.specify/memory/constitution.md` - Constitution
- `CLAUDE.md` - AI guidance
- `.git/*` - Git history
- CI/CD configuration (`.github/`, `.gitlab-ci.yml`, etc.)
- License files
- README files at project root

## Error Handling

If issues require code changes beyond cleanup:
- Set status to `NEEDS_MANUAL_REVIEW`
- List `blocking_issues` with descriptions
- Suggest running `/speckit.implement` with specific feedback
- Do not attempt to fix implementation bugs (only cleanup)

## Operating Rules

- **Scope awareness**: Respect `story_scope` if provided; don't touch unrelated code
- **Git-aware operations**: Use `git mv` for moves to preserve history
- **Incremental progress**: Report progress after each phase
- **Fail-safe**: Stop and report if uncertain about any deletion
- **Constitution is non-negotiable**: Any violation is a blocking issue
