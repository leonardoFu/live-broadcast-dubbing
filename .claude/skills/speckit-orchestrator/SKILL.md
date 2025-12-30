---
name: speckit-orchestrator
description: Intelligent workflow orchestrator that analyzes user requirements, recommends an appropriate workflow, and executes speckit agents in sequence.
---

# Speckit Orchestrator

Intelligent workflow orchestrator that analyzes user requirements, recommends an appropriate workflow, and executes speckit agents in sequence.

## Execution Flow

1. **Pre-Flight Validation** → Check git repo, tools, constitution
2. **Workflow Selection** → Analyze complexity, present recommendation, get user confirmation
3. **Agent Execution (Planning Phase)** → Run specification/planning agents
4. **🛑 MANDATORY Human Checkpoint** → Require explicit user confirmation before implementation
5. **Agent Execution (Implementation Phase)** → Run implement, test, review agents
6. **Error Recovery** → Handle failures with retry/fix logic
7. **Summary** → Report results and next steps

---

## Available Agents

| Agent | Subagent Type | Description |
|-------|---------------|-------------|
| **specify** | `speckit-specify` | Creates feature specification from user request |
| **clarify** | `speckit-clarify` | Resolves ambiguities via targeted questions |
| **research** | `speckit-research` | Fetches external docs via Context7 and web search |
| **plan** | `speckit-plan` | Generates implementation plan with data model |
| **checklist** | `speckit-checklist` | Creates validation checklist for requirements |
| **tasks** | `speckit-tasks` | Generates dependency-ordered task list |
| **analyze** | `speckit-analyze` | Cross-artifact consistency validation |
| **implement** | `speckit-implement` | Executes tasks with TDD approach |
| **test** | `speckit-test` | Quality gate validation (coverage, lint, types) |
| **review** | `speckit-review` | Active cleanup (move files, remove duplicates) |
| **taskstoissues** | `speckit-taskstoissues` | Converts tasks to GitHub issues |

---

## Workflow Selection (MANDATORY)

Before executing, analyze the request and present a workflow recommendation.

### Complexity Scoring

| Factor | 0 | 1 | 2 | 3 |
|--------|---|---|---|---|
| **Scope** | Single file | Single module | Multiple modules | Cross-service |
| **Integration** | None | Internal libs | External API | Multiple services |
| **Risk** | Experimental | Dev/staging | Prod non-critical | Prod critical |
| **Novelty** | Existing pattern | Minor variation | New feature type | Novel architecture |

**Score → Workflow:**
- 0-3: Simple
- 4-6: Standard
- 7-9: Full
- 10+: Full + Research

### Output Format

Display to user before proceeding:

```
## 📋 Workflow Analysis

**Request**: [summarized request]

| Factor | Score | Reason |
|--------|-------|--------|
| Scope | X/3 | [reason] |
| Integration | X/3 | [reason] |
| Risk | X/3 | [reason] |
| Novelty | X/3 | [reason] |
| **Total** | **X/12** | |

### 🎯 Recommended: **[Workflow Name]**
[agent sequence]

**Proceed?** [Y/n/simple/standard/full]
```

### User Response

| Response | Action |
|----------|--------|
| `Y`, `yes`, Enter | Execute recommended |
| `simple` / `standard` / `full` | Execute specified |
| `n`, `no` | Ask preference |

---

## Workflows

### Core Workflows (Complexity-Based)

| Workflow | Score | Sequence |
|----------|-------|----------|
| **Simple** | 0-3 | specify → 🛑 **CHECKPOINT** → implement → test |
| **Standard** | 4-6 | specify → clarify → plan → tasks → 🛑 **CHECKPOINT** → implement → test |
| **Full** | 7-9 | specify → clarify → plan → checklist → tasks → analyze → 🛑 **CHECKPOINT** → implement → test → review → taskstoissues |
| **Full + Research** | 10+ | specify → clarify → research → plan → checklist → tasks → analyze → 🛑 **CHECKPOINT** → implement → test → review → taskstoissues |

