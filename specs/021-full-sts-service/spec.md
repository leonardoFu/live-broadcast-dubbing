# Feature Specification: Full STS Service with Socket.IO Integration

**Feature Branch**: `021-full-sts-service`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "Complete the whole STS workflow and send dubbed audio segments to Socket.IO clients"

## Overview

The Full STS Service implements the complete Speech-to-Speech (ASR → Translation → TTS) processing pipeline with Socket.IO integration for real-time bidirectional communication with media-service. Unlike the Echo STS Service (spec 017), which simply echoes audio back for testing, this service performs actual speech recognition, translation, and text-to-speech synthesis to produce dubbed audio in the target language.

This is the **production-critical core** of the live broadcast dubbing system, responsible for transforming source audio fragments into dubbed audio fragments while maintaining real-time constraints (3-8 seconds added latency) and A/V synchronization.

The service implements the WebSocket Audio Fragment Protocol ([specs/016-websocket-audio-protocol.md](../016-websocket-audio-protocol.md)) as the Socket.IO server, receiving audio fragments from media-service workers and returning dubbed audio.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete STS Pipeline Processing (Priority: P1)

An E2E test scenario where media-service sends an audio fragment containing speech to the Full STS Service. The service performs ASR (Whisper) to transcribe the audio, translates the text (DeepL), synthesizes dubbed audio (Coqui TTS with duration matching), and returns the result via Socket.IO.

**Why this priority**: This is the core functionality that delivers the product value - transforming source speech into dubbed speech. Without this working, the entire dubbing pipeline is non-functional. All other features support or enhance this core capability.

**Independent Test**: Send real audio fragments with speech and verify complete pipeline execution.
- **Unit test**: `test_pipeline_coordinator_chains_components()` validates orchestration logic; `test_asr_transcription()`, `test_translation()`, `test_tts_synthesis()` test each component independently
- **Contract test**: `test_fragment_processed_schema_with_real_data()` validates output matches spec 016; `test_audio_asset_lineage()` validates parent_asset_ids tracking
- **Integration test**: `test_full_pipeline_english_to_spanish()` validates ASR→Translation→TTS flow with real components; `test_duration_matching_preserves_sync()` validates A/V sync
- **Success criteria**: English audio transcribed correctly (>90% accuracy), translated to Spanish, synthesized with <10% duration variance, total latency <8s, all tests pass with 80% coverage

**Acceptance Scenarios**:

1. **Given** an initialized stream session, **When** worker sends fragment:data with 6s English speech audio, **Then** service responds with fragment:ack (queued), processes through ASR→Translation→TTS, and returns fragment:processed with dubbed Spanish audio within 8 seconds
2. **Given** a fragment with clear speech, **When** processing completes successfully, **Then** fragment:processed contains status "success", dubbed_audio with valid PCM data, transcript (English text), translated_text (Spanish text), and stage_timings breakdown
3. **Given** a fragment with 6s original audio, **When** TTS synthesizes dubbed audio, **Then** dubbed audio duration is within ±10% of original duration (5.4s - 6.6s range)
4. **Given** multiple fragments sent in sequence, **When** processing completes, **Then** fragment:processed events are emitted in sequence_number order (in-order delivery guarantee)

---

### User Story 2 - Graceful Error Handling and Fallback (Priority: P1)

An E2E test scenario where the Full STS Service encounters errors during processing (e.g., ASR timeout, translation API failure, TTS synthesis error). The service handles errors gracefully, returns appropriate error responses with retryable flags, and allows the worker to implement fallback strategies.

**Why this priority**: Production environments experience transient failures (API timeouts, model errors, network issues). Without robust error handling, a single failure could disrupt the entire stream. This is critical for system reliability.

**Independent Test**: Inject errors at each pipeline stage and verify proper error handling.
- **Unit test**: `test_asr_timeout_returns_failed_asset()` validates ASR error handling; `test_translation_api_error_retryable()`, `test_tts_synthesis_error_non_retryable()` test error propagation
- **Contract test**: `test_error_response_schema()` validates error payload structure matches spec 016
- **Integration test**: `test_pipeline_handles_asr_failure()` validates error recovery; `test_retryable_errors_allow_retry()` validates retry logic
- **Success criteria**: Transient errors marked retryable=true, permanent errors marked retryable=false, error responses include stage/code/message, worker can detect and retry/fallback

**Acceptance Scenarios**:

1. **Given** an initialized stream session, **When** ASR module times out processing a fragment, **Then** service returns fragment:processed with status "failed", error.stage "asr", error.code "TIMEOUT", error.retryable true
2. **Given** a fragment that fails ASR with retryable error, **When** worker resends the same fragment, **Then** service reprocesses it (idempotent retry)
3. **Given** a fragment that fails TTS with non-retryable error (e.g., invalid text), **When** processing completes, **Then** service returns fragment:processed with status "failed", error.retryable false, allowing worker to skip/fallback
4. **Given** a fragment with silence (no speech detected), **When** ASR processing completes, **Then** service returns fragment:processed with status "success", transcript empty string, and dubbed_audio contains silence (no translation/TTS)

---

### User Story 3 - Backpressure and Flow Control (Priority: P2)

An E2E test scenario where the Full STS Service monitors in-flight fragment processing load and emits backpressure events when thresholds are exceeded. The worker responds by slowing down or pausing fragment submission, preventing queue overflow and GPU memory exhaustion.

**Why this priority**: Real-time processing requires careful flow control. GPU memory is limited, and processing time varies by audio content. Backpressure prevents system overload but is secondary to basic processing functionality.

