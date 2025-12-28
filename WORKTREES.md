# Git Worktrees for Parallel Development

## Overview

This repository uses git worktrees to enable parallel development of User Stories 3, 4, and 5 for the MediaMTX integration feature.

## Worktree Structure

```
live-broadcast-dubbing-cloud/           (main working directory)
├── worktrees/
│   ├── us3-stream-worker/              (User Story 3: Stream Worker I/O)
│   ├── us4-observability/              (User Story 4: Observability)
│   └── us5-test-utilities/             (User Story 5: Test Utilities)
```

### Branch Mapping

| Worktree Directory | Branch Name | User Story | Tasks |
|-------------------|-------------|------------|-------|
| `worktrees/us3-stream-worker/` | `001-mediamtx-integration-us3` | Stream Worker Input/Output via MediaMTX | 13 tasks (T050-T062) |
| `worktrees/us4-observability/` | `001-mediamtx-integration-us4` | Observability and Debugging | 14 tasks (T063-T076) |
| `worktrees/us5-test-utilities/` | `001-mediamtx-integration-us5` | Test Stream Publishing utilities | 10 tasks (T077-T086) |

## Quick Start

### Working in a Worktree

```bash
# Navigate to a worktree
cd worktrees/us3-stream-worker/

# Check which branch you're on
git branch --show-current
# Output: 001-mediamtx-integration-us3

# Work normally - make changes, commit, etc.
# All git operations work as usual within the worktree
```

### Parallel Development Workflow

**Terminal 1 - User Story 3:**
```bash
cd worktrees/us3-stream-worker/
# Implement User Story 3 tasks
make test
git add .
git commit -m "feat(us3): implement RTSP URL construction"
```

**Terminal 2 - User Story 4:**
```bash
cd worktrees/us4-observability/
# Implement User Story 4 tasks
make test
git add .
git commit -m "feat(us4): enable Control API endpoints"
```

**Terminal 3 - User Story 5:**
```bash
cd worktrees/us5-test-utilities/
# Implement User Story 5 tasks
make test
git add .
git commit -m "feat(us5): add FFmpeg test scripts"
```

All three can work simultaneously without conflicts!

## Common Operations

### List All Worktrees

```bash
git worktree list
```

Output:
```
/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud                               b68106a [001-mediamtx-integration]
/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktrees/us3-stream-worker   b68106a [001-mediamtx-integration-us3]
/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktrees/us4-observability   b68106a [001-mediamtx-integration-us4]
/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktrees/us5-test-utilities  b68106a [001-mediamtx-integration-us5]
```

### Check Status Across All Worktrees

```bash
# From main directory
for dir in worktrees/*/; do
  echo "=== $(basename $dir) ==="
  (cd "$dir" && git status --short)
done
```

### Run Tests in All Worktrees

```bash
# Test all worktrees in parallel
(cd worktrees/us3-stream-worker/ && make test) &
(cd worktrees/us4-observability/ && make test) &
(cd worktrees/us5-test-utilities/ && make test) &
wait
echo "All tests complete!"
```

## Merging Strategy

Once a user story is complete, merge it back to the main feature branch:

### Option 1: Merge via Main Branch (Recommended)

```bash
# 1. Switch to main feature branch
cd /Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud
git checkout 001-mediamtx-integration

# 2. Merge User Story 3
git merge --no-ff 001-mediamtx-integration-us3 -m "feat: merge User Story 3 (Stream Worker I/O)"

# 3. Merge User Story 4
git merge --no-ff 001-mediamtx-integration-us4 -m "feat: merge User Story 4 (Observability)"

# 4. Merge User Story 5
git merge --no-ff 001-mediamtx-integration-us5 -m "feat: merge User Story 5 (Test Utilities)"

# 5. Run final integration tests
make test

# 6. Push to remote
git push origin 001-mediamtx-integration
```

### Option 2: Create Separate PRs (Team Review)

```bash
# Push each user story branch for review
git push origin 001-mediamtx-integration-us3
git push origin 001-mediamtx-integration-us4
git push origin 001-mediamtx-integration-us5

# Create PRs
gh pr create --base 001-mediamtx-integration --head 001-mediamtx-integration-us3 --title "feat(us3): Stream Worker I/O"
gh pr create --base 001-mediamtx-integration --head 001-mediamtx-integration-us4 --title "feat(us4): Observability"
gh pr create --base 001-mediamtx-integration --head 001-mediamtx-integration-us5 --title "feat(us5): Test Utilities"
```

## Cleanup

### After Merging - Remove Individual Worktrees

