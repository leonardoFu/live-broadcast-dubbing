---
name: speckit-worker
description: Dispatcher for ralph-wiggum that executes speckit commands one at a time with validation
---

# Speckit Worker

A lightweight dispatcher that executes speckit commands one at a time, validates results, and updates progress. Designed for ralph-wiggum automation loops.

---

## ⚠️ CRITICAL: SINGLE ITERATION MODE ⚠️

**This skill runs in an automated loop. You MUST exit after ONE iteration.**

### MANDATORY BEHAVIOR:

1. **Execute exactly ONE speckit command** (e.g., `/speckit.specify`, `/speckit.plan`, `/speckit.implement`)
2. **Output a completion signal** (see below)
3. **IMMEDIATELY FINISH YOUR RESPONSE** - Do NOT continue with more work

### WHY THIS MATTERS:

- The outer loop (`loop.sh`) will restart Claude for the next iteration
- Each iteration gets fresh context and state
- If you don't exit, the loop cannot proceed correctly

### HOW TO EXIT:

After outputting your completion signal, simply **end your response**. Do not:
- Start another speckit command
- Say "let me continue with..."
- Do any additional work

The loop will call you again for the next step.

---

## Completion Signals

Output exactly ONE of these signals when appropriate:

| Signal | When |
|--------|------|
| `COMMAND_COMPLETE: <command>` | Single command finished and validated successfully |
| `FEATURE_COMPLETE: <feature-id>` | All phases complete AND PR merged for a feature |
| `MILESTONE_COMPLETE` | All features in milestone done |
| `WORKER_BLOCKED: <reason>` | Cannot proceed (validation failed, manual intervention needed) |

---

## Triggers

| Pattern | Action |
|---------|--------|
| `worker: <milestone-id>` | Start/resume milestone (e.g., `worker: M2`) |
| `worker resume` | Resume from state file |
| `worker status` | Report current progress |
| `worker feature <id>` | Force specific feature (e.g., `worker feature 007`) |

---

## State File

**Location**: `.specify/workflow-state/speckit-worker.json`

```typescript
interface SpeckitWorkerState {
  // Current context
  current_milestone: string;          // "M2"
  current_feature: string | null;     // "006-text-processing"

  // Last action tracking
  last_command: string;               // "speckit.specify"
  last_command_status: "success" | "failed";
  last_command_timestamp: string;     // ISO timestamp
  last_command_output?: string;       // Brief result summary

  // Phase tracking (for one-phase-at-a-time implementation)
  current_phase: string | null;       // "Phase 1: Core Implementation"
  phases_completed: string[];         // ["Phase 1: Core Implementation", ...]

  // Feedback tracking (for one-feedback-at-a-time resolution)
  pending_feedback: string[];         // Unresolved feedback items from review.md
  feedback_resolved: string[];        // Resolved feedback items this cycle

  // Git/PR tracking
  feature_branch: string | null;      // "feature/006-text-processing"
  pr_number: number | null;           // GitHub PR number once created
  pr_url: string | null;              // Full PR URL
  pr_status: "none" | "created" | "approved" | "merged"; // PR lifecycle state

  // Counters
  iteration_count: number;
  features_completed: string[];       // ["001-config-settings", ...]

  // Optional command tracking
  clarify_needed: boolean;            // Set after checking spec for [NEEDS CLARIFICATION]
  research_needed: boolean;           // Set if spec has unknowns/TBDs or complex tech choices
  research_done: boolean;             // Reset per feature
  analyze_done: boolean;              // Reset per feature
  review_done: boolean;               // Reset per feature, tracks if post-impl review passed
  reflect_done: boolean;              // Reset per feature, tracks if learnings captured
}
```

---

## Execution Protocol

**Every iteration**: Read → Decide → Execute ONE → Validate → Update → STOP

### Step 0: ENSURE Fresh Branch (Before Starting New Feature)

When starting a new feature (not resuming an in-progress one):

