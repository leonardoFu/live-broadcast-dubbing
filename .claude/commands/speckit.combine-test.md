---
description: Execute integration test plan, verify module combinations, and fix issues until all tests pass
handoffs:
  - label: Re-plan After Major Changes
    agent: speckit.combine-plan
    prompt: Re-analyze modules and update test plan
    send: false
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. **Setup and Load Context**:
   - Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse paths
   - Parse JSON output to get repository root
   - Extract WORKFLOW_CONTEXT if provided by orchestrator (contains workflow_id, feature_id, previous_results)
   - Read `specs/019-module-combination-testing/context.md`
   - Verify test plan exists (must run speckit.combine-plan first if missing)
   - Load test execution plan and priority matrix
   - Initialize test execution log with iteration counter

2. **Environment Setup**:
   - Verify Docker and Docker Compose are available
   - Check test fixtures exist in `tests/e2e/fixtures/`
   - Verify test helpers are present in `tests/e2e/helpers/`
   - Set up test environment variables if needed
   - **Enable comprehensive logging**:
     - Set `PYTEST_CURRENT_TEST` for test name tracking
     - Enable verbose pytest output (`-vv --tb=long`)
     - Capture stdout/stderr (`-s` for live output)
     - Log timestamps and durations

3. **Pre-Test Validation**:
   - Run environment health checks:
     ```bash
     docker --version
     docker compose version
     pytest --version
     python --version
     ```
   - Verify test infrastructure:
     ```bash
     ls -la tests/e2e/
     ls -la tests/e2e/helpers/
     ls -la tests/e2e/fixtures/
     ```
   - **Check 3rd party library versions**:
     ```bash
     pip list | grep -E "(pytest|docker|socketio|gstreamer|ffmpeg|pydub|numpy)"
     ```
   - Document pre-test status and library versions in context.md

4. **Execute Test Plan (Iterative)**:

   **Phase 1: Environment Setup**
   - Start Docker Compose services:
     ```bash
     cd apps/media-service && docker compose up -d
     # OR dual compose for real STS tests
     ```
   - Wait for services to be healthy
   - Verify network connectivity
   - Document setup status in context.md

   **Phase 2: Run P1 Tests (Critical)**
   - Execute all P1 priority tests with comprehensive logging:
     ```bash
     pytest tests/e2e/ -vv -m p1 --tb=long -s --log-cli-level=DEBUG 2>&1 | tee /tmp/claude/p1_tests.log
     ```
   - Capture results, logs, and metrics
   - **Collect Docker logs** for each failed test:
     ```bash
     docker compose logs media-service > /tmp/claude/media-service.log
     docker compose logs sts-service > /tmp/claude/sts-service.log
     docker compose logs mediamtx > /tmp/claude/mediamtx.log
     ```
   - For each test:
     - ✅ PASS: Document success with duration in context.md
     - ❌ FAIL:
       - Extract full stack trace
       - Capture error message and assertion details
       - Save relevant log snippets to context.md
       - Identify 3rd party library involvement (Docker, Socket.IO, GStreamer, etc.)
   - Update test execution log in context.md

   **Phase 3: Run P2 Tests (Important)**
   - Execute all P2 priority tests with comprehensive logging:
     ```bash
     pytest tests/e2e/ -vv -m p2 --tb=long -s --log-cli-level=DEBUG 2>&1 | tee /tmp/claude/p2_tests.log
     ```
   - Capture Docker logs if failures occur
   - Document results with full error context
   - Update test execution log in context.md

   **Phase 4: Run P3 Tests (Edge Cases)**
   - Execute all P3 priority tests with comprehensive logging:
     ```bash
     pytest tests/e2e/ -vv -m p3 --tb=long -s --log-cli-level=DEBUG 2>&1 | tee /tmp/claude/p3_tests.log
     ```
   - Capture Docker logs if failures occur
   - Document results with full error context
   - Update test execution log in context.md

5. **Analyze Test Results**:
   - For each failed test:
     - Extract error message and stack trace
     - Identify root cause (test issue vs implementation issue)
     - Check logs from services (media-service, sts-service, MediaMTX)
     - Review metrics and timing information
     - **Analyze 3rd party library involvement**:
       - **Docker/Docker Compose errors**:
         - Check container status: `docker compose ps`
         - Inspect container logs: `docker compose logs [service]`
         - Verify network connectivity: `docker network inspect`
         - Check resource usage: `docker stats --no-stream`
       - **Socket.IO errors**:
         - Check connection state in logs
         - Verify event emission/reception
         - Check for timeout or disconnection messages
         - Review backpressure/flow control logs
       - **GStreamer/FFmpeg errors**:
         - Look for pipeline state errors
         - Check codec compatibility issues
         - Verify element linking failures
         - Review buffer underrun/overrun messages
       - **Pytest errors**:
         - Check fixture initialization failures
         - Verify test isolation issues
         - Review assertion messages
       - **Python library errors** (numpy, pydub, etc.):
         - Check for import errors
         - Verify version compatibility
         - Look for deprecation warnings
     - Categorize issue:
       - **Test Issue**: Flaky test, incorrect assertion, missing fixture
       - **Implementation Issue**: Bug in service code, missing feature
       - **Configuration Issue**: Wrong environment setup, missing dependency
       - **Infrastructure Issue**: Docker problem, network issue
       - **3rd Party Library Issue**: Version incompatibility, API change, known bug
     - **Document comprehensive issue details in context.md**:
       - Error type and message
       - Full stack trace
       - Relevant log snippets (max 50 lines per service)
       - 3rd party library versions involved
       - Potential root causes
       - Recommended fixes or workarounds

