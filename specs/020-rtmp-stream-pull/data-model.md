# Data Model: RTMP Stream Pull Migration

**Feature**: 020-rtmp-stream-pull
**Date**: 2026-01-01
**Phase**: 1 - Design

## Overview

This migration replaces RTSP stream pulling with RTMP in the media-service input pipeline. The data model focuses on configuration entities, pipeline state transitions, and validation rules for RTMP streams.

## Entities

### 1. RTMP Stream Configuration

**Purpose**: Configuration data for RTMP stream source and pipeline setup.

**Fields**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `rtmp_url` | str | Yes | Must start with "rtmp://", non-empty | Full RTMP URL for stream source |
| `host` | str | Yes | Valid hostname or IP | MediaMTX server host (e.g., "mediamtx") |
| `port` | int | Yes | 1-65535, default 1935 | RTMP server port |
| `app_path` | str | Yes | Non-empty, URL-safe | Application path (e.g., "live") |
| `stream_id` | str | Yes | Non-empty, URL-safe | Unique stream identifier |
| `max_buffers` | int | No | > 0, default 10 | flvdemux max-buffers property for buffering control |
| `latency_ms` | int | No | > 0, default 300 | Target total pipeline latency in milliseconds |

**Validation Rules**:
- `rtmp_url` must match format: `rtmp://<host>:<port>/<app_path>/<stream_id>`
- `rtmp_url` construction: `f"rtmp://{host}:{port}/{app_path}/{stream_id}/in"`
- `max_buffers` should be >= frames equivalent to `latency_ms` at 30fps (latency_ms / 33.33)

**Relationships**:
- One-to-one with InputPipeline instance
- Referenced by WorkerRunner during pipeline initialization

**State Transitions**: None (immutable configuration)

**Example**:
```python
config = RTMPStreamConfig(
    rtmp_url="rtmp://mediamtx:1935/live/stream123/in",
    host="mediamtx",
    port=1935,
    app_path="live",
    stream_id="stream123",
    max_buffers=10,
    latency_ms=300
)
```

---

### 2. Input Pipeline State

**Purpose**: Tracks GStreamer pipeline state and readiness for RTMP stream processing.

**Fields**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `state` | enum | Yes | NULL, READY, PAUSED, PLAYING, ERROR, EOS | Current GStreamer pipeline state |
| `has_video_pad` | bool | Yes | Default False | Whether flvdemux video pad is linked |
| `has_audio_pad` | bool | Yes | Default False | Whether flvdemux audio pad is linked |
| `audio_validated` | bool | Yes | Default False | Whether audio track presence has been validated |
| `error_message` | str | No | Max 500 chars | Descriptive error if state == ERROR |
| `pipeline_start_time` | int | No | Nanoseconds since epoch | Pipeline start timestamp for latency tracking |

**Validation Rules**:
- Cannot transition to PLAYING if `has_video_pad == False`
- Cannot transition to PLAYING if `has_audio_pad == False` (audio required for dubbing)
- Must set `audio_validated = True` after PAUSED state reached and both pads verified
- `error_message` must be set if `state == ERROR`

**State Transitions**:
```
NULL -> READY (after pipeline build)
READY -> PAUSED (after caps negotiation)
PAUSED -> PLAYING (after audio validation passes)
* -> ERROR (on any error condition)
* -> NULL (on cleanup)
```

**Relationships**:
- One-to-one with InputPipeline instance
- Referenced by WorkerRunner for pipeline lifecycle management

**Example**:
```python
# Initial state
pipeline_state = InputPipelineState(
    state="NULL",
    has_video_pad=False,
    has_audio_pad=False,
    audio_validated=False
)

# After successful negotiation
pipeline_state.state = "PAUSED"
pipeline_state.has_video_pad = True
pipeline_state.has_audio_pad = True

# After validation
pipeline_state.audio_validated = True
pipeline_state.state = "PLAYING"

# Error case
pipeline_state.state = "ERROR"
pipeline_state.error_message = "Audio track required for dubbing pipeline - stream rejected"
```

---

### 3. GStreamer Pipeline Elements

**Purpose**: Represents GStreamer element references and configuration for RTMP pipeline.

