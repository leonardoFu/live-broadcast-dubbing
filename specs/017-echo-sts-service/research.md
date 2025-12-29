# Research: Echo STS Service for E2E Testing

**Feature**: 017-echo-sts-service
**Date**: 2025-12-28
**Status**: Complete

## Overview

This document captures technology research and decisions for implementing the Echo STS Service, a protocol-compliant mock that fully implements the WebSocket Audio Fragment Protocol (spec 016) for E2E testing.

---

## Research Task 1: Socket.IO Server Library for Python

### Context

The Echo STS Service must act as a Socket.IO server, accepting connections from media-service stream workers and implementing the full WebSocket Audio Fragment Protocol.

### Decision

**Library**: python-socketio >= 5.0 (AsyncServer mode)

### Rationale

1. **Official Implementation**: python-socketio is maintained by Miguel Grinberg, the author of the Socket.IO protocol specification for Python
2. **AsyncServer Support**: Native async/await support with `socketio.AsyncServer`
3. **ASGI Integration**: First-class ASGI support via `socketio.ASGIApp` - works with uvicorn
4. **High Reputation**: Context7 reports 380 code snippets and High source reputation
5. **Protocol Compatibility**: Implements Socket.IO protocol v4, matching client expectations

### Alternatives Considered

| Alternative | Rejected Because |
|------------|------------------|
| Flask-SocketIO | Synchronous by default, requires greenlet for async |
| websockets (raw) | Not Socket.IO protocol - would require custom implementation |
| Socketify.py | Less mature, fewer examples, not Socket.IO protocol |

### Implementation Pattern

```python
import socketio

# Create async Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi')

# Wrap with ASGI app for uvicorn
app = socketio.ASGIApp(sio)

# Event handler with authentication
@sio.event
async def connect(sid, environ, auth):
    if not validate_api_key(auth.get('token')):
        raise ConnectionRefusedError('AUTH_FAILED')
    print(f'Client connected: {sid}')

@sio.event
async def disconnect(sid, reason):
    print(f'Client disconnected: {sid}, reason: {reason}')

# Custom event handler
@sio.on('stream:init')
async def handle_stream_init(sid, data):
    # Validate and respond
    await sio.emit('stream:ready', response_data, room=sid)
```

### Configuration

```python
# Socket.IO server configuration matching spec 016
sio = socketio.AsyncServer(
    async_mode='asgi',
    ping_interval=25,      # Ping every 25 seconds
    ping_timeout=10,       # Timeout after 10 seconds
    max_http_buffer_size=52428800,  # 50MB for large fragments
    cors_allowed_origins="*"  # For local testing
)
```

---

## Research Task 2: Async Event Handling Patterns

### Context

The echo service must handle multiple concurrent streams and maintain in-order fragment delivery while processing events asynchronously.

### Decision

**Pattern**: Per-session asyncio.Queue for fragment ordering

### Rationale

1. **Non-blocking**: Event handlers return immediately after queuing
2. **Order Preservation**: Queue ensures FIFO delivery per stream
3. **Concurrency**: Multiple streams handled independently
4. **Backpressure**: Queue depth can trigger backpressure events

### Implementation Pattern

```python
from asyncio import Queue
from dataclasses import dataclass, field

@dataclass
class StreamSession:
    """Per-stream session state."""
    stream_id: str
    session_id: str
    state: str = "initializing"  # initializing, active, paused, ending
    max_inflight: int = 3
    inflight_count: int = 0
    output_queue: Queue = field(default_factory=Queue)
    next_sequence_to_emit: int = 0
    pending_fragments: dict = field(default_factory=dict)
    statistics: dict = field(default_factory=lambda: {
        'total_fragments': 0,
        'success_count': 0,
        'failed_count': 0,
        'total_processing_time_ms': 0
    })

async def process_fragment(session: StreamSession, fragment: dict) -> dict:
    """Echo fragment back with mock metadata."""
    start_time = time.time()

    # Simulate configurable processing delay
    if session.processing_delay_ms > 0:
        await asyncio.sleep(session.processing_delay_ms / 1000)

    processing_time_ms = int((time.time() - start_time) * 1000)

    return {
        'fragment_id': fragment['fragment_id'],
        'stream_id': fragment['stream_id'],
        'sequence_number': fragment['sequence_number'],
        'status': 'success',
        'dubbed_audio': fragment['audio'],  # Echo back original
        'transcript': '[ECHO] Original audio',
        'translated_text': '[ECHO] Original audio',
        'processing_time_ms': processing_time_ms
    }
```

---

## Research Task 3: Authentication Implementation

### Context

The protocol requires API key authentication on connection handshake using the `auth.token` field.

### Decision

**Approach**: Connection-level authentication via connect event handler

### Rationale

1. **Early Rejection**: Invalid keys rejected before any events processed
2. **Spec Compliance**: Uses `auth.token` field as per spec 016
3. **Simple Implementation**: No middleware complexity
4. **Testable**: Easy to mock for unit tests

### Implementation Pattern

