# Feature Specification: RTMP Stream Pull Migration

**Feature Branch**: `020-rtmp-stream-pull`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "Migrate the method stream worker pull stream from mediaMTX from RTSP to RTMP pull for lower complexity. Please add a feature and implement it also update existing test cases."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stream Worker Pulls RTMP Instead of RTSP (Priority: P1)

When a live stream becomes available on MediaMTX, the stream worker must pull the stream using RTMP protocol instead of RTSP. This simplifies the pipeline by eliminating RTP depayloading complexity and reduces the number of GStreamer elements required for stream processing.

**Why this priority**: This is the core migration that enables all downstream benefits. The current RTSP-based approach requires complex RTP depayloading with dynamic element creation (rtph264depay, rtpmp4gdepay), causing audio pipeline failures. RTMP provides a simpler container format with fewer moving parts.

**Independent Test**: Verify RTMP source integration
- **Unit test**: `test_input_pipeline_rtmp_url_validation()` validates RTMP URL format checking (must start with "rtmp://")
- **Unit test**: `test_input_pipeline_build_rtmp_elements()` verifies correct GStreamer elements are created (rtmpsrc, flvdemux)
- **Integration test**: `test_input_pipeline_pulls_rtmp_stream()` validates stream worker can pull live RTMP stream from MediaMTX
- **Success criteria**: All tests pass with 80% coverage, pipeline successfully receives video and audio buffers

**Acceptance Scenarios**:

1. **Given** MediaMTX is running with an active RTMP stream, **When** stream worker initializes with RTMP URL, **Then** input pipeline creates rtmpsrc element with correct location property
2. **Given** input pipeline is built with RTMP source, **When** pipeline transitions to PLAYING state, **Then** video and audio buffers are received by appsink callbacks
3. **Given** stream worker receives RTMP URL configuration, **When** URL does not start with "rtmp://", **Then** validation error is raised with clear message

---

### User Story 2 - Existing Tests Updated for RTMP (Priority: P1)

All existing unit tests, integration tests, and E2E tests must be updated to use RTMP URLs and expect RTMP-based pipeline behavior. Tests currently expecting RTSP elements (rtspsrc, rtph264depay, rtpmp4gdepay) must be updated to expect RTMP elements (rtmpsrc, flvdemux).

**Why this priority**: Without updated tests, the migration cannot be verified as successful. Test updates are as critical as the implementation itself, per TDD principles.

**Independent Test**: Verify test suite integrity
- **Unit test**: `test_worker_runner_builds_rtmp_pipeline()` validates WorkerRunner initializes InputPipeline with RTMP URL
- **Integration test**: `test_input_pipeline_rtmp_integration()` validates full InputPipeline with MediaMTX RTMP source
- **E2E test**: `test_dual_compose_full_pipeline_rtmp()` validates end-to-end flow with RTMP stream publishing
- **Success criteria**: All tests pass, no RTSP references remain, coverage maintained at 80% minimum

**Acceptance Scenarios**:

1. **Given** test fixtures publish streams via RTMP, **When** tests run against updated pipeline, **Then** all assertions pass without RTSP-specific expectations
2. **Given** E2E tests start MediaMTX with RTMP stream, **When** stream worker connects, **Then** video and audio segments are written successfully
3. **Given** unit tests mock pipeline elements, **When** tests verify element creation, **Then** rtmpsrc and flvdemux are expected instead of rtspsrc and depayloaders

---

### User Story 3 - Audio Pipeline Reliability Improved (Priority: P2)

The stream worker must reliably process both video and audio streams without caps negotiation failures. The RTMP migration eliminates the RTP depayloader complexity that caused audio pipeline failures documented in the E2E test issues.

**Why this priority**: This is a key benefit of the RTMP migration but is a consequence of P1 work rather than independent functionality. It validates that the migration achieves its goal of lower complexity.

**Independent Test**: Verify audio/video parity
- **Unit test**: `test_input_pipeline_audio_video_buffer_counts()` validates equal numbers of audio and video buffers received
- **Integration test**: `test_segment_buffer_writes_audio_and_video()` validates both media types are written to disk
- **E2E test**: `test_sts_receives_audio_fragments()` validates audio segments reach STS service
- **Success criteria**: Audio and video processing succeed at equal rates, no dropped audio samples

**Acceptance Scenarios**:

1. **Given** stream worker processes RTMP stream, **When** segment buffer accumulates 6 seconds of data, **Then** both video and audio segments are emitted
2. **Given** input pipeline receives FLV stream, **When** flvdemux separates tracks, **Then** both video appsink and audio appsink receive samples
3. **Given** E2E test runs for 30 seconds, **When** test completes, **Then** audio fragment count equals video segment count

---

### Edge Cases

