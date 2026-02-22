# Feature Specification: Stream Worker Implementation

**Feature Branch**: `003-stream-worker`
**Created**: 2025-12-28
**Status**: Draft
**Parent Spec**: [`specs/003-gstreamer-stream-worker.md`](../003-gstreamer-stream-worker.md)
**Related Specs**:
- [`specs/011-stream-orchestration.md`](../011-stream-orchestration.md)
- [`specs/013-configuration-and-defaults.md`](../013-configuration-and-defaults.md)
- [`specs/017-echo-sts-service`](../017-echo-sts-service/spec.md) - Echo STS Service for E2E testing (Socket.IO protocol)

## Overview

This implementation spec focuses on building the GStreamer-based stream worker as defined in the parent specification (003). The worker pulls RTSP input from MediaMTX, processes audio through a remote STS Service API, and publishes the dubbed output back to MediaMTX via RTMP.

## Clarifications

### Session 2025-12-29

- Q: Maximum Socket.IO reconnection attempts before permanent failure? → A: 5 attempts with exponential backoff (2s, 4s, 8s, 16s, 32s)
- Q: How to handle in-flight fragments after successful reconnection? → A: Discard in-flight (fallback to original audio), resume with next new segment
- Q: Behavior when receiving backpressure event with action "slow_down"? → A: Insert recommended_delay_ms wait before each new fragment send
- Q: Which error types should increment circuit breaker failure counter? → A: Only retryable errors (TIMEOUT, MODEL_ERROR, GPU_OOM, QUEUE_FULL, RATE_LIMIT)

### What Exists

The current implementation in `apps/media-service/src/media_service/worker/stream_worker.py` provides:
- URL generation (RTSP input, RTMP output)
- Stream ID validation
- Retry logic with exponential backoff
- Worker state management (idle, connecting, running, stopped)
- Factory function to create worker from MediaMTX events

### What Needs Implementation

The following components are missing and must be implemented:

| Component | Description | Priority |
|-----------|-------------|----------|
| GStreamer Input Pipeline | RTSP pull, FLV demux to separate video (H.264) and audio (AAC) tracks | P1 |
| Segment Buffer | 6-second buffer for both video and audio tracks | P1 |
| Video Segment Writer | Write video segments to disk as MP4 files | P1 |
| Audio Segment Writer | Write audio segments as M4A files for STS transport | P1 |
| STS Socket.io Client | Socket.io client for real-time STS Service communication | P1 |
| GStreamer Output Pipeline | Remux dubbed audio + video segments to RTMP output | P1 |
| A/V Sync Mechanism | Timestamp management with configurable offset | P2 |
| Circuit Breaker | Protect against STS failures with fallback | P2 |
| Prometheus Metrics | Expose /metrics endpoint for observability | P3 |

## User Scenarios & Testing

### User Story 1 - GStreamer Pipeline Passthrough (Priority: P1)

The stream worker can pull an RTSP stream from MediaMTX, demux video and audio, and republish to RTMP output without audio processing (bypass mode).

**Why this priority**: This establishes the core GStreamer pipeline infrastructure that all other features depend on. Without this, no stream processing can occur.

**Independent Test**: Test with 1-min-nfl.mp4 fixture published to MediaMTX
- **Unit test**: `test_build_input_pipeline()` validates GStreamer pipeline string construction
- **Unit test**: `test_build_output_pipeline()` validates output pipeline construction
- **Contract test**: `test_rtsp_input_url_format()` validates URL matches MediaMTX expectations
- **Integration test**: `test_worker_passthrough_1min_nfl()` validates full passthrough with test fixture
- **Success criteria**: Video codec remains H.264 (no re-encode), audio AAC output matches input duration

**Acceptance Scenarios**:

1. **Given** MediaMTX is running with 1-min-nfl.mp4 published to `live/test/in`, **When** worker starts with `--stream-id test --sts-mode passthrough`, **Then** output appears at `live/test/out` within 5 seconds and plays without errors
2. **Given** worker is running in passthrough mode, **When** ffprobe inspects output stream, **Then** video codec is H.264 and audio codec is AAC
3. **Given** worker is running, **When** input stream ends, **Then** worker logs EOS and transitions to stopped state

