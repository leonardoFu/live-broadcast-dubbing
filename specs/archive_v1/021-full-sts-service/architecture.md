# Full STS Service Architecture

## System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                    Live Broadcast Dubbing System                │
└─────────────────────────────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐      ┌──────────────┐      ┌──────────────┐
│   MediaMTX    │      │ media-service│      │  Full STS    │
│ (RTSP Server) │◄────►│   (EC2)      │◄────►│  Service     │
│               │      │              │      │  (RunPod)    │
└───────────────┘      └──────────────┘      └──────────────┘
                               │                      │
                               │                      │
                        Fragment Flow          ASR→Trans→TTS
                        (WebSocket)           (GPU Processing)
```

## Full STS Service Internal Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Full STS Service (Port 8000)                   │
│                  apps/sts-service/src/sts_service/full/             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Socket.IO Server (server.py)                              │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  Event Handlers                                      │  │   │
│  │  │  - connect/disconnect (lifecycle.py)                 │  │   │
│  │  │  - stream:init, pause, resume, end (stream.py)       │  │   │
│  │  │  - fragment:data → fragment:ack (fragment.py)        │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  Session Store (session.py)                          │  │   │
│  │  │  - Stream sessions (config, state, statistics)       │  │   │
│  │  │  - In-flight fragment tracking                       │  │   │
│  │  │  - Backpressure state                                │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └────────────────────────┬───────────────────────────────────┘   │
│                           │                                        │
│                           │ fragment:data received                 │
│                           ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Pipeline Coordinator (pipeline.py)                        │   │
│  │                                                             │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  Fragment Processing Queue                           │  │   │
│  │  │  - Ordered by sequence_number                        │  │   │
│  │  │  - Max in-flight limit enforcement                   │  │   │
│  │  │  - Async processing with ordering guarantee          │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  │                                                             │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  Pipeline Workflow (for each fragment)               │  │   │
│  │  │                                                       │  │   │
│  │  │  1. Decode audio (base64 → PCM bytes)                │  │   │
│  │  │  2. ASR: transcribe(audio_data) → TranscriptAsset    │  │   │
│  │  │  3. Translation: translate(transcript) → TextAsset   │  │   │
│  │  │  4. TTS: synthesize(text_asset) → AudioAsset         │  │   │
│  │  │  5. Encode audio (PCM → base64)                      │  │   │
│  │  │  6. Build fragment:processed payload                 │  │   │
│  │  │  7. Emit fragment:processed (in order)               │  │   │
│  │  │                                                       │  │   │
│  │  │  Error Handling:                                     │  │   │
│  │  │  - Check asset.status after each stage              │  │   │
│  │  │  - If FAILED, stop pipeline and emit error          │  │   │
│  │  │  - Set retryable flag based on error type           │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  │                                                             │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐         │   │
│  │  │   ASR    │  │ Translation  │  │     TTS      │         │   │
│  │  │ Module   │  │   Module     │  │   Module     │         │   │
│  │  │          │  │              │  │              │         │   │
│  │  │ Whisper  │  │    DeepL     │  │  Coqui TTS   │         │   │
│  │  │(faster-  │  │     API      │  │  (XTTS v2)   │         │   │
│  │  │whisper)  │  │              │  │ + Rubberband │         │   │
│  │  │          │  │              │  │ (duration    │         │   │
│  │  │          │  │              │  │  matching)   │         │   │
│  │  └────┬─────┘  └──────┬───────┘  └──────┬───────┘         │   │
│  │       │                │                 │                 │   │
│  │       └────────────────┴─────────────────┘                 │   │
│  │                        │                                   │   │
│  │                        ▼                                   │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  Asset Lineage Tracking                              │  │   │
│  │  │  TranscriptAsset → TextAsset → AudioAsset            │  │   │
│  │  │  (parent_asset_ids maintain provenance)              │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Observability Layer                                       │   │
│  │                                                             │   │
│  │  ┌──────────────────────┐  ┌──────────────────────────┐   │   │
│  │  │ Prometheus Metrics   │  │  Structured Logging      │   │   │
│  │  │ (metrics.py)         │  │  (logging_config.py)     │   │   │
│  │  │                      │  │                          │   │   │
│  │  │ - latency histogram  │  │ - fragment_id            │   │   │
│  │  │ - error counters     │  │ - stream_id              │   │   │
│  │  │ - in-flight gauge    │  │ - sequence_number        │   │   │
│  │  │ - GPU utilization    │  │ - stage timings          │   │   │
│  │  │ - stage breakdowns   │  │ - error details          │   │   │
│  │  └──────────────────────┘  └──────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  HTTP Endpoints (Starlette)                                │   │
│  │  - GET /health        (health check)                       │   │
│  │  - GET /metrics       (Prometheus metrics)                 │   │
│  │  - WS  /socket.io/... (Socket.IO WebSocket)                │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Fragment Processing Flow (Detailed)

```
┌─────────────┐
│media-service│
│  (Worker)   │
└──────┬──────┘
       │
       │ 1. fragment:data
       │    (audio_base64, sequence_number, fragment_id)
       ▼
