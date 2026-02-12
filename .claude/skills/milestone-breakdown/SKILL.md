---
name: milestone-breakdown
description: Break down architecture into milestones and features with priorities, dependencies, and testable goals.
---

# Milestone Breakdown Skill

Transforms architecture documents into actionable milestones and features. Each milestone represents a workable component(s), and features align with the speckit-specify agent format.

## Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MILESTONE BREAKDOWN WORKFLOW                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [ ] 1. LOAD ARCHITECTURE       ← Read docs/ARCHITECTURE.md             │
│         ↓                                                               │
│  [ ] 2. IDENTIFY COMPONENTS     ← Extract modules, layers, features     │
│         ↓                                                               │
│  [ ] 3. DEFINE MILESTONES       ← Group into workable units             │
│         ↓                                                               │
│  [ ] 4. EXTRACT FEATURES        ← Break down each milestone             │
│         ↓                                                               │
│  [ ] 5. ANALYZE DEPENDENCIES    ← Map feature relationships             │
│         ↓                                                               │
│  [ ] 6. ASSIGN PRIORITIES       ← P1/P2/P3 based on dependencies        │
│         ↓                                                               │
│  [✓] GENERATE docs/MILESTONES.md                                        │
│  [✓] GENERATE docs/progress.md  ← Track spec/plan/tasks/implemented     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Load Architecture

**Purpose**: Load and parse the architecture document.

### Actions

1. Read `docs/ARCHITECTURE.md`
2. If not found, prompt user for architecture source
3. Extract:
   - System overview
   - Design principles
   - Top-level modules
   - Module structure
   - Key features

### Required Input

Either:
- Existing `docs/ARCHITECTURE.md`
- Architecture description provided inline
- Reference to `/architecture` skill output

---

## Phase 2: Identify Components

**Purpose**: Extract all buildable components from architecture.

### Actions

1. List all modules from architecture
2. Identify external dependencies
3. Map component relationships
4. Present component inventory for user confirmation

### Output Format

```markdown
## Component Inventory

| ID | Component | Type | Dependencies | Complexity |
|----|-----------|------|--------------|------------|
| C1 | [Name] | Module/Service/Library | [C2, External] | Low/Medium/High |
| C2 | [Name] | Module/Service/Library | [None] | Low/Medium/High |
```

### 🛑 Checkpoint: Component Inventory Acceptance

Present components to user. MUST receive explicit acceptance before proceeding.

---

## Phase 3: Define Milestones

**Purpose**: Group components into milestones - logical deliverable units.

### Milestone Criteria

A milestone MUST:
- Be independently deployable or demonstrable
- Have 2-5 testable goals
- Contain 2-7 features
- Result in working functionality when completed

### Actions

1. Group related components
2. Consider dependencies (dependent components in later milestones)
3. Define testable goals for each milestone
4. Order milestones by dependency chain
5. Present for user acceptance

### Questions to Ask (via AskUserQuestion)

- What is the MVP (Minimum Viable Product)?
- Which components are critical path?
- Are there external dependencies with timelines?
- Which features need early validation?

### Output Format

```markdown
## Milestone: M1 - [Milestone Name]

**Goal**: [Single sentence describing what this milestone achieves]

**Components**: C1, C2

**Testable Goals**:
1. [Specific, measurable goal - e.g., "API returns valid JSON responses"]
2. [Specific, measurable goal - e.g., "Unit test coverage > 80%"]
3. [Specific, measurable goal - e.g., "Can process 100 requests/second"]

**Exit Criteria**: [What must be true for milestone to be complete]

**Dependencies**: [None | M0 must be complete]
```

### 🛑 Checkpoint: Milestone Definition Acceptance

Present milestones to user. MUST receive explicit acceptance before proceeding.

---

## Phase 4: Extract Features

**Purpose**: Break down each milestone into features aligned with speckit-specify format.

### Feature Criteria

A feature MUST:
- Have a clear boundary (single responsibility)
- Be independently testable
- Be small enough to implement in one speckit workflow
- Have a clear definition (WHAT, not HOW)
- Not include implementation details