**🛑 CHECKPOINT**: Mandatory human confirmation required before any implementation begins. See [MANDATORY Human Checkpoint](#-mandatory-human-checkpoint-pre-implementation-gate) section.

### Explicit Triggers (Bypass Complexity Analysis)

| Trigger | Workflow | Checkpoint |
|---------|----------|------------|
| `simple: [feature]` | Force Simple | 🛑 Yes (before implement) |
| `full: [feature]` | Force Full | 🛑 Yes (before implement) |
| `spec: [feature]` | specify → clarify | No (planning only) |
| `plan: [feature]` | specify → clarify → plan → checklist → tasks → analyze | No (planning only) |
| `clarify` | clarify only | No |
| `analyze` | analyze only | No |
| `implement` | 🛑 checkpoint → implement → test → review | 🛑 Yes (always) |
| `review` | review only | No |
| `issues` / `github` | taskstoissues only | No |

**Note**: The `implement` trigger ALWAYS requires human confirmation, even when called directly. This is non-negotiable.

---

## Pre-Flight Checks

Run before any workflow:

```
1. Git repo exists: `git rev-parse --git-dir`
   - ERROR if not a repo

2. Git status: `git status --porcelain`
   - WARN if uncommitted changes (continue)

3. Tools: make, pytest, ruff
   - WARN if missing (continue)

4. Constitution: `.specify/memory/constitution.md`
   - WARN if missing (continue)

5. Write access: `specs/` directory
   - ERROR if no access

Result: ERROR → stop | WARN → log and continue | PASS → proceed
```

---

## Agent Execution

### Context Passing

Pass context via Task tool prompt:

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

### Agent Context Requirements

| Agent | Needs From |
|-------|------------|
| specify | user_request |
| clarify | specify.spec_file |
| plan | specify.spec_file, clarify results |
| tasks | plan.plan_file |
| implement | tasks.tasks_file, plan.plan_file |
| test | implement results |
| review | test results |
| taskstoissues | tasks.tasks_file |

### Execution Loop

For each agent:
1. Set `current_agent` in state
2. Build context from previous results
3. Invoke via Task tool (30-min timeout)
4. Parse JSON response
5. If success → store result, continue
6. If error → run recovery handler
7. Persist state to `.specify/workflow-state/<workflow-id>.json`

---

## 🛑 MANDATORY Human Checkpoint (Pre-Implementation Gate)

**This checkpoint is REQUIRED and cannot be skipped.** Before any implementation (coding) begins, the orchestrator MUST pause and require explicit user confirmation.

### When This Checkpoint Triggers

The checkpoint triggers **after all planning agents complete** and **before the `implement` agent runs**. This applies to ALL workflows:

| Workflow | Planning Agents (run first) | Checkpoint | Implementation Agents (after approval) |
|----------|----------------------------|------------|----------------------------------------|
| **Simple** | specify | 🛑 STOP | implement → test |
| **Standard** | specify → clarify → plan → tasks | 🛑 STOP | implement → test |
| **Full** | specify → clarify → plan → checklist → tasks → analyze | 🛑 STOP | implement → test → review → taskstoissues |
| **Full + Research** | specify → clarify → research → plan → checklist → tasks → analyze | 🛑 STOP | implement → test → review → taskstoissues |

### Checkpoint Output Format

Display this to user and WAIT for explicit confirmation:

```
## 🛑 Pre-Implementation Checkpoint

Planning phase complete. Ready to begin implementation.

### 📋 Artifacts Created:
- Spec: specs/<feature-id>/spec.md
- Plan: specs/<feature-id>/plan.md
- Tasks: specs/<feature-id>/tasks.md (X tasks)
- [Other artifacts...]

### 📊 Implementation Scope:
- **Files to create**: X new files
- **Files to modify**: X existing files
- **Tests to write**: X test files
- **Estimated changes**: ~X lines of code

### ⚠️ Pre-Implementation Checklist:
- [ ] Review spec.md for accuracy
- [ ] Review plan.md for architecture decisions
- [ ] Review tasks.md for task ordering and completeness
- [ ] Confirm branch: <branch-name>

---

**🚨 CONFIRMATION REQUIRED**

I will NOT proceed with implementation until you explicitly confirm.

**Type one of the following:**
- `proceed` or `yes` - Begin implementation
- `review <artifact>` - Show specific artifact for review
- `abort` - Cancel workflow
- `pause` - Save state and stop (resume later)
```

### User Response Handling

| Response | Action |
|----------|--------|
| `proceed`, `yes`, `y`, `confirm` | Begin implementation phase |
| `review spec` | Display spec.md content |
| `review plan` | Display plan.md content |
| `review tasks` | Display tasks.md content |
| `abort`, `cancel`, `no` | Cancel workflow, keep artifacts |
| `pause`, `stop` | Save state, user can resume later |
| Any other response | Re-prompt for valid response |

### Why This Checkpoint Exists

1. **Prevents wasted effort**: Implementation can take significant time. Review artifacts first.
2. **Catches planning errors early**: Easier to fix spec/plan than to refactor implemented code.
3. **User maintains control**: No surprise code changes without explicit approval.
4. **Enables async workflows**: User can review artifacts offline, then resume.

### State Persistence at Checkpoint

When checkpoint is reached, state is saved:

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

### Resuming After Checkpoint

If user returns later:

```bash
# Resume workflow
orchestrator resume <workflow-id>

# Or simply:
resume
```

The orchestrator will:
1. Load state from `.specify/workflow-state/<workflow-id>.json`
2. Display checkpoint prompt again
3. Wait for user confirmation
4. Continue from `implement` agent upon approval

---

## Error Recovery

| Error Type | Strategy | Retries |
|------------|----------|---------|
| `PrerequisiteError` | Auto-run missing agent | 1 |
| `ValidationError` | Invoke clarify | 1 |
| `QualityGateFailure` | Feedback loop to source agent | 2 |
| `TestValidationError` | Re-run implement with failure details | 2 |
| `ExternalServiceError` | Exponential backoff | 3 |
| `TimeoutError` | Retry once | 1 |
| `BranchExistsError` | Ask user | N/A |
| `UnrecoverableError` | Stop, report | 0 |

### Test Failure Loop

```
implement → test
  ↓
FAILED? → retry_count < 2?
  ├─ Yes → Re-run implement with blocking_issues → test again
  └─ No → Stop, report to user
```

---

## Quality Gate Feedback Loops

The orchestrator implements **feedback loops** that route issues discovered by validation agents back to the source agents for correction. This enables iterative refinement until quality gates pass.

### Feedback Loop Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    QUALITY GATE FEEDBACK LOOPS                  │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────────┐ │
│  │ specify │ → │ clarify │ → │  plan   │ → │    tasks    │ │
│  └────▲────┘    └────▲────┘    └────▲────┘    └──────▲──────┘ │
│       │              │              │                │         │
│       │              │              │                │         │
│       │    ┌─────────┴──────────────┴────────────────┤         │
│       │    │                                         │         │
│       │    │         ┌───────────┐                   │         │
│       │    └─────────┤  analyze  │───────────────────┘         │
│       │              └─────┬─────┘                             │
│       │                    │                                   │
│       │    ISSUES FOUND?   │                                   │
│       │    ├─ Spec gaps → ─┘ (back to specify/clarify)         │
│       │    ├─ Plan issues → (back to plan)                     │
│       │    └─ Task issues → (back to tasks)                    │
│       │                                                        │
│  ┌────┴────┐    ┌─────────┐    ┌─────────┐    ┌─────────────┐ │
│  │implement│ ← │  test   │ ← │ review  │ ← │   (gate)    │ │
│  └────▲────┘    └────┬────┘    └─────────┘    └─────────────┘ │
│       │              │                                         │
│       │    FAILED?   │                                         │
│       └──────────────┘                                         │
│       (blocking_issues fed back to implement)                  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Feedback Triggers

| Source Agent | Trigger Condition | Target Agent | Feedback Content |
|--------------|-------------------|--------------|------------------|
| `analyze` | Spec ambiguity/gaps | `specify` or `clarify` | Missing sections, unclear requirements |
| `analyze` | Plan inconsistency | `plan` | Architecture gaps, data model issues |
| `analyze` | Task coverage gaps | `tasks` | Uncovered requirements, dependency issues |
| `test` | Test failures | `implement` | Failed tests, coverage gaps, blocking issues |
| `test` | Quality gate failures | `implement` | Lint errors, type errors, coverage < threshold |
| `review` | Constitution violations | `implement` | Directory structure, naming, TDD compliance |

### Feedback Loop Protocol

When a validation agent returns issues:

1. **Parse Response**: Extract `feedback_required` and `blocking_issues` from JSON
2. **Identify Target**: Determine which agent should fix the issues
3. **Build Feedback Context**: Construct `FEEDBACK_CONTEXT` with issues
4. **Re-invoke Target**: Run target agent with feedback context
5. **Re-validate**: Run validation agent again
6. **Check Loop Count**: Stop if max iterations reached

### Feedback Context Format

When re-invoking an agent to fix issues, append this to the prompt:

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
      "message": "Requirement REQ-5 has no corresponding tasks",
      "location": "spec.md:67",
      "recommendation": "Add tasks to implement REQ-5"
    },
    {
      "severity": "HIGH",
      "type": "Constitution Violation",
      "message": "Task T012 missing test step before implementation",
      "location": "tasks.md:45",
      "recommendation": "Add test implementation step before code"
    }
  ],
  "original_response": { ... }
}
```

### Loop Limits

| Feedback Loop | Max Iterations | Escalation Action |
|---------------|----------------|-------------------|
| analyze → specify/clarify | 2 | Ask user to clarify |
| analyze → plan | 2 | Ask user to review plan |
| analyze → tasks | 2 | Ask user to review tasks |
| test → implement | 2 | Stop, report blocking issues |
| review → implement | 1 | Stop, report cleanup needed |

### Feedback Decision Logic

```python
def handle_quality_gate_feedback(agent_response: dict, context: dict) -> Action:
    """
    Determine next action based on validation agent response.
    """
    if agent_response["status"] == "success":
        # No feedback needed, continue to next agent
        return Action(type="continue")

    error = agent_response.get("error", {})

    # Check if feedback is needed
    if not error.get("feedback_required"):
        # Unrecoverable error, stop workflow
        return Action(type="stop", reason=error.get("message"))

    # Check iteration count
    feedback_type = error.get("feedback_type")
    iteration = context.get(f"{feedback_type}_iterations", 0) + 1
    max_iterations = get_max_iterations(feedback_type)

    if iteration > max_iterations:
        # Max iterations reached, escalate to user
        return Action(
            type="ask_user",
            message=f"Quality gate still failing after {iteration} attempts",
            issues=error.get("blocking_issues", [])
        )

    # Determine target agent based on issue types
    target_agent = determine_feedback_target(error.get("blocking_issues", []))

    # Build feedback context
    feedback_context = build_feedback_context(
        source_agent=agent_response["agent"],
        issues=error.get("blocking_issues", []),
        iteration=iteration,
        max_iterations=max_iterations
    )

    # Update context and return feedback action
    context[f"{feedback_type}_iterations"] = iteration

    return Action(
        type="feedback_loop",
        target_agent=target_agent,
        feedback_context=feedback_context,
        revalidate_with=agent_response["agent"]
    )


