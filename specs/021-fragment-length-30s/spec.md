# Feature Specification: Fragment Length Increase from 6s to 30s

**Feature Branch**: `021-fragment-length-30s`
**Created**: 2026-01-11
**Status**: Draft
**Input**: User description: "Increase the fragment length from current 6s to 30s"

## Overview

This specification defines the changes required to increase the audio/video fragment duration from the current 6-second default to 30 seconds across the live broadcast dubbing pipeline.

### Motivation

Longer fragments (30s vs 6s) provide several benefits for translation quality:
1. **Better Translation Context**: ASR and translation models have more linguistic context to produce accurate translations
2. **Sentence Boundary Preservation**: 30-second windows are more likely to capture complete sentences and paragraphs
3. **Reduced Overhead**: Fewer fragments to process per stream means lower coordination overhead
4. **Improved TTS Prosody**: Longer text segments allow TTS to generate more natural speech patterns

### Tradeoffs

1. **Increased Latency**: Initial output delay increases from ~6-8s to ~35-55s (variable based on STS processing time)
2. **Higher Memory Usage**: Larger buffers required for video and audio accumulation (162MB vs 45MB peak)
3. **Longer Recovery Time**: On failure, more content needs to be retransmitted
4. **Extended STS Timeout**: Processing timeout must increase to accommodate longer segments

## User Scenarios & Testing

### User Story 1 - Updated Fragment Duration Processing (Priority: P1)

The media service produces 30-second segments instead of 6-second segments for both video and audio tracks.

**Why this priority**: This is the core change that all other modifications depend on. Without updating the segment duration, no other changes are meaningful.

**Independent Test**: Test with 1-min-nfl.mp4 fixture published to MediaMTX
- **Unit test**: `test_segment_buffer_accumulates_30s()` validates 30-second buffering threshold
- **Unit test**: `test_video_segment_duration_30s()` validates VideoSegment.DEFAULT_SEGMENT_DURATION_NS is 30_000_000_000
- **Unit test**: `test_audio_segment_duration_30s()` validates AudioSegment.DEFAULT_SEGMENT_DURATION_NS is 30_000_000_000
- **Integration test**: `test_segment_pipeline_60s_produces_2_segments()` validates 60s fixture produces 2 segments (not 10)
- **Success criteria**: Segments are exactly 30s (+/- 100ms), segment count matches expected (duration/30)

**Acceptance Scenarios**:

1. **Given** a 60-second input stream, **When** media service processes it, **Then** exactly 2 segments are produced (not 10)
2. **Given** stream is running, **When** 30 seconds of video accumulated, **Then** video segment is written to disk with duration_ns ~30_000_000_000
3. **Given** stream is running, **When** 30 seconds of audio accumulated, **Then** audio segment is written as M4A file with duration_ns ~30_000_000_000
4. **Given** stream ends at 45 seconds, **When** EOS received, **Then** one 30s segment and one 15s partial segment are produced

---

### User Story 2 - Extended STS Processing Timeout (Priority: P1)

The STS service timeout configuration is updated to accommodate longer fragment processing times.

**Why this priority**: Without extending timeouts, 30-second fragments will timeout during processing, causing all fragments to fallback to original audio.

**Independent Test**: Test STS timeout behavior with 30s fragments
- **Unit test**: `test_stream_session_timeout_ms_default_60000()` validates default timeout is 60000ms (60s)
- **Unit test**: `test_fragment_timeout_30s_fragment()` validates fragments do not timeout prematurely
- **Contract test**: `test_stream_init_timeout_ms_validation()` validates StreamInitPayload accepts timeout_ms up to 120000
- **Integration test**: `test_30s_fragment_processes_within_timeout()` validates 30s fragment completes successfully
- **Success criteria**: 30-second fragments complete processing without timeout errors

**Acceptance Scenarios**:

1. **Given** 30-second fragment sent to STS, **When** processing takes 20-40 seconds, **Then** fragment completes successfully (no timeout)
2. **Given** stream:init sent with timeout_ms=60000, **When** STS validates payload, **Then** configuration is accepted
3. **Given** fragment processing takes 55 seconds, **When** timeout_ms=60000, **Then** fragment completes before timeout
4. **Given** fragment processing exceeds 60 seconds, **When** timeout_ms=60000, **Then** timeout error is raised and fallback is used

---

### User Story 3 - Buffer and Wait A/V Synchronization (Priority: P1)

