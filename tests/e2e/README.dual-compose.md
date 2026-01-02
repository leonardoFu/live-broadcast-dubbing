# Dual Docker-Compose E2E Test Infrastructure

Comprehensive E2E testing infrastructure using **two separate docker-compose configurations** to test the complete live dubbing pipeline with real services: media-service + MediaMTX + **real STS service** (ASR + Translation + TTS).

## Overview

Unlike spec 018 (which uses Echo STS for fast iteration), this infrastructure validates the complete integration without mocking. It provides:

- **Service isolation**: Each service maintains its own docker-compose.yml for independent development
- **True E2E validation**: Real ASR (Whisper), real Translation, real TTS (Coqui) processing
- **Simple networking**: Services communicate via localhost + port exposure (no complex service discovery)
- **Production-like environment**: Tests validate the actual service integration that will run in production

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Dual Docker-Compose E2E Tests                  │
│                  (tests/e2e/test_dual_compose_*.py)              │
└────────────┬───────────────────────────────────┬────────────────┘
             │                                   │
             │                                   │
┌────────────▼────────────────┐     ┌────────────▼────────────────┐
│  Media Service Composition  │     │   STS Service Composition   │
│  docker-compose.e2e.yml     │     │   docker-compose.e2e.yml    │
├─────────────────────────────┤     ├─────────────────────────────┤
│  - MediaMTX (RTSP/RTMP)     │     │  - Real STS Service         │
│    Port 8554, 1935, 9997    │     │    Port 3000                │
│  - media-service            │────▶│  - ASR (Whisper-small)      │
│    Port 8080                │ via │  - Translation (Google)     │
│                             │host │  - TTS (Coqui)              │
│  Project: e2e-media         │.d.i.│  Project: e2e-sts           │
│  Network: e2e-media-network │     │  Network: e2e-sts-network   │
└─────────────────────────────┘     └─────────────────────────────┘
```

### Communication Pattern

- **Media-service → STS**: `http://host.docker.internal:3000` (bridge networking with `extra_hosts`)
- **Tests → MediaMTX**: `http://localhost:9997` (port exposure)
- **Tests → Media-service**: `http://localhost:8080` (port exposure)
- **Tests → STS**: `http://localhost:3000` (port exposure)
- **Internal (media-service → MediaMTX)**: `rtsp://mediamtx:8554` (container name)

## Prerequisites

### Software Requirements

- **Docker** & **Docker Compose v2**
- **Python 3.10.x** (per monorepo constitution)
- **ffmpeg** & **ffprobe** (for test fixture publishing and stream inspection)

### Python Dependencies

```bash
# Install test dependencies
pip install pytest pytest-asyncio python-socketio[client] httpx
```

### Test Fixture

The test fixture `30s-counting-english.mp4` is located at:
```
tests/e2e/fixtures/test_streams/30s-counting-english.mp4
```

**Properties**:
- Duration: 30 seconds
- Video: H.264, 1280x720, 30fps
- Audio: AAC, 48kHz stereo, English counting phrases "One, two, three... thirty" (~1 number/second)
- Expected Segments: 5 (6 seconds each)

This fixture enables deterministic ASR validation with known expected transcripts.

## Quick Start

### 1. Verify Docker Compose Files

```bash
# Check media-service composition
docker compose -f apps/media-service/docker-compose.e2e.yml config

# Check sts-service composition
docker compose -f apps/sts-service/docker-compose.e2e.yml config
```

### 2. Run Dual-Compose E2E Tests

**Run all P1 tests** (recommended first run):

```bash
# P1: Full pipeline + Service communication + Real STS processing
pytest tests/e2e/test_dual_compose_full_pipeline.py \
       tests/e2e/test_dual_compose_service_communication.py \
       tests/e2e/test_dual_compose_real_sts_processing.py \
       -v -s
```

**Run specific test**:

```bash
# Test 1: Full pipeline (30s fixture → real STS → dubbed output)
pytest tests/e2e/test_dual_compose_full_pipeline.py::test_full_pipeline_media_to_sts_to_output -v -s

# Test 2: Service communication (health checks)
pytest tests/e2e/test_dual_compose_service_communication.py::test_services_can_communicate -v -s

# Test 3: Real STS processing (ASR + Translation + TTS)
pytest tests/e2e/test_dual_compose_real_sts_processing.py::test_sts_processes_real_audio -v -s
```

### 3. Manual Composition Startup (Optional)

If you want to start compositions manually for debugging:

```bash
# Terminal 1: Start STS service
docker compose -f apps/sts-service/docker-compose.e2e.yml up

# Terminal 2: Start media service
docker compose -f apps/media-service/docker-compose.e2e.yml up

# Terminal 3: Run tests
pytest tests/e2e/test_dual_compose_service_communication.py -v

# Cleanup
docker compose -f apps/media-service/docker-compose.e2e.yml down -v
docker compose -f apps/sts-service/docker-compose.e2e.yml down -v
```

## Test Organization

### P1 Tests (MVP - Core Functionality)

**File**: `test_dual_compose_full_pipeline.py`
- `test_full_pipeline_media_to_sts_to_output`: Complete dubbing pipeline (fixture → dubbed output)
- Expected duration: ~180 seconds (30s fixture + real STS latency ~15s per 6s fragment)

**File**: `test_dual_compose_service_communication.py`
- `test_services_can_communicate`: Health checks for all services
- `test_socketio_connection_established`: Socket.IO connection to STS
- Expected duration: ~5 seconds

