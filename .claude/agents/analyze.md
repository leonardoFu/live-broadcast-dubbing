---
name: speckit-analyze
description: Perform cross-artifact consistency and quality analysis
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.analyze.md
color: cyan
---

# Analyze Agent

This agent performs non-destructive analysis across spec.md, plan.md, and tasks.md to detect issues.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.analyze.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "<feature-id>",
  "feature_dir": "specs/<feature-id>/",
  "previous_results": {
    "speckit-specify": { "status": "success", "spec_file": "..." },
    "speckit-plan": { "status": "success", "plan_file": "...", "data_model_file": "..." },
    "speckit-tasks": { "status": "success", "tasks_file": "...", "task_count": 23 }
  }
}

USER_REQUEST: <original user request text>
```

**Extract from context**:
- `feature_id`: Feature being analyzed
- `feature_dir`: Base directory for all spec artifacts
- `previous_results.speckit-specify.spec_file`: Path to spec.md
- `previous_results.speckit-plan.plan_file`: Path to plan.md
- `previous_results.speckit-tasks.tasks_file`: Path to tasks.md
- `USER_REQUEST`: Original user request for understanding intent

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.analyze.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.analyze.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Detecting 6 types of issues: Duplication, Ambiguity, Underspecification, Constitution Alignment, Coverage Gaps, Inconsistency
- Building semantic models (requirements, user stories, tasks) internally
- Generating structured report with findings (max 50)
- Assigning severity: CRITICAL, HIGH, MEDIUM, LOW
- Prioritizing Constitution violations as always CRITICAL
- Producing coverage table mapping requirements to tasks

### Step 3: Capture Results

After the command completes, extract:
- Analysis report path (if saved)
- Total findings count
- Findings by severity
- Coverage percentage
- Critical issues requiring immediate attention

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "analyze",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "analysis_report": "<path-to-analysis-report.md>",
    "artifacts_analyzed": ["spec.md", "plan.md", "tasks.md"],
    "total_findings": 8,
    "findings_by_severity": {
      "CRITICAL": 1,
      "HIGH": 2,
      "MEDIUM": 3,
      "LOW": 2
    },
    "findings": [
      {
        "severity": "CRITICAL",
        "type": "Constitution Violation",
        "message": "TDD principle not enforced in Task T012",
        "location": "tasks.md:45",
        "recommendation": "Add test implementation step before code implementation"
      },
      {
        "severity": "HIGH",
        "type": "Coverage Gap",
        "message": "Requirement REQ-5 has no corresponding tasks",
        "location": "spec.md:67",
        "recommendation": "Add tasks to implement REQ-5"
      }
    ],
    "coverage_analysis": {
      "total_requirements": 12,
      "requirements_with_tasks": 11,
      "coverage_percentage": 91.67,
      "uncovered_requirements": ["REQ-5"]
    },
    "recommendation": "Address CRITICAL findings before proceeding to implementation",
    "next_steps": ["Fix critical issues", "implement"]
  }
}
```

**On Error:**
```json
{
  "agent": "analyze",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "PrerequisiteError",
    "code": "MISSING_ARTIFACTS",
    "message": "Required artifacts not found for analysis",
    "details": {
      "missing_files": ["plan.md", "tasks.md"]
    },
    "recoverable": true,
    "recovery_strategy": "run_prerequisite_agent",
    "suggested_action": {
      "agent": "plan",
      "reason": "Generate missing plan.md before analysis"
    }
  }
}
```

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.analyze.md`. It performs read-only analysis and reports findings without modifying files.