Video segments are buffered in memory until corresponding dubbed audio is received, then output together as a synchronized pair. Output is re-encoded with PTS starting from 0.

**Why this priority**: This simplified approach replaces the av_offset_ns mechanism with a straightforward buffer-and-wait pattern. A/V sync is achieved naturally by pairing video with its corresponding dubbed audio before output. Re-encoding with PTS=0 simplifies downstream handling.

**Independent Test**: Verify A/V sync with buffer-and-wait pattern
- **Unit test**: `test_av_sync_manager_buffers_video_until_audio_ready()` validates video is held until audio arrives
- **Unit test**: `test_sync_pair_pts_starts_from_zero()` validates output PTS starts from 0 (re-encoded output)
- **Unit test**: `test_output_is_reencoded()` validates output video and audio are re-encoded (not passthrough)
- **Integration test**: `test_av_sync_within_threshold_30s_fragments()` validates sync < 100ms with 30s segments
- **Integration test**: `test_output_pts_zero_start()` validates output stream PTS begins at 0
- **Success criteria**: A/V sync delta remains < 100ms steady-state (naturally achieved through pairing), output PTS starts from 0

**Acceptance Scenarios**:

1. **Given** video segment arrives, **When** corresponding dubbed audio not yet received, **Then** video is buffered in memory
2. **Given** video segment is buffered, **When** corresponding dubbed audio arrives, **Then** both are output as synchronized pair
3. **Given** dubbed audio arrives first, **When** corresponding video arrives, **Then** both are output as synchronized pair
4. **Given** video and dubbed audio are paired, **When** output is generated, **Then** output PTS starts from 0 (not original stream PTS)
5. **Given** output segment is generated, **When** examining video track, **Then** video is re-encoded (not passthrough)
6. **Given** output segment is generated, **When** examining audio track, **Then** dubbed audio is included (already re-encoded by TTS)

---

### User Story 4 - Updated Stream Configuration (Priority: P2)

The stream configuration payloads (stream:init) correctly communicate 30-second chunk duration.

**Why this priority**: Configuration changes must propagate through Socket.IO protocol to ensure both media and STS services are aligned.

**Independent Test**: Validate Socket.IO protocol with updated config
- **Unit test**: `test_stream_config_chunk_duration_30000()` validates StreamConfig.chunk_duration_ms defaults to 30000
- **Contract test**: `test_stream_config_payload_le_30000()` validates Pydantic model accepts chunk_duration_ms=30000
- **Integration test**: `test_stream_init_30s_config()` validates stream:init payload contains chunk_duration_ms=30000
- **Success criteria**: Stream initialization succeeds with 30-second configuration

**Acceptance Scenarios**:

1. **Given** media service starts stream, **When** stream:init sent, **Then** config.chunk_duration_ms equals 30000
2. **Given** STS receives stream:init, **When** validating config, **Then** chunk_duration_ms=30000 is accepted
3. **Given** STS session created, **When** StreamSession checked, **Then** chunk_duration_ms equals 30000

---

### User Story 5 - E2E Test Updates (Priority: P2)

All E2E tests are updated to expect 30-second segments and adjusted timing expectations.

**Why this priority**: Tests must be updated to validate the new behavior correctly; otherwise, all tests will fail.

**Independent Test**: Run E2E test suite
- **Unit test**: `test_config_segment_duration_30()` validates TestConfig.SEGMENT_DURATION_SEC is 30
- **Integration test**: `test_e2e_full_pipeline_30s_segments()` validates full pipeline with 30s fragments
- **Success criteria**: All P1 E2E tests pass with 30-second segment configuration

**Acceptance Scenarios**:

1. **Given** 60-second test fixture, **When** E2E test runs, **Then** EXPECTED_SEGMENTS equals 2 (not 10)
2. **Given** E2E test pipeline, **When** segments verified, **Then** each segment duration is ~30 seconds
3. **Given** TimeoutConfig, **When** FRAGMENT_TIMEOUT checked, **Then** value is >= 60 seconds

---

### User Story 6 - Validation Constraint Updates (Priority: P2)

Pydantic validation constraints are updated to allow 30-second chunk durations.

**Why this priority**: Current validation constraints (max 6000ms) will reject 30-second configurations.

**Independent Test**: Validate model constraints
- **Unit test**: `test_stream_config_payload_accepts_30000ms()` validates le=30000 constraint
- **Unit test**: `test_asr_max_duration_30s()` validates ASR postprocessing accepts 30s audio
- **Success criteria**: All validation constraints accept 30-second durations