**Fields**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `rtmpsrc` | Gst.Element | Yes | Element name "rtmpsrc" | RTMP source element |
| `flvdemux` | Gst.Element | Yes | Element name "flvdemux" | FLV demuxer element |
| `h264parse` | Gst.Element | Yes | Element name "h264parse" | H.264 parser for video |
| `aacparse` | Gst.Element | Yes | Element name "aacparse" | AAC parser for audio |
| `video_queue` | Gst.Element | Yes | Element name "queue" | Video track queue buffer |
| `audio_queue` | Gst.Element | Yes | Element name "queue" | Audio track queue buffer |
| `video_appsink` | Gst.Element | Yes | Element name "appsink" | Video buffer sink with callbacks |
| `audio_appsink` | Gst.Element | Yes | Element name "appsink" | Audio buffer sink with callbacks |

**Validation Rules**:
- All elements must be successfully created before pipeline build
- Elements must be linked in correct order:
  - Video path: `rtmpsrc -> flvdemux -> h264parse -> video_queue -> video_appsink`
  - Audio path: `rtmpsrc -> flvdemux -> aacparse -> audio_queue -> audio_appsink`
- `rtmpsrc.location` must be set to valid RTMP URL
- `flvdemux.max-buffers` must be set to configuration value
- Both appsinks must have `emit-signals=True` and `sync=False`

**Relationships**:
- Owned by InputPipeline instance
- Configured using RTMP Stream Configuration

**Element Properties**:

**rtmpsrc**:
```python
rtmpsrc.set_property("location", rtmp_url)  # RTMP URL
# No timeout property - TCP connection handles reconnection
```

**flvdemux**:
```python
flvdemux.set_property("max-buffers", 10)  # Buffer queue depth
```

**video_appsink**:
```python
video_appsink.set_property("emit-signals", True)
video_appsink.set_property("sync", False)
video_appsink.set_property("caps", Gst.Caps.from_string("video/x-h264"))
```

**audio_appsink**:
```python
audio_appsink.set_property("emit-signals", True)
audio_appsink.set_property("sync", False)
audio_appsink.set_property("async", False)
audio_appsink.set_property("max-buffers", 0)  # Unlimited
audio_appsink.set_property("drop", False)
audio_appsink.set_property("caps", Gst.Caps.from_string("audio/mpeg"))
```

---

### 4. Stream Buffer Metadata

**Purpose**: Metadata for video and audio buffers received from RTMP stream (unchanged from RTSP).

**Fields**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `data` | bytes | Yes | Non-empty | Raw buffer data (H.264 NAL units or AAC frames) |
| `pts_ns` | int | Yes | >= 0 | Presentation timestamp in nanoseconds |
| `duration_ns` | int | Yes | >= 0 | Buffer duration in nanoseconds |
| `media_type` | enum | Yes | "video" or "audio" | Buffer media type |

**Validation Rules**:
- `data` must not be empty
- `pts_ns` should be monotonically increasing within each media type
- `duration_ns` should be > 0 for valid buffers

**Relationships**:
- Produced by InputPipeline appsink callbacks
- Consumed by SegmentBuffer for segment assembly

**Example**:
```python
video_buffer = StreamBufferMetadata(
    data=b'\x00\x00\x00\x01\x67...',  # H.264 NAL unit
    pts_ns=1234567890000,
    duration_ns=33333333,  # ~30fps
    media_type="video"
)

audio_buffer = StreamBufferMetadata(
    data=b'\xff\xf1...',  # AAC frame
    pts_ns=1234567890000,
    duration_ns=21333333,  # ~48kHz AAC
    media_type="audio"
)
```

---

### 5. Audio Track Validation Result

**Purpose**: Result of audio track presence validation during pipeline startup.

**Fields**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `has_audio` | bool | Yes | - | Whether audio track was detected |
| `validation_time_ms` | int | Yes | > 0 | Time taken to validate (from READY to PAUSED) |
| `error_message` | str | No | Max 500 chars | Error description if has_audio == False |

**Validation Rules**:
- If `has_audio == False`, must set `error_message`
- `validation_time_ms` should be < 2000ms (2 second timeout)

**Relationships**:
- One-to-one with InputPipeline startup sequence
- Determines whether pipeline can transition to PLAYING state

**State Transitions**:
```
Validation Started -> has_audio=True -> Pipeline PLAYING
Validation Started -> has_audio=False -> Pipeline ERROR (with error_message)
Validation Timeout (>2s) -> Pipeline ERROR ("Audio track validation timeout")
```

