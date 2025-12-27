# Stream Orchestration Service

HTTP service that receives MediaMTX hook events and manages stream worker lifecycle.

## Overview

The stream-orchestration service acts as the control plane for the live streaming pipeline:
- Receives hook events from MediaMTX when streams start/stop (runOnReady, runOnNotReady)
- Manages worker lifecycle for stream processing
- Provides observability through structured logging

## API Endpoints

### Hook Receiver Endpoints

**POST /v1/mediamtx/events/ready**
- Triggered when a stream becomes available in MediaMTX
- Payload: `{path, query, sourceType, sourceId}`
- Response: 200 OK

**POST /v1/mediamtx/events/not-ready**
- Triggered when a stream becomes unavailable in MediaMTX
- Payload: `{path, query, sourceType, sourceId}`
- Response: 200 OK

## Development

### Install dependencies

```bash
cd apps/stream-orchestration
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

### Run the service locally

```bash
uvicorn stream_orchestration.main:app --host 0.0.0.0 --port 8080 --reload
```

## Architecture

- FastAPI for HTTP endpoints
- Pydantic for request/response validation
- Structured logging with correlation fields
- Designed for containerized deployment

## Configuration

Environment variables:
- `PORT`: HTTP service port (default: 8080)
- `LOG_LEVEL`: Logging level (default: INFO)

## Testing

- Unit tests: `tests/unit/` - Test event parsing and business logic
- Contract tests: `tests/contract/` - Validate API schemas against contracts
- Integration tests: `tests/integration/` - Test HTTP endpoints with mock clients

Coverage requirement: 80% minimum