- **Video-only streams (no audio track)**: Pipeline MUST reject stream with error during initialization. Audio track is mandatory for dubbing pipeline - missing audio causes pipeline startup failure with clear error message.
- **RTMP connection drops or network interruptions**: Pipeline detects connection loss via rtmpsrc error signals, triggers reconnection logic with exponential backoff.
- **RTMP stream format changes mid-stream**: Pipeline treats codec/format changes as error condition, requires stream restart to re-negotiate caps.
- **Non-standard codecs (not H.264/AAC)**: Pipeline validates codec support during caps negotiation, rejects unsupported formats with error message specifying required codecs.
- **RTSP URL provided to RTMP-only pipeline**: URL validation (FR-002) rejects RTSP URLs with clear error message indicating RTMP requirement.
- **MediaMTX serving both RTSP and RTMP**: Not applicable - system only uses RTMP URLs after migration, RTSP support removed completely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Input pipeline MUST accept RTMP URLs in format "rtmp://host:port/app/stream"
- **FR-002**: Input pipeline MUST validate RTMP URL format and reject invalid URLs with clear error messages
- **FR-003**: Input pipeline MUST use rtmpsrc GStreamer element to pull RTMP streams from MediaMTX
- **FR-004**: Input pipeline MUST use flvdemux to separate video (H.264) and audio (AAC) tracks from FLV container
- **FR-005**: Input pipeline MUST maintain existing appsink callback interface for video and audio buffers
- **FR-006**: Input pipeline MUST preserve codec-copy behavior (no re-encoding)
- **FR-007**: Pipeline MUST remove all RTSP-specific elements (rtspsrc, rtph264depay, rtpmp4gdepay, rtpmp4adepay)
- **FR-008**: Pipeline MUST remove all RTP-specific pad handling logic from _on_pad_added callback
- **FR-009**: WorkerRunner MUST construct RTMP URL from MediaMTX configuration (host, port, stream path)
- **FR-010**: All unit tests MUST be updated to use RTMP URLs and expect RTMP elements
- **FR-011**: All integration tests MUST be updated to publish streams via RTMP instead of RTSP
- **FR-012**: All E2E tests MUST be updated to validate RTMP-based pipeline behavior
- **FR-013**: Pipeline MUST validate audio track presence during caps negotiation and fail with error if audio track is missing
- **FR-014**: Pipeline MUST use flvdemux max-buffers property for RTMP buffering control equivalent to RTSP jitter buffer
- **FR-015**: Documentation MUST be updated to reflect RTMP as the standard stream pull protocol
- **FR-016**: Pipeline MUST achieve <300ms total latency (MediaMTX input to segment write) with flexible allocation across components
- **FR-017**: System MUST remove all RTSP support completely - no backward compatibility or feature flags for protocol selection

### Key Entities

- **RTMP URL**: Stream source identifier in format "rtmp://mediamtx:1935/live/streamId/in", consisting of protocol, host, port, application path, and stream key
- **Input Pipeline**: GStreamer pipeline component responsible for pulling streams and demuxing into video/audio buffers, using rtmpsrc -> flvdemux -> parsers -> appsinks
- **FLV Container**: Flash Video container format used by RTMP, containing multiplexed H.264 video and AAC audio streams
- **Stream Configuration**: Worker configuration containing RTMP URL, STS endpoint, segment duration, and language settings
- **Test Fixture**: Sample stream file (30s MP4) published to MediaMTX via RTMP for E2E validation

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Stream worker successfully pulls and processes RTMP streams from MediaMTX within 2 seconds of stream availability
- **SC-002**: All unit tests pass with minimum 80% code coverage maintained
- **SC-003**: Integration tests demonstrate both video and audio segments are written to disk with equal counts
- **SC-004**: E2E tests show audio fragments reach STS service without caps negotiation failures
- **SC-005**: Pipeline complexity reduced by eliminating 3+ GStreamer elements (rtspsrc replaced with rtmpsrc, depayloaders removed)
- **SC-006**: Stream processing latency remains under 300ms total (MediaMTX input to segment write) with flexible allocation based on profiling
- **SC-007**: No RTSP-specific code, configuration, or compatibility layer remains in media-service codebase after migration
- **SC-008**: Test execution time remains within 10% of current baseline (no performance regression)
- **SC-009**: Documentation updated with RTMP migration rationale and configuration examples
- **SC-010**: All E2E test steps (1-6) pass consistently without audio pipeline failures

## Assumptions

- RTMP streams from MediaMTX use FLV container format with H.264 video and AAC audio codecs
- Test fixtures (30s MP4 files) contain both video and audio tracks suitable for RTMP publishing
- GStreamer rtmpsrc and flvdemux elements are available in deployed environments
- Migration is a complete replacement - no parallel RTSP support or migration period required
- All streams processed by pipeline are guaranteed to have audio tracks (enforced by validation)
- flvdemux max-buffers property provides equivalent buffering control to RTSP jitter buffer
- 300ms latency budget can be achieved through flexible allocation across pipeline components

## Dependencies

- GStreamer 1.0 with rtmpsrc, flvdemux, h264parse, aacparse, appsink elements
- MediaMTX configured to accept RTMP input streams on port 1935
- Docker Compose E2E environment with RTMP-enabled MediaMTX container
- ffmpeg for test stream publishing with RTMP output format

## Clarifications

**Session Date**: 2026-01-01

This section documents decisions made during specification clarification to resolve ambiguities:

1. **Feature Flag Strategy**: Complete migration with no backward compatibility. RTSP support will be removed immediately without feature flag. This prioritizes simplicity over backward compatibility since no production deployments exist requiring RTSP support.

2. **Video-Only Stream Behavior**: Pipeline will reject streams with missing audio tracks during initialization. This enforces the audio requirement for the dubbing pipeline and provides clear error feedback rather than silent failures downstream.

3. **RTMP Buffering Approach**: Use flvdemux max-buffers property for buffering control, following standard GStreamer RTMP patterns. This provides equivalent functionality to RTSP jitter buffer without custom buffering implementation.

4. **Latency Budget Allocation**: Target 300ms total latency with flexible allocation across components (rtmpsrc, flvdemux, parsers, segment buffer). No strict per-component breakdown - optimize based on profiling during implementation.

5. **Complete RTSP Removal**: No compatibility layer or fallback mechanism. All RTSP-specific code, configuration, and tests will be removed in this feature to reduce maintenance burden and complexity.