A feature SHOULD:
- Map to a single user story or capability
- Be completable independently (if no dependencies)
- Have acceptance criteria

### Actions

For each milestone:
1. Identify discrete capabilities
2. Ensure each feature has clear boundaries
3. Avoid over-specification (no implementation details)
4. Mark parallelizable features with `[P]`

### Output Format

```markdown
#### `001-feature-short-name` (P1) [P]

**Branch**: `001-feature-short-name`
**Short Name**: `feature-short-name`
**Milestone**: M1

**Definition**: [1-2 sentence description of WHAT this feature does]

**Acceptance Criteria**:
- [ ] [Testable criterion]
- [ ] [Testable criterion]

**Dependencies**: None | `000-other-feature`

**Speckit Command**:
```bash
speckit: [Definition sentence above]
```
```

### Feature Naming Convention

Following `speckit-specify` branch naming:

```
<NNN>-<short-name>
```

Where:
- `NNN`: 3-digit zero-padded feature number (001, 002, ...)
- `short-name`: 2-4 word action-noun format
  - Examples: `user-auth`, `oauth2-api-integration`, `data-export`
  - Preserve technical terms (OAuth2, API, JWT, etc.)

Feature numbers are sequential across the entire project (not per-milestone).

### 🛑 Checkpoint: Feature Extraction Acceptance (per milestone)

Present features for each milestone. MUST receive acceptance before next milestone.

---

## Phase 5: Analyze Dependencies

**Purpose**: Map relationships between features to identify execution order.

### Dependency Types

| Type | Symbol | Description |
|------|--------|-------------|
| Hard | `→` | Must complete before dependent |
| Soft | `⇢` | Recommended order, not required |
| None | `[P]` | Can run in parallel |

### Actions

1. Build dependency graph
2. Identify critical path
3. Mark parallel-safe features
4. Detect circular dependencies (ERROR if found)
5. Generate execution order

### Output Format

```markdown
## Dependency Graph

```
M1: Foundation
├── 001-user-auth [P] ────┐
├── 002-data-models [P] ──┤
│                         ├──→ 003-api-endpoints ──→ 004-validation
└── 005-config-setup [P] ─┘

M2: Core Features (depends on M1)
├── 006-feature-one ──→ 007-feature-two
│                           ↓
├── 008-parallel-feat [P] ⇢ 009-final-feat
```

### Critical Path

001-xxx → 003-xxx → 004-xxx → [M1 Complete] → 006-xxx → 007-xxx → [M2 Complete]

### Parallel Opportunities

- M1: `001-*`, `002-*`, `005-*` can run in parallel
- M2: `008-*` can run parallel with `006-*`→`007-*`
```

---

## Phase 6: Assign Priorities

**Purpose**: Assign P1/P2/P3 priorities based on dependencies and value.

### Priority Definitions

| Priority | Description | Criteria |
|----------|-------------|----------|
| P1 | Critical | On critical path, blocks others, core functionality |
| P2 | Important | Enhances functionality, soft dependencies only |
| P3 | Nice-to-have | Polish, optimization, non-essential |

### Actions

1. Mark critical path features as P1
2. Mark blocking features as P1
3. Evaluate remaining by user value
4. Assign P2/P3 based on:
   - User impact
   - Technical risk
   - Dependencies blocked

### Output: Priority Summary

```markdown
## Priority Summary

### P1 - Critical (must complete for milestone)
- `001-user-auth`: [Rationale]
- `003-api-endpoints`: [Rationale]

### P2 - Important (enhances milestone)
- `002-data-models`: [Rationale]
- `005-config-setup`: [Rationale]

### P3 - Nice-to-have (can defer)
- `004-validation`: [Rationale]
```

---

## Document Generation

After all phases complete, generate TWO documents:
1. `docs/MILESTONES.md` using `.specify/templates/milestone-template.md`
2. `docs/progress.md` using `.specify/templates/progress-template.md`

Key sections:

```markdown
# [Project Name] - Milestone Breakdown

**Generated**: [DATE]
**Source**: docs/ARCHITECTURE.md
**Total Milestones**: X
**Total Features**: Y
**Feature Number Range**: 001 - NNN

## Milestone Summary

| Milestone | Name | Features | Critical Path | Dependencies |
|-----------|------|----------|---------------|--------------|
| M1 | [Name] | X features | 001→003→004 | None |
| M2 | [Name] | X features | 006→007 | M1 |

---

## M1: [Milestone Name]

**Goal**: [What this milestone achieves]

**Testable Goals**:
1. [Goal 1]
2. [Goal 2]
3. [Goal 3]

**Exit Criteria**: [Completion definition]

### Features

#### `001-user-auth` (P1) [P]

**Branch**: `001-user-auth`
**Short Name**: `user-auth`

**Definition**: [What this feature does]

**Acceptance Criteria**:
- [ ] [Criterion 1]
- [ ] [Criterion 2]

**Dependencies**: None

**Speckit Command**:
```bash
speckit: [Definition sentence]
```

---

#### `002-data-models` (P2) [P]

**Branch**: `002-data-models`
**Short Name**: `data-models`

**Definition**: [What this feature does]

**Acceptance Criteria**:
- [ ] [Criterion 1]

**Dependencies**: None

**Speckit Command**:
```bash
speckit: [Definition sentence]
```

---

[Continue for all features...]

### M1 Dependency Graph

```
001-user-auth [P] ────┐
002-data-models [P] ──┼──→ 003-api-endpoints ──→ 004-validation
005-config-setup [P] ─┘
```

### M1 Execution Order

1. **Parallel**: `001-*`, `002-*`, `005-*`
2. **Sequential**: `003-*` (after parallel completes)
3. **Sequential**: `004-*` (after 003)

---

## Feature Index

| # | Branch Name | Short Name | Milestone | Priority | Parallel | Dependencies | Status |
|---|-------------|------------|-----------|----------|----------|--------------|--------|
| 001 | `001-user-auth` | user-auth | M1 | P1 | Yes | None | Pending |
| 002 | `002-data-models` | data-models | M1 | P2 | Yes | None | Pending |
| 003 | `003-api-endpoints` | api-endpoints | M1 | P1 | No | 001, 002, 005 | Pending |

---

## Next Steps

### Suggested Execution Commands

```bash
# Start with first P1 feature (creates branch 001-user-auth)
speckit: Allow users to register and authenticate with email/password

# Run parallel features
speckit: Define core data models for user and content entities
```
```

---

## Interactive Behavior

### Using AskUserQuestion

MUST use AskUserQuestion for:

1. **Milestone scope** - When grouping is ambiguous
2. **Priority conflicts** - When multiple features seem P1
3. **Dependency decisions** - When order is unclear
4. **Feature boundaries** - When scope needs clarification

Example:
```
AskUserQuestion:
  question: "How should we group these components into milestones?"
  header: "Milestone Scope"
  options:
    - label: "MVP First"
      description: "Minimal user-facing features in M1, infrastructure in M2"
    - label: "Foundation First"
      description: "All infrastructure in M1, features in M2+"
    - label: "Vertical Slices"
      description: "Complete feature paths in each milestone"
```

---

## Usage Examples

```bash
# From existing architecture
milestone-breakdown: Break down docs/ARCHITECTURE.md

# With inline guidance
milestones: Focus on getting auth working first

# Specific scope
breakdown: Only backend services for now

# Resume previous session
milestone-breakdown resume
```

---

## Triggers

| Trigger | Action |
|---------|--------|
| `milestone-breakdown:` | Full breakdown workflow |
| `milestones:` | Alias for milestone-breakdown |
| `breakdown:` | Alias for milestone-breakdown |
| `features:` | Skip to feature extraction (requires milestones) |

---

## Integration with Speckit

Features generated by this skill are designed for direct use with `speckit-specify`:

```bash
# Take a feature definition from MILESTONES.md and run speckit
# The definition becomes the input to speckit-specify
speckit: Allow users to register and authenticate with email/password

# speckit-specify will:
# 1. Generate short-name from definition (e.g., "user-auth")
# 2. Find next available number (e.g., 001)
# 3. Create branch: 001-user-auth
# 4. Generate detailed spec.md with user stories, requirements, success criteria
```

