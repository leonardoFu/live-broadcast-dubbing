# Research: RTMP Stream Pull Migration

**Feature**: 020-rtmp-stream-pull
**Date**: 2026-01-01
**Phase**: 0 - Technical Research

## Purpose

This document resolves technical unknowns for migrating from RTSP to RTMP stream pulling in the media-service input pipeline. Research focuses on GStreamer RTMP elements, buffering strategies, and migration impact on existing tests.

## Research Tasks

### 1. GStreamer RTMP Elements

**Question**: What GStreamer elements are required for RTMP stream pulling, and how do they compare to RTSP elements?

**Findings**:

**RTSP Pipeline (Current)**:
```
rtspsrc -> rtph264depay -> h264parse -> queue -> appsink (video)
        -> rtpmp4adepay/rtpmp4gdepay -> aacparse -> queue -> appsink (audio)
```

**RTMP Pipeline (Target)**:
```
rtmpsrc -> flvdemux -> h264parse -> queue -> appsink (video)
                    -> aacparse -> queue -> appsink (audio)
```

**Key Differences**:
- **rtmpsrc** replaces **rtspsrc**: Single element for RTMP protocol handling
- **flvdemux** replaces RTP depayloaders: FLV container demuxing eliminates need for rtph264depay, rtpmp4adepay, rtpmp4gdepay
- **No dynamic pad handling complexity**: flvdemux has static pad templates for video/audio, no RTP encoding detection needed
- **Simpler caps negotiation**: FLV container provides codec information upfront, no RTP payload format detection

**Element Reduction**: 3 elements removed (rtspsrc -> rtmpsrc saves 1, depayloaders -> flvdemux saves 2-3 depending on audio format)

**Decision**: Use rtmpsrc + flvdemux as direct replacement for rtspsrc + RTP depayloaders.

**Rationale**: FLV container format is simpler than RTP for live streaming - it provides multiplexed H.264/AAC without requiring dynamic element creation based on RTP encoding names.

**Alternatives Considered**:
- Keep RTSP as fallback with feature flag: Rejected per clarification - complete migration without backward compatibility reduces maintenance burden
- Use souphttpsrc with HTTP-FLV: Rejected - RTMP is standard MediaMTX protocol, no benefit to HTTP wrapper

---

### 2. RTMP Buffering Strategy

**Question**: How should buffering be controlled in RTMP pipeline to match RTSP jitter buffer behavior?

**Findings**:

**RTSP Buffering (Current)**:
- rtspsrc `latency` property: 200ms default jitter buffer
- Compensates for network jitter and packet reordering
- RTP-specific buffering for UDP transport

**RTMP Buffering (Target)**:
- RTMP uses TCP transport: No packet loss or reordering
- flvdemux `max-buffers` property: Controls queue depth before demuxer
- queue elements after demuxer: Per-track buffering for sync

**GStreamer Documentation Guidance**:
> "Live buffering: In live pipelines we usually introduce some latency between the capture and the playback elements. This latency can be introduced by a queue (such as a jitterbuffer) or by other means." (gst-docs/design/buffering.md)

**Decision**: Use flvdemux `max-buffers` property set to equivalent frame count for target latency.

**Rationale**: RTMP's TCP transport eliminates jitter compensation need. Buffering should focus on demuxer queue depth to prevent backpressure during caps negotiation and initial data flow.

**Calculation**:
- Target latency: 300ms total (per clarification)
- Assume 30fps video: 300ms ≈ 9 frames
- Set `max-buffers=10` on flvdemux for safety margin

**Alternatives Considered**:
- Custom jitterbuffer element: Rejected - TCP transport makes this unnecessary overhead
- No explicit buffering: Rejected - initial stream startup requires some buffering for smooth negotiation

---

### 3. Audio Track Validation

**Question**: How should pipeline detect and reject video-only streams (missing audio track)?

**Findings**:

**Current RTSP Behavior**:
- Dynamic pad creation in `_on_pad_added`: Detects audio/video by RTP caps
- Audio depayloader created only if audio RTP stream detected
- No explicit validation of audio track presence

