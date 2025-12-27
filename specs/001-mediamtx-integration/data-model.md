# Data Model: MediaMTX Integration

**Feature**: 001-mediamtx-integration
**Created**: 2025-12-27
**Source**: Extracted from plan.md Phase 1 design artifacts

## Overview

The data model for this feature focuses on stream paths and hook events in the MediaMTX integration layer.

## Entities

### 1. Stream Path Entity

Represents a unique stream location in MediaMTX.

**Attributes:**
- `path` (string, e.g., "live/stream123/in") - The MediaMTX path identifier
- `state` (enum: ready/not-ready) - Current availability state
- `source_type` (enum: rtmp/rtsp/webrtc) - Source protocol type
- `source_id` (string) - Unique identifier for the source connection
- `creation_time` (datetime) - When the path was first created

**Relationships:**
- `readers` (List[Reader]) - Clients reading from this path
- `hook_events` (List[HookEvent]) - State change events for this path

**Validation:**
- Path must match pattern `live/<streamId>/(in|out)`
- streamId: alphanumeric, hyphens, underscores only

### 2. Hook Event Entity

Represents a state change notification from MediaMTX to the media-service service.

**Attributes:**
- `event_type` (enum: ready/not-ready) - Type of state change
- `path` (string) - Stream path that changed state
- `query` (string, optional) - Query string from RTMP URL (e.g., "lang=es")
- `source_type` (string) - Source protocol (rtmp, rtsp, webrtc)
- `source_id` (string) - Unique identifier for the source connection
- `timestamp` (datetime) - When the event occurred
- `correlation_id` (UUID) - For tracing across services

**Relationships:**
- `stream_path` (StreamPath) - The stream that triggered this event

**Validation:**
- MUST include: path, source_type, source_id
- Optional: query, timestamp
- Event delivery target: <1 second from state change

### 3. Stream Worker Entity

**Note**: Placeholder for future implementation. Worker lifecycle management is out of scope for this feature (see specs/011-media-service.md).

**Attributes:**
- `stream_id` (string) - Identifier extracted from stream path
- `input_url` (string) - RTSP URL for reading source (e.g., "rtsp://mediamtx:8554/live/stream123/in")
- `output_url` (string) - RTMP URL for publishing processed output (e.g., "rtmp://mediamtx:1935/live/stream123/out")
- `state` (enum: starting/running/stopping/stopped) - Worker lifecycle state
- `start_time` (datetime) - When the worker was started

**Relationships:**
- `stream_path` (StreamPath) - The stream being processed
- `hook_events` (List[HookEvent]) - Events that triggered worker actions

### 4. Stream-Orchestration Service Entity

Represents the HTTP service that receives hook events from MediaMTX and manages worker lifecycle.

**Attributes:**
- `endpoint_url` (string, e.g., "http://media-service:8080") - Service base URL
- `hook_receiver_endpoints` (List[string]) - Available hook endpoints:
  - `/v1/mediamtx/events/ready`
  - `/v1/mediamtx/events/not-ready`

**Relationships:**
- `received_events` (List[HookEvent]) - All hook events received

**Validation:**
- Endpoint URL must be accessible from MediaMTX container network
- Service must be reachable before MediaMTX starts accepting streams

## Path Naming Conventions

### Ingest Paths
Format: `live/<streamId>/in`

Example: `live/broadcast-123/in`

**Used for:**
- RTMP publish from external encoders
- RTSP read by stream workers

### Output Paths
Format: `live/<streamId>/out`

Example: `live/broadcast-123/out`

**Used for:**
- RTMP publish from stream workers (processed output)
- RTSP/HLS read by downstream consumers

## URL Construction

### RTSP Read URL
```
rtsp://mediamtx:8554/<path>?protocols=tcp
```

Example:
```
rtsp://mediamtx:8554/live/broadcast-123/in?protocols=tcp
```

**Why TCP**: Avoids UDP packet loss in containerized environments

### RTMP Publish URL
```
rtmp://mediamtx:1935/<path>
```

Example:
```
rtmp://mediamtx:1935/live/broadcast-123/out
```

## State Transitions

### Stream Path Lifecycle

```
[No Path]
    ↓ (RTMP publish begins)
[Path Created, state=ready] → Hook: runOnReady fired
    ↓ (RTMP publish ends)
[Path state=not-ready] → Hook: runOnNotReady fired
    ↓ (Timeout or manual cleanup)
[Path Removed]
```

### Hook Event Flow

```
MediaMTX (stream state change)
    ↓
Hook Wrapper Script (parse MTX_* env vars)
    ↓
HTTP POST to media-service service
    ↓
Stream-Orchestration Service (receive hook event)
    ↓
Worker Management Logic (start/stop workers)
```

## Contract References

See `contracts/` directory for JSON schemas:
- `hook-events.json` - Schema for hook event payloads
- `control-api.json` - Schema for MediaMTX Control API responses