**Independent Test**: Send fragments at high rate and verify backpressure signaling.
- **Unit test**: `test_fragment_tracker_emits_backpressure()` validates threshold logic; `test_backpressure_severity_calculation()` validates low/medium/high levels
- **Contract test**: `test_backpressure_payload_schema()` validates backpressure message structure
- **Integration test**: `test_worker_slows_on_backpressure()` validates worker response; `test_backpressure_clears_when_queue_drains()` validates recovery
- **Success criteria**: Backpressure event emitted when in-flight > max_inflight, severity accurate, worker adjusts send rate, no GPU OOM errors

**Acceptance Scenarios**:

1. **Given** an initialized stream with max_inflight=3, **When** worker sends 4th fragment before any complete, **Then** service emits backpressure event with severity "medium", action "slow_down", current_inflight 4, and continues accepting fragments
2. **Given** a backpressure event was emitted, **When** fragments complete and in-flight count drops to 2, **Then** service emits backpressure event with severity "low", action "none", indicating recovery
3. **Given** high backpressure (in-flight=8), **When** event is emitted, **Then** severity is "high", action is "pause", prompting worker to pause submissions, service continues accepting
4. **Given** critical backpressure (in-flight>10), **When** worker sends new fragment, **Then** service rejects with BACKPRESSURE_EXCEEDED error and worker waits for recovery event

---

### User Story 4 - Observability and Performance Monitoring (Priority: P2)

An E2E test scenario where the Full STS Service exposes Prometheus metrics and structured logs for monitoring processing latency, error rates, GPU utilization, and throughput. Operators can detect performance degradation and debug issues using metrics and log correlation.

**Why this priority**: Production observability is critical for operations but not required for core functionality. Metrics enable performance optimization and incident response.

**Independent Test**: Process fragments and verify metrics/logs are emitted correctly.
- **Unit test**: `test_metrics_recorder_tracks_latency()` validates metric emission; `test_structured_logging_includes_fragment_id()` validates log format
- **Contract test**: `test_prometheus_metrics_endpoint()` validates /metrics format
- **Integration test**: `test_end_to_end_metrics_flow()` validates metrics for full pipeline; `test_log_correlation_by_fragment_id()` validates log tracing
- **Success criteria**: All key metrics present (latency, error rate, GPU util), logs include fragment_id/stream_id for correlation, metrics queryable via Prometheus

**Acceptance Scenarios**:

1. **Given** a fragment is processed successfully, **When** processing completes, **Then** metrics include sts_fragment_processing_seconds (histogram), sts_asr_duration_seconds, sts_translation_duration_seconds, sts_tts_duration_seconds
2. **Given** a fragment fails at TTS stage, **When** error occurs, **Then** sts_fragment_errors_total counter increments with labels stage="tts", error_code="SYNTHESIS_FAILED"
3. **Given** processing is ongoing, **When** querying /metrics, **Then** sts_fragments_in_flight gauge shows current processing count, sts_gpu_utilization_percent shows GPU usage
4. **Given** a fragment is processed, **When** reviewing logs, **Then** all log entries include fragment_id, stream_id, sequence_number for correlation across components

---

### User Story 5 - Stream Lifecycle Management (Priority: P3)

An E2E test scenario where the worker manages stream lifecycle including initialization, pause/resume, and graceful shutdown. The Full STS Service responds appropriately to lifecycle events and provides accurate statistics on stream completion.

**Why this priority**: Lifecycle management ensures clean startup/shutdown and supports operational tasks (e.g., maintenance pauses). Core processing works without this, but it's important for production robustness.

**Independent Test**: Test stream init, pause, resume, end flow.
- **Unit test**: `test_session_store_lifecycle()` validates session state transitions; `test_statistics_accumulation()` validates stat tracking
- **Contract test**: `test_stream_ready_payload()`, `test_stream_complete_payload()` validate message schemas
- **Integration test**: `test_full_lifecycle_init_to_complete()` validates complete lifecycle; `test_pause_completes_inflight_rejects_new()` validates pause behavior
- **Success criteria**: stream:init validates config and returns stream:ready, pause prevents new fragments, stream:complete returns accurate stats, connection closes gracefully

**Acceptance Scenarios**:

1. **Given** worker connects and sends stream:init with valid config (source_language "en", target_language "es", voice_profile), **When** initialization completes, **Then** service responds with stream:ready containing session_id, max_inflight 3, capabilities
2. **Given** an active stream with 2 fragments in-flight, **When** worker sends stream:pause, **Then** service completes the 2 in-flight fragments but rejects new fragment:data with STREAM_PAUSED error
3. **Given** a paused stream, **When** worker sends stream:resume, **Then** service accepts new fragment:data normally
4. **Given** a stream has processed 50 fragments (45 success, 5 failed), **When** worker sends stream:end, **Then** service completes in-flight fragments and responds with stream:complete containing total_fragments 50, success_count 45, avg_processing_time_ms, then closes connection after 5s

---

### Edge Cases

