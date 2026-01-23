# YouTube RTMP Troubleshooting Status

## Current State
- Last fix: #11 - Ping Timeout Increase
- Status: **AWAITING MANUAL VERIFICATION**

## Test Configuration
- **Success Criteria**: Stream stable for 5+ minutes, no errors in logs
- **YouTube Endpoint**: `rtmp://a.rtmp.youtube.com/live2/5c26-kw4d-k8mu-hm8a-bebz`
- **Test File**: `tests/fixtures/test-streams/speech_zh.mp4`
- **STS Service**: ElevenLabs STS (`make dev-up-light`)

## Fix History

| # | Fix | Result | Key Findings |
|---|-----|--------|--------------|
| 0 | Baseline | **SUCCESS** | Stream ran 5+ minutes without errors. No disconnection. |
| 1 | New failure (2026-01-18 23:40) | **FAILURE** | Socket.IO disconnected, reconnected but stream NOT reinitialized |
| 7 | Socket.IO reconnection fix | **APPLIED** | Stream reinits after reconnect, but FFmpeg not restarted |
| 8 | A/V duration mismatch fix | **APPLIED** | Not the root cause (durations match at ~30s) |
| 9 | FFmpeg auto-restart | **APPLIED** | Clears stale queue, restarts FFmpeg (up to 3 attempts) |
| 10 | Socket.IO manual reconnect | **APPLIED** | Auto-reconnect fails silently; added manual retry |
| 11 | Ping timeout increase | **TESTING** | Root cause: TTS takes 15s, ping_timeout was 10s |

## Fix Queue

| # | Fix Name | Type | Status |
|---|----------|------|--------|
| 0 | Baseline capture | Diagnostic | **COMPLETED** |
| 7 | Socket.IO reconnection fix | Fix | **APPLIED** |
| 8 | A/V duration mismatch fix | Fix | **APPLIED** |
| 9 | FFmpeg auto-restart | Fix | **APPLIED** |
| 10 | Socket.IO manual reconnect | Fix | **APPLIED** |
| 11 | **Ping timeout increase** | Fix | **TESTING** |
| 1-6 | Other FFmpeg/RTMP fixes | Fix | Deferred |

---

## Fix #11: Ping Timeout Increase (2026-01-19)

### Problem Identified

From user's logs showing:
```
engineio.client - ERROR - packet queue is empty, aborting
```

**Root Cause Analysis**:
- STS service `ping_timeout` was 10 seconds (default)
- TTS processing takes 12-15 seconds per fragment
- During TTS processing, the event loop is blocked
- This prevents responding to ping packets from the server
- After 10 seconds without a pong response, the connection is dropped
- Engine.IO logs "packet queue is empty, aborting" as the connection dies

### Fix Applied

**Files**:
- `apps/sts-service/src/sts_service/full/config.py`
- `apps/sts-service/src/sts_service/echo/config.py`

**Changes**:
- Increased `ping_timeout` from 10 seconds to 60 seconds
- Added comment explaining the reason for the increase

**Code**:
```python
# Increased from 10s to 60s - TTS processing can take 15+ seconds
# which may block the event loop and delay ping responses
ping_timeout: int = field(default_factory=lambda: int(os.getenv("WS_PING_TIMEOUT", "60")))
```

### Verification Steps

1. Rebuild and restart STS service (to pick up new config)
2. Start YouTube stream
3. Watch for:
   - No "packet queue is empty" errors
   - Socket.IO connection stays stable
   - Stream stable for 5+ minutes

---

## Fix #9: FFmpeg Auto-Restart (2026-01-19)

### Problem Identified

From user's observation:
- Socket.IO disconnects and reconnects successfully
- Stream processing resumes after reconnect
- **But FFmpeg process crashed and was never restarted**
- New segments queued but never pushed to YouTube

### Fix Applied

**File**: `apps/media-service/src/media_service/pipeline/ffmpeg_output.py`

