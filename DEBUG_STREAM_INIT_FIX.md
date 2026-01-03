# Stream Initialization Silent Failure - FIXED

## Root Cause

The STS service instances running on ports 8000-8003 had **stale code**.

**The Error:**
```
TypeError: PipelineCoordinator.__init__() got an unexpected keyword argument 'source_language'
```

**What Happened:**
- The old code in `handlers/stream.py` was incorrectly passing `source_language` to `PipelineCoordinator.__init__()`
- The code has already been fixed (lines 142-148 in current `stream.py`)
- However, the running services weren't restarted to pick up the new code
- This caused initialization to fail silently (caught by exception handler, emitting error event)

## The Fix

The code fix is already in place. You just need to restart the service.

### Quick Fix (Recommended)

Run the provided restart script:

```bash
./restart_full_sts.sh
```

This will:
1. Kill all old STS service instances (ports 8000-8003)
2. Start a fresh Full STS Service on port 8003
3. Enable artifact logging
4. Write logs to `/tmp/claude/sts-service.log`

### Manual Fix (Alternative)

If you prefer to restart manually:

```bash
# 1. Kill old processes
kill 6776 20371 26193 36568

# 2. Wait for ports to be released
sleep 2

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Start Full STS Service
cd apps/sts-service
export PORT=8003
export ENABLE_ARTIFACT_LOGGING=true
export ARTIFACTS_PATH=/tmp/claude/sts-artifacts
nohup python -m sts_service.full > /tmp/claude/sts-service.log 2>&1 &
```

### Testing the Fix

Run the manual test client:

```bash
cd apps/sts-service
python manual_test_client.py
```

Expected output:
```
✅ Connected to server
🎬 Stream Ready!
   Session ID: <uuid>
✓ Fragment ACK received
📦 Fragment Processed
   🎤 Transcript (EN): [transcribed text]
   🌍 Translation (ES): [translated text]
   🔊 Dubbed Audio: [audio metadata]
```

## What Was Wrong in Old Code

**Before (Old Code):**
```python
pipeline = PipelineCoordinator(
    asr=asr,
    translation=translation,
    tts=tts,
    source_language=session.source_language,  # ❌ Invalid argument
    target_language=session.target_language,  # ❌ Invalid argument
    enable_artifact_logging=enable_artifact_logging,
)
```

**After (Current Code):**
```python
pipeline = PipelineCoordinator(
    asr=asr,
    translation=translation,
    tts=tts,
    enable_artifact_logging=enable_artifact_logging,  # ✅ Correct
)
```

The `PipelineCoordinator.__init__()` signature (from `pipeline.py`) only accepts:
- `asr: ASRComponentProtocol`
- `translation: TranslationComponentProtocol`
- `tts: TTSComponentProtocol`
- `enable_artifact_logging: bool = True`

Language configuration is passed to individual components (ASR, Translation, TTS) during their initialization, NOT to the coordinator.

## Monitoring

### View Logs in Real-Time
```bash
tail -f /tmp/claude/sts-service.log
```

### Check Service Status
```bash
lsof -ti:8003  # Should return a PID if running
```

### Check Artifacts
```bash
ls -la /tmp/claude/sts-artifacts/manual-test-stream/manual-test-001/
```

Expected artifacts:
- `transcript.txt` - ASR output
- `translation.txt` - Translated text
- `dubbed_audio.m4a` - Final dubbed audio (M4A format)
- `original_audio.m4a` - Original input audio
- `metadata.json` - Processing metadata (timings, duration metrics)

## Verification Checklist

- [ ] Old processes killed (no processes on ports 8000-8003)
- [ ] New service started on port 8003
- [ ] Service logs show "Stream initialized" message
- [ ] Manual test client connects successfully
- [ ] `stream:ready` event received
- [ ] Fragment processed successfully
- [ ] Artifacts created in `/tmp/claude/sts-artifacts/`
- [ ] Dubbed audio playable: `ffplay test_dubbed_output.m4a`

## Next Steps

Once verified:
1. Add a Makefile target for easy restarts: `make sts-full`
2. Consider adding process management (systemd, supervisor, or pm2)
3. Add health check endpoint to detect stale code issues
4. Update CLAUDE.md with Full STS Service commands
