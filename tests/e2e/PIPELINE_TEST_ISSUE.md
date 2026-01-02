# Full Pipeline E2E Test - Issue Summary

**Status:** ❌ FAILING at Step 1
**Test:** `test_dual_compose_full_pipeline.py::test_full_pipeline_media_to_sts_to_output`
**Branch:** `019-dual-docker-e2e-infrastructure`
**Date:** 2026-01-01

---

## Test Overview

The full pipeline test validates the complete end-to-end dubbing pipeline from video ingestion to dubbed output.

**Expected Flow:**
```
Test Fixture (30s video)
    │
    ├──> ffmpeg publishes to RTSP
    │
    ▼
MediaMTX (RTSP Server)
    │
    ▼
WorkerRunner (media-service)
    │
    ├──> Segments audio (6s chunks)
    │
    ▼
STS Service (Socket.IO)
    │
    ├──> ASR → Translation → TTS
    │
    ▼
WorkerRunner receives dubbed audio
    │
    ├──> Remuxes with original video
    │
    ▼
MediaMTX publishes RTMP output
    │
    ▼
Dubbed Stream Available
```

---

## Test Steps (7 Total)

### ✅ Step 0: Environment Setup
- Start dual docker-compose (media + STS services)
- Initialize stream publisher with 30s test fixture
- Connect Socket.IO monitor to STS service

**Status:** PASSING

### ❌ Step 1: Verify MediaMTX Received Stream
**Location:** `test_dual_compose_full_pipeline.py:71-95`

**What it does:**
1. Use `StreamPublisher` (ffmpeg wrapper) to publish test fixture
2. Target: `rtsp://localhost:8554/live/test_XXX/in`
3. Query MediaMTX API: `GET http://localhost:8889/v3/paths/list`
4. Parse response to find active stream
5. Check if stream name appears in path list

**Expected Result:**
- Stream appears in MediaMTX path list within 10 seconds

**Actual Result:**
```
AssertionError: Stream should be active in MediaMTX within 10 seconds
assert False
```

**Failure Details:**
- ffmpeg process starts successfully (initial poll passes)
- MediaMTX API responds with 200 OK (after redirect)
- But stream **never appears** in the paths list
- Test retries 10 times (1 second intervals) - all fail

**Status:** ❌ FAILING HERE - Blocks all subsequent steps

---

### ⏸️ Step 2: Verify WorkerRunner Connects
**Location:** `test_dual_compose_full_pipeline.py:97-118`

**What it should do:**
- Query `http://localhost:8080/metrics`
- Look for `worker_audio_fragments_total` metric
- Verify WorkerRunner detected stream and started processing

**Status:** Not reached (blocked by Step 1)

---

### ⏸️ Step 3: Monitor Socket.IO Events
**Location:** `test_dual_compose_full_pipeline.py:120-168`

**What it should do:**
- Listen for `fragment:processed` events from STS service
- Expect 5 events (30s video ÷ 6s segments = 5)
- Timeout: 180 seconds

**Status:** Not reached (blocked by Step 1)

---

### ⏸️ Step 4: Verify Event Data
**Location:** `test_dual_compose_full_pipeline.py:139-162`

**What it should do:**
- Validate each `fragment:processed` event contains:
  - `dubbed_audio` (base64 encoded audio)
  - `transcript` (original speech text)
  - `translated_text` (translated speech)

**Status:** Not reached (blocked by Step 1)

---

### ⏸️ Step 5: Verify Output RTMP Stream
**Location:** `test_dual_compose_full_pipeline.py:170-210`

**What it should do:**
- Use ffprobe to inspect `rtmp://localhost:1935/live/test_XXX/out`
- Verify stream has:
  - Video: H.264 codec
  - Audio: AAC codec
  - Duration: ~30s (±500ms tolerance)

**Status:** Not reached (blocked by Step 1)

---

### ⏸️ Step 6: Verify Metrics
**Location:** `test_dual_compose_full_pipeline.py:212-230`

**What it should do:**
- Check `worker_audio_fragments_total{status="processed"}` = 5
- Verify A/V sync delta < 120ms
- Confirm pipeline completed successfully

**Status:** Not reached (blocked by Step 1)

---

## Root Cause Analysis

### Primary Issue: Stream Not Appearing in MediaMTX

The test uses ffmpeg to publish an RTSP stream, but MediaMTX never registers it as active.

### Possible Causes

