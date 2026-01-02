# Quickstart: Dual Docker-Compose E2E Tests

**Feature**: 019-dual-docker-e2e-infrastructure
**Date**: 2026-01-01

This guide covers running dual docker-compose E2E tests locally and debugging common issues.

## Prerequisites

### System Requirements

- **Docker Engine**: 20.10+ (for `host.docker.internal` support on Linux)
- **Docker Compose**: v2.x
- **Python**: 3.10.x (per monorepo constitution)
- **ffmpeg**: 5.0+ (for stream publishing and inspection)
- **ffprobe**: 5.0+ (for stream analysis)
- **Disk Space**: 5GB minimum (for STS models: Whisper + TTS)
- **Memory**: 8GB RAM minimum (STS service requires 4GB+)
- **CPU**: 4 cores minimum (CPU-only STS processing is resource-intensive)

### Installation (macOS)

```bash
# Docker Desktop (includes Docker Engine + Compose)
brew install --cask docker

# ffmpeg (includes ffprobe)
brew install ffmpeg

# Python 3.10 (if not already installed)
brew install python@3.10
```

### Installation (Linux)

```bash
# Docker Engine + Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER  # Add user to docker group
newgrp docker  # Activate group without logout

# ffmpeg
sudo apt-get update
sudo apt-get install ffmpeg

# Python 3.10
sudo apt-get install python3.10 python3.10-venv
```

---

## Project Setup

### 1. Clone Repository and Install Dependencies

```bash
# Clone repository
cd /path/to/live-broadcast-dubbing-cloud

# Create virtual environment and install dependencies
make setup

# Install E2E test dependencies
source venv/bin/activate
pip install -r tests/e2e/requirements.txt
```

### 2. Verify Docker Compose Files

Ensure both docker-compose files exist:

```bash
# Media service composition
ls apps/media-service/docker-compose.e2e.yml

# STS service composition
ls apps/sts-service/docker-compose.e2e.yml

# If missing, create from templates (see spec.md for YAML structure)
```

### 3. Verify Test Fixture

Ensure test fixture exists:

```bash
ls tests/fixtures/test_streams/30s-counting-english.mp4
```

If missing, generate synthetic fixture:

```bash
# Option 1: Using espeak + ffmpeg
espeak "One, two, three, four, five, six, seven, eight, nine, ten, eleven, twelve, thirteen, fourteen, fifteen, sixteen, seventeen, eighteen, nineteen, twenty, twenty-one, twenty-two, twenty-three, twenty-four, twenty-five, twenty-six, twenty-seven, twenty-eight, twenty-nine, thirty" -w /tmp/counting.wav -s 30

ffmpeg -f lavfi -i testsrc=duration=30:size=1280x720:rate=30 -i /tmp/counting.wav -c:v libx264 -c:a aac -shortest tests/fixtures/test_streams/30s-counting-english.mp4
```

---

## Running E2E Tests

### Run All Dual-Compose E2E Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run full E2E test suite
pytest tests/e2e/ -v --tb=short

# Expected output:
# tests/e2e/test_dual_compose_full_pipeline.py::test_full_pipeline_media_to_sts_to_output PASSED
# tests/e2e/test_dual_compose_service_communication.py::test_services_can_communicate PASSED
# ...
# ===== 7 passed in 180.23s =====
```

### Run Specific Test File

```bash
# Run only full pipeline test
pytest tests/e2e/test_dual_compose_full_pipeline.py -v

# Run only service communication test
pytest tests/e2e/test_dual_compose_service_communication.py -v
```

### Run with Debug Logging

```bash
# Enable verbose logging
pytest tests/e2e/ -v -s --log-cli-level=DEBUG

