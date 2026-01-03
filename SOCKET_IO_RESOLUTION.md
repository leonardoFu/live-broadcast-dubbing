# Socket.IO Event Emission Issue - RESOLVED ✅

## Summary

**Issue**: Socket.IO events (`stream:ready`, `fragment:ack`, `fragment:processed`) were not reaching the client.

**Root Cause**: TWO issues were identified:
1. **Server-side**: `await sio.emit()` in ASGI mode doesn't flush events to clients
2. **Client-side**: Event handler registration using `@sio.event` doesn't work with event names containing colons

**Status**: ✅ **BOTH ISSUES FIXED** - Events now working perfectly

---

## Issue #1: Server-Side ASGI Event Loop Issue

### Problem

python-socketio AsyncServer in ASGI mode (wrapped with FastAPI) has an event loop scheduling issue where `await sio.emit()` returns successfully but the event is not sent to the client until the ASGI middleware processes the next request.

### Solution

Add `await sio.sleep(0)` immediately after each `await sio.emit()` call to force the event loop to process the emission.

### Files Modified

1. **apps/sts-service/src/sts_service/full/handlers/stream.py** (line ~177)
2. **apps/sts-service/src/sts_service/full/handlers/fragment.py** (lines ~105, ~262)

### Code Changes

```python
# Before (events not sent):
await sio.emit("stream:ready", response.model_dump(), to=sid)

# After (events sent correctly):
await sio.emit("stream:ready", response.model_dump(), to=sid)
await sio.sleep(0)  # CRITICAL: Force event loop to process the emit
```

---

## Issue #2: Client-Side Event Handler Registration

### Problem

When using `@sio.event` decorator, the function name must match the event name exactly (with underscores replacing special characters). But our events use colons (`:`) in their names:
- Server emits: `stream:ready`
- Client expects: `stream_ready` (when using `@sio.event`)
- Result: **Event received but handler not called**

### Solution

Use `@sio.on('event:name')` decorator with explicit event name instead of `@sio.event`.

### Files Modified

1. **apps/sts-service/quick_test.py** (lines ~14-22)
2. **apps/sts-service/manual_test_client.py** (lines ~69-133)

### Code Changes

```python
# Before (handler not called):
@sio.event
async def stream_ready(data):
    print(f"Received: {data}")

# After (handler called correctly):
@sio.on('stream:ready')
async def on_stream_ready(data):
    print(f"Received: {data}")
```

---

## Verification

### Quick Test

```bash
cd apps/sts-service
python quick_test.py
```

**Expected Output**:
```
✅ Connected
📤 Sending stream:init...
✅ Received stream:ready: {...}
⏳ Waiting for events...
📊 Events received: ['connect', 'stream:ready']  ✅
```

### Full E2E Test

```bash
STS_PORT=8005 python manual_test_client.py
```

**Expected Output**:
```
✅ Connected to server
🎬 Stream Ready!
✓ Fragment ACK received
📦 Fragment Processed
```

---

## Technical Details

### Why `await sio.sleep(0)` Works

`await sio.sleep(0)` yields control back to the event loop without actually sleeping. This allows the event loop to:
1. Process pending I/O operations (including Socket.IO event emissions)
2. Flush websocket buffers
3. Send queued packets to clients

Without this, the ASGI middleware may handle the next request before the emit completes, causing events to be delayed or lost.

### Why `@sio.on()` vs `@sio.event`

- **`@sio.event`**: Derives event name from function name (e.g., `stream_ready` → event `stream_ready`)
- **`@sio.on('event:name')`**: Explicitly specifies event name (supports colons, dashes, etc.)

For events with special characters like `stream:ready`, you MUST use `@sio.on('stream:ready')`.

---

## Server Logs (Proof of Fix)

With debug logging enabled, you can see the emit succeeding:

```
2026-01-02 23:19:12,976 - sts_service.full.handlers.stream - INFO - [DEBUG] About to emit stream:ready to sid=TL1IfNYxerIvVGltAAAB
emitting event "stream:ready" to TL1IfNYxerIvVGltAAAB [/]
bY-h7wuJULjUXVcsAAAA: Sending packet MESSAGE data 2["stream:ready",{...}]
2026-01-02 23:19:12,977 - sts_service.full.handlers.stream - INFO - [DEBUG] Emit returned: None
```

### Client Logs (Proof of Fix)

With client logging enabled, you can see events being received AND handlers being called:

```
Received packet MESSAGE data 2["stream:ready",{...}]
Received event "stream:ready" [/]
✅ Received stream:ready: {...}
```

---

## Environment Setup

Create `.env` file in `apps/sts-service/`:

```env
DEEPL_AUTH_KEY=your-key-here
PORT=8005
HOST=0.0.0.0
ASR_MODEL_SIZE=tiny
ASR_DEVICE=cpu
TTS_DEVICE=cpu
ENABLE_ARTIFACT_LOGGING=true
LOG_LEVEL=DEBUG
```

---

## Known Separate Issues

### Processing Failure (Unrelated to Socket.IO)

The full E2E test shows processing failure due to Pydantic validation error:

```
"error": {
  "stage": "asr",
  "code": "ASR_FAILED",
  "message": "5 validation errors for TranscriptAsset: asset_id field required, fragment_id field required..."
}
```

**This is a separate bug in the ASR/pipeline code** (TranscriptAsset model instantiation) and is NOT related to the Socket.IO fix. The Socket.IO events are working correctly - we successfully receive `fragment:processed` with the error details.

---

## References

- [python-socketio AsyncServer Documentation](https://python-socketio.readthedocs.io/en/latest/server.html#asgi-mode)
- [Socket.IO Event Emitter API](https://socket.io/docs/v4/emitting-events/)
- [ASGI Specification](https://asgi.readthedocs.io/)

---

## Commit Message

```
fix: resolve Socket.IO event emission in ASGI mode

Two issues fixed:
1. Server: Add await sio.sleep(0) after emits to force event loop processing
2. Client: Use @sio.on('event:name') for events with colons in their names

Changes:
- handlers/stream.py: Add sio.sleep(0) after stream:ready emit
- handlers/fragment.py: Add sio.sleep(0) after fragment:ack and fragment:processed emits
- quick_test.py: Fix event handler registration
- manual_test_client.py: Fix event handler registration

Verified with quick_test.py and full E2E manual_test_client.py.
All Socket.IO events now reaching client successfully.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```