┌────────────────────────────────────────────────────────┐
│ Socket.IO Server                                       │
│ fragment:data handler (handlers/fragment.py)           │
└──────┬─────────────────────────────────────────────────┘
       │
       │ 2. Immediate response
       ▼
┌────────────────────────────────────────────────────────┐
│ fragment:ack emitted                                   │
│ { fragment_id, status: "queued" }                      │
└────────────────────────────────────────────────────────┘
       │
       │ 3. Add to processing queue
       ▼
┌────────────────────────────────────────────────────────┐
│ Pipeline Coordinator (pipeline.py)                     │
│ Queue ordered by sequence_number                       │
└──────┬─────────────────────────────────────────────────┘
       │
       │ 4. Process next fragment in order
       ▼
┌────────────────────────────────────────────────────────┐
│ Stage 1: ASR (Automatic Speech Recognition)            │
│ - Decode base64 → PCM bytes                            │
│ - Call asr.transcribe(audio_data, stream_id, ...)      │
│ - Output: TranscriptAsset (transcript, segments)       │
│ - Timing: asr_ms                                       │
│                                                         │
│ Error handling:                                        │
│ - if asset.status == FAILED:                           │
│   → emit fragment:processed with error, stop pipeline  │
│ - if asset.status == SUCCESS and transcript empty:     │
│   → skip translation/TTS, return silence               │
└──────┬─────────────────────────────────────────────────┘
       │
       │ 5. transcript available
       ▼
┌────────────────────────────────────────────────────────┐
│ Stage 2: Translation                                   │
│ - Call translation.translate(transcript, ...)          │
│ - Output: TextAsset (translated_text)                  │
│ - Timing: translation_ms                               │
│                                                         │
│ Error handling:                                        │
│ - if asset.status == FAILED:                           │
│   → emit fragment:processed with error, stop pipeline  │
│ - if transcript empty:                                 │
│   → skip translation, return empty TextAsset           │
└──────┬─────────────────────────────────────────────────┘
       │
       │ 6. translated_text available
       ▼
┌────────────────────────────────────────────────────────┐
│ Stage 3: TTS (Text-to-Speech)                          │
│ - Call tts.synthesize(                                 │
│     text_asset,                                        │
│     target_duration_ms = original_fragment_duration,   │
│     output_sample_rate_hz, output_channels             │
│   )                                                     │
│ - TTS performs:                                        │
│   1. Synthesis (Coqui XTTS v2)                         │
│   2. Duration matching (rubberband time-stretch)       │
│ - Output: AudioAsset (dubbed_audio PCM)                │
│ - Timing: tts_ms                                       │
│                                                         │
│ Error handling:                                        │
│ - if asset.status == FAILED:                           │
│   → emit fragment:processed with error, stop pipeline  │
│ - if asset.status == PARTIAL (clamped speed):          │
│   → emit fragment:processed with warning, continue     │
│ - if translated_text empty:                            │
│   → return silence or original audio (configurable)    │
└──────┬─────────────────────────────────────────────────┘
       │
       │ 7. dubbed_audio available
       ▼
