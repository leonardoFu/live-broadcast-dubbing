---
name: local-media-test
description: Manual testing guide for media-service with echo-sts locally. Full step-by-step instructions.
---

# Local Media Service Testing

Complete manual testing workflow for media-service + echo-sts. Echo STS returns audio unchanged (no real ASR/TTS), making it ideal for fast pipeline testing.

---

## Quick Start (TL;DR)

```bash
# Terminal 1: Start services
make dev-up-echo

# Terminal 2: Push test stream (wait 10s for services)
make dev-push

# Terminal 3: Play output (wait ~35s for first segment)
make dev-play
```

---

## Prerequisites

- Docker and Docker Compose installed
- ffmpeg and ffplay installed locally
- Test fixture exists: `tests/fixtures/test-streams/speech_zh.mp4`

---

## Step 1: Start Services

Start media-service with Echo STS (no API keys required):

```bash
make dev-up-echo
```

This starts:
- **MediaMTX** - RTMP/RTSP media server (ports 1935, 8554, 9997)
- **media-service** - Stream processing pipeline (port 8080)
- **echo-sts** - Echo STS service that returns input audio unchanged (port 3000)

### Verify Services Are Healthy

```bash
# Check all services
curl -s http://localhost:9997/v3/paths/list  # MediaMTX API
curl -s http://localhost:8080/health          # media-service
curl -s http://localhost:3000/health          # echo-sts
```

All should return successfully (HTTP 200).

---

## Step 2: Push Test Stream

**IMPORTANT**: Use `-c:v copy` (not `-c:v libx264`) due to GStreamer flvdemux compatibility.

```bash
# Option A: Use make target
make dev-push

# Option B: Manual ffmpeg command
ffmpeg -re -stream_loop -1 \
  -i tests/fixtures/test-streams/speech_zh.mp4 \
  -c:v copy \
  -c:a aac -b:a 128k \
  -f flv "rtmp://localhost:1935/live/test-stream/in"
```

### Verify Stream Is Publishing

```bash
curl -s http://localhost:9997/v3/paths/list | jq '.items[] | {name, ready, tracks}'
```

Expected output:
```json
{
  "name": "live/test-stream/in",
  "ready": true,
  "tracks": ["H264", "MPEG-4 Audio"]
}
```

---

## Step 3: Wait for Processing

The pipeline processes in 30-second segments with keyframe alignment:

| Event | Time After Start |
|-------|------------------|
| Stream ingested | Immediate |
| First segment ready | ~30-35 seconds |
| Output stream available | ~35-40 seconds |

### Monitor Segment Processing

```bash
# Watch for segment emissions
docker logs -f media-service 2>&1 | grep -E "(Video segment|Keyframe|Muxed)"
```

Expected log output:
```
Keyframe received at pts=30.00s, emitting segment (waited 0.00s for keyframe)
Video segment emitted: batch=0, duration=30.00s, buffers=63255, size=11891940...
Muxed segment: 11890081 bytes (pts=0.00s)
```

### Check Output Stream Availability

```bash
# Wait ~40 seconds then check
curl -s http://localhost:9997/v3/paths/list | jq '.items[] | select(.name | contains("out"))'
```

Expected:
```json
{
  "name": "live/test-stream/out",
  "ready": true,
  "tracks": ["H264", "MPEG-4 Audio"]
}
```

---

## Step 4: Play Output Stream

### Option A: RTMP (recommended)

```bash
# Basic playback
ffplay rtmp://localhost:1935/live/test-stream/out

# Verbose mode (shows decoder messages)
ffplay -v verbose rtmp://localhost:1935/live/test-stream/out
```

### Option B: RTSP

```bash
ffplay rtsp://localhost:8554/live/test-stream/out
```

### Option C: Use make target

```bash
make dev-play      # Play output stream
make dev-play-in   # Play input stream (for comparison)
```

### What to Look For

**Good output** (no errors):
```
Input #0, flv, from 'rtmp://localhost:1935/live/test-stream/out':
  Stream #0:0: Video: h264 (High), yuv420p, 1280x720, 30 fps
  Stream #0:1: Audio: aac (LC), 44100 Hz, stereo
```

**Bad output** (P-frame errors - indicates keyframe alignment issue):
```
[h264 @ 0x...] concealing 720 DC, 720 AC, 720 MV errors in P frame
[h264 @ 0x...] Reinit context to 1280x720, pix_fmt: yuv420p
```

---

## Step 5: Check Logs for Errors

```bash
# View all service logs
make dev-logs

# Filter for errors only
docker logs media-service 2>&1 | grep -iE "(error|exception|fail)" | head -20

# Check STS processing
docker logs media-service 2>&1 | grep -E "(Fragment|fragment)" | tail -10
```

### Expected Fragment Processing (Echo STS)

```
Fragment sent: id=xxx, batch=0, audio_size=431272
Fragment processed: id=xxx, status=success, processing_time=50ms
```

---

## Step 6: Stop Everything

