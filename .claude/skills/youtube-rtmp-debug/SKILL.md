---
name: youtube-rtmp-debug
description: Automated debugging workflow for YouTube RTMP stream disconnection issues. Uses background tasks for testing.
---

# YouTube RTMP Debug Skill

Automated troubleshooting workflow for YouTube RTMP stream disconnections. **One fix per iteration** - propose, apply, test with background tasks, verify results, decide next steps.

---

## Session Workflow

```
┌──────────────────────────────────────────────────────────────────┐
│  0. BASELINE (first run) → Capture logs WITHOUT any code changes │
│     - Proves/disproves hypothesis from actual behavior           │
│     - Documents what errors occur and when                       │
│     - This IS a valid iteration - understanding is progress      │
├──────────────────────────────────────────────────────────────────┤
│  1. READ STATUS      → Check previous fixes and their results    │
│  2. PROPOSE FIX      → Pick next untried approach                │
│  3. APPLY CODE       → Make the code changes                     │
│  4. START TEST       → Use background tasks to run services      │
│  5. WAIT & MONITOR   → Check logs for 5 minutes                  │
│  6. COLLECT RESULTS  → Get container logs, analyze errors        │
│  7. DECIDE:                                                      │
│     ├─ SUCCESS → Update status, keep code, DONE                  │
│     ├─ FAIL    → git checkout to revert, document clues, next   │
│     └─ NEED MORE DATA → Continue monitoring or add more logging │
└──────────────────────────────────────────────────────────────────┘
```

**Key Rules:**
- **Baseline first**: If root cause is unknown, capture baseline logs BEFORE any fix
- One fix per iteration
- Adding diagnostic logs IS a valid fix when root cause is unknown
- NEVER stop without getting test results from the container
- If fix works → Done
- If fix fails → Use `git checkout --` to revert, document findings, apply next fix
- Never retry a failed approach

---

## Tracking File

**Location**: `.claude/skills/youtube-rtmp-debug/TROUBLESHOOTING_STATUS.md`

Read before starting. Update after each fix attempt with results.

---

## Fix Queue (Priority Order)

| # | Fix Name | Type | File | Risk |
|---|----------|------|------|------|
| 1 | Add FFmpeg stderr monitoring | Diagnostic | `ffmpeg_output.py` | Low |
| 2 | Add segment timing diagnostics | Diagnostic | `ffmpeg_output.py` | Low |
| 3 | Add YouTube RTMP options | Fix | `ffmpeg_output.py` | Low |
| 4 | Improve timestamp handling | Fix | `ffmpeg_output.py` | Medium |
| 5 | Reduce segment duration | Fix | `worker_runner.py` | Medium |
| 6 | Add RTMP buffer size | Fix | `ffmpeg_output.py` | Low |

**Note**: Start with Step 0 (Baseline) if root cause is unknown. Diagnostic fixes (1-2) help identify root cause after baseline.

---

## Automated Test Procedure

### Step 0: Baseline Capture (FIRST RUN ONLY)

**Purpose**: Understand actual failure behavior before making any changes.

```bash
# 1. Verify code is clean (no uncommitted changes)
git status --short apps/media-service/

# 2. Run test procedure (Steps 1-5) WITHOUT any code changes
# 3. Document in TROUBLESHOOTING_STATUS.md:
#    - Exact error messages
#    - Time until failure (if any)
#    - FFmpeg exit codes
#    - Segment push patterns
```

**This step is complete when you can answer:**
- Does the stream fail? If so, after how long?
- What error messages appear?
- Are segments being generated and pushed?
- What's the gap between segment pushes?

---

### Step 1: Start Services (Background)

```bash
# Run in background - starts Docker services
export RTMP_OUTPUT_URL="rtmp://a.rtmp.youtube.com/live2/YOUR_STREAM_KEY"
make dev-down 2>/dev/null; make dev-up-light
```

Use Bash tool with `run_in_background: true` for service startup.

### Step 2: Wait for Services Ready

