# Quickstart: Echo STS Service

**Feature**: 017-echo-sts-service
**Date**: 2025-12-28

## Overview

The Echo STS Service is a mock Socket.IO server that implements the WebSocket Audio Fragment Protocol (spec 016) for E2E testing. It echoes audio fragments back without actual ASR/translation/TTS processing.

---

## Quick Setup

### 1. Install Dependencies

```bash
# From repository root - sets up all services
make setup

# Or manually with venv
python3.10 -m venv .venv
.venv/bin/pip install -e "apps/sts-service[dev]"
```

The pyproject.toml includes the required `python-socketio[asyncio]>=5.0` dependency.

### 2. Run the Echo Service

```bash
# Using Makefile (recommended)
make sts-echo

# Or with environment variables
export ECHO_PORT=8000
.venv/bin/python -m sts_service.echo

# Or activate venv first
source .venv/bin/activate
python -m sts_service.echo
```

**Note**: No authentication is required. The service accepts all connections without API keys or tokens.

Or with uvicorn directly:

```bash
.venv/bin/uvicorn sts_service.echo.server:app --host 0.0.0.0 --port 8000
```

### 3. Verify It's Running

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "sessions": 0}
```

---

## Docker Compose (E2E Testing)

The echo service is designed to run alongside media-service for E2E tests:

```yaml
# apps/sts-service/docker-compose.e2e.yml
version: '3.8'

services:
  echo-sts:
    build:
      context: .
      dockerfile: deploy/Dockerfile.echo
    ports:
      - "8000:8000"
    environment:
      - ECHO_PORT=8000
      - ECHO_PROCESSING_DELAY_MS=0
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      timeout: 3s
      retries: 3
```

---

## Client Connection Example

### Python (python-socketio)

```python
import socketio
import asyncio

async def main():
    # Create async client
    sio = socketio.AsyncClient()

    # Event handlers
    @sio.event
    async def connect():
        print("Connected to Echo STS Service")

    @sio.on('stream:ready')
    async def on_stream_ready(data):
        print(f"Stream ready: session_id={data['session_id']}")

    @sio.on('fragment:ack')
    async def on_fragment_ack(data):
        print(f"Fragment acknowledged: {data['fragment_id']}")

    @sio.on('fragment:processed')
    async def on_fragment_processed(data):
        print(f"Fragment processed: {data['fragment_id']}, status={data['status']}")
        # Echo service returns original audio in dubbed_audio
        if data['status'] == 'success':
            print(f"  Transcript: {data.get('transcript')}")
            print(f"  Processing time: {data['processing_time_ms']}ms")

    @sio.on('error')
    async def on_error(data):
        print(f"Error: {data['code']} - {data['message']}")

    @sio.event
    async def disconnect():
        print("Disconnected")

    # Connect (no authentication required)
    await sio.connect(
        'http://localhost:8000',
        headers={
            'X-Stream-ID': 'test-stream-001',
            'X-Worker-ID': 'worker-001'
        }
    )

    # Initialize stream
    await sio.emit('stream:init', {
        'stream_id': 'test-stream-001',
        'worker_id': 'worker-001',
        'config': {
            'source_language': 'en',
            'target_language': 'es',
            'voice_profile': 'default',
            'chunk_duration_ms': 1000,
            'sample_rate_hz': 48000,
            'channels': 1,
            'format': 'm4a'
        },
        'max_inflight': 3
    })

    # Wait for stream:ready
    await asyncio.sleep(0.5)

    # Send a test fragment
    import base64
    import time

    audio_data = b'\x00' * 96000  # Simulated M4A audio data (binary content for testing)
    await sio.emit('fragment:data', {
        'fragment_id': 'frag-001',
        'stream_id': 'test-stream-001',
        'sequence_number': 0,
        'timestamp': int(time.time() * 1000),
        'audio': {
            'format': 'm4a',
            'sample_rate_hz': 48000,
            'channels': 1,
            'duration_ms': 1000,
            'data_base64': base64.b64encode(audio_data).decode()
        }
    })

    # Wait for processing
    await asyncio.sleep(1)

    # End stream
    await sio.emit('stream:end', {
        'stream_id': 'test-stream-001',
        'reason': 'test_complete'
    })

    await asyncio.sleep(1)
    await sio.disconnect()