- What happens when a fragment is received before stream:init? The service responds with STREAM_NOT_FOUND error (same as Echo STS).
- How does the system handle ASR detecting multiple speakers in a fragment? ASR returns segments with speaker labels; translation preserves all text; TTS synthesizes with configured voice (speaker diarization handled in future iteration).
- What happens when translated text is significantly longer than source text? TTS synthesis may exceed target duration; duration matching stretches audio. If variance is 0-10%, returns SUCCESS; if 10-20%, returns PARTIAL with warning; if >20%, returns FAILED with DURATION_MISMATCH_EXCEEDED.
- How does the system handle fragments with only music (no speech)? ASR (faster-whisper medium) returns empty segments; service returns success with empty transcript/translation; dubbed_audio contains silence or original audio (configurable fallback).
- What happens when translation API rate limit is exceeded? Translation component returns FAILED with retryable=true, error_code "RATE_LIMIT_EXCEEDED"; worker retries with exponential backoff (1s, 2s, 4s, 8s, 16s).
- How does the system handle GPU OOM (out of memory)? Service emits error event, marks stream as failed, requests worker to reconnect and reinitialize with lower max_inflight or chunk_duration_ms.
- What happens when backpressure exceeds critical threshold (>10 in-flight)? Service rejects new fragment:data with BACKPRESSURE_EXCEEDED error; worker must wait for backpressure recovery event before resuming.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Socket.IO Server (based on Echo STS)
- **FR-001**: Service MUST act as a Socket.IO server accepting WebSocket connections on configurable port (default 8000)
- **FR-002**: Service MUST accept all connections without authentication (no API keys required per spec 017 design decision)
- **FR-003**: Service MUST support X-Stream-ID and X-Worker-ID extra headers for connection identification
- **FR-004**: Service MUST implement Socket.IO ping/pong with 25s interval and 10s timeout
- **FR-005**: Service MUST implement all message types from spec 016: stream:init, fragment:data, fragment:ack, stream:pause/resume/end

#### Stream Initialization
- **FR-006**: Service MUST validate stream:init configuration (source_language, target_language, voice_profile, chunk_duration_ms, sample_rate_hz, channels, format)
- **FR-007**: Service MUST respond to stream:init with stream:ready containing session_id, max_inflight (default 3), capabilities
- **FR-008**: Service MUST reject invalid configurations with INVALID_CONFIG error (missing required fields, unsupported language pairs)
- **FR-009**: Service MUST initialize ASR, Translation, and TTS components during stream:init based on configuration

#### ASR Processing
- **FR-010**: Service MUST use faster-whisper medium model (1.5GB, ~3-4s latency, multi-language support, 3GB VRAM) for automatic speech recognition
- **FR-010a**: Service MUST load faster-whisper model once at startup and cache in memory (singleton pattern) for all streams
- **FR-011**: Service MUST transcribe audio fragments to text using source_language from stream config
- **FR-012**: Service MUST return empty transcript for silence/no-speech (status SUCCESS, not error)
- **FR-013**: Service MUST detect and handle ASR errors (timeout, model error) with appropriate error codes and retryable flag
- **FR-014**: Service MUST support domain hints for vocabulary priming (e.g., "sports", "general", "news")
- **FR-015**: Service MUST produce TranscriptAsset with absolute timestamps (stream timeline, not fragment-relative)

#### Translation Processing
- **FR-016**: Service MUST use DeepL API for text translation (primary provider, no local fallback in production)
- **FR-016a**: Service MUST fail translation with retryable=true when DeepL API is unavailable, rate limited, or times out
- **FR-016b**: Service MUST NOT fall back to local translation models in production (hard fail strategy)
- **FR-017**: Service MUST translate ASR transcript from source_language to target_language
- **FR-018**: Service MUST skip translation for empty transcripts (silence fragments)
- **FR-019**: Service MUST handle translation errors (API timeout, rate limit, invalid text) with appropriate error codes and retryable flag
- **FR-019a**: Service MUST return error.code "TRANSLATION_API_UNAVAILABLE" with retryable=true for DeepL API failures
- **FR-019b**: Service MUST return error.code "RATE_LIMIT_EXCEEDED" with retryable=true for DeepL rate limit errors
- **FR-020**: Service MUST preserve parent_asset_ids linking TranslationAsset to TranscriptAsset for lineage tracking

#### TTS Processing
- **FR-021**: Service MUST use Coqui TTS (XTTS v2) for text-to-speech synthesis
- **FR-021a**: Service MUST load voice profiles from JSON configuration file at startup (voices.json)
- **FR-021b**: Service MUST validate voice_profile from stream:init exists in voices.json and reject with INVALID_VOICE_PROFILE if not found
- **FR-022**: Service MUST synthesize translated text to audio using voice_profile from stream config
- **FR-023**: Service MUST apply duration matching to preserve A/V synchronization (target_duration_ms = original fragment duration)
- **FR-024**: Service MUST use rubberband for time-stretching to match target duration
- **FR-025**: Service MUST return SUCCESS status when duration variance is 0-10% (acceptable A/V sync)
- **FR-025a**: Service MUST return PARTIAL status when duration variance is 10-20% with warning "duration_variance_high" and include actual_variance_percent in metadata
- **FR-025b**: Service MUST return FAILED status with error.code "DURATION_MISMATCH_EXCEEDED" when duration variance exceeds 20% (unacceptable audio quality, retryable=false)
- **FR-026**: Service MUST skip TTS for empty translations (return silence or original audio based on config)
- **FR-027**: Service MUST handle TTS errors (synthesis failure, invalid text) with appropriate error codes and retryable flag

#### Fragment Processing Workflow
- **FR-028**: Service MUST respond to fragment:data with immediate fragment:ack (status "queued")
- **FR-029**: Service MUST process fragments through ASR → Translation → TTS pipeline
- **FR-030**: Service MUST emit fragment:processed in sequence_number order (in-order delivery)
- **FR-031**: Service MUST include processing_time_ms and stage_timings (asr_ms, translation_ms, tts_ms) in fragment:processed
- **FR-032**: Service MUST populate dubbed_audio with base64-encoded PCM audio matching output format from stream config
- **FR-033**: Service MUST include transcript (ASR output) and translated_text (Translation output) in fragment:processed for debugging
- **FR-034**: Service MUST track in-flight fragments per stream and enforce max_inflight limit

