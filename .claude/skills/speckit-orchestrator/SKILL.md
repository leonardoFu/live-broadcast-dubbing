---
name: speckit-orchestrator
description: Intelligent workflow orchestrator that analyzes user requirements, recommends an appropriate workflow, and executes speckit agents in sequence.
---

# Speckit Orchestrator

Intelligent workflow orchestrator - analyzes complexity, recommends workflow, executes agents with checkpoints and feedback loops.

## Execution Flow

1. **Pre-Flight Validation** → Check git, tools, constitution
2. **Workflow Selection** → Analyze complexity, recommend, confirm
3. **Planning Phase** → Run spec/plan agents
4. **🛑 MANDATORY Checkpoint** → Require user approval before implementation
5. **Implementation Phase** → Run implement/test/review
6. **E2E Phase** (if needed) → Run e2e-test-builder/fixer
7. **Error Recovery** → Feedback loops with max retries
8. **Summary** → Report results

---

## Available Agents

| Agent | Subagent Type | Description |
|-------|---------------|-------------|
| specify | speckit-specify | Creates feature spec from request |
| clarify | speckit-clarify | Resolves ambiguities via questions |
| research | speckit-research | Fetches docs via Context7/web |
| plan | speckit-plan | Generates implementation plan |
| checklist | speckit-checklist | Creates validation checklist |
| tasks | speckit-tasks | Generates dependency-ordered tasks |
| analyze | speckit-analyze | Cross-artifact consistency validation |
| implement | speckit-implement | Executes tasks with TDD |
| test | speckit-test | Quality gate (coverage, lint, types) |
| review | speckit-review | Active cleanup (move files, remove duplicates) |
| **e2e-test-builder** | speckit-e2e-test-builder | Creates E2E tests, detects gaps |
| **e2e-test-fixer** | speckit-e2e-test-fixer | Fixes E2E failures, syncs spec |
| taskstoissues | speckit-taskstoissues | Converts tasks to GitHub issues |

---

## Workflow Selection

### Complexity Scoring

| Factor | 0 | 1 | 2 | 3 |
|--------|---|---|---|---|
| **Scope** | Single file | Single module | Multiple modules | Cross-service |
| **Integration** | None | Internal libs | External API | Multiple services |
| **Risk** | Experimental | Dev/staging | Prod non-critical | Prod critical |
| **Novelty** | Existing pattern | Minor variation | New feature type | Novel architecture |

**Score → Workflow**:
- 0-3: Simple
- 4-6: Standard
- 7-9: Full
- 10+: Full + Research

### Output Format

```
## 📋 Workflow Analysis

**Request**: [summarized]

| Factor | Score | Reason |
|--------|-------|--------|
| Scope | X/3 | [reason] |
| Integration | X/3 | [reason] |
| Risk | X/3 | [reason] |
| Novelty | X/3 | [reason] |
| **Total** | **X/12** | |

### 🎯 Recommended: **[Workflow]**
[agent sequence]

**Proceed?** [Y/n/simple/standard/full]
```

**User Response**:
- `Y`, `yes`, Enter → Execute recommended
- `simple`/`standard`/`full` → Execute specified
- `n`, `no` → Ask preference

---

## Workflows

### Core Workflows

| Workflow | Score | Sequence |
|----------|-------|----------|
| **Simple** | 0-3 | specify → 🛑 → implement → test |
| **Standard** | 4-6 | specify → clarify → plan → tasks → 🛑 → implement → test |
| **Standard + E2E** | 4-6 | specify → clarify → plan → tasks → 🛑 → implement → test → review → e2e-test-builder → e2e-test-fixer |
| **Full** | 7-9 | specify → clarify → plan → checklist → tasks → analyze → 🛑 → implement → test → review → e2e-test-builder → e2e-test-fixer → taskstoissues |
| **Full + Research** | 10+ | specify → clarify → research → plan → checklist → tasks → analyze → 🛑 → implement → test → review → e2e-test-builder → e2e-test-fixer → taskstoissues |

**🛑 CHECKPOINT**: Mandatory user confirmation before implementation.

**E2E Testing**: Runs after unit tests. If gaps detected, returns to `implement`.

### Explicit Triggers

