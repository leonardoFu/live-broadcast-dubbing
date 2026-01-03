# Full STS Service Data Model

This document describes the data models used in the Full STS (Speech-to-Speech) Service for real-time live broadcast dubbing.

## Overview

The Full STS Service processes audio fragments through a three-stage pipeline:
1. **ASR** (Automatic Speech Recognition) - Transcribes audio to text
2. **Translation** - Translates text to target language
3. **TTS** (Text-to-Speech) - Synthesizes translated text to audio

Data flows through Socket.IO events between the media-service worker and STS service.

## Model Architecture

```
                                    Socket.IO Events
                                         |
    +-------------------+       +--------v--------+       +-------------------+
    | StreamInitPayload |------>|  StreamSession  |------>| StreamStatistics  |
    +-------------------+       +--------+--------+       +-------------------+
                                         |
                                         v
    +-------------------+       +--------v--------+       +-------------------+
    |   FragmentData    |------>| Asset Pipeline  |------>|  FragmentResult   |
    +-------------------+       +--------+--------+       +-------------------+
                                         |
          +------------------------------+------------------------------+
          |                              |                              |
    +-----v-----+                  +-----v------+                 +-----v-----+
    | Transcript|----------------->| Translation|---------------->|   Audio   |
    |   Asset   |                  |   Asset    |                 |   Asset   |
    +-----------+                  +------------+                 +-----------+
```

## Core Models

### Stream Models (`models/stream.py`)

#### StreamState (Enum)
Stream lifecycle states.

| Value | Description |
|-------|-------------|
| `initializing` | stream:init received, setting up |
| `ready` | stream:ready sent, accepting fragments |
| `paused` | stream:pause received, not accepting new fragments |
| `ending` | stream:end received, draining in-flight fragments |
| `completed` | stream:complete sent, session terminated |

#### StreamConfig
Configuration for a streaming session.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `source_language` | string | Yes | "en" | Source language code (2-10 chars) |
| `target_language` | string | Yes | "es" | Target language code (2-10 chars) |
| `voice_profile` | string | Yes | "default" | TTS voice identifier |
| `chunk_duration_ms` | int | Yes | 6000 | Expected fragment duration (100-10000) |
| `sample_rate_hz` | int | Yes | 48000 | Audio sample rate (8000-96000) |
| `channels` | int | Yes | 1 | Audio channels (1-2) |
| `format` | string | Yes | "m4a" | Audio format identifier |
| `domain_hints` | list[str] | No | null | Domain vocabulary hints |

#### StreamSession
Runtime state for an active stream.

| Field | Type | Description |
|-------|------|-------------|
| `stream_id` | string | Unique stream identifier |
| `session_id` | string | Server-assigned session ID |
| `worker_id` | string | Worker instance identifier |
| `socket_id` | string | Socket.IO connection ID |
| `config` | StreamConfig | Stream configuration |
| `max_inflight` | int | Max concurrent fragments (1-10) |
| `timeout_ms` | int | Per-fragment timeout (1000-30000) |
| `state` | StreamState | Current lifecycle state |
| `fragments_received` | int | Total fragments received |
| `fragments_processed` | int | Successfully processed fragments |
| `fragments_failed` | int | Failed fragments |
| `current_inflight` | int | Currently in-flight fragment count |

#### StreamStatistics
Summary statistics for a completed stream.

| Field | Type | Description |
|-------|------|-------------|
| `total_fragments` | int | Total fragments processed |
| `success_count` | int | Successfully processed |
| `partial_count` | int | Partially processed (with warnings) |
| `failed_count` | int | Failed fragments |
| `avg_processing_time_ms` | float | Average processing time |
| `p95_processing_time_ms` | float | 95th percentile processing time |
| `total_audio_duration_ms` | int | Total audio duration processed |

### Fragment Models (`models/fragment.py`)

#### ProcessingStatus (Enum)
Fragment processing result status.

| Value | Description |
|-------|-------------|
| `success` | All stages completed successfully |
| `partial` | Completed with warnings (e.g., clamped speed ratio) |
| `failed` | Processing failed at one or more stages |