asyncio.run(main())
```

---

## Error Simulation

Configure error simulation to test worker error handling:

```python
# After stream:init, configure error simulation
await sio.emit('config:error_simulation', {
    'enabled': True,
    'rules': [
        {
            'trigger': 'sequence_number',
            'value': 5,
            'error_code': 'TIMEOUT',
            'error_message': 'Simulated timeout',
            'retryable': True
        },
        {
            'trigger': 'nth_fragment',
            'value': 10,
            'error_code': 'MODEL_ERROR',
            'error_message': 'Simulated TTS failure',
            'retryable': True,
            'stage': 'tts'
        }
    ]
})

# Wait for ack
@sio.on('config:error_simulation:ack')
async def on_error_sim_ack(data):
    print(f"Error simulation configured: {data['rules_count']} rules")
```

### Available Error Codes

| Code | Retryable | Use Case |
|------|-----------|----------|
| `TIMEOUT` | Yes | Test timeout retry logic |
| `MODEL_ERROR` | Yes | Test model failure recovery |
| `GPU_OOM` | Yes | Test OOM handling |
| `QUEUE_FULL` | Yes | Test backpressure response |
| `INVALID_SEQUENCE` | No | Test sequence validation |
| `STREAM_NOT_FOUND` | No | Test missing stream handling |

---

## Processing Delay Simulation

Simulate real STS latency:

```bash
# Environment variable
export PROCESSING_DELAY_MS=500  # 500ms delay per fragment

# Or via config event (per-session)
await sio.emit('config:processing_delay', {
    'delay_ms': 500
})
```

---

## Backpressure Testing

The echo service can simulate backpressure when configured:

```python
# Enable backpressure simulation
await sio.emit('config:backpressure', {
    'enabled': True,
    'threshold': 5,  # Trigger at 5 in-flight fragments
    'severity': 'high',
    'action': 'pause'
})

# Watch for backpressure events
@sio.on('backpressure')
async def on_backpressure(data):
    if data['action'] == 'pause':
        print("Received backpressure - pausing fragment sending")
    elif data['severity'] == 'low':
        print("Backpressure cleared - resuming")
```

---

## Health Check Endpoints

The echo service exposes HTTP endpoints for monitoring:

```bash
# Health check
curl http://localhost:8000/health
# {"status": "healthy", "sessions": 2, "uptime_seconds": 3600}

# Metrics (if prometheus enabled)
curl http://localhost:8000/metrics
```

---

## Running Tests

### Unit Tests

```bash
# Using Makefile (recommended)
make sts-test-unit

# Or directly
.venv/bin/python -m pytest apps/sts-service/tests/unit/echo/ -v
```

### E2E Tests

```bash
# Using Makefile
make sts-test-e2e

# Or directly
.venv/bin/python -m pytest apps/sts-service/tests/e2e/echo/ -v -m e2e
```

### With Coverage

```bash
# Using Makefile (80% threshold enforced)
make sts-test-coverage

# Or directly
.venv/bin/python -m pytest apps/sts-service/tests/ --cov=sts_service.echo --cov-report=html
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ECHO_HOST` | 0.0.0.0 | Server bind address |
| `ECHO_PORT` | 8000 | WebSocket server port |
| `ECHO_PROCESSING_DELAY_MS` | 0 | Default processing delay |
| `WS_MAX_CONNECTIONS` | 10 | Max concurrent connections |
| `WS_MAX_BUFFER_SIZE` | 52428800 | Max message size (50MB) |
| `WS_PING_INTERVAL` | 25 | Socket.IO ping interval (seconds) |
| `WS_PING_TIMEOUT` | 10 | Socket.IO ping timeout (seconds) |

**Note**: No authentication-related environment variables are needed as the service accepts all connections.

---

## Common Issues

### Connection Refused

```
socketio.exceptions.ConnectionError: Connection refused
```

**Solution**: Ensure the echo service is running and accessible on the configured port.

### Stream Not Found

```
{"code": "STREAM_NOT_FOUND", "message": "No active stream session"}
```

**Solution**: Send `stream:init` before sending fragments or configuration events.

---

## Next Steps

1. **Integration with media-service**: See `tests/e2e/` for full pipeline tests
2. **Custom error scenarios**: Use error simulation for edge case testing
3. **Performance testing**: Adjust `PROCESSING_DELAY_MS` to simulate real latency
