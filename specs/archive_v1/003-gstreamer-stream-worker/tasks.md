# Tasks: Stream Worker Implementation

**Input**: Design documents from `/specs/003-gstreamer-stream-worker/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/

**Tests**: Tests are MANDATORY per Constitution Principle VIII. Every user story MUST have tests written FIRST before implementation. The tasks below enforce a test-first workflow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Fixture Reference**: `tests/fixtures/test-streams/1-min-nfl.mp4` (60s H.264 1280x720 30fps + AAC 44.1kHz stereo)

**Protocol Reference**: Socket.IO WebSocket Audio Fragment Protocol per `specs/017-echo-sts-service/contracts/`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- **Source**: `apps/media-service/src/media_service/`
- **Unit Tests**: `apps/media-service/tests/unit/`
- **Integration Tests**: `apps/media-service/tests/integration/`
- **Fixtures**: `tests/fixtures/test-streams/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency configuration

- [ ] T001 Add dependencies to `apps/media-service/pyproject.toml` (PyGObject>=3.44.0, python-socketio[asyncio]>=5.0, prometheus_client>=0.19.0)
- [ ] T002 [P] Create package structure for pipeline module in `apps/media-service/src/media_service/pipeline/__init__.py`
- [ ] T003 [P] Create package structure for buffer module in `apps/media-service/src/media_service/buffer/__init__.py`
- [ ] T004 [P] Create package structure for audio module in `apps/media-service/src/media_service/audio/__init__.py`
- [ ] T005 [P] Create package structure for video module in `apps/media-service/src/media_service/video/__init__.py`
- [ ] T006 [P] Create package structure for sts module in `apps/media-service/src/media_service/sts/__init__.py`
- [ ] T007 [P] Create package structure for sync module in `apps/media-service/src/media_service/sync/__init__.py`
- [ ] T008 [P] Create package structure for metrics module in `apps/media-service/src/media_service/metrics/__init__.py`
- [ ] T009 Create shared test fixtures in `apps/media-service/tests/conftest.py` (mock_gst, mock_socketio, sample_m4a_audio, mock_sts_fragment)
- [ ] T010 Update Dockerfile for GStreamer system dependencies in `apps/media-service/deploy/Dockerfile`

**Checkpoint**: Package structure ready for development (automated tests verify, continue automatically)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures and shared utilities that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T011 Implement VideoSegment and AudioSegment data models in `apps/media-service/src/media_service/models/segments.py`
- [ ] T012 [P] Write unit tests for VideoSegment data model in `apps/media-service/tests/unit/test_models_segments.py`
- [ ] T013 [P] Write unit tests for AudioSegment data model in `apps/media-service/tests/unit/test_models_segments.py`
- [ ] T014 Implement StreamConfig, InFlightFragment, FragmentDataPayload data models in `apps/media-service/src/media_service/sts/models.py`
- [ ] T015 [P] Write unit tests for StreamConfig model in `apps/media-service/tests/unit/test_sts_models.py`
- [ ] T016 [P] Write unit tests for InFlightFragment model in `apps/media-service/tests/unit/test_sts_models.py`
- [ ] T017 Implement CircuitBreaker and AvSyncState data models in `apps/media-service/src/media_service/models/state.py`
- [ ] T018 [P] Write unit tests for CircuitBreaker state transitions in `apps/media-service/tests/unit/test_models_state.py`
- [ ] T019 [P] Write unit tests for AvSyncState PTS adjustments in `apps/media-service/tests/unit/test_models_state.py`
- [ ] T020 Verify all foundational tests pass with `pytest apps/media-service/tests/unit/test_models*.py apps/media-service/tests/unit/test_sts_models.py -v`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel (automated tests verify, continue automatically)

---

## Phase 3: User Story 1 - GStreamer Pipeline Passthrough (Priority: P1) [MVP]

**Goal**: Establish input/output pipelines for RTSP-to-RTMP passthrough

**Independent Test**: Test with 1-min-nfl.mp4 fixture published to MediaMTX; verify video codec remains H.264 (no re-encode), audio AAC output matches input duration

### Tests for User Story 1 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US1**: 80% minimum (95% for critical paths)

- [ ] T021 [P] [US1] **Unit tests** for GStreamer element builders (rtspsrc, appsink, appsrc, flvmux caps) in `apps/media-service/tests/unit/test_elements.py`
  - Test `build_rtspsrc_element()` returns properly configured element
  - Test `build_appsink_element()` with correct caps (video H.264, audio AAC)
  - Test `build_appsrc_element()` with is-live=true, format=time
  - Test `build_flvmux_element()` with streamable=true
- [ ] T022 [P] [US1] **Unit tests** for input pipeline construction in `apps/media-service/tests/unit/test_input_pipeline.py`
  - Test `InputPipeline.build()` constructs valid GStreamer pipeline string
  - Test appsink callback registration for video and audio
  - Test pipeline state transitions (NULL -> READY -> PAUSED -> PLAYING)
  - Test error handling for invalid RTSP URL
- [ ] T023 [P] [US1] **Unit tests** for output pipeline construction in `apps/media-service/tests/unit/test_output_pipeline.py`
  - Test `OutputPipeline.build()` constructs valid GStreamer pipeline string
  - Test appsrc push_buffer functionality (mocked)
  - Test AAC encoding configuration
  - Test pipeline state management
