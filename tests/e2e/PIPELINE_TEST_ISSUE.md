# Full Pipeline E2E Test - Resolution Summary

**Test:** `test_dual_compose_full_pipeline.py::test_full_pipeline_media_to_sts_to_output`
**Branch:** `019-dual-docker-e2e-infrastructure`
**Last Updated:** 2026-01-01 21:30 PST
**Status:** ✅ Step 1 RESOLVED | ✅ Step 2 RESOLVED | ⏸️ Step 3 (GStreamer segments not writing)

---

## Quick Summary

### ✅ Step 1: MediaMTX Stream Reception (RESOLVED)
**Issue:** Test fixture not appearing in MediaMTX
**Root Cause:** Using RTSP for publishing, but MediaMTX expects RTMP
**Fix:** Converted StreamPublisher to use RTMP (`-f flv rtmp://...`)
**Commit:** ea27c3f

### ✅ Step 2: WorkerRunner Connection (RESOLVED)
**Issue:** WorkerRunner fails to connect to STS within 10 seconds
**Root Causes:**
1. Missing `aiohttp` package for Socket.IO async client
2. Socket.IO namespace mismatch (client: "/sts", server: "/")
3. Missing `worker_id` field in stream:init payload
4. `chunk_duration_ms` validation too strict (5000ms vs 6000ms)
5. Test checking wrong metric (segments_processed vs worker_info)
6. Test stream not looping (ended before segments could be written)

**Fixes Applied:**
1. Added `aiohttp>=3.9.0` to Dockerfile dependencies
2. Changed Socket.IO namespace from "/sts" to "/" (3 files)
3. Added `worker_id: f"worker-{stream_id}"` to payload
4. Updated validation: `le=5000` → `le=6000`
5. Fixed test to check for `media_service_worker_info_info` metric
6. Added `loop=True` to stream publisher fixture

**Files Modified:**
- `apps/media-service/deploy/Dockerfile` - Added aiohttp dependency
- `apps/media-service/src/media_service/sts/socketio_client.py` - Changed namespace, added worker_id
- `apps/media-service/src/media_service/worker/worker_runner.py` - Changed namespace
- `apps/media-service/tests/unit/test_sts_socketio_client.py` - Updated test expectations
- `apps/sts-service/src/sts_service/echo/models/stream.py` - Updated validation
- `tests/e2e/conftest_dual_compose.py` - Added loop=True
- `tests/e2e/test_dual_compose_full_pipeline.py` - Fixed metric check

**Verification:**
```
✅ Worker metrics appear immediately after stream starts
✅ Socket.IO connection established
✅ Stream init handshake completes
✅ Metrics: media_service_worker_info_info, sts_inflight_fragments, circuit_breaker_state
```

### ⏸️ Step 3: Socket.IO Events (BLOCKED)
**Issue:** No `fragment:processed` events received (timeout after 180s)
**Root Cause:** GStreamer splitmuxsink not writing segment files to disk
**Symptoms:**
- Segment directories created: `/tmp/segments/{stream_id}/`
- No `.m4a` files written
- Input pipeline receives RTP pads (data flowing)
- No errors in logs

**Next Steps:** Investigate GStreamer pipeline configuration for audio segmentation

### ⏸️ Step 4: Event Data Validation (NOT REACHED)
**Purpose:** Validate `fragment:processed` event payload structure
**Checks:**
- Verify `fragment_id`, `status`, `processing_time_ms` fields present
- Confirm `dubbed_audio` base64-encoded M4A data
- Validate sequence numbers match sent fragments

**Blocked by:** Step 3

### ⏸️ Step 5: Output RTMP Stream (NOT REACHED)
**Purpose:** Verify dubbed audio output stream appears in MediaMTX
**Checks:**
- Query MediaMTX API for output stream path
- Verify stream marked as "ready"
- Validate output contains remuxed video + dubbed audio

**Blocked by:** Step 3

### ⏸️ Step 6: Metrics Verification (NOT REACHED)
**Purpose:** Validate end-to-end metrics after pipeline completion
**Checks:**
- `media_service_worker_segments_processed_total` > 0
- `media_service_worker_sts_fragments_sent_total` matches segment count
- `media_service_worker_sts_fragments_processed_total` matches received count
- `media_service_worker_sts_processing_latency_seconds` histogram populated
- No circuit breaker failures

**Blocked by:** Step 3

---

## Test Progress

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 0 | Environment Setup | ✅ PASS | Docker Compose environments healthy |
| 1 | MediaMTX Receives Stream | ✅ PASS | Fixed via RTMP conversion (ea27c3f) |
| 2 | WorkerRunner Connects | ✅ PASS | Fixed all 6 root causes (2026-01-01) |
| 3 | Socket.IO Events | ❌ BLOCKED | GStreamer not writing segments |
| 4 | Event Data Validation | ⏸️ Not reached | Pending Step 3 |
| 5 | Output RTMP Stream | ⏸️ Not reached | Pending |
| 6 | Metrics Verification | ⏸️ Not reached | Pending |

**Overall Progress:** 3/7 steps passing (~43% complete)

---

## Architecture Context