#### AudioData
Audio data structure for fragment payloads.

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `format` | string | Yes | - | Audio format (m4a, pcm_s16le) |
| `sample_rate_hz` | int | Yes | 8000-96000 | Sample rate in Hz |
| `channels` | int | Yes | 1-2 | Audio channels |
| `duration_ms` | int | Yes | 0-60000 | Duration in milliseconds |
| `data_base64` | string | Yes | min 1 char, max 10MB decoded | Base64-encoded audio |

#### FragmentData
Inbound fragment:data event payload.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fragment_id` | string | Yes | Unique fragment UUID |
| `stream_id` | string | Yes | Parent stream identifier |
| `sequence_number` | int | Yes | Monotonic sequence (0-based) |
| `timestamp` | int | Yes | Unix timestamp in milliseconds |
| `audio` | AudioData | Yes | Audio payload |
| `metadata` | FragmentMetadata | No | Optional PTS and custom data |

#### FragmentResult
Outbound fragment:processed event payload.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fragment_id` | string | Yes | Original fragment ID |
| `stream_id` | string | Yes | Parent stream identifier |
| `sequence_number` | int | Yes | Original sequence number |
| `status` | ProcessingStatus | Yes | Processing result status |
| `dubbed_audio` | AudioData | If success/partial | Synthesized audio |
| `transcript` | string | No | ASR transcription |
| `translated_text` | string | No | Translation output |
| `processing_time_ms` | int | Yes | Total processing time |
| `stage_timings` | StageTiming | No | Per-stage timing breakdown |
| `error` | ProcessingError | If failed/partial | Error details |
| `metadata` | DurationMetadata | No | Duration matching info |

#### StageTiming
Per-stage timing breakdown.

| Field | Type | Description |
|-------|------|-------------|
| `asr_ms` | int | ASR processing time in ms |
| `translation_ms` | int | Translation time in ms |
| `tts_ms` | int | TTS synthesis time in ms |

#### DurationMetadata
Duration matching metadata for A/V synchronization.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `original_duration_ms` | int | >= 0 | Original fragment duration |
| `dubbed_duration_ms` | int | >= 0 | Final dubbed audio duration |
| `duration_variance_percent` | float | >= 0 | Variance as percentage |
| `speed_ratio` | float | 0.5-2.0 | Applied speed adjustment |

### Asset Models (`models/asset.py`)

Assets provide lineage tracking through the pipeline for debugging and observability.

#### AssetStatus (Enum)
| Value | Description |
|-------|-------------|
| `success` | Asset created successfully |
| `partial` | Asset created with warnings/fallbacks |
| `failed` | Asset creation failed |

#### BaseAsset (Abstract)
Common fields for all pipeline assets.

| Field | Type | Description |
|-------|------|-------------|
| `asset_id` | string | Unique asset UUID |
| `fragment_id` | string | Source fragment ID |
| `stream_id` | string | Parent stream ID |
| `status` | AssetStatus | Processing status |
| `parent_asset_ids` | list[str] | Parent assets in pipeline |
| `latency_ms` | int | Processing latency |
| `created_at` | datetime | Creation timestamp |
| `error_message` | string | Error if status != success |
| `metadata` | dict | Additional metadata |

#### TranscriptAsset
ASR output with transcript and confidence.

| Field | Type | Description |
|-------|------|-------------|
| *All BaseAsset fields* | | |
| `transcript` | string | Full transcribed text |
| `segments` | list[TranscriptSegment] | Word-level segments |
| `confidence` | float (0-1) | Overall confidence score |
| `language` | string | Detected/specified language |
| `audio_duration_ms` | int | Input audio duration |
| `model_id` | string | ASR model identifier |

#### TranscriptSegment
Word-level segment from ASR.

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Word or segment text |
| `start_ms` | int | Start time in ms |
| `end_ms` | int | End time in ms |
| `confidence` | float (0-1) | Word confidence |

#### TranslationAsset
Translation output.