```bash
# Check services are up (wait up to 60s)
for i in {1..12}; do
  docker ps --format "{{.Names}}: {{.Status}}" | grep -E "media-service|mediamtx|sts" && break
  sleep 5
done
```

### Step 3: Push Test Stream (Background)

```bash
# Run in background - pushes test stream
ffmpeg -re -stream_loop -1 \
    -i tests/fixtures/test-streams/speech_zh.mp4 \
    -c:v libx264 -preset ultrafast -tune zerolatency -g 30 -keyint_min 30 \
    -c:a aac -b:a 128k \
    -f flv "rtmp://localhost:1935/live/test-stream/in" \
    2>&1
```

### Step 4: Monitor Logs (5 minutes)

```bash
# Wait and collect logs
sleep 300  # Wait 5 minutes for segments to process

# Get relevant logs
docker logs media-service 2>&1 | grep -iE "push|ffmpeg|gap|error|disconnect|segment|idle|died" | tail -100
```

### Step 5: Check for Errors

```bash
# Check if ffmpeg publisher is still running
docker exec media-service pgrep -a ffmpeg

# Check for specific error patterns
docker logs media-service 2>&1 | grep -iE "error|broken|died|disconnect|failed" | tail -20
```

### Step 6: Cleanup

```bash
# Stop test stream (kill background ffmpeg)
pkill -f "ffmpeg.*test-stream" 2>/dev/null || true

# Stop services
make dev-down
```

---

## Success Criteria

**Stream is considered stable if:**
1. FFmpeg publisher process stays alive for 5+ minutes
2. No `error`, `broken pipe`, `died`, or `disconnect` messages in logs
3. Segments are being pushed (look for `PUSH` or `Pushed` messages)
4. Gap between pushes is reasonable (< 60s for 30s segments)

---

## Fix Implementations

### Fix 1: Add FFmpeg Stderr Monitoring

**Purpose**: Capture FFmpeg error output to understand disconnection cause.

**File**: `apps/media-service/src/media_service/pipeline/ffmpeg_output.py`

**Changes**:

1. Add instance variables in `__init__`:
```python
        # Stderr monitoring thread
        self._stderr_thread: threading.Thread | None = None
        self._stderr_running = False
```

2. Add method before `_start_ffmpeg_publisher`:
```python
    def _stderr_monitor_loop(self) -> None:
        """Monitor ffmpeg stderr output continuously."""
        logger.info("FFmpeg stderr monitor started")
        while self._stderr_running and self._process and self._process.stderr:
            try:
                line = self._process.stderr.readline()
                if not line:
                    if self._process.poll() is not None:
                        logger.warning(f"FFmpeg process exited: {self._process.returncode}")
                        break
                    continue
                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str:
                    if "error" in line_str.lower():
                        logger.error(f"FFMPEG: {line_str}")
                    else:
                        logger.info(f"FFMPEG: {line_str}")
            except Exception as e:
                logger.debug(f"Stderr monitor error: {e}")
                break
        logger.info("FFmpeg stderr monitor stopped")
```

3. In `_start_ffmpeg_publisher`, after process starts:
```python
            # Start stderr monitoring thread
            self._stderr_running = True
            self._stderr_thread = threading.Thread(
                target=self._stderr_monitor_loop,
                name="FFmpegStderrMonitor",
                daemon=True,
            )
            self._stderr_thread.start()
```

4. In `stop` method:
```python
        # Stop stderr monitor
        self._stderr_running = False
```

**Expected logs**: `FFMPEG: ...` lines showing FFmpeg output.

---

### Fix 2: Add Segment Timing Diagnostics

**Purpose**: Track time gaps between segment pushes to identify timeout issues.

**File**: `apps/media-service/src/media_service/pipeline/ffmpeg_output.py`

**Changes**:

1. Add import and instance variable:
```python
import time

# In __init__:
        self._segment_count: int = 0
```

