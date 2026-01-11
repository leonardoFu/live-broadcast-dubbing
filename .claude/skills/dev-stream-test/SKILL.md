---
name: dev-stream-test
description: Start dev services, push test stream to MediaMTX, and check logs for errors.
---

# Dev Stream Test

Quick development workflow to start services, push a test stream, and verify no errors in logs.

## Execution Flow

1. **Stop existing services** → `make dev-down`
2. **Start services** → `make dev-up-light`
3. **Wait for services** → Health check endpoints
4. **Push test stream** → ffmpeg push speech.mp4 to MediaMTX
5. **Verify output stream** → ffprobe check video (h264) and audio (aac) codecs
6. **Monitor logs** → Check for errors in service logs

---

## Commands Reference

```bash
# Stop services
make dev-down

# Start lightweight services (MediaMTX + media-service + STS with ElevenLabs)
make dev-up-light

# View logs
make dev-logs
```

---

## Service Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| MediaMTX RTMP | rtmp://localhost:1935 | Stream ingest |
| MediaMTX RTSP | rtsp://localhost:8554 | Stream playback |
| MediaMTX API | http://localhost:9997/v3/paths/list | Stream status |
| Media Service | http://localhost:8080/health | Health check |
| STS Service | http://localhost:8000/health | Health check |

---

## Test Stream Asset

**File**: `tests/fixtures/test-streams/speech.mp4`

This is a short speech audio/video file suitable for testing the dubbing pipeline.

---

## FFmpeg Push Command

Push the test stream to MediaMTX:

```bash
ffmpeg -re -stream_loop -1 \
  -i tests/fixtures/test-streams/speech.mp4 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -c:a aac -b:a 128k \
  -f flv "rtmp://localhost:1935/live/test-stream/in"
```

**Parameters**:
- `-re` - Read input at native frame rate (real-time)
- `-stream_loop -1` - Loop the input indefinitely
- `-c:v libx264` - Re-encode video with H.264
- `-preset veryfast -tune zerolatency` - Low latency encoding
- `-c:a aac` - Re-encode audio with AAC
- `-f flv` - Output as FLV container for RTMP

---

## Output Stream Verification

After the stream is processed, verify the output stream is playing with correct codecs:

```bash
# Probe the output stream via RTSP
ffprobe -v error -show_streams -of json "rtsp://localhost:8554/live/test-stream/out"
```

**Expected Output**:
- **Video**: H.264 codec (`codec_name: "h264"`)
- **Audio**: AAC codec (`codec_name: "aac"`)

**Quick Validation Command**:
```bash
# One-liner to check codecs
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "rtsp://localhost:8554/live/test-stream/out" && \
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "rtsp://localhost:8554/live/test-stream/out"
```

Should output:
```
h264
aac
```

---

## Error Detection

After pushing the stream, check logs for errors:

```bash
# Get recent logs and filter for errors
docker compose -f apps/media-service/docker-compose.yml logs --tail=200 2>&1 | grep -iE "(error|exception|fail|critical)" || echo "No errors found"
```

Common error patterns to look for:
- `ERROR` - Application errors
- `Exception` - Python exceptions
- `FAIL` - Test or assertion failures
- `critical` - Critical level logs

---

## Full Workflow Script