---

### User Story 2 - Segment Buffering and Storage (Priority: P1)

The worker demuxes the incoming FLV stream into separate video (H.264) and audio (AAC) tracks, buffers them for 6 seconds, and writes segments to disk as MP4 (video) and M4A (audio) files.

**Why this priority**: Segment buffering creates the foundation for parallel video storage and audio processing. The STS service receives M4A segments directly - no PCM conversion needed.

**Independent Test**: Integration test with 1-min-nfl.mp4 fixture
- **Unit test**: `test_demuxer_separates_tracks()` validates FLV demux produces video and audio streams
- **Unit test**: `test_buffer_accumulates_6s()` validates 6-second buffering for both tracks
- **Unit test**: `test_video_segment_writer()` validates MP4 output with H.264 codec-copy
- **Unit test**: `test_audio_segment_writer()` validates M4A output with AAC codec-copy
- **Integration test**: `test_segment_pipeline_1min_nfl()` validates 10 segments from 60s fixture
- **Success criteria**: Segments are exactly 6s (+/- 100ms), MP4/M4A formats valid, timestamps preserved

**Acceptance Scenarios**:

1. **Given** FLV stream arrives from MediaMTX, **When** demuxer processes stream, **Then** video (H.264) and audio (AAC) tracks are separated without re-encoding
2. **Given** demuxer running, **When** 6 seconds of video accumulated, **Then** video segment is written to disk as MP4 file with correct PTS
3. **Given** demuxer running, **When** 6 seconds of audio accumulated, **Then** audio segment is written as M4A file ready for STS transport
4. **Given** stream ends mid-segment, **When** EOS signal received, **Then** partial segments are written with actual duration
5. **Given** video segment written, **When** corresponding dubbed audio arrives, **Then** segments can be remuxed for output

---

### User Story 3 - STS Socket.IO Client Integration (Priority: P1)

The worker connects to the remote STS Service via Socket.IO, implements the WebSocket Audio Fragment Protocol (spec 017), sends M4A audio segments for processing, and receives dubbed M4A audio responses in real-time.

**Protocol Reference**: See [`specs/017-echo-sts-service/contracts/`](../017-echo-sts-service/contracts/) for complete Socket.IO event schemas.

**Why this priority**: The STS service via Socket.IO is the core value proposition - it enables real-time bidirectional communication for low-latency dubbing.

**Independent Test**: Use Echo STS Service for deterministic testing (no GPU/ML dependencies)
- **Unit test**: `test_sts_client_connects()` validates Socket.IO connection establishment with X-Stream-ID and X-Worker-ID headers
- **Unit test**: `test_sts_client_stream_init()` validates stream:init emission and stream:ready reception
- **Unit test**: `test_sts_client_sends_fragment()` validates fragment:data emission with M4A audio
- **Unit test**: `test_sts_client_receives_ack()` validates fragment:ack reception
- **Unit test**: `test_sts_client_receives_dubbed()` validates fragment:processed reception with dubbed_audio
- **Unit test**: `test_sts_client_handles_backpressure()` validates response to backpressure events
- **Unit test**: `test_sts_client_reconnect_max_attempts()` validates 5 reconnection attempts with exponential backoff (2s, 4s, 8s, 16s, 32s)
- **Unit test**: `test_sts_client_inflight_discard_on_reconnect()` validates in-flight fragments fallback to original audio and are discarded after reconnect
- **Unit test**: `test_sts_client_slowdown_delay()` validates recommended_delay_ms is applied before sending each fragment during slow_down
- **Contract test**: `test_sts_socketio_events()` validates event names and payload schemas per spec 017 contracts
- **Integration test**: `test_sts_client_with_echo_service()` validates full Socket.IO round-trip with echo-sts-service
- **Success criteria**: Connection stable, stream lifecycle managed, segments sent/received correctly, correlation maintained via fragment_id and sequence_number

**Acceptance Scenarios**:

1. **Given** worker starts, **When** STS client initializes, **Then** Socket.IO connection established to WORKER_STS_SERVICE_URL with `X-Stream-ID` and `X-Worker-ID` extra headers
2. **Given** Socket.IO connected, **When** STS client emits `stream:init` event, **Then** payload contains stream_id, worker_id, config (source_language, target_language, format: "m4a"), max_inflight, timeout_ms
3. **Given** `stream:init` sent, **When** STS service responds, **Then** worker receives `stream:ready` with session_id, confirmed max_inflight, and capabilities
4. **Given** stream is ready, **When** worker has 6s M4A segment, **Then** STS client emits `fragment:data` with fragment_id, stream_id, sequence_number, timestamp, and audio object containing format, sample_rate_hz, channels, duration_ms, data_base64
5. **Given** `fragment:data` sent, **When** STS service receives it, **Then** worker receives `fragment:ack` with fragment_id and status "queued"
6. **Given** STS service processes segment, **When** `fragment:processed` event received with status "success", **Then** dubbed M4A (from dubbed_audio.data_base64) is stored and queued for remuxing
7. **Given** `fragment:processed` received, **When** worker applies dubbed audio, **Then** worker emits `fragment:ack` with fragment_id and status "applied"
8. **Given** STS service sends `backpressure` event with action "pause", **When** worker receives it, **Then** worker pauses sending new fragments until backpressure clears
9. **Given** STS service fails, **When** `fragment:processed` has status "failed" or timeout occurs, **Then** fallback to original audio segment and log warning
10. **Given** stream ends, **When** worker emits `stream:end`, **Then** worker receives `stream:complete` with statistics before connection closes
11. **Given** Socket.IO disconnects unexpectedly, **When** reconnection triggered, **Then** client attempts up to 5 reconnections with exponential backoff (2s, 4s, 8s, 16s, 32s)
12. **Given** Socket.IO disconnects with in-flight fragments, **When** reconnection succeeds, **Then** in-flight fragments are discarded (fallback audio used), and worker resumes with next new segment
13. **Given** STS sends backpressure with action "slow_down", **When** worker has next fragment ready, **Then** worker waits recommended_delay_ms before sending

---

### User Story 4 - A/V Synchronization (Priority: P2)

The worker maintains audio/video synchronization despite asynchronous STS processing latency.

**Why this priority**: A/V sync is critical for user experience but can be addressed after core pipeline works.

**Independent Test**: Verify sync with test fixture
- **Unit test**: `test_av_offset_calculation()` validates offset is applied correctly to PTS
- **Integration test**: `test_av_sync_within_threshold()` validates sync < 120ms with 1-min-nfl.mp4
- **Success criteria**: A/V sync delta remains < 120ms steady-state

**Acceptance Scenarios**:

1. **Given** initial buffering target is 6s, **When** first audio chunk processed, **Then** av_offset_ns equals 6_000_000_000
2. **Given** worker is running, **When** video_out_pts and audio_out_pts differ by > 120ms, **Then** metric av_sync_delta_ms reflects this
3. **Given** drift detected, **When** correction policy triggers, **Then** offset adjusts gradually (slew, not jump)

---

### User Story 5 - Circuit Breaker for STS Failures (Priority: P2)

The worker protects against STS Service failures using a circuit breaker pattern with automatic recovery.

**Why this priority**: Resilience is important for production but not required for initial functionality.

**Independent Test**: Simulate STS failures
- **Unit test**: `test_circuit_breaker_opens_after_failures()` validates breaker opens after 5 consecutive retryable errors
- **Unit test**: `test_circuit_breaker_ignores_non_retryable()` validates non-retryable errors (INVALID_CONFIG, INVALID_SEQUENCE) do not increment failure counter
- **Unit test**: `test_circuit_breaker_half_open()` validates cooldown and probe behavior
- **Unit test**: `test_circuit_breaker_closes_on_success()` validates recovery
- **Success criteria**: Breaker state transitions logged, fallback audio used when open

**Acceptance Scenarios**:

1. **Given** STS fails 5 consecutive times with retryable errors (TIMEOUT, MODEL_ERROR, GPU_OOM, QUEUE_FULL, RATE_LIMIT), **When** 6th request attempted, **Then** breaker is open and request skipped (fallback used)
2. **Given** breaker is open, **When** 30s cooldown expires, **Then** breaker enters half-open and allows 1 probe request
3. **Given** breaker is half-open and probe succeeds, **When** next request arrives, **Then** breaker closes and normal processing resumes
4. **Given** STS returns non-retryable error (INVALID_CONFIG, INVALID_SEQUENCE), **When** error received, **Then** breaker failure counter is NOT incremented

---

### User Story 6 - Prometheus Metrics Endpoint (Priority: P3)

The worker exposes a `/metrics` endpoint for Prometheus scraping with key observability metrics.

**Why this priority**: Observability is essential for production operations but not blocking for initial development.

**Independent Test**: Verify metrics format
- **Unit test**: `test_metrics_endpoint_returns_prometheus_format()` validates text/plain output
- **Unit test**: `test_sts_rtt_histogram_updated()` validates histogram buckets
- **Success criteria**: All required metrics exposed with correct types (counter, gauge, histogram)

**Acceptance Scenarios**:

1. **Given** worker is running, **When** GET /metrics requested, **Then** response is Prometheus text format with required metrics
2. **Given** worker processes 10 fragments, **When** metrics inspected, **Then** worker_audio_fragments_total shows 10
3. **Given** STS breaker is open, **When** metrics inspected, **Then** worker_sts_breaker_state equals 2

---

### Edge Cases

- What happens when RTSP connection drops mid-stream? Worker retries 3 times with exponential backoff (1s, 2s, 4s)
- What happens when STS returns audio with wrong duration? Sanitize (trim/pad) and use if valid, else fallback
- What happens when video buffers arrive before audio is ready? Video is buffered up to av_offset_ns before output
- What happens when input stream has no audio track? Worker logs error and exits (audio required for dubbing)
- What happens when MediaMTX RTMP publish fails? Worker logs error and exits with non-zero code for orchestrator restart
- What happens when Socket.IO disconnects unexpectedly? Worker attempts 5 reconnection attempts with exponential backoff (2s, 4s, 8s, 16s, 32s); in-flight fragments fallback to original audio; after successful reconnect, resume with next new segment
- What happens to in-flight fragments during disconnect? Discard them (use original audio fallback already applied) and resume with fresh sequence numbering after reconnect
- What happens when backpressure action is "slow_down"? Insert recommended_delay_ms wait before sending each new fragment
- What happens when INVALID_CONFIG error occurs? Log error and do NOT count toward circuit breaker (non-retryable error indicates client bug)

## Requirements

### Functional Requirements

**GStreamer Pipelines (P1)**

- **FR-001**: Worker MUST use GStreamer Python bindings (gi.repository) for pipeline construction
- **FR-002**: Input pipeline MUST use rtspsrc with `protocols=tcp` and configurable latency (default 200ms)
- **FR-003**: Input pipeline MUST demux FLV container into video (H.264) and audio (AAC) tracks WITHOUT re-encoding
- **FR-004**: Video track MUST be codec-copied (H.264 passthrough) to appsink for buffering
- **FR-005**: Audio track MUST be codec-copied (AAC passthrough) to appsink for buffering
- **FR-006**: Output pipeline MUST remux video (MP4 source) and audio (M4A dubbed or original) into FLV for RTMP
- **FR-007**: Output pipeline MUST use flvmux with `streamable=true` for RTMP output
- **FR-008**: All media processing MUST preserve original codec without transcoding (except final AAC for output)

**Segment Buffering and Storage (P1)**

- **FR-009**: Buffer MUST accumulate 6 seconds of video and audio separately (configurable via WORKER_SEGMENT_DURATION, default 6s)
- **FR-009a**: Video segments MUST be written to disk as MP4 files (H.264 codec-copy in MP4 container)
- **FR-009b**: Audio segments MUST be written to disk as M4A files (AAC codec-copy in MP4 container)
- **FR-010**: Each segment MUST include: fragment_id (uuid), stream_id, batch_number, t0_ns, duration_ns, file_path
- **FR-011**: Buffer MUST emit partial segment on EOS if accumulated data exists (minimum 1s)
- **FR-011a**: Segment files MUST be stored in WORKER_SEGMENT_DIR with naming: `{stream_id}/{batch_number:06d}_{video|audio}.{mp4|m4a}`

