# E2E Test Suite Quickstart Guide

**Feature**: 018-e2e-stream-handler-tests
**Date**: 2025-12-30

This guide explains how to run, debug, and extend the E2E test suite for WorkerRunner + MediaMTX + Echo STS integration.

## Prerequisites

### Required Tools

1. **Docker Engine** (20.10+)
   ```bash
   docker --version
   # Docker version 20.10.0 or later
   ```

2. **Docker Compose** (v2.0+)
   ```bash
   docker-compose --version
   # Docker Compose version v2.0.0 or later
   ```

3. **ffmpeg** (with RTSP support)
   ```bash
   ffmpeg -version
   # ffmpeg version 4.4 or later
   ```

4. **Python 3.10.x** (per constitution)
   ```bash
   python --version
   # Python 3.10.x
   ```

5. **pytest** (with required plugins)
   ```bash
   pip install pytest pytest-asyncio python-socketio[client] prometheus_client
   ```

### Test Fixture

Ensure the test fixture exists at:
```bash
tests/e2e/fixtures/test-streams/1-min-nfl.mp4
```

If missing, download or generate:
```bash
# Option 1: Download Big Buck Bunny 60s clip
curl -o tests/e2e/fixtures/test-streams/1-min-nfl.mp4 \
  https://test-videos.co.uk/bigbuckbunny/mp4-h264/720/Big_Buck_Bunny_720_10s_1MB.mp4

# Option 2: Generate synthetic fixture
ffmpeg -f lavfi -i testsrc=duration=60:size=1280x720:rate=30 \
       -f lavfi -i sine=frequency=440:duration=60:sample_rate=48000 \
       -c:v libx264 -preset fast -crf 22 \
       -c:a aac -b:a 128k \
       tests/e2e/fixtures/test-streams/1-min-synthetic.mp4
```

Verify fixture properties:
```bash
ffprobe -v quiet -print_format json -show_format -show_streams \
  tests/e2e/fixtures/test-streams/1-min-nfl.mp4
```

Expected output:
- Duration: ~60 seconds
- Video codec: h264, 1280x720, 30fps
- Audio codec: aac, 48kHz, stereo

---

## Running E2E Tests

### Run All Tests

From repository root:

```bash
# Run all E2E tests
pytest tests/e2e/ -v --log-cli-level=INFO

# Run with more verbose output
pytest tests/e2e/ -vv -s --log-cli-level=DEBUG
```

Expected output:
```
tests/e2e/test_full_pipeline.py::test_full_pipeline_rtsp_to_rtmp PASSED
tests/e2e/test_av_sync.py::test_av_sync_within_threshold PASSED
tests/e2e/test_circuit_breaker.py::test_circuit_breaker_opens_on_sts_failures PASSED
tests/e2e/test_backpressure.py::test_worker_respects_backpressure PASSED
tests/e2e/test_fragment_tracker.py::test_fragment_tracker_respects_max_inflight PASSED
tests/e2e/test_reconnection.py::test_worker_reconnects_after_sts_disconnect PASSED

======================== 6 passed in 450.23s ========================
```

### Run Specific Test Suite

```bash
# Run only P1 tests (full pipeline, A/V sync)
pytest tests/e2e/test_full_pipeline.py tests/e2e/test_av_sync.py -v

# Run only circuit breaker tests
pytest tests/e2e/test_circuit_breaker.py -v

# Run only reconnection tests
pytest tests/e2e/test_reconnection.py -v
```

### Run Specific Test Case

```bash
# Run single test function
pytest tests/e2e/test_full_pipeline.py::test_full_pipeline_rtsp_to_rtmp -v
```

---

## Test Execution Flow

### 1. Environment Setup (Automatic)

When tests start, `conftest.py` session fixture:
1. Starts Docker Compose services (MediaMTX, media-service, echo-sts)
2. Waits for health checks (RTSP ready, STS ready, metrics endpoint ready)
3. Returns control to tests

```python
# Happens automatically in conftest.py
@pytest.fixture(scope="session")
def docker_services():
    # Start services
    subprocess.run(["docker-compose", "-f", "tests/e2e/docker-compose.yml", "up", "-d"])
    # Wait for health checks
    wait_for_services()
    yield
    # Cleanup
    subprocess.run(["docker-compose", "-f", "tests/e2e/docker-compose.yml", "down", "-v"])
```

### 2. Stream Publishing (Per Test)

