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
  brew install ffmpeg gstreamer gst-plugins-good gst-plugins-bad gst-plugins-ugly

  # Ubuntu/Debian
  apt-get install ffmpeg gstreamer1.0-tools gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav
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

---

## Publishing Test Streams

### Using FFmpeg (Recommended)

#### Basic Test Stream

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

#### Using the Test Script

For convenience, use the provided FFmpeg test script:

```bash
# Default test stream (infinite duration)
./tests/fixtures/test-streams/ffmpeg-publish.sh

# Custom stream ID and 30-second duration
./tests/fixtures/test-streams/ffmpeg-publish.sh my-stream 30

# Publish to remote MediaMTX
./tests/fixtures/test-streams/ffmpeg-publish.sh my-stream 60 mediamtx.example.com 1935
```

#### FFmpeg Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `-re` | Read input at native frame rate | Required |
| `-f lavfi` | Use libavfilter virtual input | Required |
| `testsrc=size=WxH:rate=FPS` | Video pattern generator | 1280x720@30 |
| `sine=frequency=HZ` | Audio sine wave | 1000Hz |
| `-c:v libx264` | H.264 video codec | Required |
| `-preset veryfast` | Encoding speed/quality trade-off | veryfast |
| `-tune zerolatency` | Low latency mode | Recommended |
| `-c:a aac` | AAC audio codec | Required |
| `-f flv` | FLV container for RTMP | Required |
| `-t SECONDS` | Limit duration | Infinite |

#### Advanced FFmpeg Examples

```bash
# Higher quality (1080p, higher bitrate)
ffmpeg -re \
  -f lavfi -i "testsrc=size=1920x1080:rate=30" \
  -f lavfi -i "sine=frequency=1000:sample_rate=48000" \
  -c:v libx264 -preset medium -tune zerolatency -b:v 5000k \
  -c:a aac -b:a 192k \
  -f flv rtmp://localhost:1935/live/hq-stream/in

# With query parameters (for metadata)
ffmpeg -re \
  -f lavfi -i "testsrc=size=1280x720:rate=30" \
  -f lavfi -i "sine=frequency=1000:sample_rate=48000" \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -c:a aac \
  -f flv "rtmp://localhost:1935/live/test-stream/in?lang=es&quality=high"

# Publish existing file
ffmpeg -re -stream_loop -1 \
  -i tests/fixtures/test-streams/big-buck-bunny.mp4 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -c:a aac \
  -f flv rtmp://localhost:1935/live/video-file/in
```

---

### Using GStreamer (Alternative)

#### Basic GStreamer Pipeline

```bash
gst-launch-1.0 -e \
  videotestsrc pattern=smpte ! \
  "video/x-raw,width=1280,height=720,framerate=30/1" ! \
  x264enc tune=zerolatency bitrate=2000 speed-preset=veryfast ! \
  h264parse ! \
  flvmux name=mux streamable=true ! \
  rtmpsink location="rtmp://localhost:1935/live/test-stream/in live=1" \
  \
  audiotestsrc wave=sine freq=1000 ! \
  "audio/x-raw,rate=48000,channels=2" ! \
  voaacenc bitrate=128000 ! \
  aacparse ! \
  mux.
```

#### Using the Test Script

```bash
# Default test stream
./tests/fixtures/test-streams/gstreamer-publish.sh

# Custom stream ID
./tests/fixtures/test-streams/gstreamer-publish.sh my-stream

# Publish to remote MediaMTX
./tests/fixtures/test-streams/gstreamer-publish.sh my-stream mediamtx.example.com 1935
```

#### GStreamer Video Patterns

| Pattern | Description |
|---------|-------------|
| `smpte` | SMPTE color bars (default) |
| `ball` | Moving ball animation |
| `snow` | Random noise (snow) |
| `black` | Solid black |
| `white` | Solid white |
| `red` | Solid red |
| `green` | Solid green |
| `blue` | Solid blue |
| `checkers-1` | Checkerboard pattern |
| `circular` | Circular pattern |

