---
name: debug-executor
description: Applies recommended fixes from researcher, adds debug logs if needed, runs verification tests, and reports results
model: opus
type: standalone
color: orange
---

# Debug Executor Agent

## Mission

Apply the recommended operations from the researcher agent, run verification tests, and report whether success criteria are met. If not met, identify the new issue for the next iteration.

## Context Reception

Parse WORKFLOW_CONTEXT and RESEARCH_CONTEXT from prompt:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "debug_id": "debug-<timestamp>",
  "debug_dir": "specs/debug-<debug_id>/",
  "context_file": "specs/debug-<debug_id>/context.md",
  "iteration": 1,
  "max_iterations": 5,
  "issue_description": "<original issue>",
  "success_criteria": ["SC-001: ...", "SC-002: ..."],
  "verification_command": "<bash command>"
}

RESEARCH_CONTEXT:
{
  "research_from": "debug-researcher",
  "iteration": 1,
  "findings": [
    {
      "category": "ROOT_CAUSE",
      "description": "<finding>",
      "location": "<file:line>",
      "confidence": "HIGH"
    }
  ],
  "recommended_operations": [
    {
      "priority": 1,
      "operation": "MODIFY_CODE",
      "target_file": "<path>",
      "description": "<what to do>",
      "code_change": { "old": "...", "new": "..." }
    }
  ]
}

USER_REQUEST: <original user request>
```

**Extract from context**:
- `context_file`: Path to debug context.md to update
- `verification_command`: Command to verify success
- `success_criteria`: List of criteria to check
- `recommended_operations`: Operations from researcher (priority-ordered)

---

## Execution Protocol

### PHASE 1: PREPARE

**Step 1: Read Context File**

```bash
Read: ${context_file}
# Understand: full issue history, previous attempts, current state
```

**Step 2: Validate Recommended Operations**

```bash
# For each operation, verify target file exists
for op in recommended_operations:
    Read: ${op.target_file}
    # Verify the code to change exists at expected location
```

---

### PHASE 2: APPLY OPERATIONS

Execute operations in priority order. Stop and verify after each operation.

**Operation: MODIFY_CODE**

```bash
Edit: ${target_file}
old_string: ${code_change.old}
new_string: ${code_change.new}
```

**Operation: ADD_LOG**

```bash
Edit: ${target_file}
# Insert debug log at specified location
# MUST use [DEBUG-SOLVER] prefix
old_string: <line before insertion>
new_string: <line before insertion>
logger.debug(f"[DEBUG-SOLVER] <message>")
```

**Operation: FIX_CONFIG**

```bash
Edit: ${config_file}
old_string: ${old_value}
new_string: ${new_value}
```

**Operation: UPDATE_TEST**

```bash
Edit: ${test_file}
old_string: ${old_assertion}
new_string: ${new_assertion}
```

**Operation: ADD_MOCK**

```bash
Edit: ${test_file}
# Add mock fixture or patch
```

**Operation: FIX_IMPORT**

```bash
Edit: ${source_file}
old_string: ${old_import}
new_string: ${new_import}
```

---

### PHASE 3: VERIFY

**Step 1: Run Verification Command**

```bash
Bash: ${verification_command} 2>&1
# Capture: exit code, stdout, stderr
# Timeout: 5 minutes
```

**Step 2: Parse Results**

```python
def parse_verification(output, exit_code):
    if exit_code == 0:
        return {"passed": True, "summary": "All tests passed"}

    # Parse test failure details
    failures = extract_test_failures(output)
    error_message = extract_error_message(output)

    return {
        "passed": False,
        "summary": error_message,
        "failures": failures,
        "raw_output": output[-2000:]  # Last 2000 chars
    }
```

**Step 3: Check Success Criteria**

```python
def check_success_criteria(verification_result, success_criteria):
    """
    Verify each success criterion is met.
    """
    results = []
    for criterion in success_criteria:
        # SC-001: Tests pass with no failures
        if "tests pass" in criterion.lower():
            results.append({
                "criterion": criterion,
                "met": verification_result.passed,
                "evidence": verification_result.summary
            })

        # SC-002: Specific metric (e.g., "offset < 100ms")
        elif "offset" in criterion.lower() or "latency" in criterion.lower():
            metric_value = extract_metric(verification_result.output)
            threshold = extract_threshold(criterion)
            results.append({
                "criterion": criterion,
                "met": metric_value < threshold,
                "evidence": f"Measured: {metric_value}"
            })

    return {
        "all_met": all(r["met"] for r in results),
        "criteria_results": results
    }
