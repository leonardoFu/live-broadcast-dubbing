# Dual Docker-Compose E2E Test Infrastructure

**Status**: Draft
**Feature Branch**: `019-dual-docker-e2e-infrastructure`
**Related Specs**: [018-e2e-stream-handler-tests](../018-e2e-stream-handler-tests/), [017-echo-sts-service](../017-echo-sts-service/)

## Overview

This specification defines E2E test infrastructure using **two separate docker-compose configurations** to test the full live dubbing pipeline with **real services** (no mocking).

### Key Differences from Spec 018

| Aspect | Spec 018 (Echo STS) | Spec 019 (Dual Compose) |
|--------|---------------------|-------------------------|
| **STS Service** | Echo STS (mocked, instant response) | Real STS (ASR + Translation + TTS) |
| **Composition** | Single docker-compose | Two separate docker-compose files |
| **Networking** | Shared Docker network | Port exposure to host (localhost) |
| **Speed** | Fast (<90s for 60s video) | Slower (<180s for 30s video) |
| **Purpose** | Fast CI tests, integration validation | True E2E validation, real processing |
| **Coverage** | Protocol compliance, worker logic | Full pipeline correctness, real ML models |

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Host (localhost)                                               │
│                                                                 │
│  ┌──────────────────────────────┐  ┌─────────────────────────┐ │
│  │  Media Service Composition   │  │  STS Service Composition│ │
│  │  (docker-compose.e2e.yml)    │  │  (docker-compose.e2e.yml)│ │
│  │                              │  │                         │ │
│  │  ┌─────────┐  ┌────────────┐ │  │  ┌────────────────────┐ │ │
│  │  │MediaMTX │  │media-service│ │  │  │   sts-service      │ │ │
│  │  │         │  │            │ │  │  │  ┌──────────────┐  │ │ │
│  │  │ :8554   │◄─┤ WorkerRunner│ │  │  │  │ ASR (Whisper)│  │ │ │
│  │  │ :1935   │  │            │ │  │  │  └──────┬───────┘  │ │ │
│  │  └─────────┘  └────────┬───┘ │  │  │         │          │ │ │
│  │                        │     │  │  │  ┌──────▼────────┐ │ │ │
│  │                        │     │  │  │  │ Translation   │ │ │ │
│  │                        │     │  │  │  └──────┬────────┘ │ │ │
│  │                        │     │  │  │         │          │ │ │
│  │                        │     │  │  │  ┌──────▼────────┐ │ │ │
│  │                        │     │  │  │  │ TTS (Coqui)   │ │ │ │
│  │                        │     │  │  │  └───────────────┘ │ │ │
│  │                        │     │  │  │         :3000      │ │ │
│  │                        └─────┼──┼──┼─────────┘          │ │ │
│  │                              │  │  │  (Socket.IO)       │ │ │
│  └──────────────────────────────┘  └─────────────────────────┘ │
│                                                                 │
│  Communication: localhost:3000 (STS), localhost:8554/1935 (MTX)│
└─────────────────────────────────────────────────────────────────┘
```

## Usage

### Starting Services Manually

```bash
# Terminal 1: Start media-service + MediaMTX
cd apps/media-service
docker compose -f docker-compose.e2e.yml up

# Terminal 2: Start sts-service
cd apps/sts-service
docker compose -f docker-compose.e2e.yml up

# Terminal 3: Run tests
pytest tests/e2e/test_dual_compose_*.py -v
```

### Running Tests (Automated)

```bash
# Pytest fixtures handle docker-compose lifecycle
pytest tests/e2e/test_dual_compose_full_pipeline.py -v