┌────────────────────────────────────────────────────────┐
│ Build fragment:processed Payload                       │
│ - Encode audio (PCM → base64)                          │
│ - Include transcript, translated_text (for debugging)  │
│ - Include processing_time_ms, stage_timings            │
│ - Include metadata (models, GPU util)                  │
└──────┬─────────────────────────────────────────────────┘
       │
       │ 8. Wait for sequence_number order
       ▼
┌────────────────────────────────────────────────────────┐
│ In-Order Emission Logic                                │
│ - Buffer processed fragments                           │
│ - Emit only when sequence_number matches next expected │
│ - Guarantees ordering even if processing out-of-order  │
└──────┬─────────────────────────────────────────────────┘
       │
       │ 9. Emit when ready
       ▼
┌────────────────────────────────────────────────────────┐
│ fragment:processed emitted                             │
│ {                                                       │
│   fragment_id, stream_id, sequence_number,             │
│   status: "success",                                   │
│   dubbed_audio: { format, sample_rate_hz, channels,    │
│                   duration_ms, data_base64 },          │
│   transcript, translated_text,                         │
│   processing_time_ms, stage_timings,                   │
│   metadata                                             │
│ }                                                       │
└────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│media-service│
│  (Worker)   │
│ Receives    │
│ dubbed audio│
└─────────────┘
```

## Backpressure Flow

```
┌────────────────────────────────────────────────────────┐
│ Fragment Tracker                                       │
│ - Monitors in-flight fragment count                    │
│ - Configured thresholds (max_inflight = 3)             │
└──────┬─────────────────────────────────────────────────┘
       │
       │ Continuous monitoring
       ▼
┌────────────────────────────────────────────────────────┐
│ Backpressure Detection                                 │
│                                                         │
│ if in_flight > max_inflight:                           │
│   severity = "medium"                                  │
│   action = "slow_down"                                 │
│                                                         │
│ if in_flight > 2 * max_inflight:                       │
│   severity = "high"                                    │
│   action = "pause"                                     │
│                                                         │
│ if in_flight < max_inflight:                           │
│   severity = "low"                                     │
│   action = "none"  (recovery)                          │
└──────┬─────────────────────────────────────────────────┘
       │
       │ Emit backpressure event
       ▼
┌────────────────────────────────────────────────────────┐
│ backpressure event emitted                             │
│ {                                                       │
│   stream_id,                                           │
│   severity: "medium" | "high" | "low",                 │
│   action: "slow_down" | "pause" | "none",              │
│   current_inflight: 4,                                 │
│   max_inflight: 3                                      │
│ }                                                       │
└────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│media-service│
│  (Worker)   │
│ Adjusts send│
│ rate based  │
│ on action   │
└─────────────┘
```

## Error Handling Flow

```
┌────────────────────────────────────────────────────────┐
│ Pipeline Stage Execution                               │
│ - Each stage returns Asset with status                 │
└──────┬─────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Check Asset Status                                     │
│                                                         │
│ if asset.status == SUCCESS:                            │
│   → Continue to next stage                             │
│                                                         │
│ if asset.status == PARTIAL:                            │
│   → Log warning, continue to next stage                │
│   → Include warning in final response                  │
│                                                         │
│ if asset.status == FAILED:                             │
│   → Stop pipeline immediately                          │
│   → Build error response                               │
│   → Determine if retryable                             │
└──────┬─────────────────────────────────────────────────┘
       │
       │ if FAILED
       ▼