```bash
# Fetch latest from remote
git fetch origin

# Checkout and reset to latest main
git checkout main
git reset --hard origin/main

# Create feature branch
git checkout -b feature/<feature-id>
# Example: git checkout -b feature/006-text-processing
```

**IMPORTANT**: Always start from a fresh `origin/main` to avoid merge conflicts and ensure clean history.

### Step 1: READ State & Progress

1. Read state file `.specify/workflow-state/speckit-worker.json`
   - If not exists: Initialize with target milestone
2. Read `docs/progress.md` to determine current feature status
3. Read `docs/MILESTONES.md` if needed to get feature definition
4. Check current git branch - ensure we're on the correct feature branch

### Step 2: DECIDE Next Command

Use the Command Selection Logic below to determine exactly ONE command to run.

### Step 3: EXECUTE One Command

Run the selected `/speckit.*` command directly (NOT via subagents).

**IMPORTANT for `/speckit.implement`**: Only implement **ONE phase** from tasks.md OR solve **ONE feedback item** from review.md per iteration. Never do more. This ensures incremental progress with validation at each step.

### Step 4: VALIDATE Result

Check validation criteria for the executed command. See Validation Rules below.

### Step 5: UPDATE Progress

- **If validation passes**: Update `docs/progress.md` and state file
- **If validation fails**: Update state file with failure, DO NOT update progress.md

### Step 6: STOP AND EXIT

Output completion signal and **>>> STOP**.

**CRITICAL**: After outputting the signal, you MUST immediately end your response. Do NOT:
- Execute another command
- Continue with "next, I'll..."
- Do any additional work

The outer loop will restart you for the next iteration. Your job for THIS iteration is done.

---

## Command Selection Logic

### Core Commands (Always Required)

```
/speckit.specify → /speckit.plan → /speckit.tasks → /speckit.implement
```

### Optional Commands - When to Include

| Command | Include When | Purpose |
|---------|--------------|---------|
| `/speckit.clarify` | spec.md contains `[NEEDS CLARIFICATION]` markers | Resolves ambiguities before planning |
| `/speckit.research` | spec.md has TBD/TODO items, external library integrations, or complex technology choices | Resolves technical unknowns via Context7/web before planning |
| `/speckit.checklist` | Feature is P1 AND involves security/API/UX domains | Validates requirements quality |
| `/speckit.analyze` | tasks.md created AND feature is on critical path | Validates cross-artifact consistency |
| `/speckit.review` | After implementation completes, especially for complex features | Post-implementation cleanup, constitution compliance, code quality |
| `/speckit.reflect` | After review completes (or after implement if no review) | Captures learnings to CLAUDE.md, proposes constitution amendments |

### Research Triggers (when to run `/speckit.research`)

Run research when spec.md contains ANY of:
- `TBD`, `TODO`, `[NEEDS CLARIFICATION]` markers related to technology choices
- External library/framework references (e.g., "use Redis", "integrate with S3")
- Complex patterns (caching, queuing, authentication, ML pipelines)
- Version-specific API questions
- Performance requirements needing validation

**IMPORTANT**: When `research.md` exists, ALWAYS load it into context before running `/speckit.implement`. This means:
1. Read `specs/<feature>/research.md` file contents
2. Include the research findings (especially "Technologies Researched" and "Implementation Recommendations") when invoking `/speckit.implement`
3. The implement agent needs this context to use correct APIs, patterns, and library versions

### Review Triggers (when to run `/speckit.review`)

Run review when:
- Feature complexity is MEDIUM or HIGH (multiple files, external integrations)
- Feature touches security/authentication code
- Feature is on critical path
- After first implementation attempt completes

**IMPORTANT**: If review.md contains unresolved feedback items (`- [ ]` in Feedback section), re-run `/speckit.implement` with the feedback before marking feature complete.

### Feature Complexity Assessment

Before deciding on optional commands, assess feature complexity:

| Complexity | Criteria | Research? | Review? |
|------------|----------|-----------|---------|
| **LOW** | Single file, no external deps, < 100 LOC | No | No |
| **MEDIUM** | 2-5 files, simple external deps, 100-500 LOC | If unknowns | Optional |
| **HIGH** | 5+ files, complex integrations, security/auth, > 500 LOC | Yes | Yes |

