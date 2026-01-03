---
description: Iterative problem-solving workflow - investigates issues, applies fixes, and verifies against success criteria until resolved
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Task, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Problem Solver

Invoke this command to start an iterative problem-solving workflow that:
1. Creates a debug context with the issue and success criteria
2. Researches the codebase to identify potential causes
3. Applies fixes and verifies against success criteria
4. Loops until resolved or max iterations reached

## Input

$ARGUMENTS

## Execution Protocol

### PHASE 1: PARSE REQUEST

Parse the user's problem description to extract:

```
1. Issue Description: What's broken?
2. Success Criteria: How do we know it's fixed?
3. Verification Command: What command validates the fix?
```

**Examples**:

| User Input | Issue | Success Criteria | Verification |
|------------|-------|------------------|--------------|
| "Fix test_full_pipeline timeout" | E2E test times out | All tests pass | `pytest tests/e2e/test_full_pipeline.py -v` |
| "Audio sync drift > 100ms" | A/V sync exceeds threshold | offset < 100ms | `make e2e-test -k sync` |
| "RTMP output has no audio" | Audio stream missing | Audio present in output | `ffprobe rtmp://localhost/live/output` |

If not specified, prompt user:
```
To solve this problem, I need:
1. Success Criteria - How do we know it's fixed?
2. Verification Command - What command should I run to verify?
```

### PHASE 2: CREATE DEBUG CONTEXT

```bash
# Generate unique debug ID
debug_id="debug-$(date +%Y%m%d%H%M%S)"
debug_dir="specs/${debug_id}"

# Create directory
mkdir -p "${debug_dir}"

# Create context.md from template
# Read: .specify/templates/debug-context-template.md
# Replace placeholders with extracted values
# Write: ${debug_dir}/context.md
```

**Context file structure**:
```markdown
# Debug Context: [Issue Title]

**Debug ID**: debug-YYYYMMDDHHMMSS
**Created**: ISO8601 timestamp
**Status**: investigating
**Iteration**: 1 / 5

## Issue Description
[From user input]

## Success Criteria
- SC-001: [Primary criterion]
- SC-002: [Secondary if applicable]

## Verification Command
```bash
[Command to run]
```

## Investigation History
### Iteration 1
**Status**: pending
```

### PHASE 3: RESEARCH LOOP

```
max_iterations = 5
iteration = 1

while iteration <= max_iterations:
    # 3a. Invoke researcher agent
    Task(subagent_type="debug-researcher", prompt="""
    WORKFLOW_CONTEXT:
    {
      "workflow_id": "<uuid>",
      "debug_id": "${debug_id}",
      "debug_dir": "${debug_dir}",
      "context_file": "${debug_dir}/context.md",
      "iteration": ${iteration},
      "max_iterations": 5,
      "issue_description": "${issue_description}",
      "success_criteria": ${success_criteria_json},
      "verification_command": "${verification_command}",
      "previous_results": ${previous_results}
    }
    USER_REQUEST: ${original_request}
    """)

    # 3b. Parse researcher output
    research_findings = parse_json(researcher_output)

    # 3c. Invoke executor agent
    Task(subagent_type="debug-executor", prompt="""
    WORKFLOW_CONTEXT:
    {
      "workflow_id": "<uuid>",
      "debug_id": "${debug_id}",
      "debug_dir": "${debug_dir}",
      "context_file": "${debug_dir}/context.md",
      "iteration": ${iteration},
      "max_iterations": 5,
      "issue_description": "${issue_description}",
      "success_criteria": ${success_criteria_json},
      "verification_command": "${verification_command}"
    }
    RESEARCH_CONTEXT:
    ${research_findings}
    USER_REQUEST: ${original_request}
    """)

    # 3d. Parse executor output
    executor_result = parse_json(executor_output)

    # 3e. Check if success criteria met
    if executor_result.verification_result.success_criteria_met:
        status = "resolved"
        break

    # 3f. Update context with new issue
    update_context_file(debug_dir, executor_result.new_issue)

    # 3g. Store results for next iteration
    previous_results = {
        "debug-researcher": research_findings,
        "debug-executor": executor_result
    }

    iteration++
end while

if iteration > max_iterations:
    status = "exhausted"
```

### PHASE 4: GENERATE REPORT

**Success Report** (status = resolved):

```markdown
## Problem Solved

**Debug ID**: debug-XXXXXX
**Iterations Used**: 2 / 5
**Total Time**: ~15 minutes

### Issue
[Original issue description]

### Solution
[Description of fix that worked]

### Files Modified
- path/to/file1.py: [change description]
- path/to/file2.py: [change description]

### Verification
```bash
$ [verification command]
[success output]
```
Status: PASS

### Debug Context
Full investigation history: specs/debug-XXXXXX/context.md
```

**Exhausted Report** (status = exhausted):

```markdown
## Unable to Resolve

**Debug ID**: debug-XXXXXX
**Iterations Used**: 5 / 5

### Issue
[Original issue description]

### Investigation Summary

| Iteration | Attempt | Result | Progress |
|-----------|---------|--------|----------|
| 1 | [fix attempted] | FAIL | [any progress] |
| 2 | [fix attempted] | FAIL | [any progress] |
| ... | ... | ... | ... |

### Current State
[What the error looks like now]

### Recommendations
- [ ] Manual investigation of [area]
- [ ] Consider [alternative approach]
- [ ] Check [external dependency]

### Debug Context
Full investigation history: specs/debug-XXXXXX/context.md

### Debug Artifacts
- [List any debug logs still in code]
- [List any temporary changes]
```

---

## Configuration

| Setting | Default | Override |
|---------|---------|----------|
| max_iterations | 5 | `--max-iterations=N` |
| verification_timeout | 300s | `--timeout=Ns` |
| auto_cleanup_logs | true | `--keep-logs` |

---

## Examples

### Basic Usage

```
/problem-solver Fix test_full_pipeline failing with timeout

# Will prompt for:
# - Success criteria
# - Verification command
```

### With Success Criteria

```
/problem-solver Fix audio sync drift, success when A/V offset < 100ms, verify with: make e2e-test -k sync
```

### Quick Patterns

```
# Fix a specific test
/problem-solver Fix tests/e2e/test_full_pipeline.py::test_output_has_audio

# Fix with explicit verification
/problem-solver RTMP output missing audio, verify with: ffprobe -v error -show_streams rtmp://localhost/live/test

# Debug a behavior
/problem-solver STS not receiving fragments, success when fragment:data events logged
```

---

## Handoffs

- **Resolved**: Report success, show files modified
- **Exhausted**: Report investigation summary, show recommendations
- **Error**: Show error details, suggest manual debugging steps

---

## Constraints

**MUST**:
- Create debug context before any investigation
- Update context.md after each iteration
- Verify success criteria after each fix
- Clean up debug logs after resolution
- Stop at max_iterations

**MUST NOT**:
- Skip context creation
- Apply fixes without verification
- Leave debug logs after success
- Continue past max_iterations without reporting
