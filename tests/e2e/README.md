# End-to-End Tests

End-to-end tests for verifying Docker Compose service startup and inter-service communication.

## Overview

These tests verify:
- **MediaMTX startup**: Control API, metrics, RTMP/RTSP ports
- **media-service startup**: FastAPI health, hook endpoints
- **Service communication**: Docker network connectivity, environment variables
- **Complete workflows**: Simulated hook event delivery

## Prerequisites

1. **Docker and Docker Compose** installed
2. **Python 3.10+**
3. **Test dependencies** installed:
   ```bash
   pip install -r tests/e2e/requirements.txt
   ```

## Running E2E Tests

### Run all e2e tests:
```bash
pytest tests/e2e/ -m e2e
```

### Run specific test file:
```bash
pytest tests/e2e/test_mediamtx_startup.py -v
```

### Run excluding slow tests:
```bash
pytest tests/e2e/ -m "e2e and not slow"
```

### Run with detailed output:
```bash
pytest tests/e2e/ -v -s
```

## Test Structure

- `conftest.py` - Shared fixtures for Docker Compose lifecycle
- `test_mediamtx_startup.py` - MediaMTX service verification
- `test_media_service_startup.py` - FastAPI service verification
- `test_service_communication.py` - Inter-service communication

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
docker compose -f deploy/docker-compose.yml logs

# Verify Docker is running
docker ps
```

### Tests hang or timeout
- Increase timeout in `conftest.py` (default: 60s)
- Check if ports are already in use: `lsof -i :8080,9997,9998,1935,8554`

### Cleanup stuck containers
```bash
docker compose -f deploy/docker-compose.yml down -v
docker system prune -f
```

## CI/CD Integration

Add to your CI pipeline:
```yaml
- name: Run E2E Tests
  run: |
    pip install -r tests/e2e/requirements.txt
    pytest tests/e2e/ -m e2e --tb=short
```

## Test Coverage

Current e2e test coverage:
- ✅ MediaMTX startup and health
- ✅ MediaMTX ports accessibility
- ✅ MediaMTX Control API response time
- ✅ media-service startup and health
- ✅ media-service hook endpoints
- ✅ Service-to-service Docker network communication
- ✅ Environment variable configuration
- ✅ Service restart and reconnection