#### Error Handling
- **FR-035**: Service MUST return fragment:processed with status "failed" and error details when any stage fails
- **FR-036**: Service MUST set error.retryable to true for transient errors (timeout, network, rate limit)
- **FR-037**: Service MUST set error.retryable to false for permanent errors (invalid audio format, unsupported language, synthesis failure)
- **FR-038**: Service MUST include error.stage indicating which pipeline stage failed (asr, translation, tts)
- **FR-039**: Service MUST support fragment retry (idempotent processing by fragment_id)
- **FR-040**: Service MUST emit error events for fatal stream errors (GPU OOM, model load failure)

#### Flow Control and Backpressure
- **FR-041**: Service MUST monitor in-flight fragment count per stream
- **FR-042**: Service MUST emit backpressure events when in-flight count exceeds thresholds using hybrid monitoring + soft cap strategy
- **FR-042a**: Service MUST emit backpressure with severity="low", action="none" when in-flight count is 1-3 (normal operation)
- **FR-042b**: Service MUST emit backpressure with severity="medium", action="slow_down" when in-flight count is 4-6 and continue accepting fragments
- **FR-042c**: Service MUST emit backpressure with severity="high", action="pause" when in-flight count is 7-10 and continue accepting fragments
- **FR-042d**: Service MUST reject new fragment:data with error.code "BACKPRESSURE_EXCEEDED" when in-flight count exceeds 10 (critical threshold)
- **FR-043**: Service MUST include severity (low, medium, high), action (none, slow_down, pause), and current_inflight count in backpressure events
- **FR-044**: Service MUST emit backpressure recovery events when queue drains below threshold

#### Stream Lifecycle
- **FR-045**: Service MUST handle stream:pause by completing in-flight fragments and rejecting new ones with STREAM_PAUSED error
- **FR-046**: Service MUST handle stream:resume by accepting new fragments normally
- **FR-047**: Service MUST respond to stream:end with stream:complete containing statistics (total_fragments, success_count, failed_count, avg_processing_time_ms)
- **FR-048**: Service MUST auto-close connection 5 seconds after stream:complete

#### Observability
- **FR-049**: Service MUST expose Prometheus metrics at /metrics endpoint including: sts_fragment_processing_seconds (histogram), sts_fragments_in_flight (gauge), sts_fragment_errors_total (counter), sts_gpu_utilization_percent (gauge)
- **FR-050**: Service MUST emit structured logs with fragment_id, stream_id, sequence_number for correlation
- **FR-051**: Service MUST log processing timings per stage (ASR, Translation, TTS)
- **FR-052**: Service MUST track and log GPU memory utilization

#### Configuration
- **FR-053**: Service MUST be configurable via environment variables (port, model paths, API keys, processing limits)
- **FR-054**: Service MUST support configurable max_inflight per stream (default 3, range 1-10)
- **FR-055**: Service MUST support configurable timeout per fragment (default 8000ms)
- **FR-056**: Service MUST support configurable fallback mode (silence vs original audio) for empty translations

### Key Entities

- **Stream Session**: Active streaming session with configuration (source/target language, voice profile, audio format), state (initializing, active, paused, ending), statistics (total fragments, success/failure counts, avg processing time), and in-flight fragment tracker
- **Fragment**: Audio fragment with unique fragment_id, stream_id, sequence_number, timestamp, audio payload (PCM data), and processing state (queued, processing, completed, failed)
- **TranscriptAsset**: ASR output containing transcript text, segments with timestamps and speaker labels, confidence scores, and lineage (fragment_id, stream_id)
- **TranslationAsset**: Translation output containing translated text, source text, language pair, and lineage (parent TranscriptAsset reference)
- **AudioAsset**: TTS output containing dubbed audio (PCM bytes), audio metadata (sample rate, channels, duration), duration matching metadata (original duration, target duration, speed ratio), and lineage (parent TranslationAsset reference)
- **Backpressure State**: Current in-flight count, threshold levels, severity (low, medium, high), and action recommendation (none, slow_down, pause)
- **Processing Statistics**: Per-stream metrics including total fragments processed, success/failure counts, latency percentiles, error breakdown by stage and code

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Full pipeline (ASR→Translation→TTS) processes 6-second English audio fragment to Spanish dubbed audio in under 8 seconds (P95 latency, using faster-whisper medium model ~3-4s)
- **SC-002**: Dubbed audio duration variance is within ±10% of original audio duration for SUCCESS status (A/V sync preservation)
- **SC-002a**: Dubbed audio with 10-20% variance returns PARTIAL status with duration_variance_high warning
- **SC-002b**: Dubbed audio with >20% variance returns FAILED status with DURATION_MISMATCH_EXCEEDED error
- **SC-003**: ASR transcription accuracy is >90% for clear speech using faster-whisper medium model (measured against reference transcripts)
- **SC-004**: Translation quality is acceptable (BLEU score >30 or manual review confirms correctness)
- **SC-005**: Fragment:processed events are delivered in sequence_number order 100% of the time (in-order guarantee)
- **SC-006**: Service handles at least 3 concurrent streams without performance degradation (max_inflight=3 per stream)
- **SC-007**: Transient errors (timeout, rate limit) are correctly marked retryable=true; permanent errors are marked retryable=false (100% accuracy)
- **SC-008**: Backpressure events are emitted when in-flight fragments exceed max_inflight threshold
- **SC-009**: All Prometheus metrics are exposed and queryable; logs include fragment_id/stream_id for correlation
- **SC-010**: Service passes all E2E tests with 80% code coverage; critical paths (ASR, Translation, TTS) have 95% coverage

---

## Assumptions