- [ ] T024 [US1] **Contract test** for RTSP input URL format in `apps/media-service/tests/unit/test_input_pipeline.py`
  - Test URL matches MediaMTX expectations: `rtsp://host:port/path`
- [ ] T025 [US1] **Integration test** for passthrough with 1-min-nfl.mp4 in `apps/media-service/tests/integration/test_pipeline_passthrough.py`
  - Test full passthrough with MediaMTX + test fixture
  - Verify video codec remains H.264 (ffprobe inspection)
  - Verify audio output duration matches input (+/- 100ms)

**Verification**: Run `pytest apps/media-service/tests/unit/test_elements.py apps/media-service/tests/unit/test_input_pipeline.py apps/media-service/tests/unit/test_output_pipeline.py -v` - ALL tests MUST FAIL with "NotImplementedError" or similar

### Implementation for User Story 1

- [ ] T026 [P] [US1] Implement GStreamer element builders in `apps/media-service/src/media_service/pipeline/elements.py`
  - `build_rtspsrc_element(url, latency=200)` with protocols=tcp
  - `build_appsink_element(name, caps)` for video H.264 and audio AAC
  - `build_appsrc_element(name, caps, is_live=True)` for output
  - `build_flvmux_element()` with streamable=true
- [ ] T027 [US1] Implement InputPipeline class in `apps/media-service/src/media_service/pipeline/input.py`
  - Constructor takes rtsp_url, on_video_buffer, on_audio_buffer callbacks
  - `build()` method constructs pipeline with rtspsrc -> demux -> appsinks
  - Video and audio codec-copied (no re-encode)
  - `start()`, `stop()`, `get_state()` lifecycle methods
- [ ] T028 [US1] Implement OutputPipeline class in `apps/media-service/src/media_service/pipeline/output.py`
  - Constructor takes rtmp_url
  - `build()` method constructs pipeline with appsrcs -> flvmux -> rtmpsink
  - `push_video(buffer, pts_ns)` method
  - `push_audio(buffer, pts_ns)` method
  - `start()`, `stop()`, `get_state()` lifecycle methods
- [ ] T029 [US1] Add GStreamer bus error handling and logging in `apps/media-service/src/media_service/pipeline/input.py` and `apps/media-service/src/media_service/pipeline/output.py`
- [ ] T030 [US1] Verify unit tests pass with `pytest apps/media-service/tests/unit/test_elements.py apps/media-service/tests/unit/test_input_pipeline.py apps/media-service/tests/unit/test_output_pipeline.py -v`

**Checkpoint**: User Story 1 should be fully functional and testable independently (run automated tests, continue automatically)

---

## Phase 4: User Story 2 - Segment Buffering and Storage (Priority: P1)

**Goal**: Demux FLV into video (H.264) and audio (AAC), buffer 6 seconds, write to disk as MP4 (video) and M4A (audio) files

**Independent Test**: Integration test with 1-min-nfl.mp4 fixture; verify 10 segments from 60s stream, segments exactly 6s (+/- 100ms)

### Tests for User Story 2 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US2**: 90% (segment integrity critical)

- [ ] T031 [P] [US2] **Unit tests** for SegmentBuffer accumulation in `apps/media-service/tests/unit/test_segment_buffer.py`
  - Test `test_buffer_accumulates_6s_video()` - video buffers accumulated to 6 seconds
  - Test `test_buffer_accumulates_6s_audio()` - audio buffers accumulated to 6 seconds
  - Test `test_buffer_emits_video_segment()` - VideoSegment returned after 6s
  - Test `test_buffer_emits_audio_segment()` - AudioSegment returned after 6s
  - Test `test_buffer_preserves_pts()` - t0_ns captured from first buffer
  - Test `test_buffer_increments_batch_number()` - sequential batch numbers
- [ ] T032 [P] [US2] **Unit tests** for SegmentBuffer edge cases in `apps/media-service/tests/unit/test_segment_buffer.py`
  - Test `test_buffer_handles_eos_partial_segment()` - partial segment emitted on EOS (minimum 1s)
  - Test `test_buffer_rejects_short_partial()` - partial < 1s discarded
  - Test `test_buffer_handles_variable_buffer_sizes()` - varying buffer durations
  - Test `test_buffer_resets_on_flush()` - flush clears accumulated data
- [ ] T033 [P] [US2] **Unit tests** for VideoSegmentWriter in `apps/media-service/tests/unit/test_video_segment_writer.py`
  - Test `test_video_writer_creates_mp4()` - valid MP4 file created
  - Test `test_video_writer_codec_copy()` - H.264 codec-copied (no re-encode)
  - Test `test_video_writer_correct_path()` - path matches `{stream_id}/{batch:06d}_video.mp4`
  - Test `test_video_writer_updates_file_size()` - file_size populated after write
- [ ] T034 [P] [US2] **Unit tests** for AudioSegmentWriter in `apps/media-service/tests/unit/test_audio_segment_writer.py`
  - Test `test_audio_writer_creates_m4a()` - valid M4A file created
  - Test `test_audio_writer_codec_copy()` - AAC codec-copied (no re-encode)
  - Test `test_audio_writer_correct_path()` - path matches `{stream_id}/{batch:06d}_audio.m4a`
  - Test `test_audio_writer_updates_file_size()` - file_size populated after write
