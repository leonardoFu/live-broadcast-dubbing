---
name: speckit-worker-light
description: Lightweight dispatcher for single-feature development outside of milestones. Executes speckit commands one at a time with validation. This skill should be used when building a standalone feature from a description without milestone or progress tracking overhead.
---

# Speckit Worker Light

A lightweight dispatcher that executes speckit commands one at a time for single-feature development. Designed for building features outside of milestone tracking, with the same quality gates as speckit-worker but simplified state management.

---

## ⚠️ CRITICAL: SINGLE ITERATION MODE ⚠️

**This skill runs in an automated loop. Exit after ONE iteration.**

### MANDATORY BEHAVIOR:

1. **Execute exactly ONE speckit command** (e.g., `/speckit.specify`, `/speckit.plan`, `/speckit.implement`)
2. **Output a completion signal** (see below)
3. **IMMEDIATELY FINISH YOUR RESPONSE** - Do NOT continue with more work

### WHY THIS MATTERS:

- The outer loop (`loop.sh`) will restart Claude for the next iteration
- Each iteration gets fresh context and state
- If the response continues, the loop cannot proceed correctly

### HOW TO EXIT:

After outputting the completion signal, simply **end the response**. Do not:
- Start another speckit command
- Say "let me continue with..."
- Do any additional work

The loop will call again for the next step.

---

## Completion Signals

Output exactly ONE of these signals when appropriate:

| Signal | When |
|--------|------|
| `COMMAND_COMPLETE: <command>` | Single command finished and validated successfully |
| `FEATURE_COMPLETE: <feature-id>` | All phases complete AND PR merged |
| `WORKER_BLOCKED: <reason>` | Cannot proceed (validation failed, manual intervention needed) |

---

## Triggers

| Pattern | Action |
|---------|--------|
| `build: <feature-description>` | Start building a new feature |
| `build resume` | Resume from state file |
| `build status` | Report current progress |

### Examples

```
build: Add rate limiting to API endpoints
build: User avatar upload with S3 storage
build: WebSocket notifications for order status
build resume
build status
```

---

## State File

**Location**: `.specify/workflow-state/speckit-worker-light.json`

```typescript
interface LightWorkerState {
  // Feature identification
  feature_id: string;              // Generated slug from description
  feature_description: string;     // Original input description

  // Complexity assessment
  complexity: "LOW" | "MEDIUM" | "HIGH";
  complexity_reasoning: string;

  // Last action tracking
  last_command: string;            // "speckit.specify"
  last_command_status: "success" | "failed";
  last_command_timestamp: string;  // ISO timestamp
  last_command_output?: string;    // Brief result summary

  // Phase tracking (for one-phase-at-a-time implementation)
  current_phase: string | null;    // "Phase 1: Core Implementation"
  phases_completed: string[];      // ["Phase 1: Core Implementation", ...]

  // Feedback tracking (for one-feedback-at-a-time resolution)
  pending_feedback: string[];      // Unresolved feedback items from review.md
  feedback_resolved: string[];     // Resolved feedback items this cycle

  // Git/PR tracking
  feature_branch: string | null;   // "feature/<feature-id>"
  pr_number: number | null;        // GitHub PR number once created
  pr_url: string | null;           // Full PR URL
  pr_status: "none" | "created" | "approved" | "merged";

  // Workflow flags
  research_needed: boolean;
  research_done: boolean;
  analyze_done: boolean;
  review_done: boolean;
  reflect_done: boolean;

  // Counters
  iteration_count: number;
  started_at: string;              // ISO timestamp
}
```

---

## Execution Protocol

**Every iteration**: Read → Decide → Execute ONE → Validate → Update → STOP

### Step 0: INITIALIZE (First Iteration Only)

When starting a new feature:

1. **Generate feature ID** from description:
   ```
   "Add rate limiting to API endpoints" → "add-rate-limiting-to-api-endpoints"
   ```

2. **Assess complexity**:
   | Complexity | Criteria |
   |------------|----------|
   | **LOW** | Single file, no external deps, < 100 LOC estimated |
   | **MEDIUM** | 2-5 files, simple external deps, 100-500 LOC estimated |
   | **HIGH** | 5+ files, complex integrations, security/auth, > 500 LOC estimated |

   **Automatic HIGH triggers**:
   - External API integrations (Redis, S3, databases)
   - Authentication/authorization code
   - Payment or financial processing
   - ML model serving or data pipelines
   - Performance-critical paths