**Automatic HIGH complexity triggers**:
- External API integrations (Redis, S3, databases)
- Authentication/authorization code
- Payment or financial processing
- ML model serving or data pipelines
- Performance-critical paths (noted in spec)

### Decision Tree

```
1. Read progress.md, find first feature with incomplete columns
2. Get feature definition from MILESTONES.md
3. Determine phase based on progress columns:

┌─────────────────────────────────────────────────────────────────┐
│ Spec = :x: ?                                                    │
│ └─> IF NEW FEATURE (no feature_branch in state):                │
│     └─> Create fresh branch from origin/main      │
│     └─> UPDATE state: feature_branch, pr_status="none"          │
│ └─> Ensure on correct feature branch                            │
│ └─> Get feature definition from MILESTONES.md                   │
│ └─> Run: /speckit.specify <feature-definition>                  │
│ └─> VALIDATE: spec.md exists in specs/<feature>/                │
│ └─> git add + git commit                                        │
│ └─> UPDATE: Spec column → :white_check_mark: Complete           │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ Spec = :white_check_mark:, Plan = :x: ?                         │
│ └─> Read specs/<feature>/spec.md                                │
│ └─> Check for [NEEDS CLARIFICATION] markers                     │
│     ├─> If found: Run /speckit.clarify, commit → STOP           │
│     └─> If clear: Check for research triggers (see above)       │
│         ├─> If research needed & not done:                      │
│         │   Run /speckit.research, commit → STOP                │
│         └─> If no research needed OR research done:             │
│             Run /speckit.plan, commit → STOP                    │
│ └─> VALIDATE: plan.md exists (or clarifications resolved)       │
│ └─> UPDATE: Plan column → :white_check_mark: Complete           │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ Plan = :white_check_mark:, Tasks = :x: ?                        │
│ └─> Run: /speckit.tasks                                         │
│ └─> VALIDATE: tasks.md exists with task items                   │
│ └─> git add + git commit                                        │
│ └─> UPDATE: Tasks column → :white_check_mark: Complete          │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ Tasks = :white_check_mark:, Implemented = :x: ?                 │
│ └─> Check if analyze needed (critical path & not yet done):     │
│     └─> If needed: Run /speckit.analyze → STOP                  │
│ └─> **CRITICAL**: Check if specs/<feature>/research.md exists:  │
│     └─> If exists: Read file contents into context BEFORE impl  │
│     └─> Pass research findings to /speckit.implement            │
│ └─> Identify NEXT INCOMPLETE PHASE in tasks.md                  │
│ └─> Run: /speckit.implement <phase-name> (ONE PHASE ONLY!)      │
│ └─> VALIDATE: Phase tasks [X], tests pass                       │
│ └─> git add + git commit (commit after each phase)              │
│ └─> Check if MORE PHASES remain:                                │
│     ├─> If phases remain: Keep Implemented = :x:                │
│     │   └─> Output: COMMAND_COMPLETE: speckit.implement <phase> │
│     │   └─> >>> STOP (next iteration continues)                 │
│     └─> If all phases done:                                     │
│         └─> Check if review needed (see Review Triggers above)  │
│         └─> If needed & not done: Set review_needed=true        │
│         └─> UPDATE: Implemented column → :white_check_mark:     │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ Implemented = :white_check_mark:, review_needed & !review_done? │
│ └─> Run: /speckit.review                                        │
│ └─> VALIDATE: review.md exists                                  │
│ └─> Check review.md for unresolved feedback (- [ ] items):      │
│     ├─> If unresolved feedback found:                           │
│     │   └─> Set Implemented = :x: (re-implement needed)         │
│     │   └─> Pass feedback to next /speckit.implement            │
│     │   └─> >>> STOP                                            │
│     └─> If no unresolved feedback:                              │
│         └─> Set review_done=true                                │
│         └─> >>> STOP                                            │
├─────────────────────────────────────────────────────────────────┤
│ Implemented = :white_check_mark:, review_done, !reflect_done?   │
│ └─> Run: /speckit.reflect                                       │
│ └─> git add + git commit (if CLAUDE.md changed)                 │
│ └─> Set reflect_done=true                                       │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ All columns = :white_check_mark:, reflect_done, pr_status="none"│
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
│     │   └─> Reset state for next feature                        │
│     │   └─> Output: FEATURE_COMPLETE: <feature-id>              │
│     │   └─> >>> STOP                                            │
├─────────────────────────────────────────────────────────────────┤
│ pr_status = "created" (blocked on previous iteration)?          │
│ └─> Re-check PR status and attempt merge (same as above)        │
│ └─> >>> STOP                                                    │
├─────────────────────────────────────────────────────────────────┤
│ No more features in milestone?                                  │
│ └─> Output: MILESTONE_COMPLETE                                  │
│ └─> >>> STOP                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Validation Rules

| Command | Validation Criteria | On Success | On Failure |
|---------|---------------------|------------|------------|
| speckit.specify | `specs/<feature>/spec.md` exists, commit created | Update Spec column | `WORKER_BLOCKED: specify failed` |
| speckit.clarify | `[NEEDS CLARIFICATION]` count reduced OR clarifications section added | Continue to plan | Retry or WORKER_BLOCKED |
| speckit.research | `specs/<feature>/research.md` exists with Technologies section | Set research_done=true, continue to plan | Log warning, continue (non-blocking) |
| speckit.plan | `specs/<feature>/plan.md` exists, commit created | Update Plan column | `WORKER_BLOCKED: plan failed` |
| speckit.tasks | `specs/<feature>/tasks.md` exists with `- [ ]` items, commit created | Update Tasks column | `WORKER_BLOCKED: tasks failed` |
| speckit.checklist | Checklist file created (non-blocking) | Log success | Log warning, continue |
| speckit.analyze | Report generated, no CRITICAL issues | Continue to implement | If CRITICAL: `WORKER_BLOCKED` |
| speckit.implement | **One phase** tasks `[X]` OR **one feedback** resolved, `pytest` passes, commit created | Continue if phases remain, else update Implemented column | `WORKER_BLOCKED: implement failed` |
| speckit.review | `specs/<feature>/review.md` exists | Check for unresolved feedback | Log warning, continue (non-blocking) |
| speckit.reflect | `CLAUDE.md` updated with new learnings OR "no new learnings" message | Set reflect_done=true, commit if changes | Log warning, continue (non-blocking) |
| pr-workflow | PR created, checks pass, merged successfully | FEATURE_COMPLETE | `WORKER_BLOCKED: <specific reason>` |

### Validation Process

After each command, run these checks:

```bash
# After speckit.specify (includes branch creation if new feature + commit)
test -f specs/<feature>/spec.md
git log -1 --oneline  # Verify commit exists

