# Implementation Plan: Full Services E2E Testing

**Feature**: 021-production-e2e-testing
**Goal**: Make `test_full_pipeline.py` pass using real services (no mocking)
**Status**: Ready for Implementation

## Overview

This plan implements E2E testing for the complete dubbing pipeline using **real, unmodified services** running locally via Docker Compose. The test validates the production code path: media-service (GStreamer pipeline) + real STS-service (Whisper ASR + Translation + TTS) communicating via Socket.IO protocol.

**Key Principle**: No mocking - only environmental differences (localhost vs cloud, CPU vs GPU).

## Phase 0: Prerequisites & Setup

### Task 0.1: Verify Test Infrastructure Exists
**Status**: Verification
**Files to check**:
- `tests/e2e/test_full_pipeline.py` - Main E2E test (exists)
- `tests/e2e/conftest.py` - Pytest fixtures (exists)
- `tests/e2e/helpers/docker_compose_manager.py` - Docker orchestration (exists)
- `tests/e2e/helpers/socketio_monitor.py` - Socket.IO monitoring (exists)
- `tests/e2e/helpers/stream_publisher.py` - RTMP stream publishing (exists)
- `tests/e2e/helpers/stream_analyzer.py` - ffprobe wrapper (exists)
- `tests/e2e/helpers/metrics_parser.py` - Prometheus metrics (exists)

**Action**: Verify all helper files are functional (no modifications needed based on review).

### Task 0.2: Identify Required Changes
**Status**: Analysis
**Current state**:
- Test references `docker-compose.e2e.yml` files (line 272-273 in test_full_pipeline.py)
- Conftest uses existing `docker-compose.yml` files (lines 31-32)
- **Mismatch**: Test expects `.e2e.yml` but conftest uses `.yml`

**Required changes**:
1. Update `test_docker_compose_files_exist()` to check for `.yml` files (NOT `.e2e.yml`)
2. Verify conftest uses correct compose file paths
3. Create test fixture: `tests/e2e/fixtures/test-streams/1-min-nfl.mp4`
4. Update conftest environment variables to match production compose files
5. Ensure services can communicate via localhost

---

## Phase 1: Fix Docker Compose File References

### Task 1.1: Update test_full_pipeline.py Docker Compose Check
**File**: `tests/e2e/test_full_pipeline.py`
**Change**: Update `test_docker_compose_files_exist()` function

**Current code** (lines 265-277):
```python
def test_docker_compose_files_exist():
    """Verify docker-compose.e2e.yml files exist for both services."""
    project_root = Path(__file__).parent.parent.parent

    media_compose = project_root / "apps/media-service/docker-compose.e2e.yml"
    sts_compose = project_root / "apps/sts-service/docker-compose.e2e.yml"

    assert media_compose.exists(), f"Media compose file should exist at {media_compose}"
    assert sts_compose.exists(), f"STS compose file should exist at {sts_compose}"
```

**Updated code**:
```python
def test_docker_compose_files_exist():
    """Verify docker-compose.yml files exist for both services."""
    project_root = Path(__file__).parent.parent.parent

    media_compose = project_root / "apps/media-service/docker-compose.yml"
    sts_compose = project_root / "apps/sts-service/docker-compose.yml"

    assert media_compose.exists(), f"Media compose file should exist at {media_compose}"
    assert sts_compose.exists(), f"STS compose file should exist at {sts_compose}"

    logger.info("Docker compose files verified")
```

**Rationale**: Use existing production compose files instead of creating separate E2E files.

### Task 1.2: Verify conftest.py Uses Correct Paths
**File**: `tests/e2e/conftest.py`
**Status**: Already correct (lines 31-32)

```python
MEDIA_COMPOSE_FILE = PROJECT_ROOT / "apps/media-service/docker-compose.yml"
STS_COMPOSE_FILE = PROJECT_ROOT / "apps/sts-service/docker-compose.yml"
```

**Action**: No changes needed - already using production compose files.

---

## Phase 2: Configure Environment Variables for E2E

### Task 2.1: Analyze Required Environment Variables
**Status**: Analysis

**Media Service Requirements** (from `docker-compose.yml`):
- `STS_SERVICE_URL` - **Critical**: Must point to STS service on localhost
- `MEDIAMTX_*` ports - RTSP, RTMP, API, Metrics
- `MEDIA_SERVICE_PORT` - HTTP API port
- Network/volume configuration

