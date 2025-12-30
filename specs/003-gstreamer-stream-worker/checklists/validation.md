# Validation Checklist: Stream Worker Implementation

**Feature**: 003-gstreamer-stream-worker
**Purpose**: Testable validation criteria for implementation verification
**Created**: 2025-12-28
**Test Fixture**: `tests/fixtures/test-streams/1-min-nfl.mp4` (60s, H.264/AAC)

## Prerequisites

Before running validation, ensure:

```bash
# 1. MediaMTX is running
make media-dev

# 2. Test fixture is available
ls tests/fixtures/test-streams/1-min-nfl.mp4

# 3. Virtual environment is activated
source .venv/bin/activate
```

---

## Phase 1: GStreamer Pipeline Foundation

### VAL-001: GStreamer Pipeline Builds Without Errors

**Requirement**: FR-001, FR-002, FR-003

**Test Command**:
```bash
cd apps/media-service && python -c "
from media_service.pipeline.input import InputPipeline
from media_service.pipeline.output import OutputPipeline
p1 = InputPipeline.build_pipeline_string('rtsp://localhost:8554/test')
p2 = OutputPipeline.build_pipeline_string('rtmp://localhost:1935/live/out')
print('Input:', p1)
print('Output:', p2)
"
```

**Pass Criteria**:
- [ ] No ImportError or ModuleNotFoundError
- [ ] Pipeline strings contain `rtspsrc`, `rtph264depay`, `decodebin`
- [ ] Output pipeline contains `flvmux`, `rtmpsink`

**Fail Criteria**: Any exception raised or missing GStreamer elements

---

### VAL-002: RTSP Pull Works with MediaMTX

**Requirement**: FR-002, SC-001

**Test Command**:
```bash
# Terminal 1: Publish test fixture to MediaMTX
ffmpeg -re -stream_loop 0 -i tests/fixtures/test-streams/1-min-nfl.mp4 \
  -c copy -f rtsp rtsp://localhost:8554/live/test/in

# Terminal 2: Verify RTSP pull
ffprobe -v error -show_streams rtsp://localhost:8554/live/test/in
```

**Pass Criteria**:
- [ ] ffprobe shows video stream: codec_name=h264
- [ ] ffprobe shows audio stream: codec_name=aac
- [ ] No connection timeout within 5 seconds

**Fail Criteria**: Connection refused, timeout, or missing streams

---

### VAL-003: RTMP Push Works with MediaMTX

**Requirement**: FR-007

**Test Command**:
```bash
# Passthrough test (video only, 10 seconds)
ffmpeg -re -t 10 -i tests/fixtures/test-streams/1-min-nfl.mp4 \
  -c copy -f flv rtmp://localhost:1935/live/test/out

# Verify output
ffprobe -v error -show_streams rtmp://localhost:1935/live/test/out
```

**Pass Criteria**:
- [ ] RTMP publish completes without error
- [ ] Output stream accessible at `rtmp://localhost:1935/live/test/out`
- [ ] ffprobe shows matching video codec (h264)

**Fail Criteria**: Connection refused, publish failure, or codec mismatch

---

### VAL-004: Video Codec Passthrough (No Re-encode)

**Requirement**: FR-008, SC-002

**Test Command**:
```bash
# Run worker in passthrough mode (10s)
timeout 15 python -m media_service.worker.runner \
  --stream-id test \
  --sts-mode passthrough

# Compare input/output codec
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name \
  rtmp://localhost:1935/live/test/out
```

**Pass Criteria**:
- [ ] Output video codec is `h264` (not `h264_nvenc`, `libx264`, etc.)
- [ ] No "encoder" mentioned in ffprobe output
- [ ] Video bitrate within 10% of original

**Fail Criteria**: Codec re-encoding detected or significant bitrate change

---

### VAL-005: Full Passthrough with 1-min-nfl.mp4

**Requirement**: SC-001, SC-003

**Test Command**:
```bash
make media-test-integration PYTEST_ARGS="-k test_worker_passthrough_1min_nfl"
```

**Pass Criteria**:
- [ ] Worker processes 60s fixture without errors
- [ ] Worker logs "EOS received" at end
- [ ] Output duration is 60s +/- 100ms
- [ ] Exit code is 0

**Fail Criteria**: Pipeline errors, premature termination, or duration mismatch > 100ms

---

## Phase 2: Audio Chunking and STS Client

### VAL-006: Audio Chunking Produces Correct Duration Fragments

**Requirement**: FR-009, FR-010

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_chunker"
```

**Pass Criteria**:
- [ ] `test_chunker_accumulates_to_target_duration` passes
- [ ] Each chunk duration is 1000ms +/- 10ms
- [ ] `test_chunker_preserves_timestamp` passes (t0_ns captured from first buffer)
- [ ] `test_chunker_emits_metadata` passes (fragment_id, batch_number present)

**Fail Criteria**: Chunk duration outside 990-1010ms range, missing metadata

---

### VAL-007: Partial Chunk on EOS

**Requirement**: FR-011

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_chunker_handles_eos_partial_chunk"
```