```bash
#!/bin/bash
set -e

echo "=== Step 1: Stopping existing services ==="
make dev-down

echo ""
echo "=== Step 2: Starting services ==="
make dev-up-light

echo ""
echo "=== Step 3: Waiting for services to be ready ==="
sleep 10

# Health checks
echo "Checking MediaMTX..."
curl -sf http://localhost:9997/v3/paths/list > /dev/null && echo "MediaMTX: OK" || echo "MediaMTX: FAIL"

echo "Checking media-service..."
curl -sf http://localhost:8080/health > /dev/null && echo "media-service: OK" || echo "media-service: FAIL"

echo "Checking STS service..."
curl -sf http://localhost:8000/health > /dev/null && echo "STS: OK" || echo "STS: FAIL"

echo ""
echo "=== Step 4: Pushing test stream ==="
echo "Publishing tests/fixtures/test-streams/speech.mp4 to rtmp://localhost:1935/live/test-stream/in"
echo "Press Ctrl+C to stop the stream..."

# Run ffmpeg in background, capture PID
ffmpeg -re -stream_loop -1 \
  -i tests/fixtures/test-streams/speech.mp4 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -c:a aac -b:a 128k \
  -f flv "rtmp://localhost:1935/live/test-stream/in" &
FFMPEG_PID=$!

# Wait for stream to establish
sleep 15

echo ""
echo "=== Step 5: Verifying output stream codecs ==="
echo "Probing output stream at rtsp://localhost:8554/live/test-stream/out..."

VIDEO_CODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "rtsp://localhost:8554/live/test-stream/out" 2>/dev/null || echo "NONE")
AUDIO_CODEC=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "rtsp://localhost:8554/live/test-stream/out" 2>/dev/null || echo "NONE")

echo "Video codec: $VIDEO_CODEC (expected: h264)"
echo "Audio codec: $AUDIO_CODEC (expected: aac)"

if [ "$VIDEO_CODEC" = "h264" ] && [ "$AUDIO_CODEC" = "aac" ]; then
    echo "Output stream codecs: OK"
else
    echo "WARNING: Output stream codec mismatch!"
fi

echo ""
echo "=== Step 6: Checking logs for errors ==="
docker compose -f apps/media-service/docker-compose.yml logs --tail=500 2>&1 | grep -iE "(error|exception|fail|critical)" || echo "No errors found in media-service logs"

# Cleanup
echo ""
echo "Stopping ffmpeg stream..."
kill $FFMPEG_PID 2>/dev/null || true

echo ""
echo "=== Done ==="
```

---

## Execution Instructions

When this skill is invoked, execute the following steps:

### Step 1: Stop existing services
```bash
make dev-down
```

### Step 2: Start lightweight services
```bash
make dev-up-light
```

### Step 3: Wait and verify services are ready
Wait ~10 seconds, then check:
- `curl -sf http://localhost:9997/v3/paths/list` (MediaMTX)
- `curl -sf http://localhost:8080/health` (media-service)
- `curl -sf http://localhost:8000/health` (STS)

### Step 4: Push test stream
Run ffmpeg in background to push speech.mp4:
```bash
ffmpeg -re -stream_loop -1 \
  -i tests/fixtures/test-streams/speech.mp4 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -c:a aac -b:a 128k \
  -f flv "rtmp://localhost:1935/live/test-stream/in"
```

### Step 5: Verify output stream codecs
After stream runs for ~15 seconds, probe the output stream:
```bash
# Check video codec
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "rtsp://localhost:8554/live/test-stream/out"

# Check audio codec
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "rtsp://localhost:8554/live/test-stream/out"
```

Expected results:
- Video: `h264`
- Audio: `aac`

Report findings to user:
- If codecs match: Report output stream is healthy
- If codecs don't match or stream unavailable: Report warning

### Step 6: Check logs for errors
```bash
make dev-logs 2>&1 | grep -iE "(error|exception|fail|critical)" | head -50
```

Report findings to user:
- If errors found: Show the error lines and suggest investigation
- If no errors: Report success

---

## Triggers

| Trigger | Action |
|---------|--------|
| `/dev-stream-test` | Run full workflow |
| `dev-stream-test` | Run full workflow |

---

## Constraints

**MUST**:
- Always run `make dev-down` before `make dev-up-light` to ensure clean state
- Wait for services to be healthy before pushing stream
- Run ffmpeg in background so logs can be checked
- Clean up ffmpeg process after checking logs

**MUST NOT**:
- Leave orphan ffmpeg processes running
- Skip health checks
- Ignore errors in logs

---

*Dev Stream Test - Quick validation of the dubbing pipeline with test fixtures*