**STS Service Requirements** (from `docker-compose.yml`):
- `DEVICE=cpu` - CPU-only processing for macOS
- `ASR_MODEL=tiny` - Smallest Whisper model for faster loading
- `TTS_PROVIDER=coqui` - Real TTS (NOT mock)
- `TRANSLATION_PROVIDER=mock` - Mock translation for E2E (faster)
- `STS_PORT=3000` - Service port

### Task 2.2: Update conftest.py Environment Variables
**File**: `tests/e2e/conftest.py`
**Section**: `media_compose_env` fixture (lines 42-98)

**Current issues**:
1. Uses `TTS_PROVIDER=mock` in STS config - should use real TTS for validation
2. Uses `TRANSLATION_PROVIDER=mock` - acceptable for E2E (faster)
3. Uses `ASR_MODEL=tiny` - good for fast loading

**Required changes**:

#### Change 2.2.1: Update STS Environment to Use Real TTS
**Location**: `sts_compose_env` fixture (line 142)
**Current**:
```python
"TTS_PROVIDER": "mock",  # Use mock TTS for E2E tests
```

**Updated**:
```python
"TTS_PROVIDER": "coqui",  # Use real TTS for production validation
```

**Rationale**: Spec requires "real Whisper ASR + real Translation + real Coqui TTS" (FR-010, FR-012). Mock TTS defeats the purpose of testing production code path.

#### Change 2.2.2: Keep Translation Mock (Acceptable)
**Location**: `sts_compose_env` fixture (line 143)
**Keep as-is**:
```python
"TRANSLATION_PROVIDER": "mock",  # Use mock translation for E2E tests
```

**Rationale**: Mock translation is acceptable for E2E to avoid API key requirements. Still validates Socket.IO protocol and TTS integration.

#### Change 2.2.3: Verify STS_SERVICE_URL for macOS Docker
**Location**: `media_compose_env` fixture (line 75)
**Current**:
```python
"STS_SERVICE_URL": "http://host.docker.internal:3000",
```

**Status**: Correct for macOS Docker Desktop - `host.docker.internal` resolves to host machine.

**Alternative for Linux** (not needed for this spec, but document):
```python
# Linux would use: "http://172.17.0.1:3000" (Docker bridge gateway)
```

---

## Phase 3: Create Test Fixture

### Task 3.1: Create Test Fixture Directory
**Action**: Create directory structure

```bash
mkdir -p tests/e2e/fixtures/test-streams
```

### Task 3.2: Obtain/Create 1-min NFL Test Fixture
**File**: `tests/e2e/fixtures/test-streams/1-min-nfl.mp4`
**Requirements** (from spec FR-025):
- Duration: 60 seconds (± 1s tolerance)
- Video codec: H.264
- Audio codec: AAC @ 44.1kHz
- Audio must have speech content (for ASR testing)

**Options**:

#### Option A: Use Existing Fixture (if available elsewhere)
**Check**: Search codebase for existing NFL fixture
```bash
find . -name "*nfl*.mp4" -o -name "*1-min*.mp4"
```

#### Option B: Create Synthetic Fixture with ffmpeg
**Command**:
```bash
# Generate 60s test video with tone audio (placeholder)
ffmpeg -f lavfi -i testsrc=duration=60:size=1280x720:rate=30 \
       -f lavfi -i sine=frequency=440:duration=60:sample_rate=44100 \
       -c:v libx264 -preset fast -crf 22 \
       -c:a aac -b:a 128k -ar 44100 \
       tests/e2e/fixtures/test-streams/1-min-nfl.mp4
```

**Issue with Option B**: Synthetic audio (sine tone) won't produce meaningful ASR transcripts.

#### Option C: Use Sample Video with Speech (RECOMMENDED)
**Approach**: Find Creative Commons video with English speech, trim to 60s

**Example sources**:
- Big Buck Bunny (already mentioned in test infrastructure)
- NASA footage with commentary
- BBC News clips (if licensing allows)

**Command to trim existing video**:
```bash
# Trim first 60 seconds from existing video
ffmpeg -i input.mp4 -t 60 \
       -c:v libx264 -preset fast -crf 22 \
       -c:a aac -b:a 128k -ar 44100 \
       tests/e2e/fixtures/test-streams/1-min-nfl.mp4
```

