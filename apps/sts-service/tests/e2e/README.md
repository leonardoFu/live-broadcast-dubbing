# E2E Tests for Full STS Service

End-to-end tests for the Full STS Service, validating the complete ASR → Translation → TTS pipeline.

## Overview

These E2E tests validate:
- **Stream initialization** (`stream:init` → `stream:ready`)
- **Fragment processing** (ASR → Translation → TTS)
- **Backpressure monitoring** (in-flight fragment tracking)
- **Error handling** (malformed input, recovery)
- **Stream lifecycle** (`stream:end` → `stream:complete`)

## Prerequisites

### Required Software

1. **Docker with NVIDIA GPU support**
   ```bash
   # Install NVIDIA Docker runtime
   # https://github.com/NVIDIA/nvidia-docker
   ```

2. **NVIDIA GPU with CUDA 12.1+**
   - Required for ASR (faster-whisper) and TTS (Coqui TTS)
   - At least 8GB VRAM recommended

3. **DeepL API Key**
   - Sign up at https://www.deepl.com/pro-api
   - Or use the test key: `8e373354-4ca7-4fec-b563-93b2fa6930cc:fx`

4. **Python 3.10**
   ```bash
   python --version  # Should be 3.10.x
   ```

### Test Fixtures

Ensure test audio file exists:
```bash
ls -lh tests/fixtures/test-streams/1-min-nfl.m4a
# Should exist: 1-minute audio file with English speech
```

## Running E2E Tests

### Quick Start

```bash
# From repository root
cd apps/sts-service

# Run all E2E tests (starts Docker service automatically)
pytest tests/e2e/test_full_pipeline_e2e.py -v -s

# Or using marker
pytest -m e2e -v -s
```

### Running Specific Tests

```bash
# Stream initialization only
pytest tests/e2e/test_full_pipeline_e2e.py::test_stream_init_e2e -v -s

# Single fragment processing
pytest tests/e2e/test_full_pipeline_e2e.py::test_single_fragment_e2e -v -s

# Full minute pipeline (10 fragments)
pytest tests/e2e/test_full_pipeline_e2e.py::test_full_minute_pipeline_e2e -v -s

# Backpressure monitoring
pytest tests/e2e/test_full_pipeline_e2e.py::test_backpressure_monitoring_e2e -v -s

# Error handling
pytest tests/e2e/test_full_pipeline_e2e.py::test_error_handling_e2e -v -s
```

### Manual Service Management

If you want to keep the service running between tests:

```bash
# Start service manually
docker compose -f docker-compose.full.yml up -d

# Wait for health check
curl http://localhost:8000/health

# Run tests (without fixture starting/stopping service)
# Note: The fixture will still try to start the service, so this is mainly for debugging
pytest tests/e2e/test_full_pipeline_e2e.py -v -s --log-cli-level=DEBUG

# View logs
docker compose -f docker-compose.full.yml logs -f full-sts-service

# Stop service
docker compose -f docker-compose.full.yml down -v
```

## Test Descriptions

### 1. test_stream_init_e2e

**Purpose**: Validate stream initialization flow

**Steps**:
1. Connect Socket.IO client to service
2. Send `stream:init` event with configuration (en→es)
3. Wait for `stream:ready` event
4. Validate session_id, max_inflight, capabilities

**Expected Result**:
- `stream:ready` received within 10s
- Capabilities include: asr, translation, tts, duration_matching
- Session initialized successfully

**Duration**: ~5 seconds

---

### 2. test_single_fragment_e2e

**Purpose**: Validate single fragment processing

**Steps**:
1. Initialize stream
2. Send one 6-second audio fragment
3. Wait for `fragment:ack` (should be <50ms)
4. Wait for `fragment:processed` (should be <8s)
5. Validate transcript, translation, dubbed audio
6. Validate duration variance <10%

**Expected Result**:
- Ack latency < 50ms
- Processing latency < 8s
- Transcript contains English text
- Translation contains Spanish text
- Dubbed audio duration matches input ±10%

**Duration**: ~10 seconds

---

### 3. test_full_minute_pipeline_e2e

**Purpose**: Validate full pipeline with multiple fragments

**Steps**:
1. Initialize stream
2. Chunk 1-min-nfl.m4a into 10 x 6-second fragments
3. Send all fragments sequentially
4. Collect all `fragment:processed` events
5. Send `stream:end`
6. Wait for `stream:complete`
7. Validate all fragments succeeded

**Expected Result**:
- All 10 fragments process successfully
- Total latency < 10 minutes (60s audio + ~80s processing)
- `stream:complete` statistics match expectations

**Duration**: ~2-3 minutes (depending on GPU)

---

### 4. test_backpressure_monitoring_e2e

**Purpose**: Validate backpressure monitoring

**Steps**:
1. Initialize stream
2. Send 12 fragments rapidly (exceeds max_inflight=3)
3. Wait for `backpressure:state` events
4. Validate severity levels increase as in-flight grows
5. Validate backpressure decreases as fragments complete

**Expected Result**:
- Backpressure events emitted at thresholds:
  - in_flight 1-3 → severity=LOW
  - in_flight 4-6 → severity=MEDIUM
  - in_flight 7-10 → severity=HIGH
  - in_flight >10 → severity=CRITICAL (rejected)

**Duration**: ~2-3 minutes

---

### 5. test_error_handling_e2e