6. **Fix Issues (With Iteration)**:

   **For Test Issues**:
   - Fix test code directly
   - Update assertions or fixtures
   - Improve test stability
   - Document fix in context.md with before/after comparison

   **For Implementation Issues**:
   - **MINOR FIXES**: Fix directly if issue is clear and small
     - Example: Fix typo, adjust timeout, correct parameter
   - **MAJOR FIXES**: Ask user for approval before making significant changes
     - Example: Architecture change, new feature, refactoring
     - Display issue analysis and proposed fix
     - Wait for user confirmation: "Proceed with fix? (yes/no)"
   - Document all fixes in context.md with code snippets

   **For Configuration Issues**:
   - Update docker-compose.yml if needed
   - Fix environment variables
   - Adjust test configuration
   - Document changes in context.md with diffs

   **For Infrastructure Issues**:
   - Report to user with diagnosis
   - Suggest manual fixes (Docker restart, network reset)
   - Wait for user to resolve before continuing

   **For 3rd Party Library Issues**:
   - **Version Incompatibility**:
     - Document current version and incompatibility details
     - Research compatible versions using pip/documentation
     - Propose version pin or upgrade in requirements.txt
     - Test with proposed version change
   - **API Changes/Deprecations**:
     - Extract deprecation warnings from logs
     - Research migration path in library documentation
     - Update code to use new API patterns
     - Add comments explaining the change
   - **Known Bugs**:
     - Search for similar issues in library's GitHub/issue tracker
     - Document workaround if available
     - Add detailed comments in code
     - Consider pinning to working version
   - **Missing Features**:
     - Verify if feature exists in newer version
     - Implement workaround using alternative approach
     - Document limitation in context.md
   - **All 3rd party fixes**:
     - Add detailed logging around the fix
     - Include library version in comment
     - Document in context.md under "3rd Party Library Issues"

7. **Re-run Failed Tests**:
   - After fixing issues, re-run only the failed tests:
     ```bash
     pytest tests/e2e/test_specific.py::test_function -v
     ```
   - Verify fix resolved the issue
   - Check for regressions (re-run related tests)
   - Update test execution log in context.md

8. **Iteration Loop**:
   - **REPEAT steps 4-7 until**:
     - All P1 tests pass (100% success rate)
     - All P2 tests pass (100% success rate)
     - All P3 tests pass (100% success rate)
     - No regressions in previously passing tests
   - **Maximum iterations**: 10 (prevent infinite loops)
   - **After each iteration**:
     - Update context.md with progress
     - Display summary to user
     - If not complete, continue to next iteration
   - **If max iterations reached without success**:
     - Document remaining issues in context.md
     - Report to user with detailed analysis
     - Suggest next steps (manual intervention, spec revision)

9. **Verification**:
   - Run full test suite one final time:
     ```bash
     pytest tests/e2e/ -v --tb=short
     ```
   - Verify all tests pass
   - Check test coverage if applicable
   - Collect final metrics
   - Document verification results in context.md

10. **Final Report**:
    - Update context.md status to "Complete"
    - Generate summary:
      - Total tests: X
      - All passed: ✅
      - Iterations required: Y
      - Issues found and fixed: Z
      - Total time: Xm Ys
    - Display to user:
      ```
      ## ✅ Module Combination Testing Complete

      **Status**: All tests passing
      **Test Results**: X/X passed (100%)
      **Iterations**: Y
      **Issues Fixed**: Z

      ### Test Breakdown:
      - P1 (Critical): X/X passed ✅
      - P2 (Important): X/X passed ✅
      - P3 (Edge Cases): X/X passed ✅

      ### Issues Resolved:
      [List of issues fixed]

      ### Next Steps:
      - Review context.md for detailed logs
      - Consider creating PR for any fixes made
      - Module integration verified and working as expected
      ```

11. **Cleanup**:
    - Stop Docker Compose services:
      ```bash
      docker compose down
      ```
    - Clean up temporary test artifacts if needed
    - Save final context.md state

## Execution Rules

**CRITICAL**: This agent MUST iterate until all tests pass.

### Test Execution Strategy

1. **Systematic Approach**:
   - Execute tests in priority order (P1 → P2 → P3)
   - Run all tests in a phase before moving to next
   - Don't skip tests even if some fail
   - Collect complete results before analyzing

2. **Failure Handling**:
   - Document ALL failures immediately
   - Categorize failures by type
   - Prioritize fixes by impact (P1 failures first)
   - Fix in batches, then re-run all affected tests