| Trigger | Workflow | Checkpoint |
|---------|----------|------------|
| `simple: [feature]` | Force Simple | 🛑 Yes |
| `full: [feature]` | Force Full | 🛑 Yes |
| `spec: [feature]` | specify → clarify | No |
| `plan: [feature]` | specify → clarify → plan → checklist → tasks → analyze | No |
| `clarify` | clarify only | No |
| `analyze` | analyze only | No |
| `implement` | 🛑 → implement → test → review | 🛑 Yes (always) |
| `review` | review only | No |
| `e2e: [feature]` | e2e-test-builder → e2e-test-fixer | No |
| `fix-e2e [file]` | e2e-test-fixer | No |
| `issues` / `github` | taskstoissues | No |

---

## Pre-Flight Checks

```
1. Git repo: git rev-parse --git-dir → ERROR if not repo
2. Git status: git status --porcelain → WARN if uncommitted
3. Tools: make, pytest, ruff → WARN if missing
4. Constitution: .specify/memory/constitution.md → WARN if missing
5. Write access: specs/ → ERROR if no access

Result: ERROR → stop | WARN → continue | PASS → proceed
```

---

## Agent Execution

### Context Passing

```
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "<feature-id>",
  "feature_dir": "specs/<feature-id>/",
  "previous_results": {
    "<agent>": { "status": "success", ... }
  }
}
USER_REQUEST: <original request>
```

### Execution Loop

For each agent:
1. Set `current_agent` in state
2. Build context from previous results
3. Invoke via Task tool (30-min timeout)
4. Parse JSON response
5. Success → store result, continue | Error → recovery
6. Persist state to `.specify/workflow-state/<workflow-id>.json`

---

## 🛑 MANDATORY Human Checkpoint

**Non-negotiable**: Before ANY implementation, pause and require explicit user confirmation.

### When This Triggers

After planning agents complete, before `implement` runs:

| Workflow | Planning (run first) | 🛑 | Implementation (after approval) |
|----------|---------------------|----|---------------------------------|
| Simple | specify | STOP | implement → test |
| Standard | specify → clarify → plan → tasks | STOP | implement → test |
| Full | specify → clarify → plan → checklist → tasks → analyze | STOP | implement → test → review → e2e → taskstoissues |

### Checkpoint Output

```
## 🛑 Pre-Implementation Checkpoint

Planning complete. Ready for implementation.

### 📋 Artifacts:
- Spec: specs/<id>/spec.md
- Plan: specs/<id>/plan.md
- Tasks: specs/<id>/tasks.md (X tasks)

### 📊 Scope:
- Files to create: X
- Files to modify: X
- Tests to write: X
- Estimated changes: ~X LOC

### ⚠️ Checklist:
- [ ] Review spec.md
- [ ] Review plan.md
- [ ] Review tasks.md
- [ ] Confirm branch: <branch>

---

🚨 CONFIRMATION REQUIRED

**Type one of:**
- `proceed` / `yes` - Begin implementation
- `review <artifact>` - Show artifact
- `abort` - Cancel workflow
- `pause` - Save state, resume later
```

### User Response Handling

| Response | Action |
|----------|--------|
| `proceed`, `yes`, `y`, `confirm` | Begin implementation |
| `review spec` / `plan` / `tasks` | Display artifact |
| `abort`, `cancel`, `no` | Cancel, keep artifacts |
| `pause`, `stop` | Save state for resume |

### State Persistence

```json
{
  "workflow_id": "<uuid>",
  "status": "awaiting_implementation_approval",
  "checkpoint_reached_at": "<ISO8601>",
  "planning_complete": true,
  "implementation_approved": false,
  "artifacts_ready": {
    "spec": "specs/<id>/spec.md",
    "plan": "specs/<id>/plan.md",
    "tasks": "specs/<id>/tasks.md"
  },
  "resume_from": "implement"
}
```

### Resume

```bash
orchestrator resume <workflow-id>
# OR
resume
```

---

## Error Recovery