| Field | Type | Description |
|-------|------|-------------|
| *All BaseAsset fields* | | |
| `translated_text` | string | Translated text |
| `source_text` | string | Original source text |
| `source_language` | string | Source language code |
| `target_language` | string | Target language code |
| `model_id` | string | Translation API/model |
| `character_count` | int | Characters translated |
| `word_expansion_ratio` | float | Target/source word ratio |

#### AudioAsset
TTS synthesized audio output.

| Field | Type | Description |
|-------|------|-------------|
| *All BaseAsset fields* | | |
| `audio_bytes` | bytes | Raw audio data |
| `format` | string | Audio format (pcm_s16le) |
| `sample_rate_hz` | int | Sample rate |
| `channels` | int | Audio channels |
| `duration_ms` | int | Audio duration |
| `duration_metadata` | DurationMatchMetadata | A/V sync info |
| `voice_profile` | string | TTS voice used |
| `model_id` | string | TTS model identifier |
| `text_input` | string | Text that was synthesized |

### Error Models (`models/error.py`)

#### ErrorStage (Enum)
Pipeline stage where error occurred.

| Value | Description |
|-------|-------------|
| `asr` | ASR processing stage |
| `translation` | Translation stage |
| `tts` | TTS synthesis stage |

#### ErrorCode (Enum)
Standardized error codes with retryability.

**Stream Errors (not retryable):**
- `STREAM_NOT_FOUND` - Stream ID not in session store
- `STREAM_PAUSED` - Stream paused, rejecting fragments
- `INVALID_CONFIG` - Invalid stream configuration
- `INVALID_VOICE_PROFILE` - Voice profile not found
- `UNSUPPORTED_LANGUAGE` - Language pair not supported

**Processing Errors (retryable):**
- `TIMEOUT` - Processing timed out
- `RATE_LIMIT_EXCEEDED` - API rate limit hit
- `TRANSLATION_API_UNAVAILABLE` - Translation API down
- `BACKPRESSURE_EXCEEDED` - Critical threshold exceeded
- `GPU_OOM` - GPU out of memory

**Pipeline Errors (varies):**
- `ASR_FAILED` - ASR processing failed
- `TRANSLATION_FAILED` - Translation failed
- `TTS_SYNTHESIS_FAILED` - TTS synthesis failed
- `DURATION_MISMATCH_EXCEEDED` - Variance > 20%
- `INVALID_AUDIO_FORMAT` - Unsupported audio format

#### ErrorResponse
Socket.IO error event payload.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | Error code |
| `message` | string | Yes | Human-readable description |
| `retryable` | bool | Yes | Whether error is transient |
| `stage` | ErrorStage | No | Pipeline stage |
| `details` | dict | No | Additional details |

### Backpressure Models (`models/backpressure.py`)

#### BackpressureSeverity (Enum)
| Value | In-flight Range | Recommended Action |
|-------|-----------------|-------------------|
| `low` | 1-3 | None (normal operation) |
| `medium` | 4-6 | Slow down fragment rate |
| `high` | 7-10 | Pause sending fragments |

#### BackpressureAction (Enum)
| Value | Description |
|-------|-------------|
| `none` | Continue normally |
| `slow_down` | Increase delay between fragments |
| `pause` | Stop sending new fragments |

#### BackpressureState
Backpressure event payload.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stream_id` | string | Yes | Stream identifier |
| `severity` | BackpressureSeverity | Yes | Current severity level |
| `action` | BackpressureAction | Yes | Recommended action |
| `current_inflight` | int | Yes | Current in-flight count |
| `max_inflight` | int | Yes | Configured maximum (1-10) |
| `threshold_exceeded` | string | No | Which threshold was exceeded |
| `recommended_delay_ms` | int | No | Suggested delay before next fragment |

## Data Flow

### Stream Lifecycle

```
Worker                                  STS Service
  |                                          |
  |--- stream:init (StreamInitPayload) ----->|
  |                                          | Creates StreamSession
  |<---- stream:ready (StreamReadyPayload) --|
  |                                          |
  |--- fragment:data (FragmentData) -------->|
  |<---- fragment:ack (FragmentAck) ---------|
  |                                          | ASR -> Translation -> TTS
  |<---- fragment:processed (FragmentResult)-|
  |                                          |
  |<---- backpressure (BackpressureState) ---|  (if thresholds exceeded)
  |                                          |
  |--- stream:end (StreamEndPayload) ------->|
  |                                          | Drains in-flight fragments
  |<---- stream:complete (StreamStatistics) -|