- [ ] T035 [US2] **Integration test** for segment pipeline in `apps/media-service/tests/integration/test_segment_pipeline.py`
  - Test with 1-min-nfl.mp4 fixture via MediaMTX
  - Verify 10 video segments and 10 audio segments created
  - Verify segments are 6s (+/- 100ms)
  - Verify MP4/M4A formats valid (ffprobe verification)

**Verification**: Run `pytest apps/media-service/tests/unit/test_segment_buffer.py apps/media-service/tests/unit/test_video_segment_writer.py apps/media-service/tests/unit/test_audio_segment_writer.py -v` - ALL tests MUST FAIL before implementation

### Implementation for User Story 2

- [ ] T036 [US2] Implement SegmentBuffer class in `apps/media-service/src/media_service/buffer/segment_buffer.py`
  - Constructor takes stream_id, segment_duration_ns=6_000_000_000, segment_dir
  - `push_video(buffer_data: bytes, pts_ns: int, duration_ns: int) -> VideoSegment | None`
  - `push_audio(buffer_data: bytes, pts_ns: int, duration_ns: int) -> AudioSegment | None`
  - `flush_video() -> VideoSegment | None` - emit partial on EOS (minimum 1s)
  - `flush_audio() -> AudioSegment | None` - emit partial on EOS (minimum 1s)
  - Auto-generates fragment_id (UUID) and increments batch_number
- [ ] T037 [P] [US2] Implement VideoSegmentWriter class in `apps/media-service/src/media_service/video/segment_writer.py`
  - `async write(segment: VideoSegment, video_data: bytes) -> VideoSegment`
  - Creates directory if not exists
  - Writes MP4 with H.264 codec-copy using GStreamer
  - Updates segment.file_size after write
- [ ] T038 [P] [US2] Implement AudioSegmentWriter class in `apps/media-service/src/media_service/audio/segment_writer.py`
  - `async write(segment: AudioSegment, audio_data: bytes) -> AudioSegment`
  - Creates directory if not exists
  - Writes M4A with AAC codec-copy using GStreamer
  - Updates segment.file_size after write
- [ ] T039 [US2] Verify unit tests pass with `pytest apps/media-service/tests/unit/test_segment_buffer.py apps/media-service/tests/unit/test_video_segment_writer.py apps/media-service/tests/unit/test_audio_segment_writer.py -v`

**Checkpoint**: User Story 2 should be fully functional and testable independently (run automated tests, continue automatically)

---

## Phase 5: User Story 3 - STS Socket.IO Client Integration (Priority: P1)

**Goal**: Real-time STS communication via Socket.IO using WebSocket Audio Fragment Protocol (spec 017)

**Independent Test**: Use Echo STS Service for deterministic testing; verify stream lifecycle, fragment round-trip, backpressure handling, reconnection

### Tests for User Story 3 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US3**: 95% (critical real-time communication path)

#### Connection and Headers Tests

- [ ] T040 [P] [US3] **Unit tests** for StsSocketIOClient connection in `apps/media-service/tests/unit/test_sts_socketio_client.py`
  - Test `test_sts_client_connects()` - Socket.IO connection established
  - Test `test_sts_client_uses_websocket_transport()` - transports=['websocket'] only
  - Test `test_sts_client_includes_headers()` - X-Stream-ID and X-Worker-ID in extra_headers
  - Test `test_sts_client_no_auth_required()` - no API key/token needed

#### Stream Lifecycle Tests

- [ ] T041 [P] [US3] **Unit tests** for stream lifecycle in `apps/media-service/tests/unit/test_sts_socketio_client.py`
  - Test `test_sts_client_stream_init()` - emits stream:init with stream_id, worker_id, config, max_inflight, timeout_ms
  - Test `test_sts_client_waits_for_stream_ready()` - blocks until stream:ready received
  - Test `test_sts_client_stream_init_timeout()` - disconnects after 10s if no stream:ready (FR-013a-timeout)
  - Test `test_sts_client_stores_session_id()` - session_id from stream:ready stored
  - Test `test_sts_client_respects_confirmed_max_inflight()` - uses server-confirmed max_inflight
  - Test `test_sts_client_stream_pause()` - emits stream:pause and stops sending new fragments (FR-013c)
  - Test `test_sts_client_stream_resume()` - emits stream:resume and resumes sending fragments (FR-013c)
  - Test `test_sts_client_stream_end()` - emits stream:end on graceful shutdown
  - Test `test_sts_client_receives_stream_complete()` - processes stream:complete with statistics

#### Fragment Processing Tests

- [ ] T042 [P] [US3] **Unit tests** for fragment sending in `apps/media-service/tests/unit/test_sts_socketio_client.py`
  - Test `test_sts_client_sends_fragment()` - emits fragment:data with correct payload
  - Test `test_sts_client_fragment_payload_schema()` - payload matches fragment-events.json schema
  - Test `test_sts_client_encodes_m4a_base64()` - audio.data_base64 correctly encoded
  - Test `test_sts_client_increments_sequence_number()` - 0-based monotonic sequence
  - Test `test_sts_client_includes_pts_metadata()` - metadata.pts_ns from segment.t0_ns
  - Test `test_sts_client_respects_max_inflight()` - waits when at max_inflight limit