**Acceptance Scenarios**:

1. **Given** StreamConfigPayload with chunk_duration_ms=30000, **When** validated, **Then** no ValidationError raised
2. **Given** audio segment of 30 seconds, **When** ASR postprocessing validates, **Then** max_duration_seconds allows 30

---

### Edge Cases

- What happens when stream duration is less than 30 seconds? Partial segment emitted with actual duration (minimum 1 second), sent to STS for processing
- What happens when STS processing takes longer than 60 seconds? Timeout triggers, fallback to original audio used
- What happens when memory is constrained with 30s buffers? No automatic handling - rely on container memory limits for OOM protection
- How does circuit breaker behave with longer timeouts? Failure threshold timing is independent of fragment duration
- What happens with very slow translation models? Extended timeout (120000ms max) should cover extreme cases
- How are partial segments handled? All partial segments >=1s are sent to STS for processing to maintain consistency
- What happens if video arrives before dubbed audio? Video is buffered in memory until corresponding audio arrives (buffer-and-wait approach)
- What happens if dubbed audio arrives before video? Audio is buffered in memory until corresponding video arrives

## Requirements

### Functional Requirements

**Core Duration Constants (P1)**

- **FR-001**: VideoSegment.DEFAULT_SEGMENT_DURATION_NS MUST be 30_000_000_000 (30 seconds)
- **FR-002**: AudioSegment.DEFAULT_SEGMENT_DURATION_NS MUST be 30_000_000_000 (30 seconds)
- **FR-003**: SegmentBuffer.DEFAULT_SEGMENT_DURATION_NS MUST be 30_000_000_000 (30 seconds)
- **FR-004**: Segment tolerance (TOLERANCE_NS) MUST remain 100_000_000 (100ms)
- **FR-005**: Minimum partial segment duration (MIN_SEGMENT_DURATION_NS) MUST remain 1_000_000_000 (1 second)

**STS Communication (P1)**

- **FR-006**: StreamConfig.chunk_duration_ms MUST default to 30000 (30 seconds)
- **FR-007**: StreamSession.chunk_duration_ms MUST default to 30000 (30 seconds)
- **FR-008**: StreamSession.timeout_ms MUST default to 60000 (60 seconds) to accommodate 30s processing (~25-35s)
- **FR-009**: TimeoutConfig.FRAGMENT_TIMEOUT MUST be 60 (seconds)

**Buffer and Wait A/V Synchronization (P1)**

- **FR-010**: Video segments MUST be buffered in memory until corresponding dubbed audio is received
- **FR-011**: Output MUST only occur when BOTH video and dubbed audio are ready (synchronized pair)
- **FR-012**: Output video and audio MUST be re-encoded (not passthrough), with PTS starting from 0 for both tracks in each output segment
- **FR-013**: Drift correction code (apply_slew_correction, needs_correction) MUST be removed from AvSyncState

**Validation Constraints (P2)**

- **FR-014**: StreamConfigPayload.chunk_duration_ms MUST have constraint le=30000 (was le=10000)
- **FR-015**: StreamInitPayload.timeout_ms MUST have constraint le=120000 (was le=30000) to allow extended timeouts for slow models
- **FR-016**: ASR postprocessing max_duration_seconds MUST be 30 (was 6) or removed

**E2E Test Configuration (P2)**

- **FR-017**: TestConfig.SEGMENT_DURATION_SEC MUST be 30
- **FR-018**: TestConfig.SEGMENT_DURATION_NS MUST be 30_000_000_000
- **FR-019**: TestConfig.EXPECTED_SEGMENTS MUST be 2 (60s / 30s = 2)
- **FR-020**: TimeoutConfig.PIPELINE_COMPLETION MUST be >= 120 (seconds) for 30s fragments

**Worker Configuration (P2)**

- **FR-021**: WorkerConfig.segment_duration_ns default MUST be 30_000_000_000
- **FR-022**: Documentation MUST be updated to reflect 30-second segment duration

### Key Entities