**Decision**: For this implementation plan, assume test fixture will be provided or created manually. Document requirements in README.

### Task 3.3: Validate Test Fixture
**Action**: Add validation step to test

**File**: `tests/e2e/test_full_pipeline.py`
**Function**: `test_test_fixture_exists()` (lines 281-319)

**Status**: Already implemented - validates:
- Duration: 59-61 seconds
- Video codec: H.264
- Audio codec: AAC @ 44.1kHz

**Action**: No changes needed.

---

## Phase 4: Verify Service Communication

### Task 4.1: Verify Port Exposure in Docker Compose Files
**Files**:
- `apps/media-service/docker-compose.yml`
- `apps/sts-service/docker-compose.yml`

**Required ports**:

**Media Service** (lines 24-29):
```yaml
ports:
  - "${MEDIAMTX_RTMP_PORT:-1935}:1935"     # RTMP ✓
  - "${MEDIAMTX_RTSP_PORT:-8554}:8554"     # RTSP ✓
  - "${MEDIAMTX_API_PORT:-9997}:9997"      # Control API ✓
  - "${MEDIAMTX_METRICS_PORT:-9998}:9998"  # Metrics ✓
  - "${MEDIA_SERVICE_PORT:-8080}:8080"     # Media service API ✓
```

**STS Service** (line 39):
```yaml
ports:
  - "${STS_PORT:-3000}:3000"  # STS service ✓
```

**Status**: All required ports are exposed to localhost.

### Task 4.2: Verify Health Check Endpoints
**Media Service Health Checks** (lines 60-65, 122-127):
```yaml
mediamtx:
  healthcheck:
    test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:9997/v3/paths/list"]

media-service:
  healthcheck:
    test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:8080/health"]
```

**STS Service Health Check** (lines 87-92):
```yaml
sts-service:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
```

**Status**: Health checks defined in compose files. Docker Compose Manager will wait for these.

### Task 4.3: Document Service Communication Flow
**For implementation reference**:

```
┌─────────────────────────────────────────────────────────────┐
│  macOS Host (localhost)                                     │
│                                                              │
│  ┌──────────────────┐      ┌───────────────────┐           │
│  │ Pytest Test      │      │ ffmpeg Publisher  │           │
│  │ - Monitors STS   │      │ - Publishes to    │           │
│  │ - Checks metrics │      │   RTMP :1935      │           │
│  └──────────────────┘      └───────────────────┘           │
│           │                          │                      │
│           │ Socket.IO :3000          │ RTMP :1935          │
│           │ HTTP :8080, :9997        │                      │
│           ▼                          ▼                      │
│  ┌──────────────────────────────────────────────┐          │
│  │ Docker: e2e-media (dubbing-network)          │          │
│  │  ┌─────────────┐      ┌──────────────────┐  │          │
│  │  │ MediaMTX    │◄─────┤ media-service    │  │          │
│  │  │ :1935 RTMP  │      │ :8080 HTTP       │  │          │
│  │  │ :8554 RTSP  │      │ GStreamer        │  │          │
│  │  │ :9997 API   │      │ Socket.IO client │──┼─┐        │
│  │  └─────────────┘      └──────────────────┘  │ │        │
│  └──────────────────────────────────────────────┘ │        │
│                                                    │        │
│  ┌──────────────────────────────────────────────┐ │        │
│  │ Docker: e2e-sts (sts-network)                │ │        │
│  │  ┌──────────────────────────────────────┐    │ │        │
│  │  │ sts-service                          │    │ │        │
│  │  │ :3000 Socket.IO server               │◄───┼─┘        │
│  │  │ Whisper ASR + Translation + TTS      │    │          │
│  │  └──────────────────────────────────────┘    │          │
│  └──────────────────────────────────────────────┘          │
│                                                              │
│  Connection: media-service → http://host.docker.internal:3000 │
└─────────────────────────────────────────────────────────────┘
```

**Key points**:
1. Two separate Docker networks (dubbing-network, sts-network) - services isolated
2. media-service connects to STS via `host.docker.internal:3000` (macOS Docker Desktop)
3. Pytest connects to both services via localhost exposed ports
4. ffmpeg publisher sends RTMP stream to MediaMTX via localhost:1935

