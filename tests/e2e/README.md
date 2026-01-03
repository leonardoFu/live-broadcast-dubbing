# E2E Production Simulation Test

Single comprehensive E2E test that validates the complete live dubbing pipeline with real services in a production-like environment.

## Overview

**Test File**: [test_full_pipeline.py](test_full_pipeline.py)

This test simulates production conditions by running the full dubbing pipeline:
1. **Input**: Test fixture published to MediaMTX via RTMP
2. **Processing**: media-service ingests stream, segments audio, sends to real STS service
3. **STS**: Real ASR (Whisper), Translation, and TTS (Coqui) processing
4. **Output**: Dubbed audio merged back, published as RTMP stream

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    E2E Production Test                       │
│                  (test_full_pipeline.py)                     │
└───────────┬──────────────────────────────┬──────────────────┘
            │                              │
            │                              │
┌───────────▼──────────────┐   ┌──────────▼──────────────────┐
│  Media Service Stack     │   │   STS Service Stack         │
│  (docker-compose.e2e)    │   │   (docker-compose.e2e)      │
├──────────────────────────┤   ├─────────────────────────────┤
│  - MediaMTX              │   │  - Real STS Service         │
│  - media-service         │──▶│  - ASR (Whisper)            │
│  Port: 8080, 1935, 8889  │   │  - Translation (Google)     │
│                          │   │  - TTS (Coqui)              │
│  Network: e2e-media      │   │  Port: 3000                 │
│                          │   │  Network: e2e-sts           │
└──────────────────────────┘   └─────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose v2
- Python 3.10.x
- ffmpeg/ffprobe

### Install Dependencies

```bash
pip install pytest pytest-asyncio python-socketio[client] httpx
```

### Run Test

```bash
# Run the full pipeline test
pytest tests/e2e/test_full_pipeline.py::test_full_pipeline_media_to_sts_to_output -v -s

# Or use Makefile
make e2e-test-full
```

## Test Scenarios

### 1. Full Pipeline Test (P1)
**Function**: `test_full_pipeline_media_to_sts_to_output`

Validates complete dubbing pipeline:
- ✅ Stream publishing to MediaMTX
- ✅ WorkerRunner connection and processing
- ✅ Fragment processing through real STS (10 segments, 6s each)
- ✅ Dubbed audio in Socket.IO events
- ✅ Output RTMP stream validation
- ✅ A/V sync metrics (< 120ms delta)
- ✅ Prometheus metrics verification

**Expected Duration**: ~300 seconds (includes real STS latency)

### 2. Docker Compose Validation
**Function**: `test_docker_compose_files_exist`

Sanity check for required compose files.

### 3. Test Fixture Validation
**Function**: `test_test_fixture_exists`

Verifies test fixture properties (duration, codecs, sample rate).

## Test Infrastructure

### Fixtures ([conftest.py](conftest.py))

- `dual_compose_env`: Session-scoped Docker Compose manager for both services
- `publish_test_fixture`: Publishes test stream via RTMP
- `sts_monitor`: Socket.IO client monitoring STS events

### Helpers ([helpers/](helpers/))

- `docker_compose_manager.py`: Docker Compose lifecycle management
- `socketio_monitor.py`: Socket.IO event monitoring
- `stream_publisher.py`: RTMP stream publishing
- `metrics_parser.py`: Prometheus metrics parsing
- `stream_analyzer.py`: ffprobe-based stream analysis

### Configuration ([config.py](config.py))

Centralized test configuration for ports, URLs, and timeouts.

## Debugging

### View Logs

```bash
# Media service logs
docker compose -f apps/media-service/docker-compose.e2e.yml logs -f

# STS service logs
docker compose -f apps/sts-service/docker-compose.e2e.yml logs -f
```

### Check Service Health

```bash
# MediaMTX
curl http://localhost:8889/v3/paths/list

# Media Service
curl http://localhost:8080/metrics

# STS Service
curl http://localhost:3000/health
```

### Common Issues

**Test timeout waiting for fragments**
- Check STS service logs for processing errors
- Verify STS models loaded successfully (check startup logs)
- Increase timeout in test if needed for slower environments

**Output stream not available**
- Check media-service logs for RTMP publishing errors
- Verify MediaMTX is receiving the input stream
- Check network connectivity between services

**Port conflicts**
- Stop any running Docker containers on ports 1935, 8080, 8889, 3000
- Or configure custom ports in docker-compose.e2e.yml files

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Run E2E Production Test
  run: |
    pytest tests/e2e/test_full_pipeline.py -v --tb=short
  timeout-minutes: 10
```

## Related Documentation

- [Spec 021: Production E2E Testing](../../specs/021-production-e2e-testing/spec.md)
- [Media Service Docker Compose](../../apps/media-service/docker-compose.e2e.yml)
- [STS Service Docker Compose](../../apps/sts-service/docker-compose.e2e.yml)