- [ ] T043 [P] [US3] **Unit tests** for fragment acknowledgment in `apps/media-service/tests/unit/test_sts_socketio_client.py`
  - Test `test_sts_client_receives_fragment_ack()` - processes fragment:ack with status queued/processing
  - Test `test_sts_client_tracks_inflight()` - fragment added to in-flight map on send
  - Test `test_sts_client_removes_inflight_on_processed()` - fragment removed when fragment:processed received

- [ ] T044 [P] [US3] **Unit tests** for fragment:processed handling in `apps/media-service/tests/unit/test_sts_socketio_client.py`
  - Test `test_sts_client_receives_dubbed_audio()` - dubbed_audio.data_base64 decoded
  - Test `test_sts_client_handles_success_status()` - success triggers dubbed audio callback
  - Test `test_sts_client_handles_partial_status()` - partial uses available dubbed audio
  - Test `test_sts_client_handles_failed_status()` - failed triggers fallback callback
  - Test `test_sts_client_emits_applied_ack()` - emits fragment:ack with status "applied" after applying

#### Backpressure Handling Tests

- [ ] T045 [P] [US3] **Unit tests** for backpressure handling in `apps/media-service/tests/unit/test_backpressure_handler.py`
  - Test `test_backpressure_slow_down()` - inserts recommended_delay_ms before each send
  - Test `test_backpressure_pause()` - pauses all fragment sending
  - Test `test_backpressure_none()` - resumes normal sending rate
  - Test `test_backpressure_updates_delay()` - delay updated on each backpressure event

#### Reconnection Logic Tests

- [ ] T046 [P] [US3] **Unit tests** for reconnection manager in `apps/media-service/tests/unit/test_reconnection_manager.py`
  - Test `test_reconnect_exponential_backoff()` - delays are 2s, 4s, 8s, 16s, 32s
  - Test `test_reconnect_max_attempts()` - gives up after 5 attempts
  - Test `test_reconnect_resets_on_success()` - attempt counter reset after successful connect
  - Test `test_reconnect_raises_after_max()` - raises StsConnectionError after 5 failures

- [ ] T047 [P] [US3] **Unit tests** for in-flight handling on disconnect in `apps/media-service/tests/unit/test_sts_socketio_client.py`
  - Test `test_sts_client_inflight_fallback_on_disconnect()` - all in-flight fragments trigger fallback
  - Test `test_sts_client_clears_inflight_on_disconnect()` - in-flight map cleared
  - Test `test_sts_client_resets_sequence_on_reconnect()` - sequence_number reset to 0

#### Fragment Timeout Tests

- [ ] T048 [P] [US3] **Unit tests** for fragment tracker timeout in `apps/media-service/tests/unit/test_fragment_tracker.py`
  - Test `test_fragment_timeout_triggers_fallback()` - timeout after 8000ms triggers fallback
  - Test `test_fragment_timeout_configurable()` - respects WORKER_STS_TIMEOUT_MS
  - Test `test_fragment_timeout_cancelled_on_processed()` - timeout task cancelled when processed received

#### Contract Tests

- [ ] T049 [US3] **Contract tests** for Socket.IO events in `apps/media-service/tests/unit/test_sts_contracts.py`
  - Test stream:init payload matches stream-events.json schema
  - Test fragment:data payload matches fragment-events.json schema
  - Test fragment:ack (worker to STS) payload matches fragment-events.json schema
  - Test backpressure handling matches action enum values

#### Integration Tests

- [ ] T050 [US3] **Integration test** for full Socket.IO round-trip in `apps/media-service/tests/integration/test_sts_socketio_echo.py`
  - Test with Echo STS Service
  - Verify stream:init -> stream:ready lifecycle
  - Verify fragment:data -> fragment:ack -> fragment:processed round-trip
  - Verify dubbed audio received matches sent audio (echo behavior)
  - Verify fragment:ack with status "applied" sent after processing

- [ ] T051 [US3] **Integration test** for backpressure handling in `apps/media-service/tests/integration/test_sts_socketio_echo.py`
  - Configure Echo STS error simulation for backpressure
  - Verify slow_down delay is applied
  - Verify pause stops sending

- [ ] T052 [US3] **Integration test** for reconnection in `apps/media-service/tests/integration/test_sts_socketio_echo.py`
  - Simulate disconnect during processing
  - Verify in-flight fragments use fallback audio
  - Verify reconnection with exponential backoff
  - Verify fresh sequence numbering after reconnect

**Verification**: Run `pytest apps/media-service/tests/unit/test_sts_socketio_client.py apps/media-service/tests/unit/test_backpressure_handler.py apps/media-service/tests/unit/test_reconnection_manager.py apps/media-service/tests/unit/test_fragment_tracker.py apps/media-service/tests/unit/test_sts_contracts.py -v` - ALL tests MUST FAIL before implementation

### Implementation for User Story 3