Each test that needs input stream uses `stream_publisher` fixture:

```python
@pytest.fixture
def stream_publisher(docker_services):
    publisher = StreamPublisher(
        fixture_path="tests/e2e/fixtures/test-streams/1-min-nfl.mp4",
        rtsp_url="rtsp://localhost:8554/live/test/in"
    )
    publisher.start()
    time.sleep(2)  # Wait for stream to be ready
    yield publisher
    publisher.stop()
```

### 3. Test Execution

Test runs, interacts with services, and asserts expected behavior:

```python
def test_full_pipeline_rtsp_to_rtmp(docker_services, stream_publisher):
    # Wait for pipeline to complete (60s fixture + processing time)
    time.sleep(90)

    # Assert metrics
    metrics = MetricsClient("http://localhost:8000/metrics")
    fragments_total = metrics.get_counter("worker_audio_fragments_total")
    assert fragments_total == 10  # 60s / 6s = 10 segments

    # Assert output stream exists
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "rtmp://localhost:1935/live/test/out"
    ], timeout=5)
    assert result.returncode == 0  # Stream is playable
```

### 4. Cleanup (Automatic)

After all tests complete, `docker_services` fixture teardown:
1. Stops all services
2. Removes containers
3. Cleans up volumes

---

## Debugging Test Failures

### Check Service Logs

If a test fails, check container logs:

```bash
# View media-service logs
docker-compose -f tests/e2e/docker-compose.yml logs media-service

# View Echo STS logs
docker-compose -f tests/e2e/docker-compose.yml logs echo-sts

# View MediaMTX logs
docker-compose -f tests/e2e/docker-compose.yml logs mediamtx

# Follow logs in real-time
docker-compose -f tests/e2e/docker-compose.yml logs -f media-service
```

### Check Service Health

Verify services are running and healthy:

```bash
# List running containers
docker-compose -f tests/e2e/docker-compose.yml ps

# Check RTSP stream availability
ffprobe -v quiet rtsp://localhost:8554/live/test/in

# Check Echo STS health
curl http://localhost:8080/health

# Check metrics endpoint
curl http://localhost:8000/metrics
```

### Inspect Network

Verify Docker network is configured correctly:

```bash
# List networks
docker network ls | grep e2e

# Inspect network
docker network inspect e2e-test-network
```

### Manual Service Interaction

Start services manually for debugging:

```bash
# Start services
docker-compose -f tests/e2e/docker-compose.yml up

# In another terminal, publish test stream
ffmpeg -re -stream_loop -1 \
  -i tests/e2e/fixtures/test-streams/1-min-nfl.mp4 \
  -c copy -f rtsp \
  rtsp://localhost:8554/live/test/in

# In another terminal, play output stream
ffplay rtmp://localhost:1935/live/test/out

# Query metrics
curl http://localhost:8000/metrics | grep worker_
```

### Enable Debug Logging

Run tests with debug logging:

```bash
# Pytest debug logging
pytest tests/e2e/ -vv -s --log-cli-level=DEBUG

# Docker Compose debug logs
docker-compose -f tests/e2e/docker-compose.yml logs -f --tail=100
```

---

## Common Issues & Solutions

### Issue: "Services did not become healthy in time"

**Cause**: Docker Compose services failed to start or health checks failed.

**Solution**:
1. Check service logs: `docker-compose -f tests/e2e/docker-compose.yml logs`
2. Verify Docker has sufficient resources (2 CPU cores, 4GB RAM)
3. Increase health check timeout in conftest.py (default: 30s)
4. Manually test service startup: `docker-compose up`

### Issue: "Test fixture not found"

**Cause**: 1-min-nfl.mp4 is missing or has wrong path.

**Solution**:
```bash
# Verify fixture exists
ls -lh tests/e2e/fixtures/test-streams/1-min-nfl.mp4

# Re-download or regenerate
# (See "Test Fixture" section above)
```

### Issue: "RTMP output stream not available"

**Cause**: WorkerRunner failed to publish to MediaMTX RTMP endpoint.

**Solution**:
1. Check media-service logs for errors
2. Verify MediaMTX RTMP port is accessible: `telnet localhost 1935`
3. Check if input stream is being ingested: `ffprobe rtsp://localhost:8554/live/test/in`
4. Check circuit breaker state (may be open if STS failures occurred)

### Issue: "A/V sync test fails"

**Cause**: Sync delta exceeds 120ms threshold.