- The service will be implemented in `apps/sts-service/src/sts_service/full/` as a new subpackage (separate from echo/)
- Python 3.10.x will be used consistent with project constitution
- Existing ASR, Translation, and TTS modules (specs 005, 006, 008) are functional and tested
- python-socketio library will be used for Socket.IO server implementation (same as Echo STS)
- GPU resources are available (RunPod pod with CUDA 11.8, sufficient VRAM for faster-whisper medium + Coqui TTS models, minimum 8GB VRAM recommended)
- DeepL API key is available via environment variable DEEPL_API_KEY (required, no fallback to local translation)
- Model files (faster-whisper medium, Coqui TTS XTTS v2) are pre-downloaded or cached on first use
- The service will run in Docker on RunPod with GPU passthrough
- Media-service acts as Socket.IO client and implements exponential backoff retry for retryable errors (implementation in spec 003 or future iteration)
- Rubberband CLI tool is available in Docker image for time-stretching
- Default language pair is English→Spanish; additional pairs require voice profile configuration in voices.json
- Voice profile JSON file (voices.json) and speaker WAV files are mounted as Docker volumes
- Backpressure thresholds are configurable but default to: low (1-3), medium (4-6), high (7-10), critical (>10)

---

## Dependencies

- [specs/016-websocket-audio-protocol.md](../016-websocket-audio-protocol.md) - WebSocket protocol that this service implements
- [specs/017-echo-sts-service/spec.md](../017-echo-sts-service/spec.md) - Socket.IO server foundation and event handling patterns
- [specs/005-audio-transcription-module.md](../005-audio-transcription-module.md) - ASR component interface and implementation
- [specs/006-translation-component/spec.md](../006-translation-component/spec.md) - Translation component interface and DeepL integration
- [specs/008-tts-module/spec.md](../008-tts-module/spec.md) - TTS component with Coqui TTS and duration matching
- [specs/004-sts-pipeline-design.md](../004-sts-pipeline-design.md) - Original STS pipeline design reference
- [specs/015-deployment-architecture.md](../015-deployment-architecture.md) - Deployment context for STS service on RunPod

---

## Out of Scope

- HTTP/REST API for fragment processing (spec 016 section 2 mentions this as alternative, but WebSocket is primary for this spec)
- Multi-speaker voice synthesis (speaker diarization handled in future iteration)
- Real-time voice cloning (voice_profile is pre-configured, not dynamically learned)
- Video processing or video-audio synchronization (audio-only pipeline)
- Persistent storage of fragments, transcripts, or dubbed audio (stateless service, data flows through)
- Load balancing across multiple STS pods (handled by RunPod infrastructure)
- Authentication and authorization (no auth required per spec 017 design decision)
- WebSocket transport fallback to HTTP polling (WebSocket only)
- Batch processing mode (real-time streaming only)
- Custom ASR/Translation/TTS model training (pre-trained models only)

---

## Technical Notes

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Full STS Service                         │
│  (apps/sts-service/src/sts_service/full/)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Socket.IO Server (server.py)                        │  │
│  │  - Event handlers (fragment:data, stream:init, etc.) │  │
│  │  - Session management (SessionStore)                 │  │
│  │  - Connection lifecycle                              │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                         │
│  ┌────────────────▼─────────────────────────────────────┐  │
│  │  Pipeline Coordinator (pipeline.py)                  │  │
│  │  - Orchestrates ASR → Translation → TTS             │  │
│  │  - Fragment tracking and in-order delivery          │  │
│  │  - Error handling and retry logic                   │  │
│  │  - Backpressure monitoring                          │  │
│  └────┬──────────┬──────────┬─────────────────────────┘  │
│       │          │          │                             │
│  ┌────▼───┐ ┌────▼────┐ ┌──▼──────┐                      │
│  │  ASR   │ │ Trans.  │ │  TTS    │                      │
│  │ Module │ │ Module  │ │ Module  │                      │
│  │(Whisper)│ │(DeepL) │ │(Coqui)  │                      │
│  │        │ │         │ │         │                      │
│  └────────┘ └─────────┘ └─────────┘                      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Observability (metrics.py, logging.py)              │  │
│  │  - Prometheus metrics                                │  │
│  │  - Structured logging                                │  │
│  │  - GPU monitoring                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Module Structure

```
apps/sts-service/src/sts_service/full/
├── __init__.py
├── __main__.py              # Entry point (python -m sts_service.full)
├── server.py                # Socket.IO server setup (similar to echo/server.py)
├── config.py                # Configuration management
├── session.py               # Session store (extends echo/session.py)
├── pipeline.py              # Pipeline coordinator (ASR→Translation→TTS)
├── handlers/
│   ├── __init__.py
│   ├── stream.py            # stream:init, pause, resume, end handlers
│   ├── fragment.py          # fragment:data handler, fragment:processed emission
│   └── lifecycle.py         # Connection lifecycle (connect, disconnect)
├── models/
│   ├── __init__.py
│   ├── stream.py            # Stream session models
│   ├── fragment.py          # Fragment models
│   └── error.py             # Error models
├── metrics.py               # Prometheus metrics
└── logging_config.py        # Structured logging setup
```

### Pipeline Flow

```
fragment:data received
    ↓
fragment:ack emitted (status: queued)
    ↓
Add to processing queue (in-order by sequence_number)
    ↓
┌─────────────────────────────────────────┐
│ Pipeline Coordinator                    │
├─────────────────────────────────────────┤
│ 1. Decode audio (base64 → PCM bytes)   │
│ 2. Call ASR.transcribe()                │
│    ├─ SUCCESS → transcript              │
│    └─ FAILED → return error             │
│ 3. Call Translation.translate()         │
│    ├─ SUCCESS → translated_text         │
│    └─ FAILED → return error             │
│ 4. Call TTS.synthesize()                │
│    ├─ SUCCESS → dubbed_audio (PCM)     │
│    ├─ PARTIAL → dubbed_audio (warning)  │
│    └─ FAILED → return error             │
│ 5. Encode audio (PCM → base64)         │
│ 6. Build fragment:processed payload     │
└─────────────────────────────────────────┘
    ↓
fragment:processed emitted (in sequence_number order)
    ↓
Update statistics, metrics, logs
```

