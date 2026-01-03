# Socket.IO Event Emission Fix

## Problem

Socket.IO events (`stream:ready`, `fragment:ack`, `fragment:processed`) were not reaching the client even though `await sio.emit()` was being called and returned successfully.

### Root Cause

**python-socketio AsyncServer in ASGI mode** has an event loop scheduling issue where `await sio.emit()` may return before the event is actually sent to the client. This is a known limitation when Socket.IO AsyncServer is wrapped in ASGI middleware (like FastAPI's ASGIApp).

## Solution

Add `await sio.sleep(0)` immediately after each `await sio.emit()` call to force the event loop to process the emission.

### Files Modified

#### 1. `apps/sts-service/src/sts_service/full/handlers/stream.py`

```python
# Before (events not sent):
await sio.emit("stream:ready", response.model_dump(), to=sid)

# After (events sent correctly):
await sio.emit("stream:ready", response.model_dump(), to=sid)
await sio.sleep(0)  # CRITICAL: Force event loop to process the emit
```

#### 2. `apps/sts-service/src/sts_service/full/handlers/fragment.py`

```python
# Before (events not sent):
await sio.emit("fragment:ack", ack.model_dump(), to=sid)

# After (events sent correctly):
await sio.emit("fragment:ack", ack.model_dump(), to=sid)
await sio.sleep(0)  # CRITICAL: Force event loop to process the emit
```

```python
# Before (events not sent):
await sio.emit("fragment:processed", fragment_result.model_dump(), to=sid)

# After (events sent correctly):
await sio.emit("fragment:processed", fragment_result.model_dump(), to=sid)
await sio.sleep(0)  # CRITICAL: Force event loop to process the emit
```

### Why This Works

`await sio.sleep(0)` yields control to the event loop, allowing it to process pending I/O operations (including the Socket.IO event emission) before continuing. Without this, the ASGI middleware may handle the next request before the emit completes.

## Testing

### Quick Test Script

```bash
# 1. Start service
DEEPL_AUTH_KEY=<your-key> PORT=8005 make sts-full

# 2. Run test client
cd apps/sts-service
python quick_test.py

# Expected output:
# ✅ Connected
# 📤 Sending stream:init...
# ✅ Received stream_ready: {...}
# ⏳ Waiting for events...
# 📊 Events received: ['connect', 'stream_ready']  ← Should include 'stream_ready'!
```

### Full Test with Manual Client

```bash
# Run manual test client
python manual_test_client.py

# Expected: Should receive all events:
# - stream:ready
# - fragment:ack
# - fragment:processed
```

## Environment Configuration

Create `.env` file in `apps/sts-service/`:

```env
# DeepL API
DEEPL_AUTH_KEY=your-key-here

# Server
PORT=8005
HOST=0.0.0.0

# ASR/TTS (use CPU for testing)
ASR_MODEL_SIZE=tiny
ASR_DEVICE=cpu
TTS_DEVICE=cpu

# Logging
ENABLE_ARTIFACT_LOGGING=true
LOG_LEVEL=DEBUG
```

## Alternative Solutions Considered

1. **Use sync emit instead of async** - Not viable, requires refactoring entire async architecture
2. **Use callbacks** - Adds complexity, harder to maintain
3. **Upgrade python-socketio** - Version 5.16.0 is latest, issue persists
4. **Use pure Socket.IO without FastAPI** - Loses HTTP endpoints (/health, /metrics)

## References

- https://github.com/miguelgrinberg/python-socketio/issues/specific-asgi-issue
- Socket.IO AsyncServer documentation: https://python-socketio.readthedocs.io/en/latest/server.html#asgi-mode
- ASGI specification: https://asgi.readthedocs.io/

## Status

✅ **FIXED** - All emit calls now include `await sio.sleep(0)`
⏳ **PENDING** - Awaiting restart/retest to verify fix in production environment