3. **Iteration Strategy**:
   - After each fix iteration, re-run failed tests
   - Verify no regressions (run related tests)
   - Update context.md with progress
   - Display iteration summary to user

4. **User Interaction**:
   - **Minor fixes**: Proceed automatically, document in context
   - **Major fixes**: Ask user for approval first
   - **Blocked**: Report issue, wait for user resolution
   - **Progress updates**: After each iteration

### Context File Updates

Update context.md after EACH iteration:

```markdown
## Test Execution Log

### Iteration 1: [Timestamp]
- Phase: P1 Tests
- Status: 3/5 passed
- Failed Tests:
  - test_full_pipeline::test_rtsp_to_rtmp - Timeout waiting for output
  - test_av_sync::test_sync_threshold - Sync delta exceeded 120ms
- Fixes Applied:
  - Increased output timeout from 60s to 90s
  - Adjusted sync threshold calculation
- Next: Re-run failed tests

### Iteration 2: [Timestamp]
- Phase: P1 Tests (Re-run)
- Status: 5/5 passed ✅
- Phase: P2 Tests
- Status: 4/5 passed
- Failed Tests:
  - test_circuit_breaker::test_opens_on_failures - Circuit didn't open
- Fixes Applied:
  - Fixed error counting logic in circuit_breaker.py
- Next: Re-run P2 tests
```

### Issue Tracking Format

```markdown
## Issues Tracker

### Environment Information
- Python Version: 3.10.x
- Docker Version: 24.x.x
- Docker Compose Version: 2.x.x
- Key Library Versions:
  - pytest: 7.x.x
  - python-socketio: 5.x.x
  - docker-py: 6.x.x
  - (etc.)

### Active Issues
1. **[RESOLVED]** test_full_pipeline::test_rtsp_to_rtmp - Timeout
   - **Category**: Test Issue
   - **Root Cause**: Output timeout too short (60s insufficient)
   - **Error Message**:
     ```
     TimeoutError: Timed out waiting for output stream after 60s
     ```
   - **Stack Trace**:
     ```
     File "tests/e2e/test_full_pipeline.py", line 45, in test_rtsp_to_rtmp
       assert wait_for_output(timeout=60), "Output stream not detected"
     ```
   - **Fix Applied**: Increased timeout to 90s in test configuration
   - **Code Change**:
     ```python
     # Before
     assert wait_for_output(timeout=60)
     # After
     assert wait_for_output(timeout=90)
     ```
   - **Status**: ✅ Resolved in Iteration 1

2. **[ACTIVE]** test_socketio_connection - Connection refused
   - **Category**: 3rd Party Library Issue (Socket.IO)
   - **Root Cause**: Socket.IO client version incompatibility with server
   - **Error Message**:
     ```
     ConnectionError: Connection refused by server
     socketio.exceptions.ConnectionError: Connection error
     ```
   - **Library Versions**:
     - python-socketio client: 5.10.0
     - python-socketio server: 5.8.0
   - **Docker Logs** (sts-service):
     ```
     [2026-01-01 10:30:15] ERROR: Unsupported protocol version
     [2026-01-01 10:30:15] WARNING: Client connection rejected
     ```
   - **Research Notes**:
     - Socket.IO 5.10.0 client requires server >=5.9.0
     - Known issue: https://github.com/miguelgrinberg/python-socketio/issues/xxx
   - **Proposed Fix**: Upgrade server to 5.10.0 or downgrade client to 5.8.0
   - **Status**: 🔄 In Progress

### Resolved Issues
[List all resolved issues with full details as above]

### 3rd Party Library Issues Log
- **Docker**: No issues encountered
- **Socket.IO**: 1 version incompatibility (resolved in Iteration 2)
- **GStreamer**: No issues encountered
- **FFmpeg**: No issues encountered
- **Pytest**: No issues encountered
```

### Test Result Format

Document each test run:

```markdown
### Test Run: 2026-01-01 10:30:00

**Phase**: P1 Tests
**Command**: `pytest tests/e2e/ -v -m p1`

| Test File | Test Function | Status | Duration | Notes |
|-----------|---------------|--------|----------|-------|
| test_full_pipeline.py | test_rtsp_to_rtmp | ✅ PASS | 65s | Output stream detected |
| test_av_sync.py | test_sync_threshold | ❌ FAIL | 45s | Sync delta: 135ms > 120ms |

**Summary**: 3/5 passed (60%)
```

## Continuous Execution

**NEVER STOP** until:
- ✅ All P1 tests pass
- ✅ All P2 tests pass
- ✅ All P3 tests pass
- ✅ No regressions detected
- ✅ Verification run completes successfully

**OR**:
- ❌ Max iterations (10) reached
- ❌ Unrecoverable infrastructure error
- ❌ User requests abort

This agent is the "test and fix until done" agent. It should work autonomously to achieve 100% test success.

## Integration with Orchestrator

When called by orchestrator:
- Receive WORKFLOW_CONTEXT with feature_dir and previous results
- Load context.md from feature_dir
- Execute test plan
- Return JSON response with final status
- Update context.md with complete execution log

This agent works in tandem with speckit.combine-plan to provide complete module combination verification.