```bash
# Remove a specific worktree
git worktree remove worktrees/us3-stream-worker

# Or remove all at once
git worktree remove worktrees/us3-stream-worker
git worktree remove worktrees/us4-observability
git worktree remove worktrees/us5-test-utilities

# Clean up the directory
rm -rf worktrees/
```

### Delete Merged Branches (Optional)

```bash
# After merging to main feature branch
git branch -d 001-mediamtx-integration-us3
git branch -d 001-mediamtx-integration-us4
git branch -d 001-mediamtx-integration-us5
```

## Using Claude Code in Worktrees

You can run Claude Code in each worktree independently:

```bash
# Terminal 1 - Implement US3
cd worktrees/us3-stream-worker/
claude

# In Claude Code session:
> Please implement the RTSP URL construction tests and implementation for User Story 3
```

```bash
# Terminal 2 - Implement US4
cd worktrees/us4-observability/
claude

# In Claude Code session:
> Please implement the Control API integration for User Story 4
```

Each worktree has its own isolated working directory, so Claude Code can work on them simultaneously without conflicts.

## Best Practices

### ✅ Do's

- **Commit frequently** in each worktree to track progress
- **Run tests** before merging back to main branch
- **Push branches** to remote for backup during long parallel work
- **Use descriptive commit messages** with user story prefix (e.g., `feat(us3):`)
- **Sync with main branch** periodically if there are shared changes

### ❌ Don'ts

- **Don't modify the same files** across different worktrees (causes merge conflicts)
- **Don't delete worktrees** with uncommitted changes
- **Don't forget to pull** latest changes before starting work in a worktree
- **Don't work on the same branch** in multiple worktrees simultaneously

## Task Distribution

Based on `specs/001-mediamtx-integration/tasks.md`:

### User Story 3 Tasks (13 tasks)
- T050-T053: Unit/integration tests for URL construction and worker passthrough
- T054-T059: Documentation and configuration

**Focus**: Worker integration patterns, RTSP/RTMP utilities

### User Story 4 Tasks (14 tasks)
- T060-T063: Contract/integration tests for Control API and metrics
- T064-T073: MediaMTX API/metrics configuration and documentation

**Focus**: Observability, monitoring, Control API

### User Story 5 Tasks (10 tasks)
- T074-T075: Tests for FFmpeg commands and playback
- T076-T083: Test scripts and documentation

**Focus**: Developer testing utilities, FFmpeg/GStreamer scripts

## Troubleshooting

### Issue: "fatal: 'worktrees/us3-stream-worker' already exists"

**Solution**: The worktree already exists. Either:
```bash
# Use the existing worktree
cd worktrees/us3-stream-worker/

# Or remove and recreate
git worktree remove worktrees/us3-stream-worker
git worktree add -b 001-mediamtx-integration-us3 worktrees/us3-stream-worker
```

### Issue: "fatal: 'worktrees/us3-stream-worker' is not a working tree"

**Solution**: The directory exists but isn't a proper worktree:
```bash
rm -rf worktrees/us3-stream-worker
git worktree add -b 001-mediamtx-integration-us3 worktrees/us3-stream-worker
```

### Issue: Merge conflicts when merging branches

**Solution**:
```bash
# Identify conflicting files
git status

# Resolve conflicts manually or use a merge tool
git mergetool

# Complete the merge
git commit
```

### Issue: Need to sync worktree with main branch updates

**Solution**:
```bash
cd worktrees/us3-stream-worker/
git fetch origin
git merge origin/001-mediamtx-integration
# Resolve any conflicts
```

## Architecture Notes

### Why Worktrees Work for This Project

1. **Independent User Stories**: US3, US4, US5 work on different files
   - US3: `tests/integration/test_stream_urls.py`, `tests/integration/test_worker_passthrough.py`
   - US4: `tests/integration/test_control_api.py`, `mediamtx.yml` (different sections)
   - US5: `tests/fixtures/test-streams/`, `quickstart.md`

2. **Minimal Overlap**: Only `mediamtx.yml` and `quickstart.md` might have minor conflicts
   - Easily resolved during merge
   - Different sections of files (US3: RTSP config, US4: API config, US5: examples)

3. **TDD Isolation**: Each user story has independent test files
   - Tests can be written and run in parallel
   - No test interdependencies

## Summary

Git worktrees enable true parallel development for independent user stories. Use them to:
- Work on 3 user stories simultaneously
- Maintain separate test environments
- Commit and push progress independently
- Merge back when ready

Happy parallel coding! 🚀