**Purpose**: Validate error handling and recovery

**Steps**:
1. Initialize stream
2. Send malformed fragment (invalid base64 audio)
3. Wait for error response
4. Send valid fragment
5. Validate valid fragment processes successfully

**Expected Result**:
- Malformed fragment returns error with stage, code, message
- Service recovers and processes valid fragment afterward

**Duration**: ~15 seconds

---

## Test Configuration

### Environment Variables

The E2E fixtures automatically set:
```bash
DEEPL_AUTH_KEY=8e373354-4ca7-4fec-b563-93b2fa6930cc:fx
LOG_LEVEL=INFO
ENABLE_ARTIFACT_LOGGING=true
```

To override, set environment variables before running tests:
```bash
export DEEPL_AUTH_KEY=your-real-key
export LOG_LEVEL=DEBUG
pytest -m e2e -v -s
```

### Timeouts

Configured in `test_full_pipeline_e2e.py`:
```python
CHUNK_DURATION_MS = 6000  # 6 seconds per chunk
FRAGMENT_PROCESSING_TIMEOUT = 15.0  # seconds (target <8s, but allow buffer)
STREAM_INIT_TIMEOUT = 10.0  # seconds
```

### Docker Compose

Uses `apps/sts-service/docker-compose.full.yml`:
- GPU support via NVIDIA Docker runtime
- Model caching via Docker volumes
- Health check endpoint: `/health`

## Troubleshooting

### Service fails to start

**Symptom**: `RuntimeError: Service did not become healthy within 120s`

**Solutions**:
```bash
# Check Docker logs
cd apps/sts-service
docker compose -f docker-compose.full.yml logs --tail=100

# Common issues:
# 1. GPU not available
nvidia-smi  # Verify GPU is detected

# 2. Out of memory
# Reduce model size in docker-compose.full.yml:
# ASR_MODEL_SIZE=small  (instead of medium)

# 3. DeepL API key invalid
# Set valid key:
export DEEPL_AUTH_KEY=your-real-key
```

### Tests timeout

**Symptom**: `TimeoutError: Timeout waiting for event 'fragment:processed'`

**Solutions**:
```bash
# Increase timeouts in test file
# Edit test_full_pipeline_e2e.py:
FRAGMENT_PROCESSING_TIMEOUT = 30.0  # Increase from 15.0

# Or check GPU utilization
nvidia-smi  # GPU should be near 100% during ASR/TTS
```

### No backpressure events

**Symptom**: `⚠ No backpressure events received`

**Explanation**: Fragments may process too quickly on powerful GPUs

**Solutions**:
- This is expected on fast GPUs
- Backpressure events are emitted when in_flight > thresholds
- If all fragments complete before queue builds up, no events are emitted
- This is not a test failure

### ffmpeg not found

**Symptom**: `RuntimeError: Failed to convert audio to PCM`

**Solutions**:
```bash
# Install ffmpeg
brew install ffmpeg  # macOS
sudo apt install ffmpeg  # Ubuntu

# Verify installation
ffmpeg -version
```

## Performance Benchmarks

Expected performance on **NVIDIA RTX 3090** (24GB VRAM):

| Test | Duration | Fragments | Latency per Fragment |
|------|----------|-----------|---------------------|
| test_stream_init_e2e | ~5s | 0 | N/A |
| test_single_fragment_e2e | ~10s | 1 | ~6-8s |
| test_full_minute_pipeline_e2e | ~2-3 min | 10 | ~6-8s |
| test_backpressure_monitoring_e2e | ~2-3 min | 12 | ~6-8s |
| test_error_handling_e2e | ~15s | 2 | ~6-8s |

**Total E2E Suite**: ~5-7 minutes

## Test Artifacts

### Logs

Service logs are dumped to console on failure:
```bash
# View logs manually
docker compose -f docker-compose.full.yml logs -f
```

### Artifacts

Enabled by `ENABLE_ARTIFACT_LOGGING=true`:
- Location: `apps/sts-service/artifacts/`
- Contains: Fragment audio files, transcripts, translations, dubbed audio
- Useful for debugging processing issues

### Coverage

E2E tests do not contribute to code coverage (they test the deployed service).

For coverage, run unit and integration tests:
```bash
pytest tests/unit/ tests/integration/ --cov=sts_service.full --cov-report=html
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          cd apps/sts-service
          pip install -e ".[dev]"

      - name: Run E2E tests
        env:
          DEEPL_AUTH_KEY: ${{ secrets.DEEPL_AUTH_KEY }}
        run: |
          cd apps/sts-service
          pytest -m e2e -v -s

      - name: Upload artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-artifacts
          path: apps/sts-service/artifacts/
```

## Next Steps

After E2E tests pass:

1. **Run full test suite**:
   ```bash
   pytest tests/ --cov=sts_service.full --cov-report=html
   ```

2. **Deploy to RunPod**:
   - Follow `specs/021-full-sts-service/quickstart.md`
   - Push Docker image to registry
   - Configure RunPod pod with GPU

3. **Integration with media-service**:
   - Test full pipeline with media-service E2E tests
   - Located in `tests/e2e/test_full_pipeline.py` (root level)

## Support

For issues or questions:
- Check logs: `docker compose -f docker-compose.full.yml logs -f`
- Review spec: `specs/021-full-sts-service/spec.md`
- Check troubleshooting section above