# This will show:
# - Docker Compose startup logs
# - Service health check attempts
# - ffmpeg publishing output
# - Socket.IO event captures
# - Metrics parsing results
```

### Run with Test Coverage (optional)

```bash
# E2E tests don't require coverage, but helpers can be tested
pytest tests/e2e/helpers/ --cov=tests/e2e/helpers --cov-report=html
```

---

## Understanding Test Flow

### Session-Scoped Fixtures

E2E tests use session-scoped fixtures to amortize startup costs:

1. **Startup Phase** (runs once at session start):
   - Start `apps/media-service/docker-compose.e2e.yml` (MediaMTX + media-service)
   - Start `apps/sts-service/docker-compose.e2e.yml` (STS service)
   - Wait for health checks (60s timeout for STS model loading)
   - STS downloads Whisper + TTS models (~1GB, cached in Docker volume)

2. **Test Execution Phase** (each test):
   - Generate unique stream name (e.g., `test_pipeline_1735689600`)
   - Publish test fixture to unique RTSP URL
   - Execute test assertions
   - Cleanup ffmpeg process and stream

3. **Teardown Phase** (runs once at session end):
   - Stop both docker-compose environments
   - Remove volumes (model cache is preserved for next run)

### Timeline for First Run

- Docker Compose startup: 10-15s
- STS model download (first run only): 60-120s
- STS model loading: 30-40s
- Health checks: 5-10s
- Test execution (per test): 30-180s
- **Total first run**: ~5-8 minutes

### Timeline for Subsequent Runs

- Docker Compose startup: 10-15s
- STS model loading (from cache): 30-40s
- Health checks: 5-10s
- Test execution (per test): 30-180s
- **Total subsequent runs**: ~3-5 minutes

---

## Debugging Test Failures

### Check Docker Compose Status

```bash
# Check if services are running
docker-compose -f apps/media-service/docker-compose.e2e.yml -p e2e-media-019 ps
docker-compose -f apps/sts-service/docker-compose.e2e.yml -p e2e-sts-019 ps

# Expected output:
# NAME                STATUS              PORTS
# e2e-media-mediamtx  Up (healthy)        0.0.0.0:8554->8554/tcp, ...
# e2e-media-service   Up (healthy)        0.0.0.0:8080->8080/tcp
# e2e-sts-service     Up (healthy)        0.0.0.0:3000->3000/tcp
```

### Check Service Health

```bash
# MediaMTX health
curl http://localhost:9997/v3/paths/list

# Media service health
curl http://localhost:8080/health

# STS service health
curl http://localhost:3000/health
```

### View Container Logs

```bash
# Media service logs
docker-compose -f apps/media-service/docker-compose.e2e.yml -p e2e-media-019 logs media-service

# STS service logs
docker-compose -f apps/sts-service/docker-compose.e2e.yml -p e2e-sts-019 logs sts-service

# MediaMTX logs
docker-compose -f apps/media-service/docker-compose.e2e.yml -p e2e-media-019 logs mediamtx
```

### Test Specific Scenarios

```bash
# Test service communication only (fast)
pytest tests/e2e/test_dual_compose_service_communication.py::test_services_can_communicate -v

# Test fixture publishing only
pytest tests/e2e/test_dual_compose_fixture_management.py::test_publish_fixture_to_mediamtx -v

# Test real STS processing only
pytest tests/e2e/test_dual_compose_real_sts_processing.py::test_sts_processes_real_audio -v
```

### Inspect Metrics

```bash
# View Prometheus metrics
curl http://localhost:8080/metrics | grep worker_

# Expected output:
# worker_audio_fragments_total{status="sent"} 5.0
# worker_audio_fragments_total{status="processed"} 5.0
# worker_inflight_fragments 0.0
```

---

## Troubleshooting Common Issues

### Issue: Port Already in Use

**Symptom**:
```
Error: bind: address already in use (port 8554/1935/3000/8080)
```

**Solution**:
```bash
# Find process using port
lsof -i :8554
lsof -i :3000

# Kill process
kill -9 <PID>