---

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

---

## Reading and Playing Streams
## Observability and Monitoring

### Control API

MediaMTX exposes a Control API on port 9997 for querying stream status.

**Quick query using Makefile:**
```bash
make api-status
```

**Manual query:**
```bash
curl -u admin:admin http://localhost:9997/v3/paths/list | python3 -m json.tool
```

**Authentication:** Default credentials are `admin:admin` (configured in `mediamtx.yml`)

**Available endpoints:**
- `/v3/paths/list` - List all active stream paths
- `/v3/paths/get/{path}` - Get details for specific path
- `/v3/rtmpconns/list` - List active RTMP connections
- `/v3/rtspsessions/list` - List active RTSP sessions

**Response time:** < 100ms (per SC-006)

### Prometheus Metrics

MediaMTX exposes Prometheus-format metrics on port 9998 for monitoring system health.

**Quick query using Makefile:**
```bash
make metrics
```

**Manual query:**
```bash
# All metrics
curl -u admin:admin http://localhost:9998/metrics

# Path-specific metrics
curl -u admin:admin "http://localhost:9998/metrics?type=paths&path=live/test-stream/in"
```

**Key metrics to monitor:**
- `bytes_received` - Data flowing into MediaMTX
- `bytes_sent` - Data flowing out of MediaMTX
- `readers` - Number of active stream readers
- Path state (ready/not-ready)

**Response time:** < 100ms (per SC-007)

### Log Correlation Fields

All hook events and stream operations include correlation fields for debugging:

**In media-service logs:**
```json
{
  "timestamp": "2025-12-27T10:30:45.123Z",
  "level": "INFO",
  "message": "Received hook event",
  "path": "live/test-stream/in",
  "streamId": "test-stream",
  "sourceType": "rtmp",
  "sourceId": "uuid-1234-5678",
  "query": "lang=es",
  "correlation_id": "req-9876-5432"
}
```

**Key correlation fields:**
- `path` - Full MediaMTX path (e.g., `live/test-stream/in`)
- `streamId` - Extracted from path (e.g., `test-stream`)
- `sourceType` - Origin protocol (`rtmp`, `rtsp`, `webrtc`)
- `sourceId` - Unique connection identifier from MediaMTX
- `query` - URL query parameters (e.g., `lang=es`)
- `correlation_id` - Request tracking ID

**Using correlation fields for debugging:**

```bash
# Find all logs for a specific stream
make logs | grep "streamId=test-stream"

# Trace a specific connection
make logs | grep "sourceId=uuid-1234-5678"

# Filter by event type
make logs | grep "hook event: ready"
```

### Playback Server

MediaMTX exposes a playback server on port 9996 for future recording retrieval.

**Note:** Recording is disabled in v0 (`record: no` in config), but the playback server is available for future use.

## Reading Streams

### Using FFplay (Simple Playback)

Read the stream via RTSP:

```bash
# Basic playback
ffplay rtsp://localhost:8554/live/test-stream/in

# With TCP transport (recommended for containers)
ffplay -rtsp_transport tcp rtsp://localhost:8554/live/test-stream/in

# With low latency flags
ffplay -fflags nobuffer -flags low_delay \
  -rtsp_transport tcp \
  rtsp://localhost:8554/live/test-stream/in
```

### Using FFmpeg (Re-stream/Record)

#### Bypass Pattern (RTSP to RTMP)

Re-publish stream from `/in` to `/out` path:

```bash
ffmpeg -re \
  -rtsp_transport tcp \
  -i rtsp://localhost:8554/live/test-stream/in \
  -c copy \
  -f flv rtmp://localhost:1935/live/test-stream/out
```

**Note:** Use `-rtsp_transport tcp` to avoid UDP packet loss in containerized environments.

#### Record to File