- [ ] T053 [US3] Implement StsSocketIOClient class in `apps/media-service/src/media_service/sts/socketio_client.py`
  - Constructor takes url, stream_id, worker_id, config: StreamConfig, max_inflight=3, timeout_ms=8000, max_reconnect_attempts=5
  - Uses `socketio.AsyncClient(reconnection=False)` for custom reconnection logic
  - `async connect()` - connects with extra_headers={'X-Stream-ID', 'X-Worker-ID'}, transports=['websocket']
  - `async _init_stream()` - emits stream:init, waits for stream:ready
  - `async send_fragment(segment: AudioSegment) -> None` - emits fragment:data
  - `async end_stream()` - emits stream:end, waits for stream:complete
  - `async disconnect()` - graceful disconnect
  - Callbacks: on_dubbed_audio, on_fallback

- [ ] T054 [US3] Implement event handlers in `apps/media-service/src/media_service/sts/socketio_client.py`
  - `_on_stream_ready(data)` - stores session_id, updates max_inflight
  - `_on_fragment_ack(data)` - logs ack status
  - `_on_fragment_processed(data)` - decodes dubbed_audio, invokes callback, emits applied ack
  - `_on_backpressure(data)` - updates backpressure state
  - `_on_error(data)` - logs error, triggers fallback if fragment-specific
  - `_on_disconnect(reason)` - triggers reconnection flow
  - `async pause_stream(reason: str = None)` - emits stream:pause, sets internal paused flag (FR-013c)
  - `async resume_stream()` - emits stream:resume, clears paused flag (FR-013c)

- [ ] T055 [US3] Implement FragmentTracker class in `apps/media-service/src/media_service/sts/fragment_tracker.py`
  - `add(fragment_id: str, segment: AudioSegment, sequence_number: int)` - tracks in-flight fragment
  - `remove(fragment_id: str) -> InFlightFragment | None` - removes and returns fragment
  - `get(fragment_id: str) -> InFlightFragment | None` - retrieves without removing
  - `get_all() -> list[InFlightFragment]` - returns all in-flight fragments
  - `clear() -> list[InFlightFragment]` - clears all and returns them for fallback
  - Starts timeout task per fragment, cancelled on remove

- [ ] T056 [US3] Implement BackpressureHandler class in `apps/media-service/src/media_service/sts/backpressure_handler.py`
  - `update(action: str, recommended_delay_ms: int)` - updates state based on backpressure event
  - `async apply_delay()` - waits recommended_delay_ms if slow_down, returns immediately if none
  - `is_paused() -> bool` - returns True if pause action active
  - `clear()` - resets to normal state

- [ ] T057 [US3] Implement ReconnectionManager class in `apps/media-service/src/media_service/sts/reconnection_manager.py`
  - Constructor takes max_attempts=5, backoff_delays=[2, 4, 8, 16, 32]
  - `async attempt_reconnect(connect_fn: Callable) -> bool` - attempts reconnection with backoff
  - `reset()` - resets attempt counter on successful connect
  - Raises StsConnectionError after max attempts

- [ ] T058 [US3] Wire StsSocketIOClient into WorkerRunner fragment processing flow
  - Apply backpressure delay before sending
  - Track in-flight fragments
  - Handle fragment:processed callback to queue for remuxing
  - Handle fallback callback to use original audio

- [ ] T059 [US3] Verify unit tests pass with `pytest apps/media-service/tests/unit/test_sts_socketio_client.py apps/media-service/tests/unit/test_backpressure_handler.py apps/media-service/tests/unit/test_reconnection_manager.py apps/media-service/tests/unit/test_fragment_tracker.py -v`

**Checkpoint**: User Story 3 should be fully functional and testable independently (run automated tests, continue automatically)

---

## Phase 6: User Story 4 - A/V Synchronization (Priority: P2)

**Goal**: Maintain audio/video synchronization despite asynchronous STS processing latency

**Independent Test**: Verify sync with test fixture; A/V sync delta remains < 120ms steady-state

### Tests for User Story 4 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US4**: 95% (critical for user experience)

- [ ] T060 [P] [US4] **Unit tests** for AvSync PTS calculations in `apps/media-service/tests/unit/test_av_sync.py`
  - Test `test_av_offset_calculation()` - default 6s offset applied
  - Test `test_pts_adjustment_video()` - video PTS increased by offset
  - Test `test_pts_adjustment_audio()` - audio PTS increased by offset
  - Test `test_configurable_offset()` - custom offset respected
- [ ] T061 [P] [US4] **Unit tests** for AvSync drift detection in `apps/media-service/tests/unit/test_av_sync.py`
  - Test `test_drift_detection()` - detects when delta > threshold
  - Test `test_sync_delta_metric()` - sync_delta_ns updated correctly
  - Test `test_needs_correction()` - returns true when > 120ms
- [ ] T062 [US4] **Integration test** for A/V sync with pipeline in `apps/media-service/tests/integration/test_av_sync_integration.py`
  - Test with 1-min-nfl.mp4 fixture
  - Verify sync delta < 120ms steady-state
  - Verify gradual slew correction (not hard jumps)

**Verification**: Run `pytest apps/media-service/tests/unit/test_av_sync.py -v` - ALL tests MUST FAIL before implementation

### Implementation for User Story 4