2. Replace `_publisher_loop`:
```python
    def _publisher_loop(self) -> None:
        """Publisher thread loop - reads muxed segments and pushes to ffmpeg."""
        logger.info("Publisher thread started")
        last_push_time = time.time()

        while self._publisher_running:
            try:
                segment_data = self._segment_queue.get(timeout=0.5)
                if segment_data is None:
                    break

                if self._process and self._process.stdin:
                    try:
                        current_time = time.time()
                        gap = current_time - last_push_time

                        if self._first_segment_sent:
                            segment_data = self._strip_flv_header(segment_data)
                        else:
                            self._first_segment_sent = True
                            logger.info("First segment (keeping FLV header)")

                        self._segment_count += 1
                        logger.info(f"PUSH #{self._segment_count}: {len(segment_data)} bytes, gap={gap:.2f}s")

                        if gap > 15.0:
                            logger.warning(f"LARGE GAP: {gap:.2f}s - YouTube may disconnect!")

                        self._process.stdin.write(segment_data)
                        self._process.stdin.flush()
                        last_push_time = time.time()

                        if self._process.poll() is not None:
                            logger.error(f"FFmpeg died! Code: {self._process.returncode}")
                            break

                    except BrokenPipeError:
                        logger.error("ffmpeg stdin broken pipe")
                        self._check_ffmpeg_error()
                        break
                    except Exception as e:
                        logger.error(f"Error writing to ffmpeg: {e}")

            except Empty:
                idle = time.time() - last_push_time
                if idle > 20.0 and self._first_segment_sent:
                    logger.warning(f"IDLE: No segment for {idle:.1f}s")
                continue
            except Exception as e:
                logger.error(f"Publisher error: {e}")

        logger.info("Publisher thread stopped")
```

**Expected logs**: `PUSH #N: X bytes, gap=Y.YYs` and `LARGE GAP` warnings.

---

### Fix 3: Add YouTube RTMP Options

**Purpose**: Use YouTube-specific RTMP parameters.

**File**: `apps/media-service/src/media_service/pipeline/ffmpeg_output.py`

**Changes** in `_start_ffmpeg_publisher`:
```python
        is_youtube = "youtube.com" in self._rtmp_url or "rtmp.youtube.com" in self._rtmp_url

        cmd = [
            "ffmpeg", "-y",
            "-fflags", "+genpts",
            "-re",
            "-f", "flv",
            "-i", "pipe:0",
            "-c", "copy",
        ]

        if is_youtube:
            logger.info("Detected YouTube RTMP - using optimized options")
            cmd.extend(["-rtmp_live", "live"])

        cmd.extend(["-f", "flv", "-flvflags", "no_duration_filesize", self._rtmp_url])
```

---

### Fix 4: Improve Timestamp Handling

**Purpose**: Ignore DTS to prevent timestamp conflicts.

**Change**:
```python
"-fflags", "+genpts+igndts",  # was: "+genpts"
```

---

### Fix 5: Reduce Segment Duration

**Purpose**: Smaller segments = more frequent pushes = less timeout risk.

**File**: `apps/media-service/src/media_service/worker/worker_runner.py`

**Change**:
```python
segment_duration_ns: int = 10_000_000_000  # was: 30_000_000_000
```

---

### Fix 6: Add RTMP Buffer Size

**Purpose**: Buffer to handle network hiccups.

**Change** (add to YouTube detection):
```python
cmd.extend(["-rtmp_live", "live", "-rtmp_buffer", "3000"])
```

---

## Revert Commands

```bash
# Revert all changes
git checkout -- apps/media-service/src/media_service/pipeline/ffmpeg_output.py
git checkout -- apps/media-service/src/media_service/worker/worker_runner.py
```

---

## Status File Template

```markdown
# YouTube RTMP Troubleshooting Status

## Current State
- Last fix: None
- Status: Not started

## Fix History

| # | Fix | Result | Key Findings |
|---|-----|--------|--------------|
| - | -   | -      | -            |

## Observations
- (Add observations from each test)
```

---

## Triggers

| Trigger | Action |
|---------|--------|
| `/youtube-rtmp-debug` | Start/continue troubleshooting |

---

*YouTube RTMP Debug - Automated testing, one fix per iteration*