**STS Socket.IO Integration (P1)**

Per WebSocket Audio Fragment Protocol (see [`specs/017-echo-sts-service/contracts/`](../017-echo-sts-service/contracts/)):

**Connection (FR-012)**
- **FR-012a**: STS client MUST connect to STS service at WORKER_STS_SERVICE_URL via Socket.IO (WebSocket transport only)
- **FR-012b**: STS client MUST include `X-Stream-ID` and `X-Worker-ID` extra headers in connection handshake (alphanumeric plus hyphen/underscore, max 64 characters each)
- **FR-012c**: STS client MUST NOT require authentication (no API keys or tokens - service accepts all connections)
- **FR-012d**: STS client MUST support Socket.IO ping/pong (25s interval, 10s timeout)

**Stream Lifecycle (FR-013)**
- **FR-013a**: STS client MUST emit `stream:init` event on connection with: stream_id, worker_id, config (source_language, target_language, format: "m4a", sample_rate_hz: 48000, channels: 2 for stereo input), max_inflight (default 3), timeout_ms (default 8000)
- **FR-013a-timeout**: STS client MUST wait up to 10 seconds for `stream:ready` response; if not received, disconnect and trigger reconnection flow
- **FR-013b**: STS client MUST wait for `stream:ready` response before sending fragments (contains session_id, confirmed max_inflight, capabilities)
- **FR-013c**: STS client MUST support `stream:pause` and `stream:resume` for flow control
- **FR-013d**: STS client MUST emit `stream:end` when stream ends and wait for `stream:complete` with statistics

**Fragment Processing (FR-014)**
- **FR-014a**: STS client MUST emit `fragment:data` event with: fragment_id (UUID), stream_id, sequence_number (0-based monotonic), timestamp (Unix ms), audio object (format: "m4a", sample_rate_hz, channels, duration_ms, data_base64), optional metadata (pts_ns, source_pts_ns)
- **FR-014b**: STS client MUST receive and process `fragment:ack` response (status: "queued" or "processing")
- **FR-014c**: STS client MUST respect max_inflight limit - do not send more fragments than confirmed max_inflight

**Fragment Response Handling (FR-015)**
- **FR-015a**: STS client MUST listen for `fragment:processed` event containing: fragment_id, stream_id, sequence_number, status ("success", "partial", "failed"), dubbed_audio (format, sample_rate_hz, channels, duration_ms, data_base64), transcript, translated_text, processing_time_ms
- **FR-015b**: STS client MUST emit `fragment:ack` with status "applied" after successfully applying dubbed audio
- **FR-015c**: STS client MUST handle `backpressure` events by following recommended action:
  - `slow_down`: Insert recommended_delay_ms wait before sending each new fragment
  - `pause`: Stop sending new fragments until backpressure clears (via subsequent event with action "none")
  - `none`: Resume normal sending rate

**Error Handling and Timeouts (FR-016)**
- **FR-016a**: STS client MUST timeout individual fragments after WORKER_STS_TIMEOUT_MS (default 8000ms)
- **FR-016b**: On timeout, STS client MUST fallback to original audio segment and log warning
- **FR-016c**: STS client MUST handle `error` events with codes: STREAM_NOT_FOUND, INVALID_CONFIG, FRAGMENT_TOO_LARGE, TIMEOUT, MODEL_ERROR, GPU_OOM, QUEUE_FULL, INVALID_SEQUENCE, RATE_LIMIT
- **FR-016d**: STS client MUST respect `retryable` flag in error responses
- **FR-016e**: On disconnect, worker MUST fallback to original audio for all in-flight segments (fragments sent but not yet processed)
- **FR-016f**: On disconnect, worker MUST attempt reconnection with exponential backoff (2s, 4s, 8s, 16s, 32s) up to 5 attempts maximum
- **FR-016g**: After successful reconnection, worker MUST discard in-flight fragments (already using fallback audio per FR-016e), discard any partially accumulated buffer data, and resume with the next complete 6-second segment boundary using fresh sequence numbering starting from 0
- **FR-016h**: After 5 failed reconnection attempts, worker MUST transition to permanent failure state and exit with non-zero code for orchestrator restart