| Error | Strategy | Retries |
|-------|----------|---------|
| PrerequisiteError | Auto-run missing agent | 1 |
| ValidationError | Invoke clarify | 1 |
| QualityGateFailure | Feedback loop to source | 2 |
| TestValidationError | Re-run implement with failures | 2 |
| ExternalServiceError | Exponential backoff | 3 |
| TimeoutError | Retry | 1 |
| BranchExistsError | Ask user | N/A |
| UnrecoverableError | Stop, report | 0 |

### Test Failure Loop

```
implement → test
  ↓ FAILED?
retry_count < 2?
  ├─ Yes → Re-run implement with blocking_issues
  └─ No → Stop, report
```

---

## Feedback Loops

Quality gate agents route issues back to source agents for correction.

### Feedback Architecture

```
specify → clarify → plan → tasks
   ↑          ↑         ↑       ↑
   │          │         │       │
   └──────────┴─────────┴───────┤
                                │
                          ┌─────┴─────┐
                          │  analyze  │
                          └───────────┘
                                │
                          Issues found?
                          ├─ Spec gaps → specify/clarify
                          ├─ Plan issues → plan
                          └─ Task issues → tasks

implement ← test ← review
   ↑         │
   └─────────┘
   blocking_issues → implement
```

### Feedback Triggers

| Source | Trigger | Target | Feedback |
|--------|---------|--------|----------|
| analyze | Spec gaps | specify/clarify | Missing sections, unclear reqs |
| analyze | Plan inconsistency | plan | Architecture gaps, data model issues |
| analyze | Task coverage gaps | tasks | Uncovered reqs, dependencies |
| test | Test failures | implement | Failed tests, coverage gaps |
| test | Quality gates | implement | Lint, type, coverage errors |
| review | Constitution violations | implement | Directory, naming, TDD compliance |

### Feedback Context

```text
FEEDBACK_CONTEXT:
{
  "feedback_from": "speckit-analyze",
  "iteration": 2,
  "max_iterations": 3,
  "issues_to_fix": [
    {
      "severity": "CRITICAL",
      "type": "Coverage Gap",
      "message": "REQ-5 has no tasks",
      "location": "spec.md:67",
      "recommendation": "Add tasks for REQ-5"
    }
  ]
}
```

### Loop Limits

| Loop | Max Iterations | Escalation |
|------|----------------|------------|
| analyze → specify/clarify | 2 | Ask user to clarify |
| analyze → plan | 2 | Ask user to review |
| analyze → tasks | 2 | Ask user to review |
| test → implement | 2 | Stop, report |
| review → implement | 1 | Stop, report |

---

## E2E Testing Integration

E2E tests validate cross-service features end-to-end.

### When E2E Tests Are Added

Auto-added when:
1. Spec has cross-service requirements (media + STS + MediaMTX)
2. Integration-heavy (external deps, streaming, real-time)
3. User requests: `e2e:` trigger or "E2E test" in requirements

### E2E Workflow Sequence

```
implement → test (unit) → review
    ↓
e2e-test-builder (creates test from spec)
    ↓
Implementation Status Check
    ├─ COMPLETE → Run E2E Tests
    └─ MISSING → Return to implement
    ↓
Run E2E Tests
    ↓
All Pass?
    ├─ YES → SUCCESS
    └─ NO → e2e-test-fixer (max 3 iterations)
        ↓
    Root Cause Analysis
        ├─ TEST_BUG → Fix test → Re-run
        ├─ SPEC_MISMATCH → Update spec + test → Re-run
        ├─ IMPLEMENTATION_BUG (SIMPLE, score ≤ 3) → Fix code + spec → Re-run
        ├─ IMPLEMENTATION_BUG (COMPLEX, score > 3) → Return to implement
        └─ MAX_ITERATIONS → Manual investigation
```

### E2E Feedback Loop

```
e2e-test-fixer
    ↓ IMPLEMENTATION_GAP
Return FEEDBACK_CONTEXT to implement
    ↓
implement (add missing features)
    ↓
test → review
    ↓
e2e-test-fixer (retry)
    ↓ All pass?
SUCCESS
```

**Max E2E Iterations**: 3 (escalate to user if exceeded)

### E2E State Tracking

```json
{
  "e2e_workflow": {
    "test_file": "tests/e2e/test_<name>.py",
    "test_coverage": 100,
    "fixer_iteration": 2,
    "max_fixer_iterations": 3,
    "implementation_gaps_detected": 0,
    "spec_updates": [
      {
        "file": "specs/<id>/spec.md",
        "change": "Updated SC-002 from 5s to 10s",
        "approved": false
      }
    ]
  }
}
```