**File**: `test_dual_compose_real_sts_processing.py`
- `test_sts_processes_real_audio`: Real ASR + Translation + TTS processing
- `test_sts_fragment_processing_contract`: Event schema validation
- Expected duration: ~20 seconds per test

### Test Execution Times

- **Fast tests** (<5s): Service communication, health checks
- **Slow tests** (20s-180s): Full pipeline, real STS processing
- **Total P1 suite**: ~250-300 seconds (with real STS latency)

## Environment Configuration

### Default Configuration

Both compositions use sensible defaults (see `.env.e2e.example` files):

**Media Service** (`apps/media-service/.env.e2e.example`):
```env
MEDIAMTX_RTSP_PORT=8554
MEDIAMTX_RTMP_PORT=1935
MEDIA_SERVICE_PORT=8080
STS_SERVICE_URL=http://host.docker.internal:3000
```

**STS Service** (`apps/sts-service/.env.e2e.example`):
```env
STS_PORT=3000
ASR_MODEL=whisper-small
TTS_PROVIDER=coqui
DEVICE=cpu
```

### Custom Configuration

Override environment variables for CI/CD or local customization:

```bash
# Use custom ports to avoid conflicts
export MEDIAMTX_RTSP_PORT=9554
export STS_PORT=4000

# Run tests
pytest tests/e2e/test_dual_compose_*.py -v
```

## Session-Scoped Fixtures

To optimize test execution, Docker Compose environments use **session scope**:

- **Start once**: Both compositions start at the beginning of the test session
- **Model loading**: STS models (Whisper, TTS) load once (~30s), amortized across all tests
- **Test isolation**: Tests use unique stream names (e.g., `/live/test1/in`, `/live/test2/in`) to avoid conflicts
- **Teardown**: Compositions stop and volumes removed at end of session

This reduces total execution time from ~800s (restart per test) to ~300s (session scope).

## Debugging

### View Logs

```bash
# View logs from both compositions
docker compose -f apps/media-service/docker-compose.e2e.yml logs -f
docker compose -f apps/sts-service/docker-compose.e2e.yml logs -f
```

### Inspect Services

```bash
# Check service health
curl http://localhost:9997/v3/paths/list  # MediaMTX
curl http://localhost:8080/health         # Media Service
curl http://localhost:3000/health         # STS Service

# Check metrics
curl http://localhost:8080/metrics | grep worker_
```

### Common Issues

**Issue**: Port conflicts (e.g., port 8554 already in use)
**Solution**: Use environment variables to override ports:
```bash
export MEDIAMTX_RTSP_PORT=9554
export MEDIAMTX_RTMP_PORT=1936
```

**Issue**: STS model download failures (slow network)
**Solution**: Pre-download models or increase start_period in health check:
```yaml
healthcheck:
  start_period: 60s  # Increase from 30s
```

**Issue**: Tests timeout waiting for fragment:processed events
**Solution**: Check STS service logs for processing errors:
```bash
docker compose -f apps/sts-service/docker-compose.e2e.yml logs sts-service
```

**Issue**: Output stream not available
**Solution**: Check media-service logs for RTMP publishing errors:
```bash
docker compose -f apps/media-service/docker-compose.e2e.yml logs media-service
```

## Comparison with Spec 018 (Echo STS)

| Feature | Spec 018 (Echo STS) | Spec 019 (Dual Compose) |
|---------|---------------------|-------------------------|
| STS Service | Mock (Echo) | Real (ASR + Translation + TTS) |
| Execution Time | Fast (~60s total) | Slow (~300s total) |
| Docker Compose | Single file | Two separate files |
| Use Case | Fast iteration | Integration validation |
| ASR/Translation/TTS | Mocked | Real processing |
| Model Loading | N/A | 30s+ (cached in volume) |

**Recommendation**: Use spec 018 for fast development iteration, spec 019 for pre-merge validation and CI/CD.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Dual Compose Tests

on: [pull_request]

jobs:
  e2e-dual-compose:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.10
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio python-socketio[client] httpx

      - name: Run dual-compose E2E tests
        run: |
          pytest tests/e2e/test_dual_compose_*.py -v --tb=short

      - name: Upload logs on failure
        if: failure()
        run: |
          docker compose -f apps/media-service/docker-compose.e2e.yml logs > media-logs.txt
          docker compose -f apps/sts-service/docker-compose.e2e.yml logs > sts-logs.txt
```

## Contributing

When adding new dual-compose E2E tests:

1. **Follow TDD**: Write failing test FIRST, then implement
2. **Use session-scoped fixtures**: Reuse `dual_compose_env` to avoid restart overhead
3. **Unique stream names**: Use `publish_test_fixture` which generates unique names per test
4. **Mark appropriately**: Add `@pytest.mark.e2e`, `@pytest.mark.slow`, `@pytest.mark.requires_sts`
5. **Validate with real STS**: No mocking of ASR/Translation/TTS

## Related Documentation

- [Spec 019: Dual Docker-Compose E2E Infrastructure](../../specs/019-dual-docker-e2e-infrastructure/spec.md)
- [Spec 018: E2E Stream Handler Tests (Echo STS)](./README.md)
- [Spec 003: GStreamer Stream Worker](../../specs/003-gstreamer-stream-worker/spec.md)
- [Spec 016: WebSocket Audio Protocol](../../specs/016-websocket-audio-protocol.md)
- [Spec 008: TTS Module](../../specs/008-tts-module/spec.md)
