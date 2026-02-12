---
description: Capture learnings and patterns from implemented features into CLAUDE.md and optionally propose constitution amendments
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The input may include:
- `feature_id`: Specific feature to reflect on (e.g., "006-text-processing")
- `scope`: Limit to certain categories (`patterns`, `principles`, `all`)
- `dry_run`: If true, show proposed changes without writing

## Goal

After a feature is implemented, extract learnings and insights to improve future development. This command:
1. **CLAUDE.md**: Automatically appends operational patterns, workarounds, and implementation tips
2. **constitution.md**: Proposes principle amendments for user approval (never auto-updates)

## Understanding the Two Files

### CLAUDE.md (Operational Knowledge)
Location: Project root `CLAUDE.md`

**Purpose**: AI-agent specific guidance for working with this codebase
**Content Types**:
- Implementation patterns discovered during development
- Library/framework quirks and workarounds
- Project-specific conventions not captured elsewhere
- Performance tips and optimization notes
- Common pitfalls and how to avoid them

**Update Policy**: Freely append learnings after each feature (with deduplication)

### constitution.md (Project Governance)
Location: `.specify/memory/constitution.md`

**Purpose**: Non-negotiable project principles and architectural constraints
**Content Types**:
- Core principles (Specification First, Simplicity Over Cleverness, etc.)
- Quality gates and compliance requirements
- Dependency constraints and technology stack decisions
- Governance and amendment procedures

**Update Policy**: NEVER auto-update. Require explicit user approval with:
- Semantic version bump
- Sync Impact Report
- Template propagation check

## Execution Steps

### Phase 1: Gather Context

1. **Get feature scope** by running `.specify/scripts/bash/check-prerequisites.sh --json --paths-only` from repo root
   - Parse JSON for `FEATURE_DIR`, `FEATURE_SPEC`, etc.
   - If feature_id provided in args, use that to locate `specs/<feature_id>/`

2. **Read feature artifacts**:
   - `FEATURE_DIR/spec.md` - Requirements and user stories
   - `FEATURE_DIR/plan.md` - Design decisions and trade-offs
   - `FEATURE_DIR/tasks.md` - Implementation breakdown
   - `FEATURE_DIR/review.md` - Post-implementation feedback (if exists)
   - `FEATURE_DIR/research.md` - Technical research (if exists)

3. **Read current knowledge files**:
   - `CLAUDE.md` (create if not exists)
   - `.specify/memory/constitution.md`

4. **Scan implementation** to understand what was built:
   - List files created/modified for this feature
   - Identify patterns used in the implementation

### Phase 2: Extract Learnings

Analyze the feature artifacts to identify:

#### For CLAUDE.md (Operational Patterns)
Look for these in plan.md, review.md, and implementation:

| Category | What to Capture | Example |
|----------|-----------------|---------|
| `[PATTERN]` | Reusable code patterns discovered | "Use repository pattern for data access in this project" |
| `[WORKAROUND]` | Library issues and fixes | "vitest mock requires `vi.mock()` at top of file" |
| `[CONVENTION]` | Project-specific conventions | "All API responses use `{ data, error, meta }` shape" |
| `[PERFORMANCE]` | Optimization insights | "Batch Redis calls - single pipeline for <50 ops" |
| `[GOTCHA]` | Common mistakes to avoid | "Don't use `any` type - breaks downstream validation" |
| `[DECISION]` | Architectural choices and rationale | "Chose Zod over Yup for runtime validation - better TS inference" |

#### For constitution.md (Principle Amendments)
Look for these signals that suggest principle changes:

| Signal | Potential Amendment |
|--------|---------------------|
| Plan.md shows repeated principle violations with justification | Principle may be too restrictive |
| New pattern emerged that should be mandatory | New principle candidate |
| Existing principle caused friction without benefit | Principle needs refinement |
| Technology stack changed significantly | Architecture Guidelines update |
| Quality gate consistently skipped for good reason | Quality Standards adjustment |

### Phase 3: Deduplication Check (CRITICAL)

**Before adding ANY learning to CLAUDE.md, you MUST perform deduplication.**

#### Step 3.1: Parse Existing CLAUDE.md

Read the entire `CLAUDE.md` file and extract all existing learnings into a structured list:

```typescript
interface ExistingLearning {
  category: string;        // PATTERN, WORKAROUND, GOTCHA, etc.
  summary: string;         // First line/title of the learning
  details: string;         // Full content
  feature_source?: string; // Which feature added it (if tracked)
  line_number: number;     // For reference
}
```

#### Step 3.2: Compare Each New Learning

For each potential new learning, check against existing entries:

| Check | Method | Action if Match |
|-------|--------|-----------------|
| **Exact match** | Summary text is identical (case-insensitive) | SKIP - do not add |
| **Semantic match** | Same concept, different wording (use judgment) | SKIP - optionally note "already covered by line X" |
| **Partial overlap** | Related but adds new information | MERGE - update existing entry OR add as refinement |
| **Conflict** | Contradicts existing learning | FLAG - output warning for user review |
| **No match** | Truly new information | ADD - include in update |

#### Step 3.3: Deduplication Report

Before writing, output a deduplication report:

```markdown
### Deduplication Analysis

| Proposed Learning | Status | Reason |
|-------------------|--------|--------|
| [PATTERN] Use repository pattern | SKIP | Already exists at line 45 |
| [WORKAROUND] Vitest mock hoisting | ADD | New learning |
| [GOTCHA] Avoid any type | MERGE | Extends existing entry at line 78 |
| [DECISION] Zod vs Yup | CONFLICT | Contradicts line 92 - needs review |

**Summary**: 1 new, 1 merged, 1 skipped, 1 conflict
```

