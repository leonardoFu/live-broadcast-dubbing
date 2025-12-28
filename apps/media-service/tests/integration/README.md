# Integration Tests

Integration tests for verifying media-service with MediaMTX via Docker Compose.

## Overview

These tests verify:
- **MediaMTX startup**: Control API, metrics, RTMP/RTSP ports
- **media-service startup**: FastAPI health, hook endpoints
- **Service communication**: Docker network connectivity, environment variables
- **Complete workflows**: Simulated hook event delivery, RTMP publish/playback

## Prerequisites

1. **Docker and Docker Compose** installed
2. **Python 3.10+**
3. **FFmpeg** installed (for stream tests)
4. **Test dependencies** installed:
   ```bash
   cd apps/media-service
   pip install -r requirements-dev.txt
   ```

## Running Integration Tests

### From project root:

```bash
# Run all integration tests
make media-test-integration

# Or directly with pytest
pytest apps/media-service/tests/integration/ -m integration
```

### Run specific test file:
```bash
pytest apps/media-service/tests/integration/test_mediamtx_startup.py -v
```

### Run excluding slow tests:
```bash
pytest apps/media-service/tests/integration/ -m "integration and not slow"
```

### Run with detailed output:
```bash
pytest apps/media-service/tests/integration/ -v -s
```

## Test Structure

- `conftest.py` - Shared fixtures for Docker Compose lifecycle
- `test_mediamtx_startup.py` - MediaMTX service verification
- `test_media_service_startup.py` - FastAPI service verification
- `test_service_communication.py` - Inter-service communication
- `test_rtmp_publish_hook.py` - RTMP publish → hook delivery flow
- `test_observability.py` - Control API & Prometheus metrics
- `test_publish_and_playback.py` - Stream publish and RTSP playback

## How It Works

1. **Session Setup** (`docker_services` fixture):
   - Runs `docker compose up -d --build`
   - Waits for services to be healthy (max 60s)
   - Verifies health endpoints respond

2. **Test Execution**:
   - Tests run against live Docker containers
   - HTTP clients make requests to `localhost` ports
   - Container introspection via `docker exec` commands

3. **Session Teardown**:
   - Runs `docker compose down -v`
   - Removes containers and volumes
   - Cleans up Docker resources

## Performance Expectations

Based on spec requirements:
- **SC-001**: Services start within 30 seconds
- **SC-006**: Control API responds within 100ms
- **SC-007**: Prometheus metrics respond within 100ms

## Troubleshooting

### Services fail to start
```bash
# Check Docker logs
docker compose -f apps/media-service/docker-compose.yml logs

# Or from apps/media-service directory:
docker compose logs

# Verify Docker is running
docker ps
```

### Tests hang or timeout
- Increase timeout in `conftest.py` (default: 60s)
- Check if ports are already in use: `lsof -i :8080,9997,9998,1935,8554`

### Cleanup stuck containers
```bash
docker compose -f apps/media-service/docker-compose.yml down -v
docker system prune -f
```

## Test Coverage

Current integration test coverage:
- ✅ MediaMTX startup and health
- ✅ MediaMTX ports accessibility
- ✅ MediaMTX Control API response time
- ✅ media-service startup and health
- ✅ media-service hook endpoints
- ✅ Service-to-service Docker network communication
- ✅ Environment variable configuration
- ✅ Service restart and reconnection
- ✅ RTMP publish triggers ready hook
- ✅ RTMP disconnect triggers not-ready hook
- ✅ Stream observability via Control API and metrics
- ✅ RTSP playback verification