### Error Handling Strategy

Each pipeline stage (ASR, Translation, TTS) returns an Asset object with status:
- **SUCCESS**: Processing succeeded, result available
- **PARTIAL**: Processing succeeded with warnings (e.g., clamped speed ratio)
- **FAILED**: Processing failed, error details included

The Pipeline Coordinator:
1. Checks asset status after each stage
2. If FAILED, constructs fragment:processed with error details and stops pipeline
3. If SUCCESS or PARTIAL, continues to next stage
4. Preserves parent_asset_ids for lineage tracking
5. Sets retryable flag based on error type (timeout=true, invalid_format=false)

### Reusing Echo STS Components

The Full STS Service reuses significant infrastructure from Echo STS (spec 017):
- **Socket.IO server setup** (server.py pattern, ASGI app factory)
- **Session management** (SessionStore, session state machine)
- **Event handler registration** pattern
- **Connection lifecycle** handlers (connect, disconnect)
- **Stream lifecycle** handlers (init, pause, resume, end) - extend with real processing
- **Fragment acknowledgment** logic (fragment:ack emission)

**Key Differences**:
- Fragment processing: Echo returns original audio; Full runs ASR→Translation→TTS
- Processing time: Echo is instant (<50ms); Full is 3-8 seconds
- Error handling: Full implements comprehensive error detection at each stage
- Backpressure: Full actively monitors GPU load and processing queue
- Metrics: Full tracks detailed pipeline metrics, GPU utilization

### Configuration Details

This section documents the clarified configuration decisions for the Full STS Service.

#### ASR Configuration (Clarification 1)

**Model Selection**: faster-whisper medium model

**Rationale**: Balances transcription accuracy with processing latency while supporting multi-language streams.

**Configuration**:
```python
# config.py or environment variables
ASR_MODEL = "medium"  # faster-whisper model size
ASR_MODEL_PATH = "/models/faster-whisper-medium"  # Pre-downloaded model location
ASR_DEVICE = "cuda"  # GPU acceleration
ASR_COMPUTE_TYPE = "float16"  # Precision for inference
```

**Performance Characteristics**:
- Model size: 1.5GB
- Expected latency: 3-4 seconds per 6-second fragment
- GPU VRAM usage: ~3GB
- Multi-language support: Yes (90+ languages)
- Transcription accuracy: >90% for clear speech

**Model Loading Strategy**: Singleton pattern - load once at service startup and cache in memory for all streams.

```python
# Pseudocode for model initialization
class ASRModule:
    _model_instance = None

    @classmethod
    def get_model(cls):
        if cls._model_instance is None:
            cls._model_instance = WhisperModel(
                model_size="medium",
                device="cuda",
                compute_type="float16"
            )
        return cls._model_instance
```

---

#### Translation Configuration (Clarification 2)

**Provider**: DeepL API (primary and only provider)

**Fallback Strategy**: Hard fail with retryable=true (no local model fallback in production)

**Rationale**: DeepL provides superior translation quality. Local models would add significant complexity, VRAM usage, and lower quality. Workers implement exponential backoff retry for transient failures.

**Configuration**:
```python
# config.py or environment variables
TRANSLATION_PROVIDER = "deepl"  # Primary provider
TRANSLATION_API_KEY = os.getenv("DEEPL_API_KEY")  # Required
TRANSLATION_TIMEOUT_MS = 5000  # API timeout
TRANSLATION_MAX_RETRIES = 0  # Service does not retry, worker retries
```

**Error Handling**:
- DeepL API unavailable → `error.code="TRANSLATION_API_UNAVAILABLE"`, `retryable=true`
- DeepL rate limit exceeded → `error.code="RATE_LIMIT_EXCEEDED"`, `retryable=true`
- DeepL API timeout → `error.code="TIMEOUT"`, `retryable=true`
- Invalid text (e.g., empty after ASR) → Skip translation, return SUCCESS with empty translation

**Worker Retry Strategy** (implemented by media-service):
```python
# Exponential backoff on retryable=true errors
retry_delays = [1s, 2s, 4s, 8s, 16s]  # Max 5 retries
```

---

#### TTS Voice Configuration (Clarification 3)

**Voice Profile Management**: JSON configuration file loaded at startup

**Rationale**: Provides flexibility to add voices without code changes while avoiding dynamic loading complexity during stream processing.

**Configuration File Structure** (voices.json):
```json
{
  "voices": {
    "spanish_male_1": {
      "model": "xtts_v2",
      "speaker_wav": "/models/voices/es_male_1.wav",
      "language": "es",
      "description": "Spanish male voice, neutral accent"
    },
    "spanish_female_1": {
      "model": "xtts_v2",
      "speaker_wav": "/models/voices/es_female_1.wav",
      "language": "es",
      "description": "Spanish female voice, neutral accent"
    },
    "spanish_male_sports": {
      "model": "xtts_v2",
      "speaker_wav": "/models/voices/es_male_sports.wav",
      "language": "es",
      "description": "Spanish male voice, energetic tone for sports commentary"
    }
  },
  "default_voice_per_language": {
    "es": "spanish_male_1",
    "fr": "french_male_1"
  }
}
```