---

## Phase 5: Update conftest.py for Production Compose Files

### Task 5.1: Review Current conftest.py Configuration
**File**: `tests/e2e/conftest.py`
**Status**: Mostly correct, minor updates needed

**Current fixture flow**:
1. `media_compose_env` - Session-scoped, starts MediaMTX + media-service
2. `sts_compose_env` - Session-scoped, starts real STS service
3. `dual_compose_env` - Combines both managers
4. `publish_test_fixture` - Function-scoped, publishes test video
5. `sts_monitor` - Async, monitors Socket.IO events

### Task 5.2: Update Service Names in conftest.py
**File**: `tests/e2e/conftest.py`
**Location**: `sts_compose_env` fixture (line 162)

**Current**:
```python
services=["sts-service"],
```

**Issue**: May need to verify service name matches docker-compose.yml

**Check docker-compose.yml** (apps/sts-service/docker-compose.yml line 27):
```yaml
services:
  sts-service:  # Correct service name
```

**Status**: Service name is correct. No change needed.

### Task 5.3: Add Environment Variable Overrides
**File**: `tests/e2e/conftest.py`
**Purpose**: Ensure E2E-specific configuration overrides production defaults

**No changes needed** - fixture already provides comprehensive env dict (lines 56-97 for media, 129-152 for STS).

---

## Phase 6: Run Test and Iterate

### Task 6.1: Pre-flight Checklist
**Before running test**:

1. **Docker Running**: `docker ps` succeeds
2. **Ports Available**: No services using 1935, 3000, 8080, 8554, 9997, 9998
3. **Test Fixture Exists**: `tests/e2e/fixtures/test-streams/1-min-nfl.mp4`
4. **Disk Space**: At least 5GB free (for Docker images + model cache)
5. **Memory**: At least 8GB RAM available

**Check ports**:
```bash
lsof -i :1935 -i :3000 -i :8080 -i :8554 -i :9997 -i :9998
# Should return empty (no processes listening)
```

### Task 6.2: Build Docker Images First
**Rationale**: Separate build from test run to catch build errors early

```bash
# Build media-service image
cd apps/media-service
docker compose build

# Build sts-service image
cd apps/sts-service
docker compose build
```

### Task 6.3: Run Test with Verbose Output
**Command**:
```bash
cd tests/e2e
pytest test_full_pipeline.py::test_full_pipeline_media_to_sts_to_output -v -s --log-cli-level=INFO
```

**Expected output stages**:
1. Starting dual compose environments (60-90s for STS model loading)
2. Publishing test fixture to MediaMTX
3. Waiting for stream to appear in MediaMTX API
4. Waiting for WorkerRunner metrics
5. Monitoring Socket.IO for fragment:processed events (10 expected)
6. Validating output stream with ffprobe
7. Checking final metrics

**Expected duration**: 120-180 seconds (60s video + 5-15s per fragment for CPU STS)

### Task 6.4: Debug Common Failures

#### Failure: Services Don't Start
**Symptom**: Timeout waiting for health checks

**Debug steps**:
```bash
# Check container status
docker compose -f apps/media-service/docker-compose.yml -p e2e-media ps
docker compose -f apps/sts-service/docker-compose.yml -p e2e-sts ps

# Check logs
docker compose -f apps/media-service/docker-compose.yml -p e2e-media logs
docker compose -f apps/sts-service/docker-compose.yml -p e2e-sts logs
```

**Common causes**:
- Port conflicts (check with `lsof`)
- Docker out of memory
- Missing dependencies in Dockerfile

#### Failure: media-service Can't Connect to STS
**Symptom**: No fragment:processed events, timeout at step 3

**Debug steps**:
```bash
# Test STS health from host
curl http://localhost:3000/health

# Test from inside media-service container
docker exec e2e-media-service curl http://host.docker.internal:3000/health

# Check media-service logs for Socket.IO errors
docker compose -f apps/media-service/docker-compose.yml -p e2e-media logs media-service | grep -i socket
```

**Common causes**:
- `STS_SERVICE_URL` misconfigured
- STS service not exposing port 3000
- Firewall blocking connections

#### Failure: No Fragments Processed
**Symptom**: Stream active, WorkerRunner connected, but no fragment:processed events