#### 1. **ffmpeg Process Dies Silently**
- Initial poll (after 1 second) shows process is alive
- But process might fail to maintain RTSP connection
- No stderr logging captured in current implementation

**Evidence:**
```python
# stream_publisher.py:107
if self._process.poll() is not None:
    _, stderr = self._process.communicate()
    raise RuntimeError(f"ffmpeg failed to start: {stderr.decode()}")
```
- Only checks if process died immediately
- Doesn't monitor ongoing connection health

#### 2. **MediaMTX Configuration - RTSP Publish Not Enabled**
- MediaMTX might be configured for RTSP **read** only
- Publishing might require explicit permission in config

**Need to check:** `apps/media-service/deploy/mediamtx/mediamtx.yml`
- Look for `publish: yes` or similar setting
- Check path permissions/patterns

#### 3. **Stream Path Format Mismatch**
- Test uses: `live/test_test_full_pipeline_media_to_sts_to_output_1767313771/in`
- MediaMTX might expect different format
- Or paths might need pre-configuration

**Current parsing logic:**
```python
stream_name = stream_path.split("/")[1]  # Extract middle segment
# "live/test_XXX/in" → expects to find "test_XXX" in response
```

#### 4. **MediaMTX API Response Format Issue**
- Test assumes stream name appears in `paths["items"][*]["name"]`
- MediaMTX might return full paths, partial paths, or different structure
- Need to log actual response to verify

#### 5. **Network/Timing Issue**
- ffmpeg might take >1 second to fully establish RTSP connection
- MediaMTX might not immediately register newly connected streams
- Current retry logic: 10 attempts × 1 second = 10 seconds total

#### 6. **Port/Network Configuration**
- Container networking might prevent `localhost:8554` access from host
- Docker bridge network vs host network mode
- Need to verify MediaMTX is actually listening on 0.0.0.0:8554

---

## MediaMTX Port Architecture

### Why Two Different Ports?

The test uses two ports for different purposes:

| Port | Protocol | Purpose | Usage in Test |
|------|----------|---------|---------------|
| **8554** | RTSP | Stream ingestion/playback | `ffmpeg → rtsp://localhost:8554/live/test/in` |
| **8889** | HTTP API | Control/monitoring | `curl http://localhost:8889/v3/paths/list` |

### Port Separation Explained

```
┌─────────────────────────────────────────────────────────┐
│                    MediaMTX Server                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Port 8554 (RTSP)  ──> DATA PLANE                      │
│    • Publish streams (ffmpeg → MediaMTX)               │
│    • Subscribe to streams (MediaMTX → clients)         │
│    • Protocol: RTSP/RTP                                │
│    • Bandwidth: HIGH (MB/s)                            │
│                                                         │
│  Port 8889 (HTTP)  ──> CONTROL PLANE                   │
│    • Query active streams                              │
│    • Get stream statistics                             │
│    • Kick connections                                  │
│    • Protocol: HTTP/JSON                               │
│    • Bandwidth: LOW (KB/s)                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**This is correct by design** - it's separation of concerns (like Kubernetes has API server on 6443 and kubelet on 10250).

---

## Debug Steps

### 1. Verify ffmpeg Connection

**Check ffmpeg logs:**
```python
# Modify stream_publisher.py to log stderr continuously
self._process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Add monitoring
import threading
def log_stderr():
    for line in iter(self._process.stderr.readline, b''):
        logger.error(f"ffmpeg: {line.decode()}")

thread = threading.Thread(target=log_stderr, daemon=True)
thread.start()
```

### 2. Test Manual Stream Publish

```bash
# Start docker-compose
cd apps/media-service
docker-compose -f docker-compose.e2e.yml up -d

# Wait for services to be healthy
docker-compose -f docker-compose.e2e.yml ps

# Publish stream manually
ffmpeg -re -i ../../tests/e2e/fixtures/test_streams/30s-counting-english.mp4 \
  -c:v copy -c:a copy \
  -f rtsp -rtsp_transport tcp \
  rtsp://localhost:8554/live/test/in

# In another terminal, check MediaMTX API
curl -s http://localhost:8889/v3/paths/list/ | jq .

# Check MediaMTX logs
docker logs e2e-media-mediamtx
```

### 3. Check MediaMTX Configuration

```bash
# Read MediaMTX config
cat apps/media-service/deploy/mediamtx/mediamtx.yml