```bash
# Record 30 seconds to MP4
ffmpeg \
  -rtsp_transport tcp \
  -i rtsp://localhost:8554/live/test-stream/in \
  -c copy \
  -t 30 \
  output.mp4
```

### Using GStreamer (Advanced Playback)

#### GStreamer Playback

```bash
gst-launch-1.0 \
  rtspsrc location="rtsp://localhost:8554/live/test-stream/in" protocols=tcp latency=0 ! \
  rtph264depay ! avdec_h264 ! videoconvert ! autovideosink \
  rtspsrc location="rtsp://localhost:8554/live/test-stream/in" protocols=tcp latency=0 ! \
  rtpmp4gdepay ! avdec_aac ! audioconvert ! autoaudiosink
```

#### GStreamer Bypass (RTSP to RTMP)

Use the provided bypass script:

```bash
# Bypass from /in to /out
./tests/fixtures/test-streams/gstreamer-bypass.sh test-stream

# Bypass for Docker container
./tests/fixtures/test-streams/gstreamer-bypass.sh test-stream mediamtx
```

---

## Codec Configuration

### Required Codec Configuration

MediaMTX and downstream workers expect specific codec configurations for compatibility:

| Component | Video Codec | Audio Codec | Container |
|-----------|-------------|-------------|-----------|
| RTMP Ingest | H.264 (AVC) | AAC | FLV |
| RTSP Output | H.264 (AVC) | AAC | RTP |
| Worker Input | H.264 (AVC) | AAC | - |
| Worker Output | H.264 (AVC) | AAC | FLV |

### H.264 Video Settings

```bash
# FFmpeg
-c:v libx264 -preset veryfast -tune zerolatency -profile:v baseline

# GStreamer
x264enc tune=zerolatency speed-preset=veryfast
```

**Recommended settings:**
- Profile: `baseline` (widest compatibility) or `main`
- Preset: `veryfast` or `ultrafast` for low latency
- Tune: `zerolatency` to minimize encoding delay
- Bitrate: 2000-5000 kbps for 720p, 5000-10000 kbps for 1080p

### AAC Audio Settings

```bash
# FFmpeg
-c:a aac -ar 48000 -b:a 128k

# GStreamer
voaacenc bitrate=128000
```

**Recommended settings:**
- Sample rate: 48000 Hz
- Channels: 2 (stereo)
- Bitrate: 128 kbps (speech) or 192 kbps (music)

### Unsupported Codecs

The following codecs are **not recommended** for this pipeline:
- **Video:** VP8, VP9, AV1, HEVC (H.265) - not natively supported by RTMP
- **Audio:** Opus, Vorbis, MP3 - limited RTMP support

---

## Debugging

### Check Active Streams

Use the Makefile target for quick access:

```bash
make api-status
```

Or query the MediaMTX Control API directly:

```bash
curl -u admin:admin http://localhost:9997/v3/paths/list | jq
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

Use the Makefile target:

```bash
make metrics
```

Or query Prometheus metrics directly:

```bash
curl http://localhost:9998/metrics | grep mediamtx
```

**Look for:**
- `mediamtx_paths_total` - Total number of paths
- `mediamtx_paths_ready` - Ready paths count
- `mediamtx_bytes_received_total` - Data flowing into MediaMTX
- `mediamtx_bytes_sent_total` - Data flowing out of MediaMTX

### Probe Stream Information

Use ffprobe to inspect stream details:

```bash
ffprobe -rtsp_transport tcp rtsp://localhost:8554/live/test-stream/in

# Detailed output
ffprobe -v quiet -print_format json -show_streams \
  -rtsp_transport tcp rtsp://localhost:8554/live/test-stream/in | jq
```

---

## Troubleshooting

**Tip:** See the "Observability and Monitoring" section above for complete details on all available endpoints and correlation fields.

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
docker exec mediamtx curl http://media-service:8080/health

# Check hook endpoint
docker exec mediamtx curl -X POST -H "Content-Type: application/json" \
  -d '{"path":"test","sourceType":"rtmp","sourceId":"1"}' \
  http://media-service:8080/v1/mediamtx/events/ready
```