- [ ] T063 [US4] Implement AvSync class in `apps/media-service/src/media_service/sync/av_sync.py`
  - Constructor takes av_offset_ns=6_000_000_000, drift_threshold_ns=120_000_000
  - `adjust_video_pts(original_pts: int) -> int`
  - `adjust_audio_pts(original_pts: int) -> int`
  - `update_sync_state(video_pts: int, audio_pts: int)` - updates delta
  - `needs_correction() -> bool` - checks if drift exceeds threshold
  - `apply_slew_correction(amount_ns: int)` - gradual adjustment
- [ ] T064 [US4] Add sync delta metric reporting in `apps/media-service/src/media_service/sync/av_sync.py`
- [ ] T065 [US4] Verify unit tests pass with `pytest apps/media-service/tests/unit/test_av_sync.py -v`

**Checkpoint**: User Story 4 should be fully functional and testable independently (run automated tests, continue automatically)

---

## Phase 7: User Story 5 - Circuit Breaker for STS Failures (Priority: P2)

**Goal**: Protect against STS Service failures with automatic recovery, only counting retryable errors

**Independent Test**: Simulate STS failures; verify breaker opens after 5 consecutive retryable errors, non-retryable errors do not affect breaker

### Tests for User Story 5 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US5**: 90% (resilience logic)

- [ ] T066 [P] [US5] **Unit tests** for CircuitBreaker state transitions in `apps/media-service/tests/unit/test_circuit_breaker.py`
  - Test `test_circuit_breaker_opens_after_retryable_failures()` - opens after 5 retryable errors
  - Test `test_circuit_breaker_half_open_after_cooldown()` - transitions after 30s
  - Test `test_circuit_breaker_closes_on_success()` - closes on successful probe
  - Test `test_circuit_breaker_reopens_on_failed_probe()` - half_open -> open

- [ ] T067 [P] [US5] **Unit tests** for error classification in `apps/media-service/tests/unit/test_circuit_breaker.py`
  - Test `test_circuit_breaker_counts_timeout()` - TIMEOUT increments counter
  - Test `test_circuit_breaker_counts_model_error()` - MODEL_ERROR increments counter
  - Test `test_circuit_breaker_counts_gpu_oom()` - GPU_OOM increments counter
  - Test `test_circuit_breaker_counts_queue_full()` - QUEUE_FULL increments counter
  - Test `test_circuit_breaker_counts_rate_limit()` - RATE_LIMIT increments counter
  - Test `test_circuit_breaker_ignores_invalid_config()` - INVALID_CONFIG does NOT increment counter
  - Test `test_circuit_breaker_ignores_invalid_sequence()` - INVALID_SEQUENCE does NOT increment counter
  - Test `test_circuit_breaker_ignores_stream_not_found()` - STREAM_NOT_FOUND does NOT increment counter
  - Test `test_circuit_breaker_ignores_fragment_too_large()` - FRAGMENT_TOO_LARGE does NOT increment counter

- [ ] T068 [P] [US5] **Unit tests** for CircuitBreaker request decisions in `apps/media-service/tests/unit/test_circuit_breaker.py`
  - Test `test_should_allow_request_when_closed()` - returns True
  - Test `test_should_allow_request_when_half_open()` - returns True (probe)
  - Test `test_should_not_allow_request_when_open()` - returns False
  - Test `test_fallback_counter_increments_when_open()` - tracks fallbacks

- [ ] T069 [P] [US5] **Unit tests** for CircuitBreaker with StsClient in `apps/media-service/tests/unit/test_circuit_breaker.py`
  - Test `test_fallback_audio_used_when_open()` - original audio returned
  - Test `test_breaker_wraps_sts_client()` - integrates with StsSocketIOClient

- [ ] T070 [US5] **Integration test** for circuit breaker recovery in `apps/media-service/tests/integration/test_circuit_breaker_integration.py`
  - Use Echo STS error simulation to inject failures
  - Test full recovery cycle: closed -> open -> half_open -> closed
  - Test fallback audio used during open state
  - Test state transitions logged with stream correlation

**Verification**: Run `pytest apps/media-service/tests/unit/test_circuit_breaker.py -v` - ALL tests MUST FAIL before implementation

### Implementation for User Story 5

- [ ] T071 [US5] Implement CircuitBreakerWrapper class in `apps/media-service/src/media_service/sts/circuit_breaker.py`
  - Constructor takes sts_client: StsSocketIOClient, failure_threshold=5, cooldown_seconds=30
  - Class constants: RETRYABLE_ERRORS = {"TIMEOUT", "MODEL_ERROR", "GPU_OOM", "QUEUE_FULL", "RATE_LIMIT"}
  - Class constants: NON_RETRYABLE_ERRORS = {"STREAM_NOT_FOUND", "INVALID_CONFIG", "FRAGMENT_TOO_LARGE", "INVALID_SEQUENCE"}
  - `record_error(error_code: str)` - only increments failure_count if error_code in RETRYABLE_ERRORS
  - `async process(segment: AudioSegment) -> bool`
  - Returns True if STS processing started (closed/half_open)
  - Returns False if using fallback (open)
  - Logs state transitions with stream_id
- [ ] T072 [US5] Add breaker state metric reporting in `apps/media-service/src/media_service/sts/circuit_breaker.py`
- [ ] T073 [US5] Verify unit tests pass with `pytest apps/media-service/tests/unit/test_circuit_breaker.py -v`

**Checkpoint**: User Story 5 should be fully functional and testable independently (run automated tests, continue automatically)