**Pass Criteria**:
- [ ] Test passes
- [ ] Partial chunk (< 1s) emitted on EOS
- [ ] Partial chunk has correct actual duration_ns

**Fail Criteria**: Partial chunk discarded or duration_ns incorrect

---

### VAL-008: STS Client Sends Correct Request Format

**Requirement**: FR-012, FR-013

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_sts_client_builds_request"
```

**Pass Criteria**:
- [ ] Request contains: fragment_id (UUID), stream_id, sequence_number
- [ ] Request contains: audio (base64-encoded), config (languages, voice)
- [ ] Request contains: timeout_ms (default 8000)
- [ ] Authorization header present with WORKER_STS_API_KEY

**Fail Criteria**: Missing required fields or incorrect encoding

---

### VAL-009: STS Client Timeout Handling

**Requirement**: FR-014, FR-015, FR-016

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k 'test_sts_client_timeout or test_sts_client_retry'"
```

**Pass Criteria**:
- [ ] Client times out after WORKER_STS_TIMEOUT_MS (default 8000ms)
- [ ] Client retries up to WORKER_STS_MAX_RETRIES on transient failures
- [ ] Fallback to original audio after max retries exceeded

**Fail Criteria**: No timeout, missing retries, or no fallback behavior

---

### VAL-010: STS Integration with Mock Server

**Requirement**: FR-012 (integration validation)

**Test Command**:
```bash
make media-test-integration PYTEST_ARGS="-k test_sts_client_with_mock_server"
```

**Pass Criteria**:
- [ ] HTTP round-trip completes successfully
- [ ] Response parsed correctly (fragment_id, status, dubbed_audio)
- [ ] processing_time_ms > 0

**Fail Criteria**: Connection error, parsing failure, or missing response fields

---

## Phase 3: A/V Synchronization

### VAL-011: A/V Offset Calculation

**Requirement**: FR-017, FR-018

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_av_offset_calculation"
```

**Pass Criteria**:
- [ ] Default av_offset_ns is 10,000,000,000 (10 seconds)
- [ ] Offset applied correctly to video PTS
- [ ] Offset applied correctly to audio PTS

**Fail Criteria**: Incorrect default value or offset not applied

---

### VAL-012: A/V Sync Stays Within 120ms

**Requirement**: FR-019, SC-004

**Test Command**:
```bash
make media-test-integration PYTEST_ARGS="-k test_av_sync_within_threshold"
```

**Pass Criteria**:
- [ ] av_sync_delta_ms metric stays < 120ms throughout processing
- [ ] No sync drift > 120ms detected in logs
- [ ] Maximum observed delta logged at end of test

**Fail Criteria**: Any point where av_sync_delta_ms >= 120ms

---

### VAL-013: Drift Correction Uses Slew (Not Jump)

**Requirement**: FR-020

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_drift_correction_slew"
```

**Pass Criteria**:
- [ ] Correction rate is gradual (< 10ms per second adjustment)
- [ ] No PTS discontinuities > 50ms in output
- [ ] Correction direction matches drift direction

**Fail Criteria**: Hard jumps detected or discontinuities in output PTS

---

## Phase 4: Circuit Breaker

### VAL-014: Circuit Breaker Opens After 5 Failures

**Requirement**: FR-021

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_circuit_breaker_opens_after_failures"
```

**Pass Criteria**:
- [ ] Breaker state is "closed" initially
- [ ] After 5 consecutive failures, breaker state is "open"
- [ ] worker_sts_breaker_state metric equals 2 when open

**Fail Criteria**: Breaker opens before 5 failures or doesn't open after 5

---

### VAL-015: Circuit Breaker Half-Open After Cooldown

**Requirement**: FR-022

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_circuit_breaker_half_open"
```

**Pass Criteria**:
- [ ] After 30s cooldown, breaker state is "half_open"
- [ ] Exactly 1 probe request allowed in half_open state
- [ ] worker_sts_breaker_state metric equals 1 when half_open

**Fail Criteria**: Incorrect cooldown duration or multiple probes allowed

---

### VAL-016: Circuit Breaker Closes on Success