**RTMP Behavior (Target)**:
- flvdemux creates pads based on FLV container metadata
- Audio track absence results in single video pad
- No automatic error on missing audio pad

**Decision**: Add explicit audio track validation in pipeline startup.

**Implementation**:
1. Monitor flvdemux pad-added signals during caps negotiation
2. After PAUSED state reached, verify both video and audio pads exist
3. If audio pad missing, transition to NULL and raise descriptive error
4. Error message: "Audio track required for dubbing pipeline - stream rejected"

**Rationale**: Failing fast with clear error message prevents silent failures downstream in STS pipeline. Audio is mandatory for dubbing - better to reject stream immediately than process video-only content.

**Alternatives Considered**:
- Allow video-only with warning: Rejected per clarification - dubbing requires audio, no value in processing video-only streams
- Auto-generate silent audio track: Rejected - hides real problem and creates invalid dubbing output

---

### 4. Latency Budget Allocation

**Question**: How should 300ms total latency budget be allocated across RTMP pipeline components?

**Findings**:

**GStreamer Latency Model** (from gst-docs/design/latency.md):
> "Example: Suppose asrc has a latency of 20ms and vsrc a latency of 33ms, the total latency in the pipeline has to be at least 33ms. This also means that the pipeline must have at least a `33 - 20 = 13ms` buffering on the audio stream."

**Pipeline Components**:
1. **rtmpsrc**: Network receive + TCP buffering
2. **flvdemux**: FLV parsing + demuxing
3. **h264parse/aacparse**: Codec header parsing
4. **queue elements**: Per-track buffering
5. **appsink**: Buffer emission to callback

**Decision**: Flexible allocation - no strict per-component breakdown.

**Rationale** (per clarification): Optimize based on profiling during implementation. Different components may dominate latency under different conditions (network variability, CPU load, stream characteristics).

**Measurement Strategy**:
1. Add PTS logging at each pipeline stage
2. Track delta from rtmpsrc buffer receipt to appsink emission
3. Profile under typical stream conditions (1080p30 H.264 + AAC)
4. Adjust queue `max-size-time` properties if specific component dominates

**Initial Configuration** (conservative starting point):
- rtmpsrc: Default properties (no explicit buffering)
- flvdemux `max-buffers`: 10 frames (~300ms at 30fps)
- queue `max-size-time`: 0 (unlimited) for initial testing
- Tighten after profiling identifies bottlenecks

**Alternatives Considered**:
- Strict per-component budget (e.g., 100ms rtmpsrc, 50ms demux, 150ms queues): Rejected - inflexible and may not match actual latency distribution
- Zero buffering (minimum latency mode): Rejected - causes pipeline startup failures during caps negotiation

---

### 5. RTMP URL Construction

**Question**: How should WorkerRunner construct RTMP URL from MediaMTX configuration?

**Findings**:

**MediaMTX RTMP Endpoint Pattern**:
```
rtmp://<host>:<port>/<app>/<stream>
```

**Current RTSP URL (from codebase)**:
```python
rtsp_url = "rtsp://mediamtx:8554/live/stream/in"
```

**RTMP Equivalent**:
```python
rtmp_url = "rtmp://mediamtx:1935/live/stream/in"
```

**Port Change**: RTSP 8554 -> RTMP 1935 (standard RTMP port)

**Decision**: Replace RTSP URL construction with RTMP URL construction in WorkerRunner.

**Implementation**:
```python
# Before (RTSP)
rtsp_url = f"rtsp://{mediamtx_host}:{rtsp_port}/{app_path}/{stream_id}/in"

# After (RTMP)
rtmp_url = f"rtmp://{mediamtx_host}:{rtmp_port}/{app_path}/{stream_id}/in"
```

**Configuration Updates**:
- MediaMTX host: No change (mediamtx)
- Port: 8554 -> 1935
- Path structure: No change (live/stream/in)

**Rationale**: RTMP URL structure mirrors RTSP for MediaMTX, only protocol and port change.

**Alternatives Considered**:
- Environment variable for protocol selection: Rejected - feature flag explicitly rejected in clarifications
- Auto-detection of protocol: Rejected - adds complexity without benefit, RTMP is the single target protocol

---

### 6. Test Migration Strategy