- **VideoSegment**: Video segment metadata (unchanged structure, updated DEFAULT_SEGMENT_DURATION_NS constant; original PTS stored but not propagated to output)
- **AudioSegment**: Audio segment metadata (unchanged structure, updated DEFAULT_SEGMENT_DURATION_NS constant; original PTS stored but not propagated to output)
- **SegmentBuffer**: Buffer accumulator (unchanged structure, updated DEFAULT_SEGMENT_DURATION_NS constant)
- **StreamConfig**: Stream configuration for STS (updated chunk_duration_ms default)
- **StreamSession**: Per-stream session state (updated chunk_duration_ms and timeout_ms defaults)
- **AvSyncState**: A/V synchronization state (simplified - remove av_offset_ns, needs_correction, apply_slew_correction; no PTS tracking)
- **AvSyncManager**: A/V sync manager (simplified - buffer-and-wait logic, output PTS starts from 0)
- **SyncPair**: Output pair (pts_ns always 0 for each segment, re-encoded output)
- **StreamConfigPayload**: Pydantic model (updated chunk_duration_ms validation constraint)
- **TestConfig**: E2E test configuration (updated SEGMENT_DURATION_SEC, EXPECTED_SEGMENTS)
- **TimeoutConfig**: Timeout configuration (updated FRAGMENT_TIMEOUT)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Worker processes 60-second test fixture and produces exactly 2 segments (not 10)
- **SC-002**: Each segment has duration_ns within 30_000_000_000 +/- 100_000_000 (30s +/- 100ms)
- **SC-003**: A/V sync delta remains < 100ms steady-state (naturally achieved through buffer-and-wait pairing)
- **SC-004**: STS processing completes within 60-second timeout for 30-second fragments
- **SC-005**: All unit tests pass with updated duration constants
- **SC-006**: All integration tests pass with 30-second segment expectations
- **SC-007**: All P1 E2E tests pass with 30-second fragment pipeline
- **SC-008**: Stream configuration validation accepts chunk_duration_ms=30000 without errors
- **SC-009**: Memory usage increase is proportional (5x base + buffer-and-wait overhead) but within acceptable limits
- **SC-010**: Output segment PTS starts from 0 for both video and audio tracks (verified via ffprobe)

## Files Requiring Updates

### Media Service Core (P1)

| File | Change Description |
|------|-------------------|
| `apps/media-service/src/media_service/models/segments.py` | Update DEFAULT_SEGMENT_DURATION_NS from 6_000_000_000 to 30_000_000_000 in both VideoSegment and AudioSegment |
| `apps/media-service/src/media_service/buffer/segment_buffer.py` | Update DEFAULT_SEGMENT_DURATION_NS from 6_000_000_000 to 30_000_000_000 |
| `apps/media-service/src/media_service/models/state.py` | Remove av_offset_ns default, remove needs_correction(), remove apply_slew_correction() from AvSyncState |
| `apps/media-service/src/media_service/sync/av_sync.py` | Remove av_offset_ns parameter, set output PTS to 0, remove drift correction logic |
| `apps/media-service/src/media_service/sts/models.py` | Update StreamConfig.chunk_duration_ms from 6000 to 30000 |
| `apps/media-service/src/media_service/worker/worker_runner.py` | Update WorkerConfig.segment_duration_ns default |
| `apps/media-service/src/media_service/pipelines/output_pipeline.py` | Configure output muxer to start PTS from 0, ensure video re-encoding (not passthrough) |

### STS Service (P1)

| File | Change Description |
|------|-------------------|
| `apps/sts-service/src/sts_service/full/session.py` | Update StreamSession.chunk_duration_ms from 6000 to 30000, timeout_ms from 8000 to 60000 |
| `apps/sts-service/src/sts_service/echo/models/stream.py` | Update StreamConfigPayload.chunk_duration_ms constraint le=30000, timeout_ms le=120000 |
| `apps/sts-service/src/sts_service/asr/postprocessing.py` | Update max_duration_seconds from 6 to 30 (if applicable) |

### E2E Tests (P2)

| File | Change Description |
|------|-------------------|
| `tests/e2e/config.py` | Update SEGMENT_DURATION_SEC=30, SEGMENT_DURATION_NS=30_000_000_000, EXPECTED_SEGMENTS=2, FRAGMENT_TIMEOUT=60 |

### Unit Tests (P2)

Multiple test files will need assertion updates:
- Segment count expectations (60s stream: 10 -> 2 segments)
- Duration validation checks
- Timeout expectations
- Remove av_offset_ns test assertions
- Remove drift correction test cases
- Add buffer-and-wait behavior tests

## Migration Considerations

### Backward Compatibility

This is a **breaking change** for any existing deployments:
- Existing streams in progress will experience inconsistent segment sizes during transition
- Configuration must be updated atomically across all services
- No mixed-version deployment is supported