### E2E Complexity Assessment

When E2E fixer detects IMPLEMENTATION_BUG, assess complexity:

**Scoring**:
- Code Size: Simple function (+1), New file (+2), New class (+3)
- Architectural Impact: Single module (+1), Pipeline (+2), Data model (+2), Multi-service (+3)
- Risk: Config (+1), DB migration (+2), Prod critical (+2)
- Testing: Unit tests (+1), Integration tests (+2)

**Decision**:
- **Score ≤ 3**: SIMPLE → Fix in e2e-fixer
- **Score > 3**: COMPLEX → Return to orchestrator (full feature workflow)

### E2E Error Recovery

| Error | Strategy | Max Retries |
|-------|----------|-------------|
| ImplementationGap | Return to implement with missing features | 1 |
| TestBug | Fix test, re-run | 3 (within fixer) |
| SpecMismatch | Update spec + test, re-run | 2 |
| ServiceUnhealthy | Wait 30s, retry, escalate | 2 |
| MaxIterationsReached | Escalate to user | 0 |

---

## Workflow Variants

### Standard (no E2E)

```
specify → clarify → plan → tasks → 🛑 → implement → test
```

**Use**: Single-service features, utilities

### Standard + E2E

```
specify → clarify → plan → tasks → 🛑 → implement → test → review
    ↓
e2e-test-builder → e2e-test-fixer
```

**Use**: Cross-service features, streaming, APIs

### Full + E2E

```
specify → clarify → plan → checklist → tasks → analyze → 🛑
    ↓
implement → test → review
    ↓
e2e-test-builder → e2e-test-fixer → taskstoissues
```

**Use**: Production-critical cross-service features

---

## State Persistence

`.specify/workflow-state/<workflow-id>.json`:

```json
{
  "workflow_id": "<uuid>",
  "workflow_type": "standard",
  "user_request": "<request>",
  "workflow_selection": {
    "complexity_analysis": { "total_score": 6 },
    "recommended_workflow": "standard",
    "final_workflow": "standard"
  },
  "agents_to_execute": ["specify", "clarify", "plan", "tasks", "implement", "test"],
  "completed_agents": ["specify", "clarify"],
  "current_agent": "plan",
  "agent_results": {},
  "feedback_loops": {
    "test_to_implement": {
      "iteration": 1,
      "max_iterations": 2
    }
  },
  "status": "running"
}
```

---

## Agent Response Contract

All agents return:

```json
{
  "agent": "<name>",
  "status": "success|error",
  "timestamp": "<ISO8601>",
  "result": { ... },
  "error": null | {
    "type": "<ErrorType>",
    "message": "<message>",
    "recoverable": true|false,
    "feedback_required": true|false,
    "blocking_issues": [ ... ],
    "suggested_action": { "agent": "<agent>" }
  }
}
```

---

## Summary Output

```
## Workflow Complete: [Type]

**Status**: ✅ Success | ❌ Failed
**Feature**: [name] (Branch: [branch])
**Duration**: [time]

### Agents:
1. ✅ specify - Created spec.md
2. ✅ clarify - Resolved N questions
...

### Artifacts:
- Spec: specs/XXX/spec.md
- Plan: specs/XXX/plan.md
- Tasks: specs/XXX/tasks.md
- E2E Test: tests/e2e/test_XXX.py (if applicable)

### Next Steps:
- Review implementation
- Create PR: `gh pr create`
```

---

## Usage Examples

```bash
# Auto-recommend
orchestrator: Add user authentication with OAuth2

# Force workflow
simple: Add logging utility
full: Payment processing with Stripe

# Targeted
spec: WebSocket service         # spec only
plan: Notification arch         # spec + plan
implement                       # tasks only
e2e: Add health monitoring      # E2E only
fix-e2e tests/e2e/test_X.py     # Fix E2E
review                          # cleanup
issues                          # GitHub issues
```

---

*Speckit Orchestrator - Intelligent workflow execution with checkpoints, feedback loops, and E2E validation*
