# [PROJECT_NAME] - Milestone Breakdown

**Generated**: [DATE]
**Source**: [ARCHITECTURE_SOURCE]
**Total Milestones**: [MILESTONE_COUNT]
**Total Features**: [FEATURE_COUNT]
**Feature Number Range**: [START_NUMBER] - [END_NUMBER]

## Overview

[Brief description of the project and milestone strategy]

## Milestone Summary

| Milestone | Name | Features | Critical Path | Dependencies |
|-----------|------|----------|---------------|--------------|
| M1 | [Name] | X features | [Path] | None |
| M2 | [Name] | X features | [Path] | M1 |

---

## M1: [Milestone Name]

**Goal**: [Single sentence describing what this milestone achieves]

**Components**: [List of architecture components included]

**Testable Goals**:
1. [Specific, measurable goal]
2. [Specific, measurable goal]
3. [Specific, measurable goal]

**Exit Criteria**: [What must be true for milestone completion]

**Dependencies**: None | [Previous milestones]

### Features

---

#### `001-feature-short-name` (P1) [P]

**Branch**: `001-feature-short-name`
**Short Name**: `feature-short-name`

**Definition**: [1-2 sentence description of WHAT this feature does - no implementation details]

**Acceptance Criteria**:
- [ ] [Testable criterion]
- [ ] [Testable criterion]

**Dependencies**: None

**Speckit Command**:
```bash
speckit: [Definition sentence above]
```

---

#### `002-another-feature` (P2)

**Branch**: `002-another-feature`
**Short Name**: `another-feature`

**Definition**: [1-2 sentence description]

**Acceptance Criteria**:
- [ ] [Testable criterion]

**Dependencies**: `001-feature-short-name`

**Speckit Command**:
```bash
speckit: [Definition sentence above]
```

---

### M1 Dependency Graph

```
001-feature-short-name [P] ────┐
                               ├──→ 003-dependent-feature ──→ 004-final-feature
002-another-feature [P] ───────┘
```

### M1 Execution Order

1. **Parallel**: `001-feature-short-name`, `002-another-feature` (no dependencies)
2. **Sequential**: `003-dependent-feature` (after parallel completes)
3. **Sequential**: `004-final-feature` (after 003)

---

## M2: [Milestone Name]

**Goal**: [What this milestone achieves]

**Components**: [Architecture components]

**Testable Goals**:
1. [Goal]
2. [Goal]

**Exit Criteria**: [Completion definition]

**Dependencies**: M1

### Features

---

#### `005-m2-first-feature` (P1)

**Branch**: `005-m2-first-feature`
**Short Name**: `m2-first-feature`

**Definition**: [Description]

**Acceptance Criteria**:
- [ ] [Criterion]

**Dependencies**: M1 complete

**Speckit Command**:
```bash
speckit: [Definition sentence above]
```

---

[Continue pattern for remaining features and milestones...]

---

## Complete Dependency Graph

```
MILESTONE 1: Foundation
┌─────────────────────────────────────────────────────────┐
│  001-feature-short-name [P] ────┐                       │
│                                 ├──→ 003-xxx ──→ 004-xxx│
│  002-another-feature [P] ───────┘                       │
└─────────────────────────────┬───────────────────────────┘
                              │
                              ▼
MILESTONE 2: Core Features
┌─────────────────────────────────────────────────────────┐
│  005-m2-first-feature ──→ 006-m2-second-feature         │
│                               ↓                         │
│  007-parallel-feature [P]  ⇢ 008-final-feature          │
└─────────────────────────────────────────────────────────┘
```

## Critical Path

The minimum set of features required for project completion:

```
001-xxx → 003-xxx → 004-xxx → [M1 Complete] → 005-xxx → 006-xxx → [M2 Complete]
```

## Parallel Opportunities

Features that can be developed simultaneously:

| Group | Features | Milestone | Parallelism |
|-------|----------|-----------|-------------|
| A | `001-*`, `002-*` | M1 | 2 developers |
| B | `007-*` with `005-*`→`006-*` | M2 | 2 developers |

---

## Feature Index

Complete reference of all features:

| # | Branch Name | Short Name | Milestone | Priority | Parallel | Dependencies | Status |
|---|-------------|------------|-----------|----------|----------|--------------|--------|
| 001 | `001-feature-short-name` | feature-short-name | M1 | P1 | Yes | None | Pending |
| 002 | `002-another-feature` | another-feature | M1 | P2 | Yes | None | Pending |
| 003 | `003-dependent-feature` | dependent-feature | M1 | P1 | No | 001, 002 | Pending |
| 004 | `004-final-feature` | final-feature | M1 | P2 | No | 003 | Pending |
| 005 | `005-m2-first-feature` | m2-first-feature | M2 | P1 | No | M1 | Pending |
| 006 | `006-m2-second-feature` | m2-second-feature | M2 | P1 | No | 005 | Pending |
| 007 | `007-parallel-feature` | parallel-feature | M2 | P2 | Yes | M1 | Pending |
| 008 | `008-final-feature` | final-feature | M2 | P3 | No | 006, 007 | Pending |

---

## Priority Summary

### P1 - Critical (blocks milestone completion)

| Feature | Milestone | Rationale |
|---------|-----------|-----------|
| `001-feature-short-name` | M1 | [Why critical] |
| `003-dependent-feature` | M1 | [Why critical] |
| `005-m2-first-feature` | M2 | [Why critical] |
| `006-m2-second-feature` | M2 | [Why critical] |

### P2 - Important (enhances milestone)

| Feature | Milestone | Rationale |
|---------|-----------|-----------|
| `002-another-feature` | M1 | [Why important] |
| `004-final-feature` | M1 | [Why important] |
| `007-parallel-feature` | M2 | [Why important] |

### P3 - Nice-to-have (can defer)

| Feature | Milestone | Rationale |
|---------|-----------|-----------|
| `008-final-feature` | M2 | [Why deferrable] |

---

## Next Steps

After milestone breakdown is approved:

1. **Start with M1 P1 features** - These are on critical path
2. **Use speckit-specify** to create detailed specs for each feature
3. **Run parallel features concurrently** where marked with [P]
4. **Complete all M1 features** before starting M2

### Suggested Execution Commands

```bash
# Create detailed spec for first P1 feature (will create branch 001-feature-short-name)
speckit: [Definition of feature 001]

# Start parallel feature development (will create branch 002-another-feature)
speckit: [Definition of feature 002]

# After 001 and 002 complete (will create branch 003-dependent-feature)
speckit: [Definition of feature 003]
```

### Feature Numbering

The milestone breakdown pre-assigns feature numbers to maintain order:
- Feature numbers are sequential across the entire project
- When running `speckit:`, the agent will auto-detect the next available number
- If implementing in order, numbers will match this plan
- Numbers may differ if features are implemented out of order (this is OK)

### Progress Tracking

Update the Feature Index status as features are completed:
- `Pending` → `In Progress` → `Completed`

When all features in a milestone show `Completed`, the milestone is done.

---

## Appendix: Milestone Completion Checklist

### M1 Completion

- [ ] All P1 features completed
- [ ] All P2 features completed (or explicitly deferred)
- [ ] All testable goals verified
- [ ] Exit criteria met

### M2 Completion

- [ ] M1 dependency satisfied
- [ ] All P1 features completed
- [ ] All P2 features completed (or explicitly deferred)
- [ ] All testable goals verified
- [ ] Exit criteria met

---

## Appendix: Branch Name Convention

Following the `speckit-specify` naming convention:

```
<NNN>-<short-name>
```

Where:
- `NNN`: 3-digit zero-padded feature number (001, 002, ...)
- `short-name`: 2-4 word action-noun format
  - Examples: `user-auth`, `oauth2-api-integration`, `data-export`
  - Preserve technical terms (OAuth2, API, JWT, etc.)

### Examples

| Definition | Short Name | Branch |
|------------|------------|--------|
| User authentication and registration | `user-auth` | `001-user-auth` |
| OAuth2 API integration for third-party login | `oauth2-api-integration` | `002-oauth2-api-integration` |
| Export data to CSV and JSON formats | `data-export` | `003-data-export` |
| Real-time notification system | `realtime-notifications` | `004-realtime-notifications` |

---

*Generated by milestone-breakdown skill*