**Loading Strategy**:
```python
# config.py
VOICE_PROFILES_PATH = "/config/voices.json"

# Load at startup
with open(VOICE_PROFILES_PATH) as f:
    voice_profiles = json.load(f)
```

**Stream Initialization Validation**:
```python
# handlers/stream.py - stream:init handler
def validate_voice_profile(voice_profile: str) -> bool:
    if voice_profile not in voice_profiles["voices"]:
        raise InvalidConfigError(
            code="INVALID_VOICE_PROFILE",
            message=f"Voice profile '{voice_profile}' not found in voices.json"
        )
```

**Docker Volume Mapping**:
```yaml
# docker-compose.yml
volumes:
  - ./config/voices.json:/config/voices.json:ro
  - ./models/voices:/models/voices:ro
```

---

#### Backpressure Configuration (Clarification 4)

**Strategy**: Hybrid monitoring + soft cap with hard limit

**Rationale**: Allows graceful degradation under load while preventing GPU memory exhaustion. Workers can respond to backpressure signals before hard rejection occurs.

**Thresholds**:
```python
# config.py
BACKPRESSURE_THRESHOLD_LOW = 3      # severity="low", action="none"
BACKPRESSURE_THRESHOLD_MEDIUM = 6   # severity="medium", action="slow_down"
BACKPRESSURE_THRESHOLD_HIGH = 10    # severity="high", action="pause"
BACKPRESSURE_THRESHOLD_CRITICAL = 10  # Reject with BACKPRESSURE_EXCEEDED
```

**Behavior by Threshold**:

| In-Flight Count | Severity | Action | Service Behavior | Worker Expected Response |
|----------------|----------|--------|------------------|--------------------------|
| 1-3 | low | none | Accept fragments normally | Send at normal rate |
| 4-6 | medium | slow_down | Accept + emit warning | Slow send rate by 50% |
| 7-10 | high | pause | Accept + emit critical warning | Pause new submissions |
| >10 | N/A | N/A | **Reject** with BACKPRESSURE_EXCEEDED | Wait for recovery event |

**Backpressure Event Schema**:
```json
{
  "event": "backpressure",
  "data": {
    "stream_id": "stream-123",
    "severity": "medium",
    "action": "slow_down",
    "current_inflight": 5,
    "max_inflight": 3,
    "threshold_exceeded": "medium"
  }
}
```

**Recovery Event**:
```json
{
  "event": "backpressure",
  "data": {
    "stream_id": "stream-123",
    "severity": "low",
    "action": "none",
    "current_inflight": 2,
    "max_inflight": 3,
    "threshold_exceeded": null
  }
}
```

---

#### Duration Matching Configuration (Clarification 5)

**Strategy**: Soft limit with graceful degradation (0-10% SUCCESS, 10-20% PARTIAL, >20% FAILED)

**Rationale**: Prevents unusable audio quality while allowing minor sync deviations. PARTIAL status alerts workers to potential sync issues without failing the fragment.

**Thresholds**:
```python
# config.py
DURATION_VARIANCE_SUCCESS_MAX = 0.10  # 10% variance → SUCCESS
DURATION_VARIANCE_PARTIAL_MAX = 0.20  # 20% variance → PARTIAL
# >20% variance → FAILED
```

**Calculation**:
```python
# pipeline.py - duration matching logic
def calculate_duration_variance(original_duration_ms: int, dubbed_duration_ms: int) -> float:
    variance = abs(dubbed_duration_ms - original_duration_ms) / original_duration_ms
    return variance

def determine_status_from_variance(variance: float) -> tuple[str, dict]:
    if variance <= DURATION_VARIANCE_SUCCESS_MAX:
        return "success", {}
    elif variance <= DURATION_VARIANCE_PARTIAL_MAX:
        return "partial", {
            "warning": "duration_variance_high",
            "actual_variance_percent": round(variance * 100, 2)
        }
    else:
        return "failed", {
            "error": {
                "stage": "tts",
                "code": "DURATION_MISMATCH_EXCEEDED",
                "message": f"Duration variance {variance*100:.1f}% exceeds acceptable limit",
                "retryable": False
            }
        }
```

**Fragment:processed Response Examples**:

SUCCESS (5% variance):
```json
{
  "status": "success",
  "dubbed_audio": "base64...",
  "metadata": {
    "original_duration_ms": 6000,
    "dubbed_duration_ms": 6300,
    "duration_variance_percent": 5.0,
    "speed_ratio": 0.95
  }
}
```

PARTIAL (15% variance):
```json
{
  "status": "partial",
  "dubbed_audio": "base64...",
  "warnings": ["duration_variance_high"],
  "metadata": {
    "original_duration_ms": 6000,
    "dubbed_duration_ms": 6900,
    "actual_variance_percent": 15.0,
    "speed_ratio": 0.87
  }
}
```

FAILED (25% variance):
```json
{
  "status": "failed",
  "error": {
    "stage": "tts",
    "code": "DURATION_MISMATCH_EXCEEDED",
    "message": "Duration variance 25.0% exceeds acceptable limit of 20%",
    "retryable": false
  },
  "metadata": {
    "original_duration_ms": 6000,
    "dubbed_duration_ms": 7500,
    "actual_variance_percent": 25.0
  }
}
```

---

### Testing Strategy

**Unit Tests** (apps/sts-service/tests/unit/full/):
- Pipeline coordinator orchestration logic
- Fragment ordering and in-order delivery
- Error propagation and retryable flag logic
- Backpressure threshold calculations
- Metrics emission

**Integration Tests** (apps/sts-service/tests/integration/full/):
- Full pipeline with real ASR, Translation, TTS components
- Duration matching accuracy (A/V sync validation)
- Error handling with real component failures
- Multi-fragment processing (ordering, latency)

