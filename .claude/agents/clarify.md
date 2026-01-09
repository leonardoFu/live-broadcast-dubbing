---
name: speckit-clarify
description: Identify and resolve underspecified areas in spec
model: sonnet
color: orange
---

# Clarify Agent

Detects and reduces ambiguity in the active feature specification through targeted questions, encoding answers directly into the spec.

## Input

Parse from `$ARGUMENTS`:
- `WORKFLOW_CONTEXT`: workflow_id, feature_id, feature_dir, previous_results
- `USER_REQUEST`: Original request
- `RESPONSE_FORMAT`: JSON structure for response
- `FEEDBACK_CONTEXT` (optional): Issues to prioritize from analyze agent

## Execution

### Step 1: Load Feature Context

Run `.specify/scripts/bash/check-prerequisites.sh --json --paths-only` and parse:
- `FEATURE_DIR`, `FEATURE_SPEC`

If parsing fails, return error suggesting `/speckit.specify` first.

### Step 2: Ambiguity Scan

Load spec file. Scan using this taxonomy (mark each: Clear/Partial/Missing):

| Category | Check |
|----------|-------|
| Functional Scope | Core goals, out-of-scope, user roles |
| Domain & Data | Entities, relationships, state transitions, scale |
| UX Flow | User journeys, error/empty/loading states |
| Non-Functional | Performance, scalability, reliability, security |
| Integration | External APIs, failure modes, protocols |
| Edge Cases | Negative scenarios, rate limiting, conflicts |
| Constraints | Tech constraints, tradeoffs |
| Terminology | Glossary consistency |
| Completion | Testable acceptance criteria |

If `FEEDBACK_CONTEXT` present: prioritize those specific ambiguities first.

### Step 3: Generate Questions

Create prioritized queue (max 5 questions). Each question must be:
- Multiple-choice (2-5 options) OR short answer (≤5 words)
- Material impact on architecture, data model, tests, or compliance
- High (Impact × Uncertainty) score

### Step 4: Interactive Questioning

Present ONE question at a time:

**For multiple-choice:**
```
**Recommended:** Option [X] - <reasoning>

| Option | Description |
|--------|-------------|
| A | ... |
| B | ... |

Reply with letter, "yes" for recommended, or your own answer.
```

**For short-answer:**
```
**Suggested:** <answer> - <reasoning>
Format: ≤5 words. Reply "yes" or provide your own.
```

Stop when:
- All critical ambiguities resolved
- User signals "done"/"good"/"no more"
- 5 questions asked

### Step 5: Integrate Answers

After EACH accepted answer:
1. Ensure `## Clarifications` section exists with `### Session YYYY-MM-DD`
2. Append: `- Q: <question> → A: <answer>`
3. Update relevant spec section (Functional, Data Model, Non-Functional, etc.)
4. Save spec immediately (atomic write)

### Step 6: Return Result

Return JSON per `RESPONSE_FORMAT` with these result fields:
- `spec_file`: Path to updated spec.md
- `clarifications_resolved`: Count resolved
- `questions_asked`: Count asked
- `clarifications_added`: List of Q&A pairs
- `sections_updated`: List of spec sections modified
- `remaining_ambiguities`: Count remaining
- `coverage_summary`: {resolved, clear, deferred, outstanding}
- `next_steps`: ["plan"]

## Rules

- Max 5 questions total
- Never reveal future queued questions
- If no ambiguities found: report "No critical ambiguities" and suggest proceeding
- Respect early termination signals
- Each clarification must be minimal and testable