**Changes**:
1. Added `_restart_ffmpeg()` method to clean up and restart FFmpeg process
2. Modified `_publisher_loop()` to detect FFmpeg crash and auto-restart
3. Up to 3 restart attempts before giving up
4. Resets `_first_segment_sent` flag so new FLV header is sent

**Expected Logs on Restart**:
```
🔴 FFmpeg process died with exit code X
🔄 Restart attempt 1/3
🔄 Attempting to restart FFmpeg...
✅ FFmpeg restarted successfully
📦 First segment (keeping FLV header)
📤 Pushed segment #N: X bytes (total: Y MB)
```

---

## Fix #8: A/V Duration Mismatch (2026-01-19)

### Problem Identified

From user's logs:
```
Video segment emitted: batch=10, duration=31.47s
Audio segment emitted: batch=10, duration=30.00s

Video segment emitted: batch=11, duration=31.37s
Audio segment emitted: batch=11, duration=30.00s
```

**Root Cause**: Video segments wait for keyframes (~31s), but audio is fixed at 30s. This ~1.4s mismatch per segment accumulates:
- After 10 segments: ~14 seconds of A/V drift
- YouTube disconnects streams with significant A/V desync

### Fix Applied

**File**: `apps/media-service/src/media_service/pipeline/ffmpeg_output.py`

**Changes**:
1. Added audio time-stretching using FFmpeg's `atempo` filter
2. When video duration ≠ audio duration (>100ms diff), stretch audio to match
3. Added FFmpeg stderr monitoring for real-time error capture
4. Added FFmpeg process health checks
5. Added segment push counting for debugging

**Expected Logs**:
```
⏱️ Time-stretching audio: 30.00s -> 31.47s (tempo=0.9533)
📤 Pushed segment #N: X bytes (total: Y MB)
🔴 FFmpeg: <any errors will now be visible>
```

### Verification Steps

1. Rebuild and restart media-service
2. Start YouTube stream
3. Watch for:
   - `⏱️ Time-stretching audio` logs (confirms fix is active)
   - Stream stability for 5+ minutes
   - No `🔴 FFmpeg` error messages

---

## Previous Analysis

### Socket.IO Reconnection Bug (Fix #7 - Applied)

**Timeline:**
```
23:40:31 - Batch 6 output successfully (last working output at ~180s = 3 min)
23:41:16 - Batch 8 audio sent to STS
23:41:25 - Batch 8 video segment emitted
23:41:31 - Socket.IO DISCONNECTED
23:41:40 - Socket.IO reconnected (after ~9 seconds)
23:41:46 - Fragment timeout for batch 7 (60s elapsed)
23:41:46 - ERROR: "Stream not ready - call init_stream() first"
```

**Fix Applied**: Auto-reinitialize stream on reconnection in `socketio_client.py`

**User Feedback**: Still disconnecting after this fix - suggests additional root cause.

---

## Baseline Results (2026-01-18 23:27 - 23:34)

### Test Duration
- Stream started: 23:28:18
- Test ended: ~23:34 (5+ minutes)
- Total runtime: **~6 minutes**

### Stream Health
- **FFmpeg publisher**: Running (PID 50, still alive at end of test)
- **Errors**: None
- **Disconnections**: None
- **Broken pipes**: None

### Segment Push Timing
| Time | Size | Gap from Previous |
|------|------|------------------|
| 23:29:35 | 13.96 MB | (first) |
| 23:30:05 | 14.04 MB | ~30s |
| 23:30:35 | 14.00 MB | ~30s |
| 23:31:05 | 13.91 MB | ~30s |
| 23:31:35 | 14.06 MB | ~30s |
| 23:32:05 | 14.18 MB | ~30s |
| 23:32:35 | 13.92 MB | ~30s |
| 23:33:05 | 14.23 MB | ~30s |
| 23:33:35 | 14.04 MB | ~30s |

**Gaps**: All gaps are ~30 seconds (matching segment duration)