**Example**:
```python
# Success case
validation_result = AudioTrackValidationResult(
    has_audio=True,
    validation_time_ms=150,
    error_message=None
)

# Failure case
validation_result = AudioTrackValidationResult(
    has_audio=False,
    validation_time_ms=180,
    error_message="Audio track required for dubbing pipeline - stream rejected (FLV container has video-only content)"
)
```

---

## Data Flow

### RTMP Stream Processing Flow

```
1. WorkerRunner constructs RTMP URL from configuration
   -> RTMPStreamConfig created

2. InputPipeline.__init__ receives RTMP URL
   -> Validates URL format (must start with "rtmp://")
   -> InputPipelineState initialized (state=NULL)

3. InputPipeline.build() creates GStreamer elements
   -> GStreamer Pipeline Elements created
   -> Elements linked in pipeline
   -> InputPipelineState.state = READY

4. InputPipeline.start() transitions to PAUSED
   -> flvdemux detects video and audio pads
   -> InputPipelineState.has_video_pad = True
   -> InputPipelineState.has_audio_pad = True

5. Audio validation check
   -> AudioTrackValidationResult created
   -> If has_audio == False: state = ERROR, raise exception
   -> If has_audio == True: InputPipelineState.audio_validated = True

6. Pipeline transitions to PLAYING
   -> InputPipelineState.state = PLAYING
   -> InputPipelineState.pipeline_start_time = current timestamp

7. Buffers flow through appsinks
   -> StreamBufferMetadata created for each buffer
   -> Callbacks invoked with (data, pts_ns, duration_ns)
   -> SegmentBuffer accumulates buffers
```

---

## Migration Impact

### Changed Entities

**InputPipeline** (apps/media-service/src/media_service/pipeline/input.py):
- `__init__`: Replace `rtsp_url` parameter with `rtmp_url`
- `__init__`: Remove `latency` parameter (RTSP jitter buffer), add `max_buffers` parameter (flvdemux buffering)
- `build()`: Replace element creation logic (rtmpsrc + flvdemux instead of rtspsrc + depayloaders)
- `_on_pad_added()`: Simplify - no RTP encoding detection needed, flvdemux pads are known types
- Add `_validate_audio_track()`: New method for audio presence validation

**WorkerRunner** (apps/media-service/src/media_service/worker/worker_runner.py):
- URL construction: Change from RTSP to RTMP format
- Port configuration: 8554 -> 1935
- InputPipeline initialization: Pass `rtmp_url` and `max_buffers` instead of `rtsp_url` and `latency`

### Unchanged Entities

- **SegmentBuffer**: No changes - still receives buffers via callbacks
- **AudioSegmentWriter**: No changes - still processes AAC frames
- **VideoSegmentWriter**: No changes - still processes H.264 NAL units
- **WorkerMetrics**: No changes - still tracks pipeline metrics
- **STSSocketIOClient**: No changes - still sends/receives STS fragments

### Removed Entities

- RTP-specific pad detection logic in `_on_pad_added`
- Dynamic audio depayloader creation (rtpmp4adepay vs rtpmp4gdepay selection)
- RTSP protocol configuration

---

## Validation & Constraints Summary

### Critical Validations

1. **RTMP URL Format**: Must start with "rtmp://", reject with clear error if invalid
2. **Audio Track Presence**: Must have audio pad after PAUSED state, fail fast if missing
3. **Element Creation**: All 8 GStreamer elements must create successfully
4. **Caps Negotiation**: Video must be H.264, audio must be AAC (audio/mpeg)

### Performance Constraints

1. **Latency Budget**: 300ms total from rtmpsrc to segment write
2. **Validation Timeout**: Audio track validation must complete within 2 seconds
3. **Buffer Queue Depth**: max_buffers >= 10 to prevent pipeline stalls during startup

### Data Integrity Constraints

1. **PTS Monotonicity**: Buffer timestamps must increase within each media type
2. **Buffer Completeness**: No partial frames - flvdemux emits complete AAC/H.264 units
3. **Sync Preservation**: Video and audio PTS must maintain original stream timing

---

## Next Steps

Proceed to contracts generation and quickstart documentation.