#### Step 3.4: User Confirmation for Conflicts

If any conflicts detected:
1. Output the conflict details
2. Ask user which version to keep
3. Do NOT auto-resolve conflicts

### Phase 4: Update CLAUDE.md (With Deduplication Applied)

1. **Only proceed with ADD and MERGE items** from Phase 3

2. **For ADD items**, append under appropriate section:

```markdown
## Learnings from <feature-id>

### Patterns Discovered

- [PATTERN] <description>
  - Context: <when to use>
  - Example: <code snippet or reference>

### Workarounds & Gotchas

- [WORKAROUND] <issue description>
  - Solution: <how to fix>
  - Reference: <file:line if applicable>

- [GOTCHA] <mistake description>
  - Prevention: <how to avoid>

### Decisions Made

- [DECISION] <what was decided>
  - Rationale: <why>
  - Trade-offs: <what we gave up>
```

3. **For MERGE items**, update the existing entry in-place:
   - Add new context or examples
   - Note the additional feature source
   - Keep the entry coherent (don't just append)

4. **Write updated CLAUDE.md**

### Phase 5: Propose Constitution Amendments (If Applicable)

**IMPORTANT**: This phase only PROPOSES changes. It does NOT modify constitution.md.

1. **Analyze for amendment candidates**:
   - Check plan.md "Constitution Check" section for violations with justifications
   - Check if new mandatory patterns emerged
   - Check if existing principles blocked legitimate work

2. **If amendments identified**, output proposal:

```markdown
## Proposed Constitution Amendments

Based on the implementation of <feature-id>, the following amendments may be warranted:

### Amendment 1: <Title>

**Current Principle**:
> <quote from current constitution>

**Proposed Change**:
> <proposed new text>

**Rationale**:
<why this change improves the project>

**Impact Assessment**:
- Templates affected: <list>
- Existing features affected: <list>
- Version bump: MAJOR/MINOR/PATCH

---

To apply these amendments, run:
`/speckit.constitution <paste amendment details>`
```

3. **If no amendments needed**, state:
```
No constitution amendments identified. All principles applied cleanly.
```

### Phase 6: Output Summary

```markdown
## Reflection Complete: <feature-id>

### CLAUDE.md Updates
- Added: N new learnings
- Merged: N existing entries updated
- Skipped: N duplicates avoided
- Conflicts: N (requiring user review)

### Deduplication Stats
- Existing entries scanned: X
- New learnings proposed: Y
- Final entries added: Z

### Constitution Status
- Amendments proposed: Y/N
- Action required: <describe if user needs to review amendments>

### Files Modified
- `CLAUDE.md` - Updated with new learnings (if any non-duplicates)

### Recommended Follow-up
- [ ] Review proposed constitution amendments (if any)
- [ ] Resolve any flagged conflicts
- [ ] Share learnings with team
```

## CLAUDE.md Template (Create If Missing)

If `CLAUDE.md` doesn't exist, create it with:

```markdown
# CLAUDE.md - AI Development Guide

This file contains operational knowledge for AI agents working on this project.
Updated automatically by `/speckit.reflect` after feature implementations.

## Project Context

<!-- Brief project description - fill from README or constitution -->

## Implementation Patterns

<!-- Patterns discovered during development -->

## Workarounds & Gotchas

<!-- Library issues, common mistakes, etc. -->

## Decisions Log

<!-- Architectural decisions and their rationale -->

---

*Last updated: <date> (Feature: <feature-id>)*
```

## Operating Rules

### MUST
- **ALWAYS perform deduplication check before adding any learning**
- Read entire existing CLAUDE.md before appending
- Include feature-id reference for traceability
- Keep learnings concise and actionable
- Propose constitution changes, never auto-apply
- Output deduplication report before writing

### MUST NOT
- Modify `.specify/memory/constitution.md` directly
- Add duplicate or near-duplicate learnings
- Auto-resolve conflicts (always ask user)
- Add vague or non-actionable learnings
- Skip the deduplication phase

### Deduplication Decision Matrix

| Existing Entry | New Learning | Similarity | Action |
|----------------|--------------|------------|--------|
| "Use Zod for validation" | "Use Zod for schema validation" | >90% | SKIP |
| "Vitest needs mock hoisting" | "vi.mock must be at file top" | ~70% | SKIP (same concept) |
| "Repository pattern for data" | "Repository pattern with caching" | ~50% | MERGE (adds detail) |
| "Use async/await" | "Avoid callback patterns" | <30% | ADD (different focus) |
| "Use Yup for validation" | "Use Zod for validation" | CONFLICT | FLAG for user |

## Error Handling

| Situation | Action |
|-----------|--------|
| Feature artifacts missing | Report which files missing, proceed with available |
| CLAUDE.md doesn't exist | Create from template |
| No learnings identified | Output "No new learnings from this feature" |
| All learnings are duplicates | Output "All learnings already captured - no updates needed" |
| Constitution violation found but justified | Propose amendment |
| Conflict detected | Stop, ask user to resolve |

## Integration with Workflow

This command should run:
- **After `/speckit.implement`** completes all phases
- **Before PR creation** (so learnings are captured in the branch)
- **Optionally after `/speckit.review`** if review uncovered insights

In the speckit-worker flow, add between "Implemented" and "PR workflow":

```
Iter N:   implement (final phase) → COMMAND_COMPLETE    >>> STOP
Iter N+1: reflect → COMMAND_COMPLETE: speckit.reflect   >>> STOP
Iter N+2: pr-workflow → FEATURE_COMPLETE                >>> STOP
```