**A/V Synchronization (P2)**

- **FR-017**: Worker MUST apply av_offset_ns to both video and audio output PTS
- **FR-018**: Default av_offset_ns MUST be 6 seconds (matching segment duration for lower latency)
- **FR-019**: Worker MUST emit av_sync_delta_ms metric periodically
- **FR-020**: Sync drift correction MUST use gradual slew (not hard jumps)

**Circuit Breaker (P2)**

- **FR-021**: Breaker MUST open after 5 consecutive STS failures; only retryable errors count toward failure threshold (TIMEOUT, MODEL_ERROR, GPU_OOM, QUEUE_FULL, RATE_LIMIT); failure counter resets to 0 immediately upon any successful fragment:processed response
- **FR-021a**: Non-retryable errors (STREAM_NOT_FOUND, INVALID_CONFIG, FRAGMENT_TOO_LARGE, INVALID_SEQUENCE) MUST NOT increment circuit breaker failure counter
- **FR-022**: Breaker MUST enter half-open after 30s cooldown
- **FR-023**: Breaker MUST close on successful probe in half-open state
- **FR-024**: While open, breaker MUST skip STS calls and use fallback audio
- **FR-025**: Breaker state transitions MUST be logged with stream correlation

**Observability (P3)**

- **FR-026**: Worker MUST expose GET /metrics endpoint on configurable port
- **FR-027**: Worker MUST emit: worker_audio_fragments_total, worker_fallback_total, worker_gst_bus_errors_total
- **FR-028**: Worker MUST emit: worker_inflight_fragments, worker_av_sync_delta_ms, worker_sts_breaker_state
- **FR-029**: Worker MUST emit: worker_sts_rtt_ms histogram
- **FR-030**: All logs MUST include streamId, runId, instanceId per 013 spec

### Key Entities

- **VideoSegment**: Video segment metadata (fragment_id, batch_number, t0_ns, duration_ns, file_path to MP4)
- **AudioSegment**: Audio segment metadata (fragment_id, batch_number, t0_ns, duration_ns, file_path to M4A)
- **StreamInitEvent**: Socket.IO `stream:init` event payload (stream_id, worker_id, config: {source_language, target_language, voice_profile, chunk_duration_ms, sample_rate_hz, channels, format}, max_inflight, timeout_ms) - see [`stream-events.json`](../017-echo-sts-service/contracts/stream-events.json)
- **StreamReadyEvent**: Socket.IO `stream:ready` response (stream_id, session_id, max_inflight, capabilities: {batch_processing, async_delivery})
- **FragmentDataEvent**: Socket.IO `fragment:data` event payload (fragment_id, stream_id, sequence_number, timestamp, audio: {format, sample_rate_hz, channels, duration_ms, data_base64}, metadata: {pts_ns, source_pts_ns}) - see [`fragment-events.json`](../017-echo-sts-service/contracts/fragment-events.json)
- **FragmentProcessedEvent**: Socket.IO `fragment:processed` response (fragment_id, stream_id, sequence_number, status, dubbed_audio: {format, sample_rate_hz, channels, duration_ms, data_base64}, transcript, translated_text, processing_time_ms, stage_timings, error)
- **BackpressureEvent**: Socket.IO `backpressure` event (stream_id, severity, current_inflight, queue_depth, action, recommended_delay_ms)
- **StsErrorEvent**: Socket.IO `error` event (error_id, stream_id, fragment_id, code, message, severity, retryable, metadata) - see [`error-events.json`](../017-echo-sts-service/contracts/error-events.json)
- **CircuitBreaker**: State machine (closed, half_open, open) with failure counters and cooldown timer

## Success Criteria

### Measurable Outcomes

- **SC-001**: Worker processes 1-min-nfl.mp4 test fixture end-to-end without errors in passthrough mode
- **SC-002**: Video remains H.264 passthrough (verified by ffprobe codec inspection)
- **SC-003**: Audio output duration matches input duration (+/- 100ms)
- **SC-004**: A/V sync delta remains < 120ms steady-state during processing
- **SC-005**: All unit tests pass with 80% code coverage minimum
- **SC-006**: Integration tests complete successfully with MediaMTX + test fixture
- **SC-007**: Circuit breaker opens after 5 failures and recovers after cooldown
- **SC-008**: Metrics endpoint returns valid Prometheus format with all required metrics