#### 3. Codec Issues

**Error:** Stream doesn't play or shows errors

**Checklist:**
- Use H.264 + AAC (other codecs may not work)
- Check FFmpeg encoding settings match test commands
- Verify stream with `ffprobe`:

```bash
ffprobe -rtsp_transport tcp rtsp://localhost:8554/live/test-stream/in
```

**Common codec errors:**
- "Unknown codec" - Publishing with unsupported codec
- "No audio" - Missing audio track or wrong audio codec
- "Green/corrupted video" - Codec mismatch or encoding error

#### 4. RTSP Connection Fails

**Error:** `Connection refused` or `Connection timed out`

**Checklist:**
1. Verify MediaMTX is running: `make ps`
2. Check RTSP port: `nc -zv localhost 8554`
3. Verify stream exists: `curl http://localhost:9997/v3/paths/list`
4. Try TCP transport: `-rtsp_transport tcp`

#### 5. High Latency

**Error:** Stream delay >2 seconds

**Solutions:**
1. Use RTSP over TCP: `-rtsp_transport tcp`
2. Enable zero-latency tuning in encoders: `-tune zerolatency`
3. Reduce buffer sizes in playback: `-fflags nobuffer`
4. Check container resource limits: `docker stats`

#### 6. UDP Packet Loss

**Error:** Video artifacts, stuttering, or freezing

**Solutions:**
1. **Force TCP transport:**
   ```bash
   # FFmpeg
   ffmpeg -rtsp_transport tcp -i rtsp://...

   # GStreamer
   rtspsrc protocols=tcp location=...
   ```

2. **Increase buffer sizes:**
   ```bash
   ffplay -rtsp_transport tcp -buffer_size 1024000 rtsp://...
   ```

#### 7. MediaMTX Not Accepting Streams

**Checklist:**
1. Check MediaMTX is running: `make ps`
2. Check RTMP port: `nc -zv localhost 1935`
3. Review MediaMTX configuration: `deploy/mediamtx/mediamtx.yml`
4. Check MediaMTX logs for errors: `make logs | grep mediamtx`

#### 8. Worker Not Triggered

**Error:** Stream publishes but no worker starts

**Checklist:**
1. Verify hook events in media-service logs
2. Check worker implementation (future feature)
3. Verify path naming follows convention: `live/<streamId>/in`

---

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

### Query Control API
```bash
# List all paths
curl -u admin:admin http://localhost:9997/v3/paths/list | jq

# List RTMP connections
curl -u admin:admin http://localhost:9997/v3/rtmpconns/list | jq
```

### Run Tests
```bash
# All tests
make test

# Integration tests only
pytest tests/integration/ -v

# With coverage
pytest --cov=apps/media-service --cov-report=term-missing
```

---

## Port Reference

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| 1935 | MediaMTX | RTMP | Stream publishing |
| 8554 | MediaMTX | RTSP | Stream reading |
| 8080 | media-service | HTTP | Hook receiver API |
| 9997 | MediaMTX | HTTP | Control API |
| 9998 | MediaMTX | HTTP | Prometheus metrics |
| 9996 | MediaMTX | HTTP | Playback server |

---

## Next Steps

Once you have the local environment running:

1. **Implement stream workers** - See specs/003-gstreamer-stream-worker.md
2. **Add worker orchestration logic** - Respond to hook events and start workers
3. **Test concurrent streams** - Publish 5 streams simultaneously
4. **Review observability** - Set up metrics dashboards

---

## Reference

- **Architecture Spec**: specs/002-mediamtx.md
- **Feature Spec**: specs/001-mediamtx-integration/spec.md
- **Implementation Plan**: specs/001-mediamtx-integration/plan.md
- **Tasks**: specs/001-mediamtx-integration/tasks.md
- **Test Scripts**: tests/fixtures/test-streams/