### Feature → Spec Mapping

| MILESTONES.md | speckit-specify |
|---------------|-----------------|
| Branch Name | Branch created by specify |
| Short Name | Generated from definition |
| Feature Definition | User Scenarios description |
| Acceptance Criteria | Success Criteria |
| Dependencies | Technical Context |
| Priority | Story priority (P1/P2/P3) |

### Workflow

1. Run `milestone-breakdown:` to generate `docs/MILESTONES.md`
2. Copy feature **Definition** from milestone doc
3. Run `speckit: [definition]` to create detailed spec
4. Feature number auto-assigned by speckit-specify

---

## Constraints

**MUST**:
- Complete checklist phases in order
- Get user acceptance at each checkpoint
- Use AskUserQuestion for ambiguous groupings
- Keep features at definition level (no implementation details)
- Mark parallel features with `[P]`
- Generate comprehensive docs/MILESTONES.md at the end
- Generate docs/progress.md for tracking spec/plan/tasks/implemented status
- Ensure all milestones completed = project complete

**MUST NOT**:
- Skip any checklist phase
- Proceed without user acceptance
- Include implementation details in features
- Create features too large for single speckit workflow
- Generate document before all phases complete
- Create circular dependencies

---

## Output Artifacts

### 1. Milestones Document

**Location**: `docs/MILESTONES.md`

The final document should be:
- Self-contained and readable
- Actionable with clear feature definitions
- Ready for speckit-specify consumption
- Include execution order recommendations
- Have clear dependency visualization

### 2. Progress Tracker

**Location**: `docs/progress.md`

A living document to track project progress. Generated using `.specify/templates/progress-template.md`.

**Purpose**: Track the status of each feature across the development lifecycle.

**Status Columns**:

| Column | Description | How to Determine |
|--------|-------------|------------------|
| Spec | Feature specification | Check if `specs/<NNN-feature>/spec.md` exists |
| Plan | Implementation plan | Check if `specs/<NNN-feature>/plan.md` exists |
| Tasks | Task breakdown | Check if `specs/<NNN-feature>/tasks.md` exists |
| Implemented | Code implementation | Check if feature branch merged or code exists |

**Status Values**:

| Icon | Meaning |
|------|---------|
| :white_check_mark: Complete | Artifact exists and is complete |
| :construction: In Progress | Work has started |
| :x: Not started | Work has not begun |
| :warning: Blocked | Blocked by dependency |

**Initial Generation**:

When first generated, all features start with:
- Spec: :x: Not started
- Plan: :x: Not started
- Tasks: :x: Not started
- Implemented: :x: Not started

**progress.md Format**:

```markdown
# [Project Name] - Progress Tracker

**Last Updated**: [DATE]

## Project Overview

| Metric | Value |
|--------|-------|
| Total Milestones | X |
| Total Features | Y |
| Features Completed | 0 |
| Overall Progress | 0% |

## Feature Status

| # | Feature | Spec | Plan | Tasks | Implemented |
|---|---------|------|------|-------|-------------|
| 001 | Cloud Storage Import | :white_check_mark: Complete | :x: Not started | :x: Not started | :x: Not started |
| 002 | Feature Two | :x: Not started | :x: Not started | :x: Not started | :x: Not started |

## M1: [Milestone Name]

**Status**: Not Started
**Progress**: 0/X features complete

| # | Feature | Spec | Plan | Tasks | Implemented |
|---|---------|------|------|-------|-------------|
| 001 | Feature One | :white_check_mark: Complete | :x: Not started | :x: Not started | :x: Not started |
```

**Updating progress.md**:

The progress.md should be updated:
1. After running `speckit-specify` (Spec column)
2. After running `speckit-plan` (Plan column)
3. After running `speckit-tasks` (Tasks column)
4. After feature implementation is complete (Implemented column)

This can be done manually or via automation that checks for file existence.

---

*Milestone Breakdown Skill - Transform architecture into actionable milestones and features through guided decomposition*