# After speckit.research
test -f specs/<feature>/research.md && grep -q "## Technologies Researched" specs/<feature>/research.md

# After speckit.plan
test -f specs/<feature>/plan.md
git log -1 --oneline  # Verify commit exists

# After speckit.tasks
grep -q "\- \[ \]" specs/<feature>/tasks.md
git log -1 --oneline  # Verify commit exists

# After speckit.implement (one phase at a time)
# Check that at least one more task was completed this iteration
grep -q "\- \[X\]" specs/<feature>/tasks.md && pytest
git log -1 --oneline  # Verify commit exists
# Count remaining incomplete tasks to determine if more phases needed
REMAINING=$(grep -c "^\- \[ \]" specs/<feature>/tasks.md 2>/dev/null || echo "0")

# After speckit.review
test -f specs/<feature>/review.md
# Check for unresolved feedback
UNRESOLVED=$(grep -c "^- \[ \]" specs/<feature>/review.md 2>/dev/null || echo "0")
if [ "$UNRESOLVED" -gt 0 ]; then
  echo "Review has $UNRESOLVED unresolved items - re-implement needed"
fi

# PR workflow (push + create + check + merge - all in one iteration)
git push -u origin feature/<feature-id>
gh pr create --base main --head feature/<feature-id> \
  --title "feat: <feature-id> - <feature-name>" \
  --body "## Summary
