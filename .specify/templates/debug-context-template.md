# Debug Context: [ISSUE_TITLE]

**Debug ID**: debug-[TIMESTAMP]
**Created**: [ISO8601_DATE]
**Status**: investigating
**Iteration**: 1 / 5

---

## Issue Description

[ISSUE_DESCRIPTION]

### Original Error

```
[ERROR_OUTPUT]
```

### Affected Files

- [FILE1]
- [FILE2]

---

## Success Criteria

How to verify the issue is resolved:

- **SC-001**: [PRIMARY_SUCCESS_CRITERION]
- **SC-002**: [SECONDARY_CRITERION_IF_APPLICABLE]

---

## Verification Command

```bash
[VERIFICATION_COMMAND]
```

---

## Investigation History

### Iteration 1

**Timestamp**: [ISO8601_TIMESTAMP]
**Status**: in_progress

#### Research Findings

| Category | Finding | Location | Confidence |
|----------|---------|----------|------------|
| [ROOT_CAUSE/SYMPTOM/RELATED] | [FINDING_DESCRIPTION] | [FILE:LINE] | [HIGH/MEDIUM/LOW] |

#### Recommended Operations

| Priority | Operation | Target | Description |
|----------|-----------|--------|-------------|
| 1 | [ADD_LOG/MODIFY_CODE/etc] | [FILE:LINE] | [DESCRIPTION] |

#### Applied Fix

- **Operation**: [DESCRIPTION]
- **Files Modified**:
  - [FILE1]
  - [FILE2]

#### Verification Result

```bash
$ [VERIFICATION_COMMAND]
[OUTPUT]
```

**Exit Code**: [0/1]
**Success Criteria Met**: [YES/NO]

#### New Issue (if not resolved)

**Description**: [NEW_ISSUE_DESCRIPTION]
**Evidence**: [ERROR_MESSAGE_OR_LOG]
**Progress Made**: [DESCRIPTION_OF_ANY_IMPROVEMENT]

---

### Iteration 2

**Timestamp**: [ISO8601_TIMESTAMP]
**Status**: pending

_(To be filled during next iteration)_

---

### Iteration 3

**Timestamp**: [ISO8601_TIMESTAMP]
**Status**: pending

_(To be filled during next iteration)_

---

### Iteration 4

**Timestamp**: [ISO8601_TIMESTAMP]
**Status**: pending

_(To be filled during next iteration)_

---

### Iteration 5

**Timestamp**: [ISO8601_TIMESTAMP]
**Status**: pending

_(To be filled during next iteration)_

---

## Resolution Summary

**Final Status**: [resolved/exhausted]
**Total Iterations**: [N] / 5
**Resolution Time**: [DURATION]

### Solution Applied

[DESCRIPTION_OF_FINAL_FIX]

### Files Modified

- [FILE1]: [CHANGE_DESCRIPTION]
- [FILE2]: [CHANGE_DESCRIPTION]

### Lessons Learned

- [LESSON_1]
- [LESSON_2]

---

## Debug Artifacts

### Debug Logs Added

| File | Line | Log Statement | Status |
|------|------|---------------|--------|
| [FILE] | [LINE] | `logger.debug(f"[DEBUG-SOLVER] ...")` | [active/cleaned] |

### Temporary Changes

| File | Change | Status |
|------|--------|--------|
| [FILE] | [DESCRIPTION] | [active/reverted] |

---

## Metadata

```json
{
  "debug_id": "[DEBUG_ID]",
  "workflow_id": "[WORKFLOW_ID]",
  "created_at": "[ISO8601]",
  "updated_at": "[ISO8601]",
  "status": "[investigating/fixing/verifying/resolved/exhausted]",
  "iteration": 1,
  "max_iterations": 5,
  "verification_command": "[COMMAND]",
  "success_criteria": [
    "[SC-001]",
    "[SC-002]"
  ],
  "agents_invoked": [
    {
      "agent": "debug-researcher",
      "iteration": 1,
      "timestamp": "[ISO8601]"
    },
    {
      "agent": "debug-executor",
      "iteration": 1,
      "timestamp": "[ISO8601]"
    }
  ]
}
```
