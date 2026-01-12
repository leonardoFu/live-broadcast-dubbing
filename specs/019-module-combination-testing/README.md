# Module Combination Testing Workflow

This directory contains the specialized agents and context for systematically testing module combinations in the live-broadcast-dubbing-cloud project.

## Overview

The module combination testing workflow verifies that previously implemented modules work together correctly by:
1. Analyzing existing specs and E2E tests
2. Generating a comprehensive test execution plan
3. Running tests iteratively until all pass
4. Fixing issues discovered during testing
5. Tracking progress in a context file

## Agents

### speckit.combine-plan

**Purpose**: Analyze implemented modules and E2E tests to generate a comprehensive integration test plan.

**Location**: `.claude/commands/speckit.combine-plan.md`

**What it does**:
- Reads all specs in `specs/` to understand module requirements
- Reads all E2E tests in `tests/e2e/` to understand test coverage
- Identifies module combination scenarios
- Generates structured test execution plan by priority (P1/P2/P3)
- Documents expected behaviors for each module combination
- Creates test priority matrix
- Updates `specs/019-module-combination-testing/context.md` with complete analysis

**Output**: Test plan saved to context.md

### speckit.combine-test

**Purpose**: Execute integration test plan, verify module combinations, and fix issues until all tests pass.

**Location**: `.claude/commands/speckit.combine-test.md`

**What it does**:
- Loads test plan from context.md
- Sets up test environment (Docker Compose)
- Executes tests in priority order (P1 → P2 → P3)
- Analyzes test failures and categorizes issues
- Fixes issues (with user approval for major changes)
- Re-runs failed tests after fixes
- Iterates until all tests pass (max 10 iterations)
- Updates context.md with execution log and issue tracker
- Never stops until 100% test success or unrecoverable error

**Output**: Complete test execution log in context.md, all tests passing

## Usage

### Via Orchestrator (Recommended)

```bash
# Run the complete combine workflow
/speckit-orchestrator
combine
```

This will:
1. Run `speckit.combine-plan` to analyze and plan
2. Run `speckit.combine-test` to execute and fix
3. Iterate until all tests pass

### Direct Agent Invocation

```bash
# Step 1: Generate test plan
/speckit.combine-plan

# Step 2: Execute test plan
/speckit.combine-test
```

## Context File

The workflow maintains state in `specs/019-module-combination-testing/context.md`:

**Sections**:
- **Overview**: High-level summary and goals
- **Implemented Modules Analysis**: Detailed analysis of services and libraries
- **E2E Test Coverage Analysis**: Complete test inventory
- **Module Combination Scenarios**: Identified test scenarios by priority
- **Test Execution Plan**: Structured plan with phases and success criteria
- **Test Priority Matrix**: Table mapping tests to modules and expected results
- **Expected Behaviors**: Documented behaviors for each combination
- **Test Execution Log**: Iteration-by-iteration test results (updated by combine-test)
- **Issues Tracker**: Active and resolved issues (updated by combine-test)
- **Next Steps**: Current status and recommended actions

## Workflow Characteristics

### Iterative Execution

The combine-test agent runs in a loop:
1. Execute test phase (P1, P2, or P3)
2. Collect results
3. Analyze failures
4. Fix issues
5. Re-run failed tests
6. Repeat until all tests pass

**Max Iterations**: 10 (prevents infinite loops)

### Issue Categorization

Issues are categorized as:
- **Test Issue**: Flaky test, incorrect assertion, missing fixture → Fix directly
- **Implementation Issue**: Bug in service code → Fix with user approval for major changes
- **Configuration Issue**: Wrong environment setup → Fix configuration
- **Infrastructure Issue**: Docker/network problem → Report to user for manual resolution

### User Interaction

- **Minor fixes**: Automatic (documented in context.md)
- **Major fixes**: Requires user approval before proceeding
- **Blocked scenarios**: Reports to user and waits for resolution
- **Progress updates**: After each iteration

### Success Criteria

The workflow is complete when:
- ✅ All P1 tests pass (100%)
- ✅ All P2 tests pass (100%)
- ✅ All P3 tests pass (100%)
- ✅ No regressions in previously passing tests
- ✅ Final verification run completes successfully

## Example Output

After successful completion:

```
## ✅ Module Combination Testing Complete

**Status**: All tests passing
**Test Results**: 38/38 passed (100%)
**Iterations**: 3
**Issues Fixed**: 5

### Test Breakdown:
- P1 (Critical): 13/13 passed ✅
- P2 (Important): 19/19 passed ✅
- P3 (Edge Cases): 6/6 passed ✅

### Issues Resolved:
1. test_full_pipeline - Timeout increased from 60s to 90s
2. test_circuit_breaker - Fixed error counting logic
3. test_av_sync - Adjusted sync threshold calculation
4. test_reconnection - Fixed exponential backoff timing
5. test_dual_compose - Updated service health check config

### Next Steps:
- Review context.md for detailed logs
- Consider creating PR for fixes made
- Module integration verified and working as expected
```

## Integration with Orchestrator

The combine workflow is integrated into the speckit orchestrator as a specialized workflow:

**Trigger**: `combine`

**Workflow Sequence**:
1. `combine-plan` → Generate test plan
2. `combine-test` → Execute tests iteratively until all pass

**No Checkpoint Required**: This is a testing workflow, not an implementation workflow, so it doesn't require the mandatory human checkpoint.

**Continuous Execution**: The orchestrator will keep the combine-test agent running until all tests pass or max iterations reached.

## File Structure

```
specs/019-module-combination-testing/
├── README.md           # This file
└── context.md          # Test plan and execution log (updated by agents)

.claude/commands/
├── speckit.combine-plan.md   # Planning agent definition
└── speckit.combine-test.md   # Testing agent definition
```

## Benefits

1. **Systematic Testing**: Ensures all module combinations are tested in priority order
2. **Automated Fixing**: Identifies and fixes issues automatically where possible
3. **Progress Tracking**: Context file provides complete audit trail
4. **Iterative Improvement**: Keeps running until all tests pass
5. **User Control**: Asks for approval before major changes
6. **Documentation**: Generates comprehensive test documentation

## Use Cases

- **Pre-Release Verification**: Run before creating release to ensure all modules work together
- **Post-Implementation Testing**: After implementing new features, verify no regressions
- **CI/CD Integration**: Can be integrated into CI pipeline for continuous verification
- **Onboarding**: New developers can understand module interactions by reading context.md

## Next Steps

To use the combine workflow:

1. Ensure all E2E tests are in `tests/e2e/`
2. Run `/speckit-orchestrator` and type `combine`
3. Wait for agents to complete (may take time depending on test count)
4. Review context.md for results
5. Address any unresolved issues if max iterations reached
