---
name: speckit-plan
description: Execute implementation planning workflow using plan template
model: opus
color: green
---

# Plan Agent

Generates technical design artifacts from feature specification.

## Input

Parse from `$ARGUMENTS`:
- `WORKFLOW_CONTEXT`: workflow_id, feature_id, feature_dir, previous_results
- `USER_REQUEST`: Original request
- `RESPONSE_FORMAT`: JSON structure for response
- `FEEDBACK_CONTEXT` (optional): Issues from analyze agent

## Execution

### Step 1: Setup

Run `.specify/scripts/bash/setup-plan.sh --json` and parse:
- `FEATURE_SPEC`, `IMPL_PLAN`, `SPECS_DIR`, `BRANCH`

### Step 2: Load Context

Read:
- `FEATURE_SPEC` (spec.md)
- `.specify/memory/constitution.md`
- `IMPL_PLAN` template (already copied)

### Step 3: Phase 0 - Research

1. Extract unknowns from Technical Context marked `NEEDS CLARIFICATION`
2. For each unknown/dependency/integration → research task
3. Generate `research.md` with format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives: [what else evaluated]

### Step 4: Phase 1 - Design

Prerequisites: `research.md` complete

1. **Data Model** (`data-model.md`):
   - Extract entities from spec
   - Fields, relationships, validation rules
   - State transitions if applicable

2. **API Contracts** (`contracts/`):
   - Map user actions → endpoints
   - Generate OpenAPI/GraphQL schemas

3. **Quickstart** (`quickstart.md`):
   - Test scenarios from spec

4. **Agent Context Update**:
   - Run `.specify/scripts/bash/update-agent-context.sh claude`

### Step 5: Constitution Check

Evaluate gates from constitution. ERROR if violations unjustified.

### Step 6: Return Result

Return JSON per `RESPONSE_FORMAT` with these result fields:
- `plan_file`: Path to plan.md
- `research_file`: Path to research.md
- `data_model_file`: Path to data-model.md
- `contracts_dir`: Path to contracts/
- `quickstart_file`: Path to quickstart.md
- `technologies`: List of tech stack choices
- `constitution_violations`: List (empty if none)
- `artifacts_created`: List of created files
- `next_steps`: ["checklist", "tasks"]

## Key Rules

- Use absolute paths
- ERROR on gate failures or unresolved clarifications
- Command ends after Phase 1 planning

## Feedback Handling

When `FEEDBACK_CONTEXT.issues_to_fix` present:
1. Parse issues: `architecture_gap`, `data_model_issue`, `design_flaw`
2. Update data-model.md for relationship/schema issues
3. Update plan.md for architecture gaps
4. Return success only if all resolved