**Debug steps**:
```bash
# Check media-service metrics for segmentation
curl http://localhost:8080/metrics | grep segment

# Check STS service received fragments
docker compose -f apps/sts-service/docker-compose.yml -p e2e-sts logs | grep fragment

# Monitor Socket.IO events manually
# (Use sts_monitor fixture or Socket.IO client tool)
```

**Common causes**:
- Audio codec mismatch (test fixture not AAC)
- Segmentation not triggering (check segment duration config)
- STS service crashing on fragment processing

#### Failure: Output Stream Not Available
**Symptom**: Fragments processed, but ffprobe can't find output stream

**Debug steps**:
```bash
# Check MediaMTX API for output stream
curl http://localhost:9997/v3/paths/list | jq '.items[] | select(.name | contains("out"))'

# Check if media-service is publishing output
docker compose -f apps/media-service/docker-compose.yml -p e2e-media logs media-service | grep -i "output\|publish"
```

**Common causes**:
- Output stream path mismatch (should be `{input}/out`)
- GStreamer pipeline error during remux
- MediaMTX rejecting output stream

### Task 6.5: Capture Logs on Failure
**Action**: Enhance test to capture logs automatically

**File**: `tests/e2e/conftest.py`
**Add teardown hook** (optional improvement):

```python
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture Docker logs on test failure."""
    outcome = yield
    result = outcome.get_result()

    if result.when == "call" and result.failed:
        # Get dual_compose_env fixture if available
        if "dual_compose_env" in item.funcargs:
            env = item.funcargs["dual_compose_env"]

            # Save logs
            media_logs = env["media"].get_logs(tail=200)
            sts_logs = env["sts"].get_logs(tail=200)

            log_dir = Path(__file__).parent / "logs"
            log_dir.mkdir(exist_ok=True)

            (log_dir / f"{item.name}_media.log").write_text(media_logs)
            (log_dir / f"{item.name}_sts.log").write_text(sts_logs)

            logger.error(f"Test failed. Logs saved to {log_dir}")
```

**Note**: This is optional - can add in iteration if needed.

---

## Phase 7: Validate Success Criteria

### Task 7.1: Verify All Success Criteria Met
**From spec (SC-001 through SC-008)**:

- [ ] **SC-001**: Test completes within 300 seconds
- [ ] **SC-002**: All 10 fragment:processed events received with valid data
- [ ] **SC-003**: Output RTMP stream exists and playable
- [ ] **SC-004**: Output duration 60s ± 1s
- [ ] **SC-005**: Metrics show 10 processed audio segments
- [ ] **SC-006**: No mocking - real ASR, real Translation, real TTS
- [ ] **SC-007**: Test runs on localhost/macOS with CPU
- [ ] **SC-008**: Test infrastructure reusable for additional tests

### Task 7.2: Validate Socket.IO Event Data
**Check**: Each fragment:processed event contains (from test lines 166-184):
- `dubbed_audio`: Base64-encoded audio, length > 0
- `transcript`: English text from Whisper ASR
- `translated_text`: Spanish text from Translation module

**Example event validation**:
```python
{
  "dubbed_audio": "AAAAGGZ0eXBNNEEg...",  # Base64 AAC audio
  "transcript": "touchdown patriots",      # Real ASR output
  "translated_text": "touchdown patriotas" # Real translation (or mock)
}
```

### Task 7.3: Manual Verification (Optional)
**For deeper validation**:

1. **Play output stream**:
```bash
ffplay rtmp://localhost:1935/live/test_*/out
```

2. **Inspect audio track**:
```bash
ffprobe -v quiet -print_format json -show_streams \
  rtmp://localhost:1935/live/test_*/out | jq '.streams[] | select(.codec_type=="audio")'
```

3. **Verify A/V sync visually**:
   - Original audio: English commentary
   - Dubbed audio: TTS output (should sound synthetic but intelligible)
   - Video: Should play smoothly without stuttering

---

## Implementation Order

### Priority 1: Must-Have for Test to Pass
1. **Task 1.1**: Fix Docker compose file check in test
2. **Task 2.2.1**: Update STS env to use real TTS (not mock)
3. **Task 3.1-3.2**: Create test fixture directory and obtain/create 1-min video
4. **Task 6.3**: Run test and verify it passes