┌────────────────────────────────────────────────────────┐
│ Error Classification                                   │
│                                                         │
│ Transient errors (retryable = true):                   │
│ - TIMEOUT                                              │
│ - RATE_LIMIT_EXCEEDED                                  │
│ - NETWORK_ERROR                                        │
│ - TEMPORARY_UNAVAILABLE                                │
│                                                         │
│ Permanent errors (retryable = false):                  │
│ - INVALID_AUDIO_FORMAT                                 │
│ - UNSUPPORTED_LANGUAGE                                 │
│ - TTS_SYNTHESIS_FAILED (invalid phonemes)              │
│ - INVALID_TEXT                                         │
└──────┬─────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ fragment:processed emitted (status: "failed")          │
│ {                                                       │
│   fragment_id, stream_id, sequence_number,             │
│   status: "failed",                                    │
│   processing_time_ms,                                  │
│   stage_timings: { asr_ms, translation_ms, tts_ms },   │
│   error: {                                             │
│     code: "TIMEOUT",                                   │
│     message: "ASR processing timed out after 5000ms",  │
│     stage: "asr",                                      │
│     retryable: true                                    │
│   }                                                     │
│ }                                                       │
└────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│media-service│
│  (Worker)   │
│ Decides:    │
│ - Retry if  │
│   retryable │
│ - Fallback  │
│   if not    │
└─────────────┘
```

## Data Models

### Stream Session
```python
@dataclass
class StreamSession:
    session_id: str
    stream_id: str
    worker_id: str
    config: StreamConfig  # source/target language, voice, audio format
    state: SessionState   # initializing, active, paused, ending
    statistics: StreamStatistics  # total fragments, success/fail counts, avg latency
    in_flight_tracker: FragmentTracker  # current in-flight fragments
    backpressure_state: BackpressureState
    created_at: datetime
    updated_at: datetime
```

### Fragment
```python
@dataclass
class Fragment:
    fragment_id: str
    stream_id: str
    sequence_number: int
    timestamp: int  # Unix timestamp ms
    audio_data: bytes  # PCM data (decoded from base64)
    audio_metadata: AudioMetadata  # format, sample_rate, channels, duration
    processing_state: ProcessingState  # queued, processing, completed, failed
    transcript_asset: TranscriptAsset | None
    translation_asset: TextAsset | None
    tts_asset: AudioAsset | None
    error: FragmentError | None
    timings: StageTimings  # asr_ms, translation_ms, tts_ms
```

### Asset Lineage
```
Fragment (fragment_id: "abc-123", sequence: 42)
    ↓
TranscriptAsset (asset_id: "transcript-abc-123-42")
  - transcript: "Hello, welcome to the game."
  - segments: [...]
  - parent_asset_ids: ["fragment:abc-123"]
    ↓
TextAsset (asset_id: "translation-abc-123-42")
  - translated_text: "Hola, bienvenido al juego."
  - source_text: "Hello, welcome to the game."
  - parent_asset_ids: ["transcript-abc-123-42"]
    ↓
AudioAsset (asset_id: "audio-abc-123-42")
  - audio_data: <PCM bytes>
  - duration_ms: 6050
  - parent_asset_ids: ["translation-abc-123-42"]
```

## Configuration

### Environment Variables
```bash
# Server
STS_PORT=8000
STS_HOST=0.0.0.0

# Processing
MAX_INFLIGHT=3              # Max concurrent fragments per stream
FRAGMENT_TIMEOUT_MS=8000    # Per-fragment processing timeout
MAX_CONCURRENT_STREAMS=5    # Max concurrent stream sessions

# Fallback
FALLBACK_MODE=silence       # "silence" or "original" when TTS fails

# Models
ASR_MODEL=faster-whisper-base
TRANSLATION_PROVIDER=deepl
TTS_MODEL=coqui-xtts-v2

# API Keys
DEEPL_API_KEY=<secret>

# GPU
CUDA_VISIBLE_DEVICES=0
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Observability
LOG_LEVEL=INFO
METRICS_PORT=8000  # Same as STS_PORT
```

## Deployment (RunPod)

```yaml
# RunPod Pod Configuration
image: custom-sts-service:latest
gpu: NVIDIA RTX 4090 (24GB VRAM)
cpu: 8 vCPUs
memory: 32GB RAM
disk: 100GB SSD (for model caching)

environment:
  - STS_PORT=8000
  - MAX_INFLIGHT=3
  - DEEPL_API_KEY=${DEEPL_API_KEY}
  - CUDA_VISIBLE_DEVICES=0

ports:
  - 8000:8000  # Socket.IO + /health + /metrics

volumes:
  - /workspace/models:/models  # Persistent model cache

health_check:
  path: /health
  interval: 30s
  timeout: 10s
```