def determine_feedback_target(issues: list) -> str:
    """
    Determine which agent should fix the issues.
    Priority: Most upstream agent that can fix the root cause.
    """
    issue_types = {issue.get("category", issue.get("type", "")) for issue in issues}

    # Route to most appropriate agent
    if any(t in issue_types for t in ["spec_ambiguity", "missing_requirement", "unclear_scope"]):
        return "speckit-specify"  # or speckit-clarify

    if any(t in issue_types for t in ["architecture_gap", "data_model_issue", "design_flaw"]):
        return "speckit-plan"

    if any(t in issue_types for t in ["coverage_gap", "dependency_error", "task_ordering"]):
        return "speckit-tasks"

    if any(t in issue_types for t in ["test_failure", "coverage", "lint_error", "type_error"]):
        return "speckit-implement"

    # Default to implement for unknown issues
    return "speckit-implement"
```

### State Persistence for Feedback Loops

Track feedback loop state in workflow state file:

```json
{
  "workflow_id": "<uuid>",
  "feedback_loops": {
    "analyze_to_spec": {
      "iteration": 1,
      "max_iterations": 2,
      "issues_history": [
        {
          "iteration": 1,
          "issues_count": 3,
          "issues_fixed": 2,
          "issues_remaining": 1
        }
      ]
    },
    "test_to_implement": {
      "iteration": 2,
      "max_iterations": 2,
      "issues_history": [...]
    }
  }
}
```

### User Notification on Feedback Loops

When entering a feedback loop, notify user:

```
## 🔄 Quality Gate Feedback

