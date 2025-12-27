# Quick Start Guide: MediaMTX Integration

**Feature**: 001-mediamtx-integration
**Created**: 2025-12-27
**Audience**: Developers setting up local development environment

## Prerequisites

Before you begin, ensure you have:

- **Docker** and **Docker Compose** installed
  - Docker Desktop (macOS/Windows) or Docker Engine (Linux)
  - Docker Compose v2.0+ (included in Docker Desktop)
- **FFmpeg** or **GStreamer** for testing streams (optional but recommended)
  ```bash
  # macOS
  brew install ffmpeg gstreamer

  # Ubuntu/Debian
  apt-get install ffmpeg gstreamer1.0-tools gstreamer1.0-plugins-good
  ```
- **Basic familiarity** with RTMP/RTSP protocols and streaming concepts

## Initial Setup

### 1. Clone and Navigate

```bash
cd /path/to/live-broadcast-dubbing-cloud
```

### 2. Start Services

Run the entire MediaMTX-based streaming pipeline:

```bash
make dev
```

**Expected output:**
- All services start within 30 seconds
- MediaMTX accepts RTMP connections on port 1935
- Stream-orchestration service listens on port 8080
- Control API available at http://localhost:9997
- Metrics available at http://localhost:9998

### 3. Verify Services

Check that all services are running:

```bash
make ps
```

Expected services:
- `mediamtx` - Media router
- `media-service` - Hook receiver and worker manager

## Publishing Test Streams

### Using FFmpeg (Recommended)

Publish a test stream with video and audio:

```bash
# Generate test pattern: color bars + 1kHz tone
ffmpeg -re \
  -f lavfi -i "testsrc=size=1280x720:rate=30" \
  -f lavfi -i "sine=frequency=1000:sample_rate=48000" \
  -c:v libx264 -preset veryfast -tune zerolatency -b:v 2000k \
  -c:a aac -b:a 128k \
  -f flv rtmp://localhost:1935/live/test-stream/in
```

**What this does:**
- Generates 1280x720 color bars at 30fps
- Adds 1kHz sine wave audio
- Encodes as H.264 + AAC
- Publishes to `live/test-stream/in`

### Using GStreamer (Alternative)

```bash
gst-launch-1.0 \
  videotestsrc pattern=smpte ! \
  "video/x-raw,width=1280,height=720,framerate=30/1" ! \
  x264enc tune=zerolatency bitrate=2000 ! h264parse ! \
  audiotestsrc wave=sine freq=1000 ! \
  "audio/x-raw,rate=48000,channels=2" ! \
  voaacenc bitrate=128000 ! aacparse ! \
  flvmux name=mux ! \
  rtmpsink location="rtmp://localhost:1935/live/test-stream/in"
```

## Verifying Hook Delivery

After publishing a stream, verify that MediaMTX triggered hook events:

```bash
make logs
```

**Look for these log entries:**

In **media-service** logs:
```
INFO: Received hook event: ready for path=live/test-stream/in
INFO: sourceType=rtmp, sourceId=<connection-id>
```

In **mediamtx** logs:
```
INFO: Hook executed successfully: runOnReady for live/test-stream/in
```

**Timeline:**
- Hook events should appear within **1 second** of stream becoming ready

## Reading Streams

### Using FFplay (Playback)

Read the stream via RTSP:

```bash
ffplay rtsp://localhost:8554/live/test-stream/in
```

### Using FFmpeg (Re-stream)

Bypass pattern (RTSP → RTMP):

```bash
ffmpeg -re \
  -rtsp_transport tcp \
  -i rtsp://localhost:8554/live/test-stream/in \
  -c copy \
  -f flv rtmp://localhost:1935/live/test-stream/out
```

**Note:** Use `-rtsp_transport tcp` to avoid UDP packet loss

## Debugging

### Check Active Streams

Query the MediaMTX Control API:

```bash
curl http://localhost:9997/v3/paths/list | jq
```

**Example response:**
```json
{
  "items": [
    {
      "name": "live/test-stream/in",
      "ready": true,
      "tracks": ["H264", "AAC"]
    }
  ]
}
```

### Check Metrics

Query Prometheus metrics:

```bash
curl http://localhost:9998/metrics?type=paths&path=live/test-stream/in
```

**Look for:**
- `bytes_received` - Data flowing into MediaMTX
- `readers` - Number of active readers
- Stream state (ready/not-ready)

### Common Errors

#### 1. Port Conflicts

**Error:** `bind: address already in use`

**Solution:**
```bash
# Check what's using the port
lsof -i :1935  # RTMP
lsof -i :8554  # RTSP
lsof -i :8080  # Stream-orchestration

# Stop conflicting services or change ports in docker-compose.yml
```

#### 2. Hook Delivery Failures

**Error:** Stream publishes but no hook events in logs

**Checklist:**
- Is media-service service running? (`make ps`)
- Is ORCHESTRATOR_URL set correctly in MediaMTX environment?
- Check MediaMTX logs for hook execution errors

**Debug:**
```bash
# Check MediaMTX can reach media-service
docker exec mediamtx curl http://media-service:8080/v1/mediamtx/events/ready

# Expected: Method not allowed (POST required)
```

#### 3. Codec Issues

**Error:** Stream doesn't play or shows errors

**Checklist:**
- Use H.264 + AAC (other codecs may not work)
- Check FFmpeg encoding settings match test commands
- Verify stream with `ffprobe`:

```bash
ffprobe rtsp://localhost:8554/live/test-stream/in
```

## Common Tasks

### Start Services
```bash
make dev
```

### View Logs
```bash
make logs

# Follow specific service
make logs | grep media-service
```

### Stop Services
```bash
make down
```

### List Running Services
```bash
make ps
```

### Restart After Changes
```bash
make down && make dev
```

## Troubleshooting

### MediaMTX Not Accepting Streams

1. Check MediaMTX is running: `make ps`
2. Check RTMP port: `nc -zv localhost 1935`
3. Review MediaMTX configuration: `deploy/mediamtx/mediamtx.yml`

### Hook Events Not Firing

1. Verify media-service is reachable from MediaMTX container
2. Check ORCHESTRATOR_URL environment variable in `deploy/docker-compose.yml`
3. Review hook wrapper script: `deploy/mediamtx/hooks/mtx-hook`

### High Latency

1. Use RTSP over TCP: `-rtsp_transport tcp`
2. Enable zero-latency tuning in encoders: `-tune zerolatency`
3. Check container resource limits: `docker stats`

## Next Steps

Once you have the local environment running:

1. **Implement stream workers** - See specs/003-gstreamer-stream-worker.md
2. **Add worker orchestration logic** - Respond to hook events and start workers
3. **Test concurrent streams** - Publish 5 streams simultaneously
4. **Review observability** - Set up metrics dashboards

## Reference

- **Architecture Spec**: specs/002-mediamtx.md
- **Feature Spec**: specs/001-mediamtx-integration/spec.md
- **Implementation Plan**: specs/001-mediamtx-integration/plan.md
- **Tasks**: specs/001-mediamtx-integration/tasks.md