---

## Phase 8: User Story 6 - Prometheus Metrics Endpoint (Priority: P3)

**Goal**: Expose `/metrics` endpoint for Prometheus scraping with key observability metrics

**Independent Test**: Verify metrics format; GET /metrics returns Prometheus text format with all required metrics

### Tests for User Story 6 (MANDATORY - Test-First)

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US6**: 80% (observability)

- [ ] T074 [P] [US6] **Unit tests** for metrics definitions in `apps/media-service/tests/unit/test_prometheus.py`
  - Test `test_metrics_endpoint_returns_prometheus_format()` - text/plain content-type
  - Test `test_counter_audio_fragments_increments()` - increments correctly
  - Test `test_counter_fallback_increments()` - increments on fallback
  - Test `test_counter_gst_bus_errors_increments()` - increments with error_type label
- [ ] T075 [P] [US6] **Unit tests** for gauge metrics in `apps/media-service/tests/unit/test_prometheus.py`
  - Test `test_gauge_inflight_fragments_updates()` - reflects current count
  - Test `test_gauge_av_sync_delta_updates()` - reflects current delta
  - Test `test_gauge_sts_breaker_state_updates()` - 0=closed, 1=half_open, 2=open
- [ ] T076 [P] [US6] **Unit tests** for histogram metrics in `apps/media-service/tests/unit/test_prometheus.py`
  - Test `test_histogram_sts_rtt_records()` - observations recorded
  - Test `test_histogram_buckets_correct()` - bucket boundaries as specified

**Verification**: Run `pytest apps/media-service/tests/unit/test_prometheus.py -v` - ALL tests MUST FAIL before implementation

### Implementation for User Story 6

- [ ] T077 [US6] Implement WorkerMetrics class in `apps/media-service/src/media_service/metrics/prometheus.py`
  - Counters: audio_fragments_total, fallback_total, gst_bus_errors_total
  - Gauges: inflight_fragments, av_sync_delta_ms, sts_breaker_state
  - Histogram: sts_rtt_ms with buckets [50, 100, 250, 500, 1000, 2000, 4000, 8000]
  - All metrics include stream_id label
- [ ] T078 [US6] Add metrics endpoint to FastAPI app in `apps/media-service/src/media_service/main.py`
  - GET /metrics returns prometheus_client output
- [ ] T079 [US6] Verify unit tests pass with `pytest apps/media-service/tests/unit/test_prometheus.py -v`

**Checkpoint**: User Story 6 should be fully functional and testable independently (run automated tests, continue automatically)

---

## Phase 9: Worker Orchestrator Integration

**Goal**: Integrate all components into WorkerRunner orchestrator

**Independent Test**: Full end-to-end test with MediaMTX, Echo STS Service, and 1-min-nfl.mp4 fixture

### Tests for Worker Orchestrator

- [ ] T080 [P] **Unit tests** for WorkerRunner lifecycle in `apps/media-service/tests/unit/test_worker_runner.py`
  - Test `test_worker_runner_creates_pipelines()` - input and output pipelines created
  - Test `test_worker_runner_wires_segment_processing()` - buffer -> writer -> STS -> output
  - Test `test_worker_runner_handles_video_passthrough()` - video PTS adjusted
  - Test `test_worker_runner_handles_eos()` - graceful shutdown on EOS
- [ ] T081 **Integration test** for full worker with MediaMTX and Echo STS in `apps/media-service/tests/integration/test_worker_full.py`
  - Test with 1-min-nfl.mp4 fixture
  - Verify Socket.IO connection established
  - Verify segments sent and processed
  - Verify metrics updated during processing
  - Verify circuit breaker fallback works
  - Verify A/V sync within threshold

### Implementation for Worker Orchestrator

- [ ] T082 Implement WorkerRunner class in `apps/media-service/src/media_service/worker/worker_runner.py`
  - Constructor takes StreamWorker, sts_url, stream_config, segment_dir, metrics: WorkerMetrics
  - Creates InputPipeline, OutputPipeline, SegmentBuffer, VideoSegmentWriter, AudioSegmentWriter
  - Creates StsSocketIOClient, CircuitBreakerWrapper, AvSync
  - `async start()` - connects to STS, initializes and starts pipelines
  - `async stop()` - graceful shutdown
  - `_handle_video(buffer, pts_ns)` - passthrough with PTS adjustment
  - `_handle_audio(buffer, pts_ns)` - buffer -> write segment -> STS or fallback -> output
- [ ] T083 Wire WorkerRunner into existing StreamWorker in `apps/media-service/src/media_service/worker/stream_worker.py`
- [ ] T084 Verify integration tests pass with `pytest apps/media-service/tests/integration/ -v`