**E2E Tests** (tests/e2e/):
- Complete flow: media-service → Full STS → dubbed output
- WebSocket protocol compliance (all message types)
- Backpressure response by media-service
- Connection resilience (reconnection after failure)
- Performance under load (concurrent streams)

**Contract Tests** (apps/sts-service/tests/contract/):
- fragment:processed payload schema validation
- stream:ready, stream:complete schema validation
- Error response schema validation
- Audio asset schema validation (dubbed_audio structure)

---

## Implementation Phases (Suggested)

### Phase 1: Pipeline Coordinator Foundation (P1)
- Implement pipeline.py with ASR→Translation→TTS orchestration
- Unit tests for coordinator logic (mocked components)
- Error propagation and retryable flag logic
- Asset lineage tracking (parent_asset_ids)

### Phase 2: Socket.IO Server Integration (P1)
- Extend Echo STS server.py for Full STS
- Implement fragment:data handler calling pipeline coordinator
- Implement fragment:processed emission with real data
- Integration tests with Socket.IO client

### Phase 3: In-Order Delivery and Fragment Tracking (P1)
- Implement fragment queue with sequence_number ordering
- Ensure fragment:processed events emitted in order
- Implement in-flight fragment tracking
- E2E tests validating ordering under concurrent load

### Phase 4: Error Handling and Retry (P1)
- Implement comprehensive error detection at each stage
- Set retryable flags correctly (transient vs permanent)
- Implement fragment retry (idempotent by fragment_id)
- E2E tests for error scenarios (timeout, API failure, etc.)

### Phase 5: Backpressure and Flow Control (P2)
- Implement in-flight monitoring and threshold checks
- Emit backpressure events with severity/action
- Integration tests with worker response
- Prevent GPU OOM under high load

### Phase 6: Observability (P2)
- Implement Prometheus metrics (latency, error rate, GPU util)
- Configure structured logging with fragment_id correlation
- Expose /metrics endpoint
- Integration tests querying metrics

### Phase 7: Stream Lifecycle (P3)
- Implement stream:pause/resume logic
- Implement stream:complete with statistics
- Auto-close connection after stream:complete
- E2E tests for full lifecycle

### Phase 8: Configuration and Deployment (P3)
- Environment variable configuration
- Docker image with GPU support, model caching
- Deployment documentation for RunPod
- Performance tuning (max_inflight, timeouts)

---

## Clarifications

This section documents decisions made during specification review on 2026-01-02.

### Clarification Session (2026-01-02)

**Q1: ASR Model Selection** - Which faster-whisper model size should be used?
- **Decision**: Use **medium model** (1.5GB, ~3-4s latency, 3GB VRAM)
- **Rationale**: Balances accuracy and latency while supporting multi-language streams
- **Loading Strategy**: Singleton pattern - load once at startup, cache for all streams

**Q2: Translation Fallback Strategy** - What happens when DeepL API fails?
- **Decision**: **Hard fail with retryable=true** (no local model fallback)
- **Rationale**: DeepL quality is critical; local models add complexity and lower quality
- **Worker Strategy**: Implements exponential backoff retry (1s, 2s, 4s, 8s, 16s)

**Q3: TTS Voice Configuration** - How are voice profiles configured?
- **Decision**: **JSON configuration file** (voices.json) loaded at startup
- **Rationale**: Flexibility to add voices without code changes, no dynamic loading complexity
- **Validation**: Stream:init validates voice_profile exists, rejects with INVALID_VOICE_PROFILE if not found

**Q4: Backpressure Thresholds** - What are exact thresholds and actions?
- **Decision**: **Hybrid approach** with monitoring + soft cap + hard limit
  - Low (1-3): severity="low", action="none"
  - Medium (4-6): severity="medium", action="slow_down", continue accepting
  - High (7-10): severity="high", action="pause", continue accepting
  - Critical (>10): **Reject** with BACKPRESSURE_EXCEEDED error
- **Rationale**: Gradual degradation before hard rejection, allows worker response time

**Q5: A/V Sync Duration Tolerance** - What happens when duration variance exceeds ±10%?
- **Decision**: **Soft limit with graceful degradation**
  - 0-10%: status="success" (acceptable A/V sync)
  - 10-20%: status="partial", warning="duration_variance_high" (potential sync issues)
  - >20%: status="failed", error.code="DURATION_MISMATCH_EXCEEDED" (unacceptable quality)
- **Rationale**: Allows minor variance while preventing unusable audio quality

---

## Open Questions

1. **Model Caching**: Should models be cached in memory (faster but more VRAM) or loaded per-stream (slower but more flexible)? (Recommendation: singleton model cache, loaded once on startup) - **RESOLVED: See Clarification Q1**

2. **Fallback Audio**: When TTS fails or translation is empty, should service return silence or original audio? (Recommendation: configurable via FALLBACK_MODE env var, default to silence for testing, original for production)

3. **GPU Allocation**: How should GPU resources be allocated across concurrent streams? (Recommendation: rely on PyTorch's automatic GPU memory management, limit max concurrent streams via config)

4. **Language Pair Support**: Should service validate supported language pairs on stream:init or allow any pair and fail during processing? (Recommendation: validate on init, return UNSUPPORTED_LANGUAGE_PAIR error immediately)

5. **Retry Logic**: Should service implement automatic retry for transient errors or rely on worker to retry? (Recommendation: worker retries, service is stateless and idempotent) - **RESOLVED: See Clarification Q2**

6. **Prometheus Metrics Port**: Should /metrics be on same port as Socket.IO or separate port? (Recommendation: same port via HTTP GET /metrics route, simpler deployment)