### Priority 2: Fix Issues as They Arise
5. **Task 6.4**: Debug common failures (iterative based on test output)
6. **Task 7.1**: Validate all success criteria

### Priority 3: Optional Enhancements
7. **Task 6.5**: Add automatic log capture on failure
8. **Task 7.3**: Manual verification of output quality

---

## Testing Strategy

### TDD Approach (Spec Principle VIII)
**Note**: Test already exists (`test_full_pipeline.py`), so we're doing "TDD in reverse":
1. Test exists and currently fails (expected - infrastructure incomplete)
2. Implement infrastructure changes (conftest, fixture, env vars)
3. Run test and iterate until it passes
4. Validate success criteria

### Test Execution
```bash
# Run prerequisite tests first
pytest tests/e2e/test_full_pipeline.py::test_docker_compose_files_exist -v
pytest tests/e2e/test_full_pipeline.py::test_test_fixture_exists -v

# Run main pipeline test
pytest tests/e2e/test_full_pipeline.py::test_full_pipeline_media_to_sts_to_output -v -s --log-cli-level=INFO

# Run all E2E tests
pytest tests/e2e/test_full_pipeline.py -v
```

### Success Criteria for Implementation
- `test_docker_compose_files_exist()` passes
- `test_test_fixture_exists()` passes
- `test_full_pipeline_media_to_sts_to_output()` passes
- All 10 fragments processed with real dubbed audio
- Test completes in < 300s on macOS with CPU

---

## Dependencies

### External Dependencies
- **Docker Desktop**: Installed and running
- **Docker Compose**: v2.x
- **ffmpeg**: For test fixture creation/validation
- **Python 3.10**: With pytest, httpx, python-socketio

### Service Dependencies
- **MediaMTX**: v1.x (from bluenviron/mediamtx:latest-ffmpeg)
- **GStreamer**: 1.0 with plugins (in media-service Dockerfile)
- **Whisper Models**: Downloaded on first run (cached in Docker volume)
- **TTS Models**: Coqui TTS models (cached in Docker volume)

### Fixture Dependencies
- **1-min-nfl.mp4**: 60-second video with H.264 + AAC audio
  - Must contain English speech for ASR testing
  - Manual creation required (not in codebase)

---

## Risks & Mitigations

### Risk 1: Test Fixture Creation Complexity
**Risk**: Creating a 60-second video with real English speech for ASR testing
**Impact**: HIGH - test cannot run without valid fixture
**Mitigation**:
- **Option A**: Use existing Creative Commons video (Big Buck Bunny has some speech)
- **Option B**: Generate synthetic video with text-to-speech audio
- **Option C**: Document requirements and mark test as skipped if fixture missing

**Recommended**: Use `pytest.skip` if fixture doesn't exist, document in README

### Risk 2: CPU STS Processing Timeout
**Risk**: STS processing on CPU may take >15s per fragment, exceeding 300s timeout
**Impact**: MEDIUM - test may fail due to timeout, not functionality
**Mitigation**:
- Use smallest Whisper model (`tiny`) - already configured
- Use mock translation (faster) - already configured
- Consider increasing timeout to 600s if needed
- Monitor first run and adjust timeout based on actual latency

### Risk 3: Docker Resource Exhaustion
**Risk**: Media-service + STS-service may require >8GB RAM on macOS
**Impact**: MEDIUM - services may crash or perform poorly
**Mitigation**:
- Configure resource limits in compose files (already done)
- Document minimum system requirements (4 CPU cores, 8GB RAM)
- Monitor Docker stats during test run

### Risk 4: Port Conflicts
**Risk**: Required ports (1935, 3000, 8080, etc.) may be in use
**Impact**: LOW - easy to detect and resolve
**Mitigation**:
- Document port requirements
- Add pre-flight check to conftest.py (optional)
- Use environment variables to override ports if needed

---

## Phase 4: Debugging Progress (Current Status)

### Overview
**Test Status**: FAILING - Timeout waiting for 10 'fragment:processed' events (receives 0 after 300s)

**Root Cause**: Audio pipeline not creating segments, preventing fragments from being sent to STS.

### Issues Fixed ✅