**Expected Flow:**
```
Test Fixture (30s MP4, looping)
    ↓
ffmpeg -re -stream_loop -1 → RTMP publish
    ↓
MediaMTX RTMP input (port 1935)
    ↓
MediaMTX calls hook → http://media-service:8080/v1/mediamtx/events/ready
    ↓
WorkerRunner starts:
  - Socket.IO connects to STS (http://host.docker.internal:3000)
  - Input pipeline: RTSP → splitmuxsink → .m4a segments
  - Output pipeline: rtmpsink → MediaMTX
    ↓
SegmentBuffer detects new .m4a files → sends to STS
    ↓
STS processes (echo mode) → fragment:processed events
    ↓
WorkerRunner remuxes → publishes to output RTMP
```

**Current State:** Pipeline stops at segment writing (Step 3)

---

## Configuration (E2E Environment)

### Media Service (apps/media-service/docker-compose.e2e.yml)
- Port: 8080 (metrics/API)
- RTSP source: `rtsp://mediamtx:8554`
- RTMP output: `rtmp://mediamtx:1935`
- STS URL: `http://host.docker.internal:3000`
- Segments: `/tmp/segments` (mounted volume)
- Namespace: `/` (default)

### STS Service (apps/sts-service/docker-compose.e2e.yml)
- Port: 3000
- Mode: Echo (no actual ASR/TTS)
- Socket.IO path: `/socket.io/` (default)
- Namespace: `/` (default)

### MediaMTX (bluenviron/mediamtx:latest-ffmpeg)
- RTSP: 8554
- RTMP: 1935
- API: 8889
- Hooks: ready, not-ready → `http://media-service:8080/v1/mediamtx/events/{event}`

---

## Key Learnings

1. **Socket.IO Configuration**: Path vs namespace are separate concepts
   - `socketio_path`: HTTP endpoint where Socket.IO is mounted (e.g., `/ws/sts` or `/socket.io/`)
   - `namespace`: Logical channel for events (e.g., `/sts` or `/`)
   - Standardizing on defaults (`/socket.io/` and `/`) simplifies configuration

2. **Test Design**: Check for initialization metrics, not processing metrics
   - `media_service_worker_info_info` appears immediately when Worker starts
   - `media_service_worker_segments_processed_total` only appears after processing
   - Step 2 should verify connection, not processing

3. **Stream Lifecycle**: Use `-stream_loop -1` for E2E tests
   - 30s fixture ends too quickly for segment writing (6s chunks)
   - Looping ensures stream stays active during test

4. **Dependency Management**: Always include async client dependencies
   - `python-socketio[asyncio]` requires `aiohttp` for async WebSocket support
   - Not listed in package metadata, must be explicit

---

## Files Modified (All Steps)

### Step 1: RTMP Conversion
1. `tests/e2e/helpers/stream_publisher.py` - RTSP → RTMP
2. `tests/e2e/conftest_dual_compose.py` - Updated base URL
3. `tests/e2e/test_dual_compose_full_pipeline.py` - Updated assertions
4. `apps/media-service/deploy/mediamtx/mediamtx.yml` - Disabled WebRTC
5. `apps/media-service/docker-compose.e2e.yml` - Mounted config

### Step 2: STS Connection
6. `apps/media-service/deploy/Dockerfile` - Added aiohttp
7. `apps/media-service/src/media_service/sts/socketio_client.py` - Namespace + worker_id
8. `apps/media-service/src/media_service/worker/worker_runner.py` - Namespace
9. `apps/media-service/tests/unit/test_sts_socketio_client.py` - Test updates
10. `apps/sts-service/src/sts_service/echo/models/stream.py` - Validation
11. `tests/e2e/conftest_dual_compose.py` - Loop=True
12. `tests/e2e/test_dual_compose_full_pipeline.py` - Metric check

**Total:** 12 files modified across both steps

---

## Next Actions

1. **Investigate GStreamer Pipeline** (Step 3 blocker)
   - Check splitmuxsink configuration in input pipeline
   - Verify max-size-time, max-size-bytes settings
   - Confirm audio extraction and AAC encoding
   - Test manual ffmpeg command to validate GStreamer approach

2. **Alternative Approach** (if GStreamer blocked)
   - Use ffmpeg directly for segmentation instead of GStreamer
   - Simpler, more reliable for audio extraction
   - May require pipeline redesign

3. **After Step 3 Passes**
   - Validate fragment:processed payload structure
   - Verify output stream appears in MediaMTX
   - Confirm metrics updated correctly

---

## Useful Commands

```bash
# Check Worker logs
docker logs e2e-media-service 2>&1 | grep -E "(Worker|Socket.IO|pipeline)"

# Check segment files
docker exec e2e-media-service ls -laR /tmp/segments/

# Check metrics
curl -s http://localhost:8080/metrics | grep media_service_worker

# Manually publish looping stream
ffmpeg -re -stream_loop -1 -i tests/e2e/fixtures/test_streams/30s-counting-english.mp4 \
  -c copy -f flv rtmp://localhost:1935/live/manual_test/in

# Check MediaMTX streams
curl -s http://localhost:8889/v3/paths/list | jq

# Clean up Docker environments
docker compose -f apps/media-service/docker-compose.e2e.yml -p e2e-media down -v
docker compose -f apps/sts-service/docker-compose.e2e.yml -p e2e-sts down -v
```