<feature description from MILESTONES.md>

## Changes
- Spec: specs/<feature>/spec.md
- Plan: specs/<feature>/plan.md
- Implementation: src/<feature-related-files>

## Testing
- All tests passing: \`pytest\`
"
PR_NUMBER=$(gh pr view --json number -q '.number')
# Check if mergeable and merge
gh pr view $PR_NUMBER --json mergeable,state,reviewDecision
gh pr merge $PR_NUMBER --squash --delete-branch
# Clean up local
git checkout main && git pull origin main
```

---

## Progress Update Rules

### When to Update progress.md

| Condition | Column Update |
|-----------|---------------|
| speckit.specify validates | Spec → `:white_check_mark: Complete` |
| speckit.plan validates | Plan → `:white_check_mark: Complete` |
| speckit.tasks validates | Tasks → `:white_check_mark: Complete` |
| speckit.implement validates | Implemented → `:white_check_mark: Complete` |
| Any validation fails | **DO NOT UPDATE** |

### How to Update progress.md

1. Read `docs/progress.md`
2. Find feature row by number (e.g., `| 006 |`)
3. Update the specific column
4. Update milestone progress counts in header
5. Add entry to Progress History section:
   ```
   | YYYY-MM-DD | <action> complete: <feature-id> | X |
   ```
6. Write updated progress.md

### Example Update

Before:
```markdown
| 006 | text-processing | :x: Not started | :x: Not started | :x: Not started | :x: Not started |
```

After speckit.specify:
```markdown
| 006 | text-processing | :white_check_mark: Complete | :x: Not started | :x: Not started | :x: Not started |
```

---

## Recording Learnings

### When to Update CLAUDE.md

- New pattern discovered during implementation
- Workaround for a library issue
- Important architectural decision

Use `/speckit.reflect` to capture these automatically (with deduplication).

### When to Update constitution.md

- **NEVER** during normal workflow
- Only when user explicitly approves a principle change
- Principle conflicts should be logged, not auto-resolved

`/speckit.reflect` may **propose** amendments but never auto-applies them.

---

## Example Execution Trace

### Simple Feature Flow (with git/PR)

```
Iter 1: specify   → branch created + spec + commit        >>> STOP
Iter 2: plan      → COMMAND_COMPLETE: speckit.plan + commit   >>> STOP
Iter 3: tasks     → COMMAND_COMPLETE: speckit.tasks + commit  >>> STOP
Iter 4: implement Phase 1 → COMMAND_COMPLETE + commit         >>> STOP
Iter 5: implement Phase 2 → COMMAND_COMPLETE + commit         >>> STOP
Iter 6: reflect   → COMMAND_COMPLETE + commit (if learnings)  >>> STOP
Iter 7: pr-workflow → push + PR + merge → FEATURE_COMPLETE    >>> STOP
```

### Complex Feature Flow (with research + review + reflect + PR)

```
Iter 1:  specify   → branch created + spec + commit       >>> STOP
Iter 2:  research  → COMMAND_COMPLETE + commit            >>> STOP
Iter 3:  plan      → COMMAND_COMPLETE + commit            >>> STOP
Iter 4:  tasks     → COMMAND_COMPLETE + commit            >>> STOP
Iter 5:  implement Phase 1 → COMMAND_COMPLETE + commit    >>> STOP
Iter 6:  implement Phase 2 → COMMAND_COMPLETE + commit    >>> STOP
Iter 7:  review    → Found 2 feedback items               >>> STOP
Iter 8:  implement feedback-1 → COMMAND_COMPLETE + commit >>> STOP
Iter 9:  implement feedback-2 → COMMAND_COMPLETE + commit >>> STOP
Iter 10: review    → All resolved, set review_done=true   >>> STOP
Iter 11: reflect   → Learnings captured + commit          >>> STOP
Iter 12: pr-workflow → push + PR + merge → FEATURE_COMPLETE >>> STOP
```