### Deployment Strategy

1. **Stop all active streams** before deployment
2. **Deploy all services simultaneously** (media-service and sts-service)
3. **Update environment variables** if any are used to override defaults
4. **Restart services** with new configuration
5. **Verify with test stream** before resuming production traffic

### Rollback Plan

If issues are detected:
1. Stop all streams
2. Revert to previous container images
3. Restart services
4. Resume streams

## Memory and Resource Implications

### Buffer Size Impact

| Component | 6s Configuration | 30s Configuration | Increase Factor |
|-----------|------------------|-------------------|-----------------|
| Video Buffer | ~3MB per segment | ~15MB per segment | 5x |
| Audio Buffer | ~180KB per segment | ~900KB per segment | 5x |
| In-flight Fragments (max 3) | ~9MB total | ~45MB total | 5x |
| **Buffer-and-Wait Peak** | N/A | ~162MB total | New overhead |

### Buffer-and-Wait Memory Calculation

With the buffer-and-wait approach, memory usage can spike when multiple segments are buffered:
- **Worst case**: 3 video segments waiting for dubbed audio (3 x 30s x ~15MB = ~45MB video)
- **Plus**: 3 audio segments buffered (3 x 30s x ~900KB = ~2.7MB audio)
- **Plus**: 3 in-flight STS requests (3 x 30s x ~15MB = ~45MB payload)
- **Plus**: 3 dubbed audio responses pending (3 x 30s x ~900KB = ~2.7MB)
- **Total peak memory**: ~95MB for buffers + ~67MB for in-flight = ~162MB peak

This is higher than the previous 45MB estimate due to the buffer-and-wait pattern, but still manageable for container environments.

### Processing Time Impact

| Stage | 6s Fragment | 30s Fragment | Notes |
|-------|-------------|--------------|-------|
| ASR | ~2-3s | ~10-15s | Linear scaling |
| Translation | ~0.5-1s | ~1-3s | Near-linear |
| TTS | ~2-3s | ~10-15s | Linear scaling |
| Total | ~5-7s | ~25-35s | Within 60s timeout |

### Latency Impact

| Metric | 6s Configuration | 30s Configuration | Notes |
|--------|------------------|-------------------|-------|
| Initial delay | ~6-8s | ~35-55s | Variable based on STS processing |
| Segment-to-segment | ~6s | ~30s | Fixed by segment duration |
| End-to-end latency | ~12-15s | ~55-75s | Initial + processing |

## Assumptions

- ASR models can handle 30-second audio segments (no internal chunking required)
- Translation models perform well with longer text segments
- TTS can generate 30 seconds of audio in a single inference
- System has sufficient memory for buffer-and-wait peak (~162MB)
- Network bandwidth is sufficient for larger payloads
- Initial latency increase (6s to 35-55s) is acceptable for the use case
- Variable latency from buffer-and-wait is acceptable

## Dependencies

- All components from spec 003-gstreamer-stream-worker
- All components from spec 017-echo-sts-service
- All components from spec 018-e2e-stream-handler-tests
- Memory monitoring capability (optional but recommended)

## Design Decisions

### D1: Timeout Configuration

**Decision**: Use 60s timeout (60000ms) with maximum validation constraint le=120000ms

**Rationale**: Processing time analysis shows 30s fragments take 25-35s to process (ASR: 10-15s, Translation: 1-3s, TTS: 10-15s). A 60s timeout provides a 25-second safety margin for processing variability under load. The 120000ms maximum validation allows for extreme edge cases with very slow models while keeping the default safe and predictable.

**Impact**: FR-008, FR-009, FR-015

### D2: Chunk Duration Validation

**Decision**: Strict maximum validation constraint le=30000 (exactly 30s)

**Rationale**: This feature is specifically scoped for 30-second fragments. Setting the validation maximum to exactly 30000ms prevents configuration errors and accidental deployment of untested fragment durations. If longer fragments are needed in the future, they would require separate analysis of timeout, memory, and processing implications in a new specification.

**Impact**: FR-014

### D3: Memory Constraint Handling

**Decision**: No automatic handling - rely on container memory limits

**Rationale**: The buffer-and-wait approach increases peak memory to ~162MB (vs previous 45MB estimate). This is still modest in absolute terms for modern container environments. Container memory limits provide clear OOM signals for capacity planning. Dynamic max_inflight adjustment would add implementation complexity without clear benefit given the relatively small absolute memory footprint. If memory becomes an issue in production, it can be addressed as a separate optimization spec.