## Test Fixtures and Verification

### Primary Test Fixture

- **File**: `tests/fixtures/test-streams/1-min-nfl.mp4`
- **Duration**: 60 seconds
- **Video**: H.264, resolution and framerate from fixture
- **Audio**: AAC, 48kHz stereo (verify or convert)

### Test Workflow

1. **Start MediaMTX** via docker-compose
2. **Publish test fixture** using `tests/fixtures/test-streams/ffmpeg-publish.sh` or `gstreamer-publish.sh`
3. **Run worker** with appropriate mode (passthrough for P1, enabled for full STS)
4. **Verify output** using ffplay/ffprobe on `rtmp://localhost:1935/live/test/out`
5. **Check metrics** via `curl http://localhost:8000/metrics`

### Echo STS Service for Testing

For deterministic testing without GPU/ML dependencies, use the Echo STS Service (spec 017):

```bash
# Start Echo STS Service via docker-compose
docker-compose -f apps/sts-service/docker-compose.yml up echo-sts

# Or run directly
python -m sts_service.echo --port 8080
```

The Echo STS Service implements the full WebSocket Audio Fragment Protocol:
- Echoes received audio back as `dubbed_audio`
- Supports all Socket.IO events: stream:init, stream:ready, fragment:data, fragment:ack, fragment:processed, etc.
- Provides configurable error simulation via `config:error_simulation` event
- Supports backpressure simulation for flow control testing

See [`specs/017-echo-sts-service/spec.md`](../017-echo-sts-service/spec.md) for full documentation.

## Implementation Gap Analysis

| Current Implementation | Gap | Action Required |
|------------------------|-----|-----------------|
| `StreamWorker.get_rtsp_input_url()` | No GStreamer pipeline | Implement `build_input_pipeline()` |
| `StreamWorker.get_rtmp_output_url()` | No GStreamer pipeline | Implement `build_output_pipeline()` |
| `StreamWorker.connect_with_retry()` | Placeholder `_connect_rtsp()` | Implement with real GStreamer |
| N/A | No audio chunker | Implement `Chunker` class |
| N/A | No STS client | Implement `StsClient` class |
| N/A | No circuit breaker | Implement `CircuitBreaker` class |
| N/A | No metrics endpoint | Implement with prometheus_client |

## Assumptions

- MediaMTX is running and accessible at configured host/port
- STS Service is available at WORKER_STS_SERVICE_URL via Socket.IO (Echo STS for testing, production STS for deployment)
- STS Service requires no authentication (per spec 017 design decision)
- Audio format for STS transport is M4A (AAC audio in MP4 container), NOT PCM
- GStreamer 1.x with Python bindings (gi.repository) is installed
- Test fixture 1-min-nfl.mp4 contains valid H.264 video and AAC audio tracks
- Python 3.10.x environment per monorepo constitution

## Dependencies

- **External**: GStreamer (gst-plugins-base, gst-plugins-good, gst-plugins-bad, gst-plugins-ugly)
- **Python**: PyGObject (gi), python-socketio (Socket.IO client), prometheus_client
- **Infrastructure**: MediaMTX container, STS Service (Echo STS for testing, production STS for deployment)
- **Specifications**:
  - [`specs/017-echo-sts-service/spec.md`](../017-echo-sts-service/spec.md) - Echo STS Service implementation
  - [`specs/017-echo-sts-service/contracts/stream-events.json`](../017-echo-sts-service/contracts/stream-events.json) - Stream lifecycle events
  - [`specs/017-echo-sts-service/contracts/fragment-events.json`](../017-echo-sts-service/contracts/fragment-events.json) - Fragment processing events
  - [`specs/017-echo-sts-service/contracts/error-events.json`](../017-echo-sts-service/contracts/error-events.json) - Error handling events
- **Test Fixtures**: tests/fixtures/test-streams/1-min-nfl.mp4, ffmpeg or gstreamer CLI tools