# Look for:
# - publish permissions
# - path patterns
# - RTSP server settings
```

### 4. Add Debug Logging to Test

```python
# In test_dual_compose_full_pipeline.py, after line 82
logger.info(f"MediaMTX API response: {paths}")
logger.info(f"Looking for stream: {stream_name}")
logger.info(f"Available paths: {[p.get('name') for p in paths.get('items', [])]}")
```

### 5. Verify Network Connectivity

```bash
# Check if MediaMTX is actually listening on 8554
docker exec e2e-media-mediamtx netstat -tlnp | grep 8554

# Check if port is accessible from host
telnet localhost 8554

# Try RTSP OPTIONS request
ffmpeg -v debug -rtsp_transport tcp -i rtsp://localhost:8554/live/test/in -t 1 -f null -
```

### 6. Check Docker Network Configuration

```yaml
# In docker-compose.e2e.yml, verify network mode
services:
  mediamtx:
    ports:
      - "8554:8554"  # Should be host:container
    networks:
      - e2e-media-network
```

---

## Workarounds to Try

### Option 1: Use host network mode
```yaml
# docker-compose.e2e.yml
services:
  mediamtx:
    network_mode: "host"
    # Remove ports section - not needed with host mode
```

### Option 2: Pre-configure MediaMTX paths
```yaml
# mediamtx.yml
paths:
  live/~path~/in:
    source: publisher
    runOnReady: echo "Stream started"
    runOnNotReady: echo "Stream stopped"
```

### Option 3: Increase wait time
```python
# In test, increase retry count and interval
for attempt in range(30):  # Was 10
    # ...
    await asyncio.sleep(2)  # Was 1
```

### Option 4: Use MediaMTX's builtin stream source
```yaml
# Test with a static source first
paths:
  test:
    source: rtsp://rtsp.stream/pattern
```

---

## Success Criteria

Step 1 will pass when:

1. ✅ ffmpeg successfully connects to MediaMTX
2. ✅ Stream appears in `http://localhost:8889/v3/paths/list/` response
3. ✅ Stream name matches expected pattern
4. ✅ Happens within 10 seconds of publish start

**Example successful response:**
```json
{
  "itemCount": 1,
  "pageCount": 1,
  "items": [
    {
      "name": "live/test_test_full_pipeline_media_to_sts_to_output_1767313771/in",
      "source": {
        "type": "rtspSession",
        "id": "abc123"
      },
      "ready": true,
      "readyTime": "2026-01-01T17:29:32Z",
      "bytesReceived": 1234567
    }
  ]
}
```

---

## Related Files

**Test Files:**
- `tests/e2e/test_dual_compose_full_pipeline.py` - Main test
- `tests/e2e/conftest_dual_compose.py` - Fixtures (publish_test_fixture)
- `tests/e2e/helpers/stream_publisher.py` - ffmpeg wrapper

**Configuration:**
- `apps/media-service/docker-compose.e2e.yml` - MediaMTX container
- `apps/media-service/deploy/mediamtx/mediamtx.yml` - MediaMTX config

**Test Assets:**
- `tests/e2e/fixtures/test_streams/30s-counting-english.mp4` - Test video

---

## Next Steps

1. **Immediate:** Add debug logging to capture MediaMTX API response format
2. **Short-term:** Test manual stream publish to isolate issue
3. **Medium-term:** Review MediaMTX configuration for publish permissions
4. **Long-term:** Consider adding ffmpeg health monitoring to StreamPublisher

Once Step 1 passes, the remaining pipeline should work (assuming WorkerRunner and STS service are functional).

---

## Additional Context

**Passing Tests (5/7):**
- ✅ `test_docker_compose_files_exist` - Infrastructure validation
- ✅ `test_test_fixture_exists` - Test asset validation
- ✅ `test_services_can_communicate` - HTTP health checks
- ✅ `test_socketio_connection_established` - Socket.IO connectivity

**Failing Tests (2/7):**
- ❌ `test_full_pipeline_media_to_sts_to_output` - Stream ingestion (THIS ISSUE)
- ❌ `test_sts_processes_real_audio` - Fragment processing (echo service handlers not implemented)

**Test Infrastructure Status:**
- Docker compose orchestration: ✅ Working
- Health checks: ✅ Working
- Service communication: ✅ Working
- Socket.IO: ✅ Working
- Stream ingestion: ❌ Blocked at Step 1

---

**Last Updated:** 2026-01-01
**Issue Owner:** Development Team
**Priority:** High (blocks full E2E validation)