```

### Asset Pipeline

```
FragmentData
    |
    v
+-------------------+
| TranscriptAsset   | <-- ASR Stage
| - transcript      |     latency: ~1200ms
| - segments[]      |
| - confidence      |
+--------+----------+
         |
         v
+-------------------+
| TranslationAsset  | <-- Translation Stage
| - translated_text |     latency: ~150ms
| - source_text     |
| - language_pair   |
+--------+----------+
         |
         v
+-------------------+
| AudioAsset        | <-- TTS Stage
| - audio_bytes     |     latency: ~3100ms
| - duration_ms     |
| - duration_meta   |
+--------+----------+
         |
         v
FragmentResult
```

## JSON Schema References

The Pydantic models conform to the JSON schemas in `contracts/`:
- `fragment-schema.json` - Fragment event schemas
- `stream-schema.json` - Stream lifecycle schemas
- `backpressure-schema.json` - Backpressure event schema
- `error-schema.json` - Error response schema

## Usage Examples

### Creating a Stream Session
```python
from sts_service.full.models import StreamConfig, StreamSession, StreamState

config = StreamConfig(
    source_language="en",
    target_language="es",
    voice_profile="spanish_male_1",
    chunk_duration_ms=6000,
)

session = StreamSession(
    stream_id="stream-abc-123",
    session_id="session-xyz-789",
    worker_id="worker-001",
    socket_id="sid-12345",
    config=config,
    state=StreamState.READY,
)
```

### Processing a Fragment
```python
from sts_service.full.models import (
    FragmentData, FragmentResult, AudioData,
    ProcessingStatus, StageTiming, DurationMetadata
)

# Incoming fragment
fragment = FragmentData(
    fragment_id="frag-001",
    stream_id="stream-abc-123",
    sequence_number=0,
    timestamp=1704067200000,
    audio=AudioData(
        format="m4a",
        sample_rate_hz=48000,
        channels=1,
        duration_ms=6000,
        data_base64="...",
    ),
)

# Processing result
result = FragmentResult(
    fragment_id=fragment.fragment_id,
    stream_id=fragment.stream_id,
    sequence_number=fragment.sequence_number,
    status=ProcessingStatus.SUCCESS,
    dubbed_audio=AudioData(
        format="pcm_s16le",
        sample_rate_hz=48000,
        channels=1,
        duration_ms=6050,
        data_base64="...",
    ),
    transcript="Hello, welcome to the game.",
    translated_text="Hola, bienvenido al juego.",
    processing_time_ms=4500,
    stage_timings=StageTiming(asr_ms=1200, translation_ms=150, tts_ms=3100),
    metadata=DurationMetadata(
        original_duration_ms=6000,
        dubbed_duration_ms=6050,
        duration_variance_percent=0.83,
        speed_ratio=0.99,
    ),
)
```

### Handling Backpressure
```python
from sts_service.full.models import BackpressureState

# Calculate backpressure from current state
bp = BackpressureState.calculate(
    stream_id="stream-abc-123",
    current_inflight=5,
    max_inflight=3,
)

if bp.severity.value == "high":
    # Emit pause recommendation to worker
    emit("backpressure", bp.to_event_payload())
```

### Creating Error Responses
```python
from sts_service.full.models import ErrorResponse, ErrorCode, ErrorStage

# Stream not found
error = ErrorResponse.stream_not_found("stream-abc-123")

# Timeout error
error = ErrorResponse.timeout(
    stage=ErrorStage.ASR,
    timeout_ms=5000,
)

# Rate limit error
error = ErrorResponse.rate_limit_exceeded(
    api_name="DeepL",
    retry_after_seconds=60,
)
```