**Source**: speckit-analyze
**Target**: speckit-tasks (iteration 1/2)

### Issues to Fix:
1. [CRITICAL] Requirement REQ-5 has no corresponding tasks
2. [HIGH] Task T012 missing test step before implementation

Re-running speckit-tasks to address these issues...
```

---

## Workflow Adaptation

During execution, suggest workflow changes if complexity differs from initial assessment.

**Upgrade Triggers** (Simple→Standard, Standard→Full):
- Clarify finds >3 ambiguities
- Plan identifies >5 integration points
- Multiple test failures

**Downgrade Triggers** (Full→Standard, Standard→Simple):
- Spec is straightforward
- Plan reveals simpler implementation

Prompt user:
```
## ⚡ Workflow Adjustment

During [phase], discovered:
- [findings]

**Suggestion**: Upgrade to [workflow]
**Accept?** [Y/n]
```

---

## State Persistence

State file: `.specify/workflow-state/<workflow-id>.json`

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
  "agents_to_execute": ["specify", "clarify", ...],
  "completed_agents": ["specify"],
  "current_agent": "clarify",
  "agent_results": {},
  "test_retry_count": 0,
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
    "suggested_action": { "agent": "<agent>" }
  }
}
```

---

## Workflow Summary Output

After completion:

```
## Workflow Complete: [Type]

**Status**: ✅ Success | ❌ Failed
**Feature**: [name] (Branch: [branch])

### Agents:
1. ✅ specify - Created spec.md
2. ✅ clarify - Resolved N clarifications
...

### Artifacts:
- Spec: specs/XXX/spec.md
- Plan: specs/XXX/plan.md
- Tasks: specs/XXX/tasks.md

### Next Steps:
- Review implementation
- Create PR: `gh pr create`
```