```bash
# Stop the ffmpeg push (Ctrl+C in that terminal, or:)
pkill -f "ffmpeg.*test-stream"

# Stop all services
make dev-down
```

---

## Troubleshooting

### Issue: No Video Detected (Only Audio Pad)

**Symptom**: Logs show only `Pad added: audio, media type: audio/mpeg`

**Cause**: Using `-c:v libx264` instead of `-c:v copy`

**Fix**: Always use `-c:v copy` when pushing streams:
```bash
ffmpeg -re -stream_loop -1 -i input.mp4 -c:v copy -c:a aac -f flv rtmp://...
```

### Issue: Output Stream Not Available

**Symptom**: `/out` path not showing in MediaMTX

**Possible causes**:
1. Not enough time elapsed (wait 40+ seconds)
2. STS service not healthy
3. Pipeline error

**Debug**:
```bash
# Check service health
curl -s http://localhost:3000/health

# Check for pipeline errors
docker logs media-service 2>&1 | grep -i error
```

### Issue: P-Frame Decode Errors in Player

**Symptom**: `concealing DC, AC, MV errors in P frame`

**Cause**: Segments not starting on keyframe boundaries

**Fix**: This is fixed in the current codebase with keyframe-aligned emission. If still occurring, check:
```bash
docker logs media-service 2>&1 | grep "Keyframe received"
```
Should show segments emitting on keyframe boundaries.

### Issue: Video Stutter/Freeze at 30s Boundaries

**Symptom**: Video freezes every ~30 seconds

**Cause**: Timestamp discontinuities or missing keyframes

**Debug**:
```bash
# Check muxing timestamps
docker logs media-service 2>&1 | grep "Muxed segment"
```

---

## Service Endpoints Reference

| Service | Endpoint | Purpose |
|---------|----------|---------|
| MediaMTX RTMP | `rtmp://localhost:1935` | Stream ingest/output |
| MediaMTX RTSP | `rtsp://localhost:8554` | Stream playback |
| MediaMTX API | `http://localhost:9997/v3/paths/list` | Stream status |
| media-service | `http://localhost:8080/health` | Health check |
| echo-sts | `http://localhost:3000/health` | Health check |

---

## Make Targets Reference

| Command | Description |
|---------|-------------|
| `make dev-up-echo` | Start services with Echo STS |
| `make dev-up-light` | Start services with ElevenLabs STS |
| `make dev-down` | Stop all services |
| `make dev-push` | Push test stream (loops forever) |
| `make dev-play` | Play output stream |
| `make dev-play-in` | Play input stream |
| `make dev-logs` | View service logs |
| `make dev-ps` | List running containers |

---

## Full Test Script

Copy and run this complete test script:

```bash
#!/bin/bash
set -e

echo "=== 1. Stopping existing services ==="
make dev-down 2>/dev/null || true
pkill -f "ffmpeg.*test-stream" 2>/dev/null || true

echo ""
echo "=== 2. Starting services (echo mode) ==="
make dev-up-echo

echo ""
echo "=== 3. Waiting for services to be healthy ==="
sleep 10
curl -sf http://localhost:8080/health >/dev/null && echo "media-service: OK"
curl -sf http://localhost:3000/health >/dev/null && echo "echo-sts: OK"

echo ""
echo "=== 4. Pushing test stream ==="
ffmpeg -re -stream_loop -1 \
  -i tests/fixtures/test-streams/speech_zh.mp4 \
  -c:v copy -c:a aac -b:a 128k \
  -f flv "rtmp://localhost:1935/live/test-stream/in" \
  > /tmp/ffmpeg-test.log 2>&1 &
FFMPEG_PID=$!
echo "FFmpeg PID: $FFMPEG_PID"

echo ""
echo "=== 5. Waiting for first segment (~35s) ==="
sleep 35

echo ""
echo "=== 6. Checking output stream ==="
OUTPUT=$(curl -s http://localhost:9997/v3/paths/list | grep -c "test-stream/out" || echo "0")
if [ "$OUTPUT" -gt "0" ]; then
    echo "Output stream is READY"
    echo ""
    echo "=== 7. Checking for errors ==="
    ERRORS=$(docker logs media-service 2>&1 | grep -iE "(error|exception)" | grep -v "No errors" | head -5)
    if [ -z "$ERRORS" ]; then
        echo "No errors found"
    else
        echo "Errors found:"
        echo "$ERRORS"
    fi
    echo ""
    echo "=== SUCCESS ==="
    echo "Play the output with: ffplay rtmp://localhost:1935/live/test-stream/out"
else
    echo "Output stream NOT READY"
    echo "Check logs: docker logs media-service"
fi

echo ""
echo "Press Enter to stop test, or Ctrl+C to keep running..."
read
kill $FFMPEG_PID 2>/dev/null || true
make dev-down
```

---

## Triggers

| Trigger | Action |
|---------|--------|
| `/local-media-test` | Show this guide |
| `local-media-test` | Show this guide |

---

*Local Media Service Testing - Manual testing guide for media-service + echo-sts*