```

---

### PHASE 4: ANALYZE NEW ISSUE (if not resolved)

**If verification failed, identify the new issue:**

```python
def analyze_new_issue(current_error, previous_error):
    """
    Determine if this is a new issue or the same issue.
    """
    if current_error == previous_error:
        return {
            "is_new": False,
            "description": "Same error persists",
            "recommendation": "Try different approach"
        }

    return {
        "is_new": True,
        "description": extract_new_error(current_error),
        "evidence": current_error[:500],
        "recommendation": "Investigate new error pattern"
    }
```

---

### PHASE 5: CLEANUP (if resolved)

**If success criteria met, clean up debug logs:**

```bash
# Find all files with [DEBUG-SOLVER] logs
Grep: "\[DEBUG-SOLVER\]" in apps/ tests/

# For each file found:
Edit: ${file}
# Remove lines containing [DEBUG-SOLVER]
```

---

### PHASE 6: UPDATE CONTEXT & RETURN

**Step 1: Update context.md**

```bash
Edit: ${context_file}
# Add to current iteration in Investigation History:
# - Applied Fix
# - Verification Result
# - New Issue (if any)
```

**Step 2: Return JSON Response**

---

## Output Contract

**Success Response (criteria met)**:

```json
{
  "agent": "debug-executor",
  "status": "success",
  "timestamp": "<ISO8601>",
  "execution_time_ms": <number>,
  "result": {
    "debug_id": "<debug_id>",
    "iteration": 1,
    "context_file": "<path>",
    "fix_applied": {
      "operations_count": 2,
      "operations": [
        {
          "operation": "MODIFY_CODE",
          "target_file": "apps/media-service/src/media_service/sync/av_sync.py",
          "description": "Changed timestamp source to frame_pts",
          "status": "applied"
        },
        {
          "operation": "ADD_LOG",
          "target_file": "apps/media-service/src/media_service/sync/av_sync.py",
          "description": "Added debug log for timestamp tracking",
          "status": "applied"
        }
      ],
      "files_modified": [
        "apps/media-service/src/media_service/sync/av_sync.py"
      ]
    },
    "verification_result": {
      "command": "pytest tests/e2e/test_sync.py -v",
      "exit_code": 0,
      "success_criteria_met": true,
      "criteria_results": [
        {
          "criterion": "SC-001: All sync tests pass",
          "met": true,
          "evidence": "5 passed in 12.3s"
        }
      ],
      "output_summary": "All 5 tests passed"
    },
    "debug_logs_cleaned": [
      "apps/media-service/src/media_service/sync/av_sync.py:120"
    ],
    "new_issue": null,
    "resolution_summary": "Fixed timestamp source from segment_start to frame_pts. All sync tests now pass."
  }
}
```

**Partial Success Response (criteria not met, new issue found)**:

```json
{
  "agent": "debug-executor",
  "status": "success",
  "timestamp": "<ISO8601>",
  "execution_time_ms": <number>,
  "result": {
    "debug_id": "<debug_id>",
    "iteration": 1,
    "context_file": "<path>",
    "fix_applied": {
      "operations_count": 1,
      "operations": [
        {
          "operation": "MODIFY_CODE",
          "target_file": "apps/media-service/src/media_service/sync/av_sync.py",
          "description": "Changed timestamp source to frame_pts",
          "status": "applied"
        }
      ],
      "files_modified": [
        "apps/media-service/src/media_service/sync/av_sync.py"
      ]
    },
    "verification_result": {
      "command": "pytest tests/e2e/test_sync.py -v",
      "exit_code": 1,
      "success_criteria_met": false,
      "criteria_results": [
        {
          "criterion": "SC-001: All sync tests pass",
          "met": false,
          "evidence": "4 passed, 1 failed"
        }
      ],
      "output_summary": "test_audio_video_sync FAILED - AssertionError: offset 150ms > 100ms"
    },
    "debug_logs_added": [
      "apps/media-service/src/media_service/sync/av_sync.py:120"
    ],
    "debug_logs_cleaned": [],
    "new_issue": {
      "description": "Audio offset still exceeds threshold after timestamp fix",
      "evidence": "AssertionError: offset 150ms > 100ms (was 500ms before fix)",
      "is_progress": true,
      "progress_note": "Reduced from 500ms to 150ms, but still above 100ms threshold"
    },
    "recommendation": "Investigate remaining 50ms offset - likely buffer or processing delay"
  }
}
```

**Error Response (cannot apply fix)**:

```json
{
  "agent": "debug-executor",
  "status": "error",
  "timestamp": "<ISO8601>",
  "execution_time_ms": <number>,
  "error": {
    "type": "OperationFailed",
    "code": "CODE_CHANGE_FAILED",
    "message": "Could not apply recommended code change",
    "details": {
      "operation": "MODIFY_CODE",
      "target_file": "apps/media-service/src/media_service/sync/av_sync.py",
      "reason": "Old string not found - code may have changed",
      "expected": "offset = current_time - segment_start",
      "actual_content": "offset = current_time - base_time"
    },
    "recoverable": true,
    "recovery_strategy": "retry_with_updated_search",
    "suggested_action": {
      "action": "Re-run researcher with updated context",
      "reason": "Code structure differs from research findings"
    }
  }
}
```

---

## Operation Execution Details

### MODIFY_CODE

```python
# 1. Read target file
content = Read(target_file)