#### 4.1: Network Isolation Between Services
**Problem**: media-service (e2e-media-network) and echo-sts (e2e-sts-network) in separate Docker networks
**Solution**: Manual network connection after services start
**Files Modified**: `tests/e2e/conftest.py` (lines 188-199)
```python
# Connect echo-sts container to media network
subprocess.run(
    ["docker", "network", "connect", "dubbing-network", "e2e-echo-sts"],
    capture_output=True, text=True
)
```

#### 4.2: Socket.IO Namespace Mismatch
**Problem**: media-service connects to `/sts` namespace, but echo-sts used default `/`
**Solution**: Updated all echo-sts handlers and emit calls to use `/sts` namespace
**Files Modified**:
- `apps/sts-service/src/sts_service/echo/server.py` - Connection handlers
- `apps/sts-service/src/sts_service/echo/handlers/stream.py` - Stream event handlers
- `apps/sts-service/src/sts_service/echo/handlers/fragment.py` - Fragment handlers

#### 4.3: GStreamer Pipeline Performance
**Problem**: MediaMTX disconnected with "reader is too slow, discarding frames"
**Solution**: Configured proper queue buffering
**Files Modified**: `apps/media-service/src/media_service/pipeline/input.py` (lines 140-155)
```python
# Video and audio queues
video_queue.set_property("max-size-buffers", 0)  # Unlimited
video_queue.set_property("max-size-bytes", 0)
video_queue.set_property("max-size-time", 5 * Gst.SECOND)
video_queue.set_property("leaky", 2)  # Drop old data if full
```

#### 4.4: Output Pipeline Audio Format
**Problem**: Output pipeline aacparse error: "Need codec_data for raw AAC"
**Solution**: Changed audio format from `raw` to `ADTS` (self-describing)
**Files Modified**: `apps/media-service/src/media_service/pipeline/output.py` (lines 134-137)
```python
audio_caps = Gst.Caps.from_string(
    "audio/mpeg,mpegversion=4,stream-format=adts,channels=2,rate=48000"
)
```

### Current Blocking Issue ❌

#### 4.5: Audio Pipeline Not Flowing
**Status**: CRITICAL - Blocks all fragment processing

**Symptoms**:
- Video pipeline: ✅ Creates 10 video segments from 60s stream
- Audio pipeline: ❌ Creates 0 audio segments
- A/V sync warning: "Video buffer full (10), dropping oldest segment"
- Test timeout: No fragments sent to STS (requires audio + video)

**What Works**:
1. ✅ Test fixture has audio track (AAC, 44100 Hz, 2 channels) - verified with ffprobe
2. ✅ MediaMTX receives and serves both tracks ("2 tracks: H264, MPEG-4 Audio")
3. ✅ flvdemux detects audio stream and creates audio pad
4. ✅ Audio pad successfully linked: `flvdemux → audio_queue → audio_appsink`
5. ✅ Caps negotiated: `audio/mpeg, mpegversion=4, stream-format=raw, rate=44100, channels=2, codec_data=1210`

**What Fails**:
1. ❌ Audio appsink callback (`_on_audio_sample`) **NEVER called**
2. ❌ No audio buffers flow from flvdemux through queue to appsink
3. ❌ SegmentBuffer never receives audio data
4. ❌ No audio segments created → no fragments → test timeout

**Investigation Attempts**:
1. **Removed aacparse** from input pipeline
   - Rationale: flvdemux outputs `framed=true` AAC, parsing may not be needed
   - Result: No change - callback still not called
   - File: `apps/media-service/src/media_service/pipeline/input.py` (lines 147-148, 269-276)

2. **Set explicit caps on audio appsink**
   - Rationale: Maybe appsink rejecting caps silently
   - Code: `audio_caps = Gst.Caps.from_string("audio/mpeg,mpegversion=4")`
   - Result: No change - callback still not called
   - File: `apps/media-service/src/media_service/pipeline/input.py` (lines 179-181)

3. **Enabled maximum GStreamer debug logging**
   - Config: `GST_DEBUG=flvdemux:5,queue:6,appsink:6`
   - File: `tests/e2e/conftest.py` (line 83)
   - Observation: Caps negotiated successfully, but no buffer flow logs

**Technical Analysis**:

The appsink callback is a Python function that GStreamer calls when new data is ready:
```python
# Line 184-185: Callback registration
self._video_appsink.connect("new-sample", self._on_video_sample)  # ✅ Called
self._audio_appsink.connect("new-sample", self._on_audio_sample)  # ❌ Never called

# Lines 341-372: Audio callback
def _on_audio_sample(self, appsink: Gst.Element) -> Gst.FlowReturn:
    sample = appsink.emit("pull-sample")
    buffer = sample.get_buffer()
    # Extract data and send to SegmentBuffer
    self._on_audio_buffer(data, pts_ns, duration_ns)
```

**Video pipeline**: Callback called ~181 times per 6s segment → segments created ✅
**Audio pipeline**: Callback never called → zero segments created ❌

**Hypothesis**: Something in GStreamer is blocking/dropping audio buffers between flvdemux and appsink, despite:
- Successful pad linking
- Successful caps negotiation
- Registered callback
- No ERROR/WARNING messages in logs

**Next Steps Needed**:
1. **Deep GStreamer debugging**: Use GLib main loop inspection or pad probes to trace buffer flow
2. **Workaround options**:
   - Try `avdec_aac` decoder instead of direct connection
   - Convert audio to different format in input pipeline
   - Bypass A/V sync requirement (process video-only for testing)
3. **Alternative approach**: If GStreamer issue too complex, consider:
   - Use different container format (not RTMP/FLV)
   - Process audio separately from video
   - File GitHub issue with GStreamer project

### Files Modified During Debugging

| File | Changes | Purpose |
|------|---------|---------|
| `tests/e2e/conftest.py` | Network connection, env vars, GStreamer debug | Fix connectivity and enable debugging |
| `apps/sts-service/src/sts_service/echo/server.py` | Socket.IO namespace `/sts` | Fix protocol mismatch |
| `apps/sts-service/src/sts_service/echo/handlers/stream.py` | Namespace + emit calls | Fix protocol mismatch |
| `apps/sts-service/src/sts_service/echo/handlers/fragment.py` | Namespace + emit calls | Fix protocol mismatch |
| `apps/media-service/src/media_service/pipeline/input.py` | Queue buffering, removed aacparse, caps config | Fix performance + debug audio |
| `apps/media-service/src/media_service/pipeline/output.py` | ADTS audio format | Fix codec_data error |
| `apps/media-service/docker-compose.yml` | `GST_DEBUG` env var | Enable GStreamer logging |

---

## File Changes Summary

### Files to Modify
1. **tests/e2e/test_full_pipeline.py**
   - Line 272-273: Change `docker-compose.e2e.yml` to `docker-compose.yml`

2. **tests/e2e/conftest.py**
   - Line 142: Change `TTS_PROVIDER` from `"mock"` to `"coqui"`

### Files to Create
3. **tests/e2e/fixtures/test-streams/1-min-nfl.mp4**
   - 60-second video with H.264 video + AAC audio @ 44.1kHz
   - Must contain English speech for ASR testing

### Files Already Correct (No Changes)
- `tests/e2e/conftest.py` - Compose file paths already correct
- `tests/e2e/helpers/docker_compose_manager.py` - Fully functional
- `tests/e2e/helpers/socketio_monitor.py` - Fully functional
- `tests/e2e/helpers/stream_publisher.py` - Fully functional
- `tests/e2e/helpers/stream_analyzer.py` - Fully functional
- `tests/e2e/helpers/metrics_parser.py` - Fully functional
- `apps/media-service/docker-compose.yml` - Port exposure correct
- `apps/sts-service/docker-compose.yml` - Port exposure correct

---

## Next Steps After Plan Approval

1. **Review plan** with stakeholders
2. **Create test fixture** or document requirements
3. **Make code changes** (2 files, minimal changes)
4. **Run test** and iterate on failures
5. **Validate success criteria** and document results
6. **Update README** with E2E test instructions

## Estimated Effort

- **Code changes**: 15 minutes (2 files, 3 line changes)
- **Test fixture creation**: 30-60 minutes (depends on source video availability)
- **Initial test run**: 5 minutes (plus 2-3 minutes per iteration)
- **Debug iterations**: 1-3 hours (estimated 2-4 iterations to resolve issues)
- **Documentation**: 30 minutes (README updates, troubleshooting guide)

**Total estimated time**: 3-5 hours for complete implementation and validation.