# With custom ports (avoid conflicts)
STS_PORT=3001 MEDIAMTX_RTSP_PORT=8555 pytest tests/e2e/ -v
```

## Test Fixtures

### Primary Fixture: `30s-english-speech.mp4`

- **Duration**: 30 seconds (5 segments @ 6s each)
- **Video**: H.264, 1280x720, 30fps
- **Audio**: AAC, 48kHz stereo, clear English speech
- **Content**: Scripted speech with known text for transcript validation
- **Location**: `tests/fixtures/test-streams/30s-english-speech.mp4`

### Why 30 Seconds?

- **Fast enough**: <3 minutes total test time including real STS processing
- **Comprehensive**: 5 segments validate multi-fragment processing, A/V sync over time
- **Realistic**: Enough audio content for meaningful ASR, translation, TTS validation
- **CI-friendly**: Fits within typical CI timeout constraints

## Service Endpoints

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| MediaMTX RTSP | 8554 | `rtsp://localhost:8554` | RTSP input stream |
| MediaMTX RTMP | 1935 | `rtmp://localhost:1935` | RTMP output stream |
| MediaMTX API | 9997 | `http://localhost:9997` | Health check, stream list |
| Media Service | 8080 | `http://localhost:8080` | Metrics, health check |
| STS Service | 3000 | `http://localhost:3000` | Socket.IO fragment processing |

All ports are configurable via environment variables.

## Success Validation

### What the Tests Validate

1. **Real Processing**: Actual Whisper ASR → Google Translate → Coqui TTS pipeline
2. **Transcript Accuracy**: Output transcript matches expected English text from fixture
3. **Translation Correctness**: Output translation is valid Spanish (not gibberish)
4. **Dubbed Audio**: Output stream contains Spanish TTS audio, not original English
5. **A/V Sync**: Sync delta remains <120ms throughout 30-second stream
6. **Output Playability**: RTMP stream is valid and playable via ffprobe
7. **Service Communication**: Media-service successfully communicates with STS via localhost:3000

### What Success Looks Like

```bash
# Test output
test_dual_compose_full_pipeline.py::test_full_pipeline PASSED [100%]

# Assertions passed:
✓ All 5 segments processed successfully
✓ Transcripts show English text matching fixture script
✓ Translations show Spanish text
✓ Output stream duration: 30.2s (within tolerance)
✓ A/V sync delta: max 87ms, avg 43ms (well under 120ms threshold)
✓ Output audio codec: AAC (dubbed), not original
✓ Total test time: 156 seconds
```

## Troubleshooting

### Port Conflicts

```bash
# Check if ports are in use
lsof -i :3000  # STS service
lsof -i :8554  # MediaMTX RTSP
lsof -i :1935  # MediaMTX RTMP

# Use custom ports
STS_PORT=3001 MEDIAMTX_RTSP_PORT=8555 MEDIAMTX_RTMP_PORT=1936 \
  pytest tests/e2e/ -v
```

### Service Not Reachable

```bash
# Check health endpoints
curl http://localhost:8080/health  # Media service
curl http://localhost:3000/health  # STS service
wget -qO- http://localhost:9997/v3/paths/list  # MediaMTX

# Check docker-compose logs
docker compose -f apps/media-service/docker-compose.e2e.yml logs
docker compose -f apps/sts-service/docker-compose.e2e.yml logs
```

### Model Download Issues

```bash
# Pre-download models before tests
docker compose -f apps/sts-service/docker-compose.e2e.yml run --rm sts-service \
  python -c "from TTS.api import TTS; TTS('tts_models/en/ljspeech/tacotron2-DDC')"

# Check model cache volume
docker volume inspect sts-service_model-cache
```

## Comparison with Spec 018

### When to Use Spec 018 (Echo STS)

- **Fast iteration**: Developing worker logic, testing protocol compliance
- **CI pipeline**: Every commit, PR validation
- **Unit/integration tests**: Testing individual components
- **No GPU available**: Local development on laptops

### When to Use Spec 019 (Dual Compose)

- **Release validation**: Before deploying to production
- **Integration bugs**: Debugging issues that only appear with real STS
- **Model updates**: Validating new ASR/TTS model versions
- **End-to-end confidence**: Ensuring the full pipeline works correctly

### Recommendation

Use **both**:
1. Run spec 018 tests on every commit (fast feedback)
2. Run spec 019 tests nightly or pre-release (comprehensive validation)

## Next Steps

1. **Implement docker-compose files**: Create `docker-compose.e2e.yml` in both services
2. **Create test fixtures**: Generate 30s English speech video with known content
3. **Implement pytest fixtures**: Docker lifecycle management, fixture publishing
4. **Implement E2E tests**: Full pipeline test, output validation tests
5. **CI integration**: Add nightly job for dual-compose tests