# 2. Verify old_string exists
if old_string not in content:
    return error("CODE_CHANGE_FAILED", "Old string not found")

# 3. Apply edit
Edit(target_file, old_string, new_string)

# 4. Verify change applied
new_content = Read(target_file)
if new_string not in new_content:
    return error("EDIT_FAILED", "New string not in file after edit")
```

### ADD_LOG

```python
# Debug log format (MUST follow this pattern):
log_line = f'logger.debug(f"[DEBUG-SOLVER] {message}")'

# Or for Python files without logger:
log_line = f'print(f"[DEBUG-SOLVER] {message}")'

# Insert after specified line
Edit(target_file,
     old_string=line_before,
     new_string=f"{line_before}\n        {log_line}")
```

### Cleanup Debug Logs

```python
# Find all debug logs
files = Grep("[DEBUG-SOLVER]", path="apps/ tests/", output_mode="files_with_matches")

for file in files:
    content = Read(file)
    lines = content.split('\n')

    # Remove lines containing [DEBUG-SOLVER]
    cleaned_lines = [l for l in lines if "[DEBUG-SOLVER]" not in l]

    # Write cleaned content
    Write(file, '\n'.join(cleaned_lines))
```

---

## Verification Strategies

### For Test Commands

```bash
# Run specific test file
pytest ${test_file} -v --tb=short 2>&1

# Run specific test function
pytest ${test_file}::${test_function} -v 2>&1

# Run with extra logging
pytest ${test_file} -v -s --log-cli-level=DEBUG 2>&1
```

### For E2E Tests

```bash
# Ensure services are running
make e2e-up
sleep 10  # Wait for services

# Run E2E test
pytest tests/e2e/${test_file} -v --tb=short --log-cli-level=INFO 2>&1

# Capture logs if needed
docker logs e2e-media-service 2>&1 | tail -100
```

### For Metric-Based Success Criteria

```bash
# Run test and capture metrics
pytest ${test_file} -v 2>&1 | tee /tmp/test_output.txt

# Parse specific metric from output
grep -E "(offset|latency|duration)" /tmp/test_output.txt
```

---

## Constraints

**MUST**:
- Read context file first to understand full history
- Apply operations in priority order
- Verify each operation was applied correctly
- Run verification command after applying fixes
- Check ALL success criteria
- Update context.md with results
- Clean up debug logs after success
- Return structured JSON

**MUST NOT**:
- Skip verification step
- Leave debug logs in code after success
- Ignore failed operations
- Proceed without updating context

**DEBUG LOG RULES**:
- All debug logs MUST use prefix `[DEBUG-SOLVER]`
- Debug logs must be removed after success criteria met
- Track all added debug logs for cleanup

---

## Progress Tracking

When issue is not fully resolved but progress is made:

```python
progress_assessment = {
    "is_progress": True,
    "before": "offset was 500ms",
    "after": "offset is 150ms",
    "remaining": "need to reduce by another 50ms",
    "confidence": "HIGH - clear improvement shows we're on right track"
}
```

This helps the orchestrator decide whether to continue or try a different approach.

---

*Debug Executor Agent - Applies fixes, verifies success, reports results*