**Impact**: Deployment strategy, assumptions, memory implications

### D4: Partial Segment Processing

**Decision**: Send all partial segments >=1s to STS for processing

**Rationale**: The spec already defines MIN_SEGMENT_DURATION_NS = 1_000_000_000 (1 second) in FR-005. Discarding partial segments would create an inconsistent user experience where the last few seconds of a stream are not dubbed. Even if translation quality degrades for very short segments, maintaining consistency is more important than perfect quality. The 1s minimum threshold prevents sending trivial fragments while maximizing dubbing coverage.

**Impact**: FR-005, Edge Cases, User Story 1

### D5: Validation Constraint Upper Bounds

**Decision**: le=30000 for chunk_duration_ms, le=120000 for timeout_ms

**Rationale**: Strict bounds prevent configuration errors. The 30s chunk limit matches exactly what this spec validates. The 120s timeout allows 2x the expected processing time for slow models or degraded conditions.

**Impact**: FR-014, FR-015

### D6: Buffer and Wait Approach with Re-encoding (ARCHITECTURAL DECISION)

**Decision**: Remove av_offset_ns, use "buffer and wait" approach for A/V synchronization, and re-encode output with PTS starting from 0

**Rationale**:
- **Simpler code**: No offset calculations, no drift correction, no slew rate adjustments
- **Naturally synchronized**: Video and audio are paired before output, guaranteeing sync
- **PTS reset to 0**: Each output segment starts fresh with PTS=0, eliminating PTS tracking complexity
- **Easier debugging**: Sync issues are immediately visible as buffered segments
- **Clean output**: Output is a fresh stream, not a continuation of original timestamps

**PTS Reset Benefits**:
- No need to track or propagate original stream PTS through the pipeline
- Downstream consumers receive clean segments starting from 0
- Simplifies segment model (no original_pts tracking needed)
- Output muxer configuration is simpler (always start from 0)

**Re-encoding Implications**:
- **Video**: Must be re-encoded (transcoded), not passthrough - allows PTS reset
- **Audio**: Already re-encoded by TTS (dubbed audio is new audio data)
- **GStreamer pipeline**: Output muxer configured to start PTS from 0
- **Quality**: Re-encoding may introduce minor quality loss vs passthrough (acceptable tradeoff)

**Tradeoffs acknowledged**:
- **Higher memory**: Peak ~162MB vs ~45MB (3.6x increase) due to buffering multiple segments
- **Variable latency**: 35-55s initial delay (depends on STS processing time) vs fixed 35s delay
- **Buffer management**: Need to handle buffer overflow and cleanup on stream end
- **CPU usage**: Re-encoding video requires more CPU than passthrough

**Removed components**:
- AvSyncState.av_offset_ns
- AvSyncState.needs_correction()
- AvSyncState.apply_slew_correction()
- AvSyncState.slew_rate_ns
- AvSyncManager av_offset_ns parameter
- AvSyncManager drift correction in _create_pair()
- Original PTS preservation logic (PTS now reset to 0)

**Impact**: FR-010, FR-011, FR-012, FR-013, User Story 3, SC-003

## Clarifications

### Session 2026-01-11

- Q: STS Processing Timeout - Which timeout value should be used given 30s fragments may take 25-35s to process? -> A: 60s timeout (60000ms) with le=120000 validation max
- Q: Validation Constraint Upper Bounds - Should chunk_duration_ms validation allow values above 30 seconds? -> A: le=30000 (exactly 30s max)
- Q: Memory Constraint Handling - What should happen when memory usage is high with 30s buffers (9MB->45MB increase)? -> A: No automatic handling - rely on container limits
- Q: Partial Segment Handling - Should partial segments (duration <30s) be sent to STS for processing? -> A: Yes - send all partial segments >=1s to STS

### Session 2026-01-11 (Architectural Update)

- Q: A/V Synchronization Approach - Should we use av_offset_ns with drift correction or buffer-and-wait? -> A: Buffer and wait approach - simpler, naturally synchronized, removes offset complexity
- Removed: av_offset_ns from AvSyncState (was 35s default)
- Removed: needs_correction() and apply_slew_correction() from AvSyncState
- Added: Buffer-and-wait requirements (FR-010 through FR-013)
- Updated: SC-003 to reflect natural sync from pairing (<=100ms)
- Updated: Memory implications to reflect buffer-and-wait overhead (~162MB peak)