# Or use different ports via environment variables
export MEDIAMTX_RTSP_PORT=8555
export STS_PORT=3001
pytest tests/e2e/ -v
```

### Issue: STS Service Unhealthy (Model Download Timeout)

**Symptom**:
```
AssertionError: STS service not healthy after 60s
```

**Solution**:
```bash
# Increase health check timeout
# Edit apps/sts-service/docker-compose.e2e.yml:
# healthcheck:
#   start_period: 120s  # Increase from 30s

# Or manually download models first
docker-compose -f apps/sts-service/docker-compose.e2e.yml -p e2e-sts-019 up -d
docker-compose -f apps/sts-service/docker-compose.e2e.yml -p e2e-sts-019 logs -f

# Wait for "Model loading complete" message
```

### Issue: Test Fixture Not Found

**Symptom**:
```
FileNotFoundError: tests/fixtures/test_streams/30s-counting-english.mp4
```

**Solution**:
```bash
# Create fixture directory
mkdir -p tests/fixtures/test_streams

# Generate synthetic fixture (see "Verify Test Fixture" section above)
```

### Issue: ffmpeg Process Not Cleaned Up

**Symptom**:
```
Multiple ffmpeg processes consuming CPU after tests
```

**Solution**:
```bash
# Kill all ffmpeg processes
pkill ffmpeg

# Tests should clean up automatically, but this is a fallback
```

### Issue: Docker Volume Fills Disk

**Symptom**:
```
No space left on device
```

**Solution**:
```bash
# Check Docker volume usage
docker system df

# Remove unused volumes
docker volume prune

# Remove specific E2E volumes
docker volume rm e2e-media-019_segments-data
docker volume rm e2e-sts-019_model-cache
```

### Issue: A/V Sync Assertion Fails

**Symptom**:
```
AssertionError: A/V sync delta 150ms > 120ms threshold
```

**Solution**:
```bash
# Check output stream with ffprobe
ffprobe -v quiet -show_packets -select_streams v:0 rtmp://localhost:1935/live/test_abc_123/out

# Review media-service logs for sync warnings
docker logs e2e-media-service 2>&1 | grep "sync"

# If consistently failing, may need to tune A/V sync logic in media-service
```

---

## Adding New E2E Tests

### Test Template

```python
# tests/e2e/test_dual_compose_my_feature.py
import pytest

@pytest.mark.asyncio
async def test_my_feature(dual_compose_env, publish_test_fixture):
    """Test description following spec user story."""
    # 1. Setup: Services already running (dual_compose_env)
    # 2. Arrange: Test fixture already publishing (publish_test_fixture)

    # 3. Act: Perform test actions
    # ...

    # 4. Assert: Validate expected behavior
    # ...

    # 5. Cleanup: Automatic via fixtures
```

### Running New Test

```bash
# Run new test
pytest tests/e2e/test_dual_compose_my_feature.py -v

# Debug with print statements
pytest tests/e2e/test_dual_compose_my_feature.py -v -s
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests (Dual Compose)

on: [push, pull_request]

jobs:
  e2e-dual-compose:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Compose
        run: docker-compose version

      - name: Set up Python 3.10
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r tests/e2e/requirements.txt

      - name: Install ffmpeg
        run: sudo apt-get install -y ffmpeg

      - name: Run E2E tests
        run: pytest tests/e2e/ -v --tb=short --timeout=600

      - name: Upload logs on failure
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-logs
          path: |
            /tmp/e2e-*.log
```

---

## Performance Tips

1. **Preserve Docker volumes**: Model cache (`model-cache`) persists between runs, saving 60-120s download time
2. **Use session-scoped fixtures**: Avoid restarting Docker Compose for each test
3. **Run P1 tests first**: Full pipeline tests cover most integration points
4. **Skip E2E in unit test runs**: Use pytest markers to separate unit and E2E tests

---

## Next Steps

- Review spec.md for detailed requirements
- Review data-model.md for test data structures
- Review contracts/ for environment variable schemas
- Run `/speckit.tasks` to generate implementation tasks
- Run `/speckit.checklist` to generate validation checklist