**Checkpoint**: Full worker should process streams end-to-end (run automated tests, continue automatically)

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T085 [P] Add structured logging with streamId, fragmentId, batchNumber, sessionId across all modules
- [ ] T086 [P] Add environment variable configuration (WORKER_STS_SERVICE_URL, WORKER_SEGMENT_DIR, WORKER_SEGMENT_DURATION, WORKER_STS_TIMEOUT_MS, etc.)
- [ ] T087 [P] Run full test suite with coverage: `pytest apps/media-service/tests/ --cov=media_service --cov-report=term-missing`
- [ ] T088 Verify coverage >= 80% overall, >= 95% for sts/socketio_client.py, sts/fragment_tracker.py, sync/av_sync.py, buffer/segment_buffer.py
- [ ] T089 [P] Run linting: `make lint`
- [ ] T090 [P] Run type checking: `make typecheck`
- [ ] T091 Update README with quickstart instructions in `apps/media-service/README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1 (Pipeline) can then proceed immediately
  - US2 (Segment Buffering) can proceed in parallel with US1
  - US3 (Socket.IO Client) depends on US2 (needs AudioSegment to send)
  - US4 (A/V Sync) depends on US1 (uses pipeline PTS)
  - US5 (Circuit Breaker) depends on US3 (wraps STS Socket.IO client)
  - US6 (Metrics) can proceed in parallel with US1-5
- **Worker Orchestrator (Phase 9)**: Depends on all user stories being complete
- **Polish (Phase 10)**: Depends on Phase 9 completion

### User Story Dependencies

```
Phase 2: Foundational (BLOCKS ALL)
    |
    +--> US1: Pipeline Passthrough ----------------------+
    |                                                    |
    +--> US2: Segment Buffering (parallel with US1) ----+---> US3: Socket.IO Client
    |                                                    |          |
    +--> US4: A/V Sync (needs US1 for pipeline PTS) ----+          +---> US5: Circuit Breaker
    |                                                    |
    +--> US6: Metrics (parallel with all) --------------+---> Phase 9: WorkerRunner
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation tasks in order of dependencies
- Verification step confirms tests pass
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**: T002-T008 can run in parallel
**Phase 2 (Foundational)**: T012-T013 can run in parallel; T015-T016 can run in parallel; T018-T019 can run in parallel
**Phase 3 (US1)**: T021-T023 can run in parallel; T026 independent
**Phase 4 (US2)**: T031-T034 can run in parallel; T037-T038 can run in parallel
**Phase 5 (US3)**: T040-T048 can run in parallel (different test files)
**Phase 6 (US4)**: T060-T061 can run in parallel
**Phase 7 (US5)**: T066-T069 can run in parallel
**Phase 8 (US6)**: T074-T076 can run in parallel
**Phase 10 (Polish)**: T085, T086, T087, T089, T090 can run in parallel

---

## Parallel Example: User Story 3 Tests

```bash
# Launch all unit tests for User Story 3 together:
Task T040: "Unit tests for StsSocketIOClient connection in apps/media-service/tests/unit/test_sts_socketio_client.py"
Task T041: "Unit tests for stream lifecycle in apps/media-service/tests/unit/test_sts_socketio_client.py"
Task T042: "Unit tests for fragment sending in apps/media-service/tests/unit/test_sts_socketio_client.py"
Task T045: "Unit tests for backpressure handling in apps/media-service/tests/unit/test_backpressure_handler.py"
Task T046: "Unit tests for reconnection manager in apps/media-service/tests/unit/test_reconnection_manager.py"
Task T048: "Unit tests for fragment tracker in apps/media-service/tests/unit/test_fragment_tracker.py"

# Then implementation (can be parallel on different files):
Task T053: "Implement StsSocketIOClient in apps/media-service/src/media_service/sts/socketio_client.py"
Task T055: "Implement FragmentTracker in apps/media-service/src/media_service/sts/fragment_tracker.py"
Task T056: "Implement BackpressureHandler in apps/media-service/src/media_service/sts/backpressure_handler.py"
Task T057: "Implement ReconnectionManager in apps/media-service/src/media_service/sts/reconnection_manager.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2 + 3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Pipeline Passthrough)
4. Complete Phase 4: User Story 2 (Segment Buffering)
5. Complete Phase 5: User Story 3 (Socket.IO Client)
6. **STOP and VALIDATE**: Test with Echo STS Service
7. Deploy/demo if ready (streams work with echo dubbing)

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready
2. Add US1 (Pipeline) -> Test independently -> Can stream passthrough
3. Add US2 (Segment Buffering) -> Test independently -> 6s MP4/M4A segments work
4. Add US3 (Socket.IO Client) -> Test independently -> Real-time STS communication works
5. Add US4 (A/V Sync) -> Test independently -> Sync maintained
6. Add US5 (Circuit Breaker) -> Test independently -> Resilience added
7. Add US6 (Metrics) -> Test independently -> Observability added
8. Add WorkerRunner -> Full integration -> Production ready

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Pipeline)
   - Developer B: User Story 2 (Segment Buffering)
   - Developer C: User Story 6 (Metrics)
3. After US1 complete:
   - Developer A: User Story 4 (A/V Sync)
4. After US2 complete:
   - Developer B: User Story 3 (Socket.IO Client)
5. After US3 complete:
   - Developer B: User Story 5 (Circuit Breaker)
6. All integrate in Phase 9

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Checkpoints are informational - run automated tests to validate, then continue automatically unless manual verification is explicitly required
- Fixture: `tests/fixtures/test-streams/1-min-nfl.mp4` (60s H.264/AAC)
- Echo STS Service: `docker-compose -f apps/sts-service/docker-compose.yml up echo-sts`
- Socket.IO protocol reference: `specs/017-echo-sts-service/contracts/`