```python
from typing import Optional
import os

class AuthConfig:
    """Authentication configuration from environment."""

    def __init__(self):
        self.api_key = os.environ.get('STS_API_KEY', 'test-api-key')
        self.require_auth = os.environ.get('REQUIRE_AUTH', 'true').lower() == 'true'

    def validate_token(self, token: Optional[str]) -> bool:
        """Validate API key token."""
        if not self.require_auth:
            return True
        return token == self.api_key

auth_config = AuthConfig()

@sio.event
async def connect(sid, environ, auth):
    """Handle client connection with authentication."""
    token = auth.get('token') if auth else None

    if not auth_config.validate_token(token):
        raise ConnectionRefusedError({
            'code': 'AUTH_FAILED',
            'message': 'Invalid API key',
            'severity': 'fatal',
            'retryable': False
        })

    # Extract headers for logging
    stream_id = environ.get('HTTP_X_STREAM_ID', 'unknown')
    worker_id = environ.get('HTTP_X_WORKER_ID', 'unknown')

    print(f'Authenticated connection: sid={sid}, stream={stream_id}, worker={worker_id}')
```

---

## Research Task 4: Error Simulation via Socket.IO Event

### Context

Per clarification, error simulation should be configured via `config:error_simulation` Socket.IO event for maximum test flexibility.

### Decision

**Approach**: Dynamic error configuration per session via Socket.IO event

### Rationale

1. **Runtime Configuration**: No service restart needed
2. **Per-Test Isolation**: Each test can configure its own error scenarios
3. **Flexible Targeting**: Errors can target specific sequence numbers or fragment IDs
4. **Protocol Extension**: Uses `config:` namespace to separate from core protocol

### Implementation Pattern

```python
from pydantic import BaseModel
from typing import Optional, Literal

class ErrorSimulationRule(BaseModel):
    """Single error simulation rule."""
    trigger: Literal['sequence_number', 'fragment_id', 'nth_fragment']
    value: int | str  # Sequence number, fragment ID, or N
    error_code: str  # From spec 016: TIMEOUT, MODEL_ERROR, GPU_OOM, etc.
    retryable: bool = True

class ErrorSimulationConfig(BaseModel):
    """Error simulation configuration."""
    enabled: bool = False
    rules: list[ErrorSimulationRule] = []

@sio.on('config:error_simulation')
async def handle_error_simulation_config(sid, data):
    """Configure error simulation for the session."""
    session = get_session(sid)
    if not session:
        await sio.emit('error', {
            'code': 'STREAM_NOT_FOUND',
            'message': 'No active stream session'
        }, room=sid)
        return

    try:
        config = ErrorSimulationConfig.model_validate(data)
        session.error_simulation = config
        await sio.emit('config:error_simulation:ack', {
            'status': 'configured',
            'rules_count': len(config.rules)
        }, room=sid)
    except ValidationError as e:
        await sio.emit('error', {
            'code': 'INVALID_CONFIG',
            'message': str(e)
        }, room=sid)
```

---

## Research Task 5: In-Order Fragment Delivery

### Context

Spec 016 requires fragments to be delivered in sequence_number order, even if processed out of order.

### Decision

**Approach**: Output buffer with sequence tracking

### Rationale

1. **Decouples Processing from Delivery**: Fragments can process in parallel
2. **Simple Implementation**: Dict-based pending buffer with sequence counter
3. **Low Memory**: Only holds fragments until predecessors complete
4. **Spec Compliant**: Matches "output buffer" requirement in spec 016

### Implementation Pattern

```python
async def emit_in_order(session: StreamSession, processed: dict):
    """Emit processed fragments in sequence order."""
    sequence = processed['sequence_number']
    session.pending_fragments[sequence] = processed

    # Emit all consecutive fragments starting from next_sequence_to_emit
    while session.next_sequence_to_emit in session.pending_fragments:
        fragment = session.pending_fragments.pop(session.next_sequence_to_emit)
        await sio.emit('fragment:processed', fragment, room=session.sid)
        session.next_sequence_to_emit += 1
        session.inflight_count -= 1

        # Check if backpressure can be cleared
        if session.backpressure_active and session.inflight_count < session.backpressure_threshold:
            await emit_backpressure_clear(session)
```

---

## Research Task 6: Pydantic Models for Protocol Compliance

### Context

All Socket.IO event payloads must match the schemas defined in spec 016.

### Decision

**Approach**: Pydantic v2 models with strict validation

### Rationale

1. **Runtime Validation**: Catch malformed payloads immediately
2. **Documentation**: Models serve as schema documentation
3. **Type Safety**: IDE support and type checking
4. **Serialization**: Built-in JSON serialization

### Key Models

See `specs/017-echo-sts-service/data-model.md` for complete model definitions.

---

## Summary of Decisions

| Research Area | Decision | Key Benefit |
|--------------|----------|-------------|
| Socket.IO Library | python-socketio AsyncServer | Official implementation, ASGI support |
| Event Handling | Per-session asyncio.Queue | Non-blocking, order preservation |
| Authentication | Connect handler validation | Early rejection, spec compliance |
| Error Simulation | config:error_simulation event | Runtime flexibility, per-test isolation |
| Fragment Ordering | Output buffer with sequence tracking | Decoupled processing, spec compliance |
| Payload Validation | Pydantic v2 models | Runtime validation, type safety |

---

## Dependencies to Add

```toml
# apps/sts-service/pyproject.toml - add to dependencies
"python-socketio[asyncio]>=5.0",
```

---

## References

- [specs/016-websocket-audio-protocol.md](../016-websocket-audio-protocol.md) - Protocol specification
- [python-socketio Documentation](https://python-socketio.readthedocs.io/) - Library documentation
- [Context7 python-socketio](https://context7.com/miguelgrinberg/python-socketio) - Code examples