**Question**: What is the comprehensive strategy for updating existing unit, integration, and E2E tests?

**Findings**:

**Current Test Structure** (from codebase analysis):
```
apps/media-service/tests/
├── unit/
│   ├── test_input_pipeline.py       # Mock GStreamer elements
│   └── test_worker_runner.py        # Mock WorkerRunner initialization
└── integration/
    ├── test_publish_and_playback.py # ffmpeg RTSP publish
    └── test_segment_pipeline.py     # Full pipeline with MediaMTX

tests/e2e/
└── test_dual_compose_full_pipeline.py  # Cross-service E2E
```

**Test Changes Required**:

**Unit Tests**:
- `test_input_pipeline.py`: Update element mocks (rtmpsrc, flvdemux instead of rtspsrc, depayloaders)
- `test_worker_runner.py`: Update URL validation expectations (rtmp:// instead of rtsp://)
- Element creation tests: Expect rtmpsrc + flvdemux instead of rtspsrc + depayloaders
- URL validation: Expect RTMP URL format checking

**Integration Tests**:
- `test_publish_and_playback.py`: Change ffmpeg publish command from RTSP to RTMP
- `test_segment_pipeline.py`: Update MediaMTX configuration for RTMP endpoints
- Stream fixture publishing: Use RTMP output format in ffmpeg

**E2E Tests**:
- `test_dual_compose_full_pipeline.py`: Update docker-compose RTMP configuration
- MediaMTX configuration: Enable RTMP input, disable RTSP if not needed elsewhere
- Test assertions: Expect RTMP connection logs instead of RTSP

**Decision**: Parallel test update strategy - update tests alongside implementation per TDD.

**Implementation Order** (per TDD workflow):
1. Write failing unit tests for RTMP URL validation
2. Write failing unit tests for RTMP element creation
3. Implement RTMP URL validation
4. Implement RTMP element creation
5. Write failing integration tests for RTMP publish
6. Implement integration test fixtures (ffmpeg RTMP publish)
7. Write failing E2E tests for RTMP pipeline
8. Update E2E docker-compose configuration

**Coverage Maintenance**:
- Current coverage: 80% minimum per constitution
- RTMP migration: Maintain 80% minimum, target 95% for input pipeline (critical path)
- Remove RTSP-specific tests completely - no legacy test retention

**Rationale**: TDD workflow ensures tests define behavior before implementation. Parallel update prevents test rot and validates migration correctness at each level.

**Alternatives Considered**:
- Update all tests after implementation: Rejected - violates TDD principle (Principle VIII)
- Keep RTSP tests as regression suite: Rejected - RTSP support being completely removed per clarification
- Separate test PR from implementation PR: Rejected - tests and implementation must be atomic per TDD

---

## Technology Stack Confirmation

**Language**: Python 3.10 (per constitution and pyproject.toml)
**GStreamer Version**: 1.0 (PyGObject >= 3.44.0 from pyproject.toml)
**Required Elements**:
- rtmpsrc (gst-plugins-bad)
- flvdemux (gst-plugins-good)
- h264parse (gst-plugins-bad)
- aacparse (gst-plugins-good)
- appsink (gst-plugins-base)

**Deployment Verification**: All required elements available in standard GStreamer 1.0 installation on Ubuntu 20.04+ (media-service deployment target)

## Summary of Decisions

1. **Pipeline Architecture**: rtmpsrc -> flvdemux -> parsers -> appsinks (3 fewer elements than RTSP)
2. **Buffering**: flvdemux `max-buffers=10` for initial implementation, tune via profiling
3. **Audio Validation**: Explicit check after PAUSED state, fail fast with descriptive error
4. **Latency Budget**: 300ms total, flexible allocation based on profiling (no strict per-component breakdown)
5. **URL Construction**: Replace RTSP URLs with RTMP URLs (port 8554 -> 1935)
6. **Test Migration**: Parallel TDD update - write failing tests, implement, update fixtures
7. **RTSP Removal**: Complete removal - no backward compatibility, feature flags, or legacy test retention

## Next Steps

Proceed to Phase 1: Design artifacts (data-model.md, contracts/, quickstart.md)