**Requirement**: FR-023, SC-007

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_circuit_breaker_closes_on_success"
```

**Pass Criteria**:
- [ ] Successful probe transitions breaker to "closed"
- [ ] Normal processing resumes after close
- [ ] worker_sts_breaker_state metric equals 0 when closed

**Fail Criteria**: Breaker stays in half_open after success

---

### VAL-017: Fallback Audio When Breaker Open

**Requirement**: FR-024

**Test Command**:
```bash
make media-test-unit PYTEST_ARGS="-k test_fallback_audio_used_when_open"
```

**Pass Criteria**:
- [ ] STS API not called when breaker open
- [ ] Original audio (passthrough) used for output
- [ ] worker_fallback_total counter increments

**Fail Criteria**: STS called when breaker open or no fallback audio

---

### VAL-018: Circuit Breaker State Logging

**Requirement**: FR-025

**Test Command**:
```bash
make media-test-integration PYTEST_ARGS="-k test_circuit_breaker_recovery_cycle -v" 2>&1 | grep -E "(OPEN|HALF_OPEN|CLOSED)"
```

**Pass Criteria**:
- [ ] Log entry for each state transition
- [ ] Log contains streamId correlation
- [ ] State transitions: closed -> open -> half_open -> closed

**Fail Criteria**: Missing state transition logs or no streamId

---

## Phase 5: Prometheus Metrics

### VAL-019: Prometheus Metrics Endpoint Exposed

**Requirement**: FR-026, SC-008

**Test Command**:
```bash
# Start worker with metrics
python -m media_service.worker.runner --stream-id test &
sleep 5
curl -s http://localhost:8000/metrics | head -20
```

**Pass Criteria**:
- [ ] GET /metrics returns HTTP 200
- [ ] Response content-type is text/plain
- [ ] Response contains "# HELP" and "# TYPE" lines

**Fail Criteria**: Connection refused, non-200 status, or invalid format

---

### VAL-020: Counter Metrics Exposed

**Requirement**: FR-027

**Test Command**:
```bash
curl -s http://localhost:8000/metrics | grep -E "^worker_(audio_fragments|fallback|gst_bus_errors)_total"
```

**Pass Criteria**:
- [ ] worker_audio_fragments_total present with TYPE counter
- [ ] worker_fallback_total present with TYPE counter
- [ ] worker_gst_bus_errors_total present with TYPE counter

**Fail Criteria**: Missing metrics or wrong TYPE

---

### VAL-021: Gauge Metrics Exposed

**Requirement**: FR-028

**Test Command**:
```bash
curl -s http://localhost:8000/metrics | grep -E "^worker_(inflight_fragments|av_sync_delta_ms|sts_breaker_state)"
```

**Pass Criteria**:
- [ ] worker_inflight_fragments present with TYPE gauge
- [ ] worker_av_sync_delta_ms present with TYPE gauge
- [ ] worker_sts_breaker_state present with TYPE gauge (0=closed, 1=half_open, 2=open)

**Fail Criteria**: Missing metrics or wrong TYPE

---

### VAL-022: Histogram Metrics Exposed

**Requirement**: FR-029

**Test Command**:
```bash
curl -s http://localhost:8000/metrics | grep -E "^worker_sts_rtt_ms"
```

**Pass Criteria**:
- [ ] worker_sts_rtt_ms present with TYPE histogram
- [ ] Buckets defined (_bucket suffix)
- [ ] _sum and _count suffixes present

**Fail Criteria**: Missing histogram or missing bucket definitions

---

### VAL-023: Structured Logging with Correlation IDs

**Requirement**: FR-030

**Test Command**:
```bash
make media-test-integration PYTEST_ARGS="-k test_worker_passthrough" -v 2>&1 | grep -E '"streamId":|"runId":|"instanceId":'
```

**Pass Criteria**:
- [ ] All log entries contain streamId
- [ ] All log entries contain runId
- [ ] All log entries contain instanceId

**Fail Criteria**: Missing correlation IDs in log entries

---

## End-to-End Validation

### VAL-024: Full Pipeline Integration Test

**Requirement**: All FR, SC-001 through SC-008

**Test Command**:
```bash
make media-test-integration
```

**Pass Criteria**:
- [ ] All integration tests pass (exit code 0)
- [ ] No test timeouts
- [ ] Coverage report generated

**Fail Criteria**: Any test failure or timeout

---

### VAL-025: Coverage Threshold Met

**Requirement**: SC-005

**Test Command**:
```bash
make media-test-coverage
```

**Pass Criteria**:
- [ ] Overall coverage >= 80%
- [ ] audio/chunker.py coverage >= 95%
- [ ] sync/av_sync.py coverage >= 95%
- [ ] sts/client.py coverage >= 90%

**Fail Criteria**: Coverage below thresholds

---

## Summary

| Phase | Checks | Critical |
|-------|--------|----------|
| Phase 1: GStreamer Pipeline | VAL-001 to VAL-005 | VAL-002, VAL-003, VAL-005 |
| Phase 2: Audio Chunking & STS | VAL-006 to VAL-010 | VAL-006, VAL-008 |
| Phase 3: A/V Sync | VAL-011 to VAL-013 | VAL-012 |
| Phase 4: Circuit Breaker | VAL-014 to VAL-018 | VAL-014, VAL-017 |
| Phase 5: Prometheus Metrics | VAL-019 to VAL-023 | VAL-019 |
| End-to-End | VAL-024 to VAL-025 | VAL-025 |

**Total Checks**: 25
**Critical Checks**: 10 (must pass for phase completion)

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-28 | 1.0 | Initial validation checklist |