3. **Create fresh branch from origin/main**:
   ```bash
   git fetch origin
   git checkout main
   git reset --hard origin/main
   git checkout -b feature/<feature-id>
   ```

4. **Initialize state file** with assessed complexity

### Step 1: READ State

1. Read state file `.specify/workflow-state/speckit-worker-light.json`
   - If not exists and prompt is `build resume`: `WORKER_BLOCKED: No state file found`
   - If not exists and prompt is `build: <desc>`: Initialize new state (Step 0)
2. Check current git branch - ensure on correct feature branch

### Step 2: DECIDE Next Command

Use the Decision Tree below to determine exactly ONE command to run.

### Step 3: EXECUTE One Command

Run the selected `/speckit.*` command directly (NOT via subagents).

**IMPORTANT for `/speckit.implement`**: Only implement **ONE phase** from tasks.md OR solve **ONE feedback item** from review.md per iteration.

### Step 4: VALIDATE Result

Check validation criteria for the executed command. See Validation Rules below.

### Step 5: UPDATE State

- **If validation passes**: Update state file
- **If validation fails**: Update state file with failure status

### Step 6: STOP AND EXIT

Output completion signal and **>>> STOP**.

---

## Decision Tree

```
┌─────────────────────────────────────────────────────────────────┐
│ spec.md missing?                                                │
│ └─> IF NEW FEATURE (no feature_branch in state):                │
│     └─> Assess complexity                                       │
│     └─> Create fresh branch from origin/main                    │
│     └─> UPDATE state: feature_id, complexity, feature_branch    │
│ └─> Ensure on correct feature branch                            │
│ └─> Run: /speckit.specify <feature-description>                 │
│ └─> VALIDATE: spec.md exists in specs/<feature-id>/             │
│ └─> git add + git commit                                        │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ spec.md exists, plan.md missing?                                │
│ └─> Read specs/<feature-id>/spec.md                             │
│ └─> Check for [NEEDS CLARIFICATION] markers                     │
│     ├─> If found: Run /speckit.clarify, commit → STOP           │
│     └─> If clear: Check for research triggers                   │
│         ├─> If research needed & not done:                      │
│         │   Run /speckit.research, commit → STOP                │
│         └─> If no research needed OR research done:             │
│             Run /speckit.plan, commit → STOP                    │
│ └─> VALIDATE: plan.md exists (or clarifications resolved)       │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ plan.md exists, tasks.md missing?                               │
│ └─> Run: /speckit.tasks                                         │
│ └─> VALIDATE: tasks.md exists with task items                   │
│ └─> git add + git commit                                        │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ tasks.md exists, implementation incomplete?                     │
│ └─> Check if analyze needed (HIGH complexity & not yet done):   │
│     └─> If needed: Run /speckit.analyze → STOP                  │
│ └─> **CRITICAL**: Check if specs/<feature-id>/research.md exists│
│     └─> If exists: Read file contents into context BEFORE impl  │
│     └─> Pass research findings to /speckit.implement            │
│ └─> Identify NEXT INCOMPLETE PHASE in tasks.md                  │
│ └─> Run: /speckit.implement <phase-name> (ONE PHASE ONLY!)      │
│ └─> VALIDATE: Phase tasks [X], tests pass                       │
│ └─> git add + git commit (commit after each phase)              │
│ └─> Check if MORE PHASES remain:                                │
│     ├─> If phases remain:                                       │
│     │   └─> Output: COMMAND_COMPLETE: speckit.implement <phase> │
│     │   └─> >>> STOP (next iteration continues)                 │
│     └─> If all phases done:                                     │
│         └─> Check if review needed (MEDIUM/HIGH complexity)     │
│         └─> >>> STOP                                            │
├─────────────────────────────────────────────────────────────────┤
│ Implementation done, review needed & !review_done?              │
│ └─> Run: /speckit.review                                        │
│ └─> VALIDATE: review.md exists                                  │
│ └─> Check review.md for unresolved feedback (- [ ] items):      │
│     ├─> If unresolved feedback found:                           │
│     │   └─> Mark implementation as needing rework               │
│     │   └─> Pass feedback to next /speckit.implement            │
│     │   └─> >>> STOP                                            │
│     └─> If no unresolved feedback:                              │
│         └─> Set review_done=true                                │
│         └─> >>> STOP                                            │
├─────────────────────────────────────────────────────────────────┤
│ Implementation done, review_done (or not needed), !reflect_done?│
│ └─> Run: /speckit.reflect                                       │
│ └─> git add + git commit (if CLAUDE.md changed)                 │
│ └─> Set reflect_done=true                                       │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ All phases complete, reflect_done, pr_status="none"?            │
│ └─> Push branch, create PR, check status, merge if ready:       │
│     git push -u origin feature/<feature-id>                     │
│     gh pr create --base main --title "<feature-id>" ...         │
│     gh pr view --json mergeable,state,reviewDecision            │
│     ├─> If checks failing: WORKER_BLOCKED: PR checks failing    │
│     ├─> If changes requested: WORKER_BLOCKED: PR needs changes  │
│     ├─> If pending review: WORKER_BLOCKED: PR awaiting review   │
│     ├─> If mergeable & approved (or no review required):        │
│     │   └─> gh pr merge --squash --delete-branch                │
│     │   └─> git checkout main && git pull origin main           │
│     │   └─> Output: FEATURE_COMPLETE: <feature-id>              │
│     │   └─> >>> STOP                                            │
├─────────────────────────────────────────────────────────────────┤
│ pr_status = "created" (blocked on previous iteration)?          │
│ └─> Re-check PR status and attempt merge (same as above)        │
│ └─> >>> STOP                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Optional Commands - When to Include

| Command | Include When | Purpose |
|---------|--------------|---------|
| `/speckit.clarify` | spec.md contains `[NEEDS CLARIFICATION]` markers | Resolves ambiguities before planning |
| `/speckit.research` | spec.md has TBD/TODO items, external library integrations, or complex technology choices | Resolves technical unknowns before planning |
| `/speckit.analyze` | tasks.md created AND complexity is HIGH | Validates cross-artifact consistency |
| `/speckit.review` | After implementation completes, for MEDIUM/HIGH complexity | Post-implementation cleanup, code quality |
| `/speckit.reflect` | After review completes (or after implement if no review) | Captures learnings to CLAUDE.md |

### Research Triggers

Run research when spec.md contains ANY of:
- `TBD`, `TODO`, `[NEEDS CLARIFICATION]` markers related to technology choices
- External library/framework references (e.g., "use Redis", "integrate with S3")
- Complex patterns (caching, queuing, authentication, ML pipelines)
- Version-specific API questions
- Performance requirements needing validation

**IMPORTANT**: When `research.md` exists, ALWAYS load it into context before running `/speckit.implement`.

### Review Triggers

Run review when:
- Feature complexity is MEDIUM or HIGH
- Feature touches security/authentication code
- After first implementation attempt completes

---

## Validation Rules

| Command | Validation Criteria | On Success | On Failure |
|---------|---------------------|------------|------------|
| speckit.specify | `specs/<feature-id>/spec.md` exists, commit created | Continue | `WORKER_BLOCKED: specify failed` |
| speckit.clarify | `[NEEDS CLARIFICATION]` count reduced OR clarifications section added | Continue to plan | Retry or WORKER_BLOCKED |
| speckit.research | `specs/<feature-id>/research.md` exists with Technologies section | Set research_done=true | Log warning, continue |
| speckit.plan | `specs/<feature-id>/plan.md` exists, commit created | Continue | `WORKER_BLOCKED: plan failed` |
| speckit.tasks | `specs/<feature-id>/tasks.md` exists with `- [ ]` items, commit created | Continue | `WORKER_BLOCKED: tasks failed` |
| speckit.analyze | Report generated, no CRITICAL issues | Continue to implement | If CRITICAL: `WORKER_BLOCKED` |
| speckit.implement | **One phase** tasks `[X]` OR **one feedback** resolved, tests pass, commit created | Continue if phases remain | `WORKER_BLOCKED: implement failed` |
| speckit.review | `specs/<feature-id>/review.md` exists | Check for unresolved feedback | Log warning, continue |
| speckit.reflect | `CLAUDE.md` updated OR "no new learnings" message | Set reflect_done=true | Log warning, continue |
| pr-workflow | PR created, checks pass, merged successfully | FEATURE_COMPLETE | `WORKER_BLOCKED: <reason>` |

---

## Example Execution Traces

### LOW Complexity Feature (4-5 iterations)

```
Iter 1: specify   → assess LOW, branch + spec + commit   >>> STOP
Iter 2: plan      → COMMAND_COMPLETE + commit            >>> STOP
Iter 3: tasks     → COMMAND_COMPLETE + commit            >>> STOP
Iter 4: implement → single phase + commit                >>> STOP
Iter 5: pr-workflow → push + PR + merge → FEATURE_COMPLETE >>> STOP
```

### MEDIUM Complexity Feature (6-8 iterations)

```
Iter 1: specify   → assess MEDIUM, branch + spec + commit >>> STOP
Iter 2: plan      → COMMAND_COMPLETE + commit             >>> STOP
Iter 3: tasks     → COMMAND_COMPLETE + commit             >>> STOP
Iter 4: implement Phase 1 → COMMAND_COMPLETE + commit     >>> STOP
Iter 5: implement Phase 2 → COMMAND_COMPLETE + commit     >>> STOP
Iter 6: reflect   → COMMAND_COMPLETE + commit             >>> STOP
Iter 7: pr-workflow → push + PR + merge → FEATURE_COMPLETE >>> STOP
```

### HIGH Complexity Feature (10-15 iterations)

```
Iter 1:  specify   → assess HIGH, branch + spec + commit  >>> STOP
Iter 2:  research  → COMMAND_COMPLETE + commit            >>> STOP
Iter 3:  plan      → COMMAND_COMPLETE + commit            >>> STOP
Iter 4:  tasks     → COMMAND_COMPLETE + commit            >>> STOP
Iter 5:  analyze   → COMMAND_COMPLETE                     >>> STOP
Iter 6:  implement Phase 1 → COMMAND_COMPLETE + commit    >>> STOP
Iter 7:  implement Phase 2 → COMMAND_COMPLETE + commit    >>> STOP
Iter 8:  implement Phase 3 → COMMAND_COMPLETE + commit    >>> STOP
Iter 9:  review    → Found 2 feedback items               >>> STOP
Iter 10: implement feedback-1 → COMMAND_COMPLETE + commit >>> STOP
Iter 11: implement feedback-2 → COMMAND_COMPLETE + commit >>> STOP
Iter 12: review    → All resolved, review_done=true       >>> STOP
Iter 13: reflect   → Learnings captured + commit          >>> STOP
Iter 14: pr-workflow → push + PR + merge → FEATURE_COMPLETE >>> STOP
```

---

## Constraints

### MUST

- Validate command result before updating state
- Write state file at END of every iteration
- Use `/speckit.*` commands directly (not subagents)
- Re-run `/speckit.implement` with feedback when review has unresolved items
- Run `/speckit.reflect` before PR workflow to capture learnings
- **Complete PR workflow (push → create → check → merge) in single iteration**
- **Wait for PR to be merged before outputting FEATURE_COMPLETE**
- **Use squash merge** to keep main branch history clean

### MUST NOT

- Execute multiple speckit commands in one iteration
- **Implement multiple phases in a single `/speckit.implement` call**
- **Resolve multiple feedback items in a single `/speckit.implement` call**
- Skip validation steps
- Modify constitution.md without explicit user approval
- Skip `/speckit.reflect` - learnings must be captured before PR
- **Call `/speckit.implement` without loading `research.md` when it exists**
- **Work on main branch directly** - always use feature branches
- **Mark feature complete before PR is merged**
- **Force push to main branch**
- **Merge without passing CI checks**

---

## Error Recovery

| Error Type | Detection | Recovery |
|------------|-----------|----------|
| Command fails | Non-zero exit or missing output file | Log error, WORKER_BLOCKED |
| Validation fails | Expected file/content not found | Don't update state, STOP for retry |
| Test failure | pytest returns non-zero | WORKER_BLOCKED with test output |
| Git conflict | Merge conflict during branch creation | `git reset --hard origin/main`, retry |
| Branch exists | Feature branch already exists | Check state - resume if same feature |
| PR checks failing | CI/CD checks not passing | WORKER_BLOCKED: fix failing checks |
| PR changes requested | Reviewer requested changes | WORKER_BLOCKED: address review comments |
| PR merge conflict | Branch diverged from main | Rebase: `git fetch origin && git rebase origin/main` |

### On WORKER_BLOCKED

1. Output blocking reason with details
2. Save state with `last_command_status: "failed"`
3. **>>> STOP**
4. User must resolve issue before next iteration

---

## Differences from speckit-worker

| Aspect | speckit-worker | speckit-worker-light |
|--------|----------------|---------------------|
| Input | Milestone ID → looks up features in MILESTONES.md | Feature description directly |
| Progress tracking | Updates `docs/progress.md` | None - state file only |
| Feature source | Reads from `docs/MILESTONES.md` | Takes description from prompt |
| State file | `speckit-worker.json` | `speckit-worker-light.json` |
| Complexity | Determined by feature definition | Auto-assessed from description |
| Use case | Batch processing of milestone features | Single standalone feature |

---

*Speckit Worker Light - Build one feature at a time, no milestone overhead.*