### When PR Blocked (review required or checks failing)

```
Iter 12: pr-workflow → WORKER_BLOCKED: PR awaiting review >>> STOP
... (user approves PR) ...
Iter 13: pr-workflow → PR merged → FEATURE_COMPLETE       >>> STOP
```

### Key Points Illustrated

- **One phase per iteration**: Iterations handle exactly one phase
- **One feedback per iteration**: Review feedback items resolved one at a time
- **Reflect before PR**: Learnings captured to CLAUDE.md before creating PR
- **PR workflow in single iteration**: Push, create, check, merge all happen together
- **Re-review after fixes**: Review re-runs to verify all feedback resolved

---

## Constraints

### MUST

- Validate command result before updating progress
- Write state file at END of every iteration
- Use `/speckit.*` commands directly (not subagents)
- Re-run `/speckit.implement` with feedback when review has unresolved items
- Reset `research_done`, `analyze_done`, `review_done`, `reflect_done`, `feature_branch`, `pr_number`, `pr_url`, `pr_status` when switching features
- Run `/speckit.reflect` before PR workflow to capture learnings in the branch
- **Complete PR workflow (push → create → check → merge) in single iteration**
- **Wait for PR to be merged before marking feature complete**
- **Use squash merge** to keep main branch history clean

### MUST NOT

- Execute multiple speckit commands in one iteration
- **Implement multiple phases in a single `/speckit.implement` call**
- **Resolve multiple feedback items in a single `/speckit.implement` call**
- Update progress.md if validation fails
- Skip validation steps
- Auto-continue to next milestone after completion
- Modify constitution.md without explicit user approval (even via `/speckit.reflect`)
- Skip `/speckit.reflect` - learnings must be captured before PR
- Skip review for HIGH complexity features
- Ignore unresolved review feedback
- **Call `/speckit.implement` without loading `research.md` when it exists** - research findings contain critical API patterns and library versions
- **Work on main branch directly** - always use feature branches
- **Mark feature complete before PR is merged**
- **Force push to main branch** (force-with-lease on feature branches OK for rebase)
- **Merge without passing CI checks**

---

## Error Recovery

| Error Type | Detection | Recovery |
|------------|-----------|----------|
| Command fails | Non-zero exit or missing output file | Log error, WORKER_BLOCKED |
| Validation fails | Expected file/content not found | Don't update progress, STOP for retry |
| Test failure | pytest returns non-zero | WORKER_BLOCKED with test output |
| Missing dependency | Feature depends on incomplete feature | Skip to blocked, try next feature |
| Git conflict | Merge conflict during branch creation | `git reset --hard origin/main`, retry |
| Branch exists | Feature branch already exists | Check state - resume if same feature, error if different |
| PR checks failing | CI/CD checks not passing | WORKER_BLOCKED: fix failing checks |
| PR changes requested | Reviewer requested changes | WORKER_BLOCKED: address review comments |
| PR merge conflict | Branch diverged from main | Rebase: `git fetch origin && git rebase origin/main` |
| PR not mergeable | GitHub reports not mergeable | Check mergeable status, resolve blockers |

### On WORKER_BLOCKED

1. Output blocking reason with details
2. Save state with `last_command_status: "failed"`
3. **>>> STOP**
4. User must resolve issue before next iteration

### Git-Specific Recovery

```bash
# If branch creation fails due to existing branch (resuming feature)
git checkout feature/<feature-id>
git fetch origin
git rebase origin/main  # Ensure up-to-date

# If merge conflict during rebase
git rebase --abort  # Safe recovery
# Then: WORKER_BLOCKED: merge conflict needs manual resolution

# If PR has merge conflicts
git fetch origin
git rebase origin/main
git push --force-with-lease  # Safe force push to feature branch only
```

---

*Speckit Worker - Execute one command at a time, commit changes, create PRs, validate, update progress, STOP.*