---

## Usage Examples

```bash
# Analyze and recommend (default)
orchestrator: Add user authentication with OAuth2

# Force workflow
simple: Add logging utility
full: Payment processing with Stripe

# Targeted operations
spec: WebSocket service          # spec only
plan: Notification architecture  # spec + plan
implement                        # run tasks
review                           # cleanup
issues                           # create GitHub issues
```

---

## Full Workflow Example

**User Request**: `orchestrator: Add RTMP stream health monitoring`

### Step 1: Workflow Analysis Output

```
## 📋 Workflow Analysis

**Request**: Add RTMP stream health monitoring

| Factor | Score | Reason |
|--------|-------|--------|
| Scope | 2/3 | Affects media-service stream handling |
| Integration | 1/3 | Uses existing GStreamer pipeline |
| Risk | 2/3 | Production stream monitoring |
| Novelty | 1/3 | Similar to existing health check patterns |
| **Total** | **6/12** | |

### 🎯 Recommended: **Standard**
specify → clarify → plan → tasks → implement → test

**Proceed?** [Y/n/simple/standard/full]
```

**User**: `Y`

### Step 2: Planning Phase Execution

```
## Workflow: Standard (Planning Phase)

1. ✅ speckit-specify (3.2s)
   - Created branch: 006-rtmp-health-monitoring
   - Spec: specs/006-rtmp-health-monitoring/spec.md

2. ✅ speckit-clarify (4.1s)
   - Asked 3 clarification questions
   - Updated spec with answers

3. ✅ speckit-plan (5.8s)
   - Created: plan.md, data-model.md
   - Identified 4 implementation phases

4. ✅ speckit-tasks (2.4s)
   - Generated 12 tasks
   - Dependencies mapped
```

### Step 3: 🛑 Mandatory Human Checkpoint

```
## 🛑 Pre-Implementation Checkpoint

Planning phase complete. Ready to begin implementation.

### 📋 Artifacts Created:
- Spec: specs/006-rtmp-health-monitoring/spec.md
- Plan: specs/006-rtmp-health-monitoring/plan.md
- Tasks: specs/006-rtmp-health-monitoring/tasks.md (12 tasks)
- Data Model: specs/006-rtmp-health-monitoring/data-model.md

### 📊 Implementation Scope:
- **Files to create**: 8 new files
- **Files to modify**: 2 existing files
- **Tests to write**: 6 test files
- **Estimated changes**: ~450 lines of code

### ⚠️ Pre-Implementation Checklist:
- [ ] Review spec.md for accuracy
- [ ] Review plan.md for architecture decisions
- [ ] Review tasks.md for task ordering and completeness
- [ ] Confirm branch: 006-rtmp-health-monitoring

---

**🚨 CONFIRMATION REQUIRED**

I will NOT proceed with implementation until you explicitly confirm.

**Type one of the following:**
- `proceed` or `yes` - Begin implementation
- `review <artifact>` - Show specific artifact for review
- `abort` - Cancel workflow
- `pause` - Save state and stop (resume later)
```

**User**: `proceed`

### Step 4: Implementation Phase Execution

```
## Workflow: Standard (Implementation Phase)

5. ✅ speckit-implement (45.2s)
   - Implemented all 12 tasks
   - Created 8 source files, 6 test files

6. ✅ speckit-test (8.3s)
   - Tests: 24/24 passing
   - Coverage: 89%
   - Lint: 0 errors
   - Types: 0 errors
```

### Step 5: Summary Output

```
## Workflow Complete: Standard

**Status**: ✅ Success
**Feature**: RTMP Health Monitoring (Branch: 006-rtmp-health-monitoring)
**Duration**: 69.0s

### Artifacts:
- Spec: specs/006-rtmp-health-monitoring/spec.md
- Plan: specs/006-rtmp-health-monitoring/plan.md
- Tasks: specs/006-rtmp-health-monitoring/tasks.md
- Data Model: specs/006-rtmp-health-monitoring/data-model.md

### Implementation:
- Source: apps/media-service/src/media_service/health/
- Tests: apps/media-service/tests/unit/test_health_monitor.py

### Next Steps:
- Review implementation in branch `006-rtmp-health-monitoring`
- Create PR: `gh pr create`
```