**Solution**:
1. Check A/V sync metrics: `curl http://localhost:8000/metrics | grep av_sync`
2. Review media-service logs for sync warnings
3. Verify test fixture has valid audio/video tracks
4. Increase threshold tolerance if environment is slow (not recommended for production)

### Issue: "Reconnection test hangs"

**Cause**: Echo STS did not disconnect, or reconnection logic failed.

**Solution**:
1. Verify Echo STS supports `simulate:disconnect` event
2. Check Echo STS logs for disconnect event
3. Check media-service logs for reconnection attempts
4. Manually trigger disconnect and verify reconnection

---

## Adding New E2E Tests

### 1. Create Test File

```bash
touch tests/e2e/test_new_scenario.py
```

### 2. Use Standard Fixtures

```python
# tests/e2e/test_new_scenario.py
import pytest
from helpers.metrics_parser import MetricsClient

def test_new_scenario(docker_services, stream_publisher):
    """Test description following spec user story."""

    # Wait for expected behavior
    import time
    time.sleep(30)

    # Assert expected state
    metrics = MetricsClient("http://localhost:8000/metrics")
    some_metric = metrics.get_counter("worker_some_metric_total")
    assert some_metric > 0

    # Add more assertions...
```

### 3. Run New Test

```bash
pytest tests/e2e/test_new_scenario.py -v
```

### 4. Add to CI Pipeline

Update `.github/workflows/e2e-tests.yml` (or equivalent) to include new test.

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  e2e:
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
          pip install pytest pytest-asyncio python-socketio[client] prometheus_client

      - name: Install ffmpeg
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg

      - name: Download test fixture
        run: |
          mkdir -p tests/e2e/fixtures/test-streams
          # Download or generate fixture here

      - name: Run E2E tests
        run: |
          pytest tests/e2e/ -v --log-cli-level=INFO --maxfail=1

      - name: Upload logs on failure
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: docker-logs
          path: |
            /tmp/e2e-logs/
```

### Local Pre-Push Validation

```bash
# Run E2E tests before pushing
./scripts/pre-push-e2e.sh

# Script contents:
#!/bin/bash
set -e

echo "Running E2E tests..."
pytest tests/e2e/ -v --log-cli-level=INFO

echo "E2E tests passed! Safe to push."
```

---

## Performance Benchmarks

Expected test execution times (on 2 CPU, 4GB RAM environment):

| Test Suite | Duration | Notes |
|------------|----------|-------|
| test_full_pipeline.py | ~90s | 60s fixture + 30s processing |
| test_av_sync.py | ~90s | Same as full pipeline |
| test_circuit_breaker.py | ~45s | Shorter due to early failure |
| test_backpressure.py | ~60s | Includes pause/resume cycles |
| test_fragment_tracker.py | ~60s | Standard pipeline duration |
| test_reconnection.py | ~50s | Includes reconnection backoff |
| **Total** | **~8 minutes** | Parallel execution not supported |

Tips for faster execution:
- Use shorter test fixtures for development (e.g., 10s instead of 60s)
- Run specific test suites instead of full suite
- Use pytest-xdist for parallel execution (if tests are independent)

---

## Troubleshooting Checklist

Before opening an issue, verify:

- [ ] Docker and Docker Compose are installed and running
- [ ] Test fixture exists and has correct properties (60s, H.264, AAC)
- [ ] All services start successfully: `docker-compose up`
- [ ] RTSP endpoint is accessible: `ffprobe rtsp://localhost:8554/live/test/in`
- [ ] Echo STS is accessible: `curl http://localhost:8080/health`
- [ ] Metrics endpoint is accessible: `curl http://localhost:8000/metrics`
- [ ] Python dependencies are installed: `pip list | grep pytest`
- [ ] Sufficient system resources (2+ CPU cores, 4GB+ RAM)
- [ ] No port conflicts (8554, 1935, 8080, 8000 are free)

If all checks pass and tests still fail, capture logs and open an issue with:
1. Test command that failed
2. Full pytest output
3. Docker service logs (`docker-compose logs`)
4. System info (OS, Docker version, Python version)

---

## Next Steps

- Review spec.md for test scenarios and acceptance criteria
- Review data-model.md for test fixture and entity definitions
- Review contracts/sts-simulate-disconnect.json for Echo STS enhancement
- Run /speckit.tasks to generate implementation tasks
- Run /speckit.checklist to generate validation checklist
