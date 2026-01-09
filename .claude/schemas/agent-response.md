# Agent Response Schema

All speckit agents must return JSON responses conforming to these schemas.

## Workflow Context (Input)

Agents receive context from the orchestrator:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "<feature-id>",
  "feature_dir": "specs/<feature-id>/",
  "previous_results": {
    "<agent-name>": { "status": "success|error", ... }
  }
}

USER_REQUEST: <original user request text>
```

**Extract**: `feature_id`, `feature_dir`, relevant paths from `previous_results`.

## Feedback Context (Input, Optional)

When an agent is re-invoked due to issues from a downstream agent:

```text
FEEDBACK_CONTEXT:
{
  "feedback_from": "<source-agent>",
  "iteration": 1,
  "max_iterations": 2,
  "issues_to_fix": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "type": "<issue-type>",
      "message": "<description>",
      "location": "<file:line>",
      "recommendation": "<how to fix>"
    }
  ]
}
```

**When present**: Prioritize fixing `issues_to_fix` before normal execution.

## Success Response

```json
{
  "agent": "<agent-name>",
  "status": "success",
  "timestamp": "<ISO8601>",
  "execution_time_ms": 1234,
  "result": {
    // Agent-specific result fields
    "next_steps": ["<next-agent>"]
  }
}
```

## Error Response

```json
{
  "agent": "<agent-name>",
  "status": "error",
  "timestamp": "<ISO8601>",
  "execution_time_ms": 1234,
  "error": {
    "type": "<ErrorType>",
    "code": "<ERROR_CODE>",
    "message": "<human-readable message>",
    "details": {},
    "recoverable": true,
    "recovery_strategy": "<strategy>",
    "suggested_action": {
      "agent": "<agent-to-run>",
      "reason": "<why>"
    }
  }
}
```

## Error Types

| Type | When | Recovery |
|------|------|----------|
| `PrerequisiteError` | Missing required file/artifact | Run prerequisite agent |
| `ValidationError` | Invalid input or state | Fix input, retry |
| `QualityGateFailure` | Tests/coverage/lint failed | Fix issues, retry |
| `ConstitutionViolationError` | Violates project rules | Manual resolution |
| `BranchExistsError` | Git branch conflict | Ask user |
| `TimeoutError` | Operation timed out | Retry |
| `ExternalServiceError` | External API failed | Retry with backoff |

## Recovery Strategies

| Strategy | Action |
|----------|--------|
| `run_prerequisite_agent` | Execute suggested agent first |
| `feedback_loop` | Re-run source agent with issues |
| `fix_and_retry` | Auto-fix and retry same agent |
| `ask_user` | Require user decision |
| `manual_resolution` | Cannot auto-recover |

## Agent-Specific Result Fields

### specify
```json
{
  "branch_name": "<branch>",
  "spec_file": "<path>",
  "feature_number": 123,
  "short_name": "<name>",
  "clarifications_needed": 0,
  "sections_generated": ["Overview", "..."],
  "checklist_status": "complete|incomplete"
}
```

### clarify
```json
{
  "spec_file": "<path>",
  "clarifications_resolved": 3,
  "questions_asked": 3,
  "remaining_ambiguities": 0
}
```

### research
```json
{
  "research_cache_file": "<path>",
  "technologies_researched": [
    {"name": "<tech>", "context7_id": "<id>", "topics": [], "snippet_count": 10}
  ],
  "decisions": [
    {"decision": "<what>", "choice": "<chosen>", "rationale": "<why>", "alternatives": []}
  ],
  "confidence_level": "HIGH|MEDIUM|LOW"
}
```

### plan
```json
{
  "plan_file": "<path>",
  "research_file": "<path>",
  "data_model_file": "<path>",
  "contracts_dir": "<path>",
  "quickstart_file": "<path>",
  "technologies": ["<tech>"],
  "constitution_violations": [],
  "artifacts_created": ["<file>"]
}
```

### checklist
```json
{
  "checklist_file": "<path>",
  "domain": "ux|api|security|performance|data",
  "total_items": 15,
  "categories": ["Completeness", "Clarity", "Consistency", "Measurability"]
}
```

### tasks
```json
{
  "tasks_file": "<path>",
  "task_count": 23,
  "phases": {"setup": 3, "foundational": 8, "user_stories": 10, "polish": 2},
  "parallelizable_tasks": 12,
  "task_ids": ["T001", "..."],
  "dependencies_mapped": true
}
```

### analyze
```json
{
  "analysis_report": "<path>",
  "artifacts_analyzed": ["spec.md", "plan.md", "tasks.md"],
  "total_findings": 8,
  "findings_by_severity": {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 2},
  "findings": [
    {"severity": "<sev>", "type": "<type>", "message": "<msg>", "location": "<loc>", "recommendation": "<fix>"}
  ],
  "coverage_analysis": {
    "total_requirements": 12,
    "requirements_with_tasks": 11,
    "coverage_percentage": 91.67,
    "uncovered_requirements": ["REQ-5"]
  }
}
```

### implement
```json
{
  "tasks_file": "<path>",
  "tasks_completed": 23,
  "tasks_total": 23,
  "completion_percentage": 100,
  "tests_passed": 127,
  "tests_total": 127,
  "coverage_percentage": 94.2,
  "files_created": 45,
  "files_modified": 12,
  "implementation_phases": {"setup": "completed", "...": "..."}
}
```

### test
```json
{
  "feature_id": "<id>",
  "overall_status": "PASSED|FAILED",
  "quality_gates": {
    "tests_passing": {"status": "PASSED", "details": {"total": 45, "passed": 45, "failed": 0}},
    "coverage": {"status": "PASSED", "details": {"overall": 87.5, "required": 80.0}},
    "code_quality": {"status": "PASSED", "details": {"lint_errors": 0, "type_errors": 0}},
    "build_validation": {"status": "PASSED", "details": {"docker_compose": "valid"}}
  },
  "success_criteria": [
    {"id": "SC-001", "description": "<desc>", "status": "PASSED|FAILED|NOT_TESTED"}
  ]
}
```

### review
```json
{
  "feature_id": "<id>",
  "overall_status": "APPROVED|APPROVED_WITH_WARNINGS|NEEDS_MANUAL_REVIEW",
  "changes_made": {
    "files_moved": [{"from": "<path>", "to": "<path>"}],
    "files_deleted": [{"path": "<path>", "reason": "<why>"}],
    "files_created": [{"path": "<path>", "reason": "<why>"}],
    "files_modified": [{"path": "<path>", "changes": "<what>"}]
  },
  "constitution_compliance": {"status": "PASS|FAIL", "passed": 8, "failed": 0},
  "cleanup_summary": {"tests_removed": 7, "files_moved": 3, "dead_code_lines_removed": 150}
}
```

### taskstoissues
```json
{
  "issues_created": 12,
  "issues": [{"number": 123, "title": "<title>", "url": "<url>", "task_id": "T001"}],
  "labels_applied": ["feature", "priority-high"]
}
```
