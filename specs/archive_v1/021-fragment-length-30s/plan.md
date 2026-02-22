# Implementation Plan: Fragment Length Increase (6s to 30s)

**Feature ID**: 021-fragment-length-30s
**Spec File**: specs/021-fragment-length-30s/spec.md
**Created**: 2026-01-11
**Status**: Ready for Implementation

## Executive Summary

This plan details the implementation of increasing the fragment/segment duration from 6 seconds to 30 seconds across the live broadcast dubbing pipeline. The change impacts both media-service and sts-service, with corresponding updates to E2E test configurations.

**IMPORTANT ARCHITECTURAL CHANGE**: This plan uses the "buffer and wait" approach for A/V synchronization instead of av_offset_ns. Video segments are buffered until corresponding dubbed audio arrives, then output together as a synchronized pair. **Output is re-encoded with PTS starting from 0** (not original stream PTS).

### Key Changes Summary

| Component | Current Value | New Value |
|-----------|---------------|-----------|
| Segment Duration | 6s (6_000_000_000ns) | 30s (30_000_000_000ns) |
| A/V Sync Approach | av_offset_ns (6s) | Buffer and Wait (no offset) |
| Output PTS | Original stream PTS | PTS=0 (reset per segment) |
| Output Mode | Passthrough | Re-encoded |
| STS Timeout | 8s (8000ms) | 60s (60000ms) |
| Chunk Duration | 6000ms | 30000ms |
| Validation Max (chunk) | le=6000 | le=30000 |
| Validation Max (timeout) | le=30000 | le=120000 |
| Expected Segments (60s) | 10 | 2 |
| Fragment Timeout (E2E) | 8s | 60s |
| Pipeline Completion (E2E) | 90s | 120s |
| Peak Memory | ~45MB | ~162MB |

### Removed Components (Buffer and Wait Architecture)

| Component | File | Reason |
|-----------|------|--------|
| av_offset_ns | state.py | Replaced by buffer-and-wait pairing |
| needs_correction() | state.py | No drift correction with pairing |
| apply_slew_correction() | state.py | No drift correction with pairing |
| slew_rate_ns | state.py | No slew adjustment needed |
| av_offset_ns parameter | av_sync.py | PTS reset to 0 (not original PTS) |
| Drift correction logic | av_sync.py | Sync achieved through pairing |
| Original PTS preservation | av_sync.py | PTS starts from 0 per segment |
| Video passthrough | output_pipeline.py | Re-encoding required for PTS reset |

---

## Implementation Phases

### Phase 1: Test Infrastructure (TDD Setup)

Per Constitution Principle VIII (Test-First Development), all tests must be written before implementation.

**Priority**: P0 - Must complete before any code changes
**Estimated Duration**: 1-2 hours

#### 1.1 Update Existing Unit Tests

Tests that currently validate 6-second durations must be updated to expect 30-second durations.

**Files to Modify**:

| Test File | Changes Required |
|-----------|------------------|
| `apps/media-service/tests/unit/test_models_segments.py` | Update `DEFAULT_SEGMENT_DURATION_NS` assertions from 6s to 30s |
| `apps/media-service/tests/unit/test_models_state.py` | Remove `av_offset_ns` tests, add buffer-and-wait behavior tests |
| `apps/media-service/tests/unit/test_segment_buffer.py` | Update duration threshold checks and expected segment counts |
| `apps/media-service/tests/unit/test_av_sync.py` | Remove offset tests, add buffer-and-wait tests, verify original PTS usage |
| `apps/media-service/tests/unit/test_sts_models.py` | Update `StreamConfig.chunk_duration_ms` default from 6000 to 30000 |
| `apps/media-service/tests/unit/test_worker_runner.py` | Update `WorkerConfig.segment_duration_ns` default from 6s to 30s |

#### 1.2 Add New Unit Tests

**New Tests to Create** (per spec User Stories):

```python
# apps/media-service/tests/unit/test_models_segments.py
def test_video_segment_duration_30s():
    """FR-001: VideoSegment.DEFAULT_SEGMENT_DURATION_NS is 30_000_000_000."""
    assert VideoSegment.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000

def test_audio_segment_duration_30s():
    """FR-002: AudioSegment.DEFAULT_SEGMENT_DURATION_NS is 30_000_000_000."""
    assert AudioSegment.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000

# apps/media-service/tests/unit/test_segment_buffer.py
def test_segment_buffer_accumulates_30s():
    """FR-003: SegmentBuffer emits at 30s threshold."""
    buffer = SegmentBuffer(stream_id="test", segment_dir=Path("/tmp"))
    assert buffer.segment_duration_ns == 30_000_000_000

# apps/media-service/tests/unit/test_av_sync.py
def test_av_sync_manager_buffers_video_until_audio_ready():
    """FR-010: Video segments buffered until dubbed audio received."""
    manager = AvSyncManager()
    # Push video, should return None (buffered)
    result = await manager.push_video(video_segment, video_data)
    assert result is None
    assert manager.video_buffer_size == 1

def test_sync_pair_pts_starts_from_zero():
    """FR-012: Output PTS starts from 0 (re-encoded output)."""
    manager = AvSyncManager()
    # Create pair and verify PTS is 0, not original
    pair = manager._create_pair(video_segment, video_data, audio_segment, audio_data)
    assert pair.pts_ns == 0  # PTS reset to 0

def test_av_sync_state_no_offset():
    """FR-012: AvSyncState should not have av_offset_ns."""
    state = AvSyncState()
    assert not hasattr(state, 'av_offset_ns') or state.av_offset_ns == 0

def test_output_is_reencoded():
    """FR-012: Output video must be re-encoded (not passthrough)."""
    manager = AvSyncManager()
    pair = manager._create_pair(video_segment, video_data, audio_segment, audio_data)
    # Verify output is marked for re-encoding
    assert pair.requires_reencode == True

# apps/media-service/tests/unit/test_sts_models.py
def test_stream_config_chunk_duration_30000():
    """FR-006: StreamConfig.chunk_duration_ms defaults to 30000."""
    config = StreamConfig()
    assert config.chunk_duration_ms == 30000
```

**STS Service Tests**:

```python
# apps/sts-service/tests/unit/test_session.py (create if not exists)
def test_stream_session_timeout_ms_default_60000():
    """FR-008: StreamSession.timeout_ms defaults to 60000."""
    session = StreamSession(sid="test", stream_id="s1", worker_id="w1")
    assert session.timeout_ms == 60000

def test_stream_session_chunk_duration_30000():
    """FR-007: StreamSession.chunk_duration_ms defaults to 30000."""
    session = StreamSession(sid="test", stream_id="s1", worker_id="w1")
    assert session.chunk_duration_ms == 30000

# apps/sts-service/tests/unit/test_stream_models.py (create if not exists)
def test_stream_config_payload_accepts_30000ms():
    """FR-014: StreamConfigPayload accepts chunk_duration_ms=30000."""
    payload = StreamConfigPayload(chunk_duration_ms=30000)
    assert payload.chunk_duration_ms == 30000

def test_stream_init_payload_timeout_120000_valid():
    """FR-015: StreamInitPayload accepts timeout_ms up to 120000."""
    payload = StreamInitPayload(
        stream_id="test",
        worker_id="w1",
        config=StreamConfigPayload(),
        timeout_ms=120000,
    )
    assert payload.timeout_ms == 120000
```

---

### Phase 2: Media Service Core Changes (P1)

**Priority**: P1 - Core functionality
**Estimated Duration**: 2-3 hours
**Dependencies**: Phase 1 tests must fail first

#### 2.1 Update Segment Duration Constants

**File**: `apps/media-service/src/media_service/models/segments.py`

| Line | Current | New |
|------|---------|-----|
| 49 | `DEFAULT_SEGMENT_DURATION_NS: ClassVar[int] = 6_000_000_000` | `DEFAULT_SEGMENT_DURATION_NS: ClassVar[int] = 30_000_000_000` |
| 152 | `DEFAULT_SEGMENT_DURATION_NS: ClassVar[int] = 6_000_000_000` | `DEFAULT_SEGMENT_DURATION_NS: ClassVar[int] = 30_000_000_000` |

Also update docstrings:
- Line 8: "Each segment represents ~6 seconds" -> "Each segment represents ~30 seconds"
- Line 36-37: "duration_ns should be ~6_000_000_000 (6 seconds)" -> "duration_ns should be ~30_000_000_000 (30 seconds)"
- Line 137-138: Same change for AudioSegment

**File**: `apps/media-service/src/media_service/buffer/segment_buffer.py`

| Line | Current | New |
|------|---------|-----|
| 68 | `DEFAULT_SEGMENT_DURATION_NS = 6_000_000_000` | `DEFAULT_SEGMENT_DURATION_NS = 30_000_000_000` |

Also update docstrings:
- Line 5: "default 6 seconds" -> "default 30 seconds"
- Line 8: "6-second segments" -> "30-second segments"
- Line 54: "6-second segments" -> "30-second segments"
- Line 83: "segment_duration_ns: Target segment duration (default 6 seconds)" -> "segment_duration_ns: Target segment duration (default 30 seconds)"

#### 2.2 Simplify A/V Sync (Buffer and Wait)

**File**: `apps/media-service/src/media_service/models/state.py`

**REMOVE the following from AvSyncState**:
- `av_offset_ns` field (line 192)
- `slew_rate_ns` field (line 197)
- `av_offset_ms` property (lines 205-207)
- `adjust_video_pts()` method - modify to return original PTS
- `adjust_audio_pts()` method - modify to return original PTS
- `needs_correction()` method (lines 244-250)
- `apply_slew_correction()` method (lines 252-281)

**Simplified AvSyncState**:
```python
@dataclass
class AvSyncState:
    """A/V synchronization state (buffer-and-wait approach).

    Video segments are buffered until corresponding dubbed audio arrives,
    then output together as a synchronized pair using original PTS values.

    Attributes:
        video_pts_last: Last video PTS pushed to output.
        audio_pts_last: Last audio PTS pushed to output.
        sync_delta_ns: Current measured delta between video and audio.
        drift_threshold_ns: Threshold for logging sync warnings.
    """

    video_pts_last: int = 0
    audio_pts_last: int = 0
    sync_delta_ns: int = 0
    drift_threshold_ns: int = 100_000_000  # 100ms (for logging only)

    @property
    def sync_delta_ms(self) -> float:
        """Current sync delta in milliseconds."""
        return self.sync_delta_ns / 1_000_000

    def update_sync_state(self, video_pts: int, audio_pts: int) -> None:
        """Update sync state after pushing frames."""
        self.video_pts_last = video_pts
        self.audio_pts_last = audio_pts
        self.sync_delta_ns = abs(video_pts - audio_pts)

    def reset(self) -> None:
        """Reset sync state to initial values."""
        self.video_pts_last = 0
        self.audio_pts_last = 0
        self.sync_delta_ns = 0
```

**File**: `apps/media-service/src/media_service/sync/av_sync.py`

**REMOVE from AvSyncManager**:
- `av_offset_ns` parameter from __init__ (line 65)
- Drift correction logic in `_create_pair()` (lines 186-192)
- Original PTS preservation (output PTS now starts from 0)

**ADD to AvSyncManager**:
- Set `pts_ns=0` in SyncPair (output starts from 0)
- Add `requires_reencode=True` flag to SyncPair

**Updated _create_pair()**:
```python
def _create_pair(
    self,
    video_segment: VideoSegment,
    video_data: bytes,
    audio_segment: AudioSegment,
    audio_data: bytes,
) -> SyncPair:
    """Create synchronized pair from video and audio segments.

    Output PTS is reset to 0 for each segment. Video and audio are paired
    together before output (buffer-and-wait approach) and re-encoded.
    """
    # Output PTS starts from 0 (re-encoded output, not original stream PTS)
    output_pts = 0

    # Track original PTS for logging only
    original_video_pts = video_segment.t0_ns
    original_audio_pts = audio_segment.t0_ns

    # Log sync delta for monitoring (informational only)
    sync_delta_ns = abs(original_video_pts - original_audio_pts)
    if sync_delta_ns > self.state.drift_threshold_ns:
        logger.warning(
            f"Original PTS sync delta exceeds threshold: {sync_delta_ns / 1e6:.1f}ms > "
            f"{self.state.drift_threshold_ns / 1e6:.0f}ms"
        )

    pair = SyncPair(
        video_segment=video_segment,
        video_data=video_data,
        audio_segment=audio_segment,
        audio_data=audio_data,
        pts_ns=output_pts,  # PTS reset to 0
        requires_reencode=True,  # Video must be re-encoded
    )

    logger.info(
        f"A/V PAIR CREATED: batch={video_segment.batch_number}, "
        f"output_pts=0, original_pts={original_video_pts / 1e9:.2f}s, "
        f"v_size={len(video_data)}, a_size={len(audio_data)}, "
        f"dubbed={audio_segment.is_dubbed}, reencode=True"
    )

    return pair
```

Also update docstrings:
- Line 10: Remove "6-second default offset" reference
- Line 68: Remove "av_offset_ns: Base PTS offset..." from docstring

#### 2.3 Update STS Communication Models

**File**: `apps/media-service/src/media_service/sts/models.py`

| Line | Current | New |
|------|---------|-----|
| 43 | `chunk_duration_ms: int = 6000` | `chunk_duration_ms: int = 30000` |

#### 2.4 Update Worker Configuration

**File**: `apps/media-service/src/media_service/worker/worker_runner.py`

| Line | Current | New |
|------|---------|-----|
| 66 | `segment_duration_ns: int = 6_000_000_000  # 6 seconds` | `segment_duration_ns: int = 30_000_000_000  # 30 seconds` |

Also update docstrings:
- Line 6: "Segment buffer (accumulate to 6s segments)" -> "Segment buffer (accumulate to 30s segments)"
- Line 75: "Segment buffer accumulates 6-second segments" -> "Segment buffer accumulates 30-second segments"

---

### Phase 3: STS Service Changes (P1)

**Priority**: P1 - Required for timeout and validation
**Estimated Duration**: 1-2 hours
**Dependencies**: Phase 1 tests must fail first

#### 3.1 Update Session Defaults

**File**: `apps/sts-service/src/sts_service/full/session.py`

| Line | Current | New |
|------|---------|-----|
| 95 | `chunk_duration_ms: int = 6000` | `chunk_duration_ms: int = 30000` |
| 100 | `timeout_ms: int = 8000` | `timeout_ms: int = 60000` |

#### 3.2 Update Validation Constraints

**File**: `apps/sts-service/src/sts_service/echo/models/stream.py`

| Line | Current | New |
|------|---------|-----|
| 31 | `le=6000,  # Updated to accept 6000ms (6 second segments)` | `le=30000,  # Accept up to 30000ms (30 second segments)` |
| 73-74 | `le=30000,` | `le=120000,` |

Full change for chunk_duration_ms:
```python
chunk_duration_ms: int = Field(
    default=1000,
    ge=100,
    le=30000,  # Accept up to 30000ms (30 second segments)
    description="Expected fragment duration in milliseconds",
)
```

Full change for timeout_ms:
```python
timeout_ms: int = Field(
    default=8000,
    ge=1000,
    le=120000,  # Allow extended timeouts up to 120s for slow models
    description="Per-fragment timeout in milliseconds",
)
```

#### 3.3 Update ASR Postprocessing (if needed)

**File**: `apps/sts-service/src/sts_service/asr/postprocessing.py`

The `split_long_segments` function has a default `max_duration_seconds: float = 6.0`. This should be updated:

| Line | Current | New |
|------|---------|-----|
| 95 | `max_duration_seconds: float = 6.0,` | `max_duration_seconds: float = 30.0,` |

Note: This is a parameter default. The actual shaping config may override it. Review `UtteranceShapingConfig` in `asr/models.py` to ensure `max_segment_duration_seconds` defaults are also updated if applicable.

---

### Phase 4: E2E Test Configuration (P2)

**Priority**: P2 - Required for test validation
**Estimated Duration**: 1 hour
**Dependencies**: Phases 2-3 complete

#### 4.1 Update E2E Config

**File**: `tests/e2e/config.py`

| Class | Field | Current | New |
|-------|-------|---------|-----|
| TestConfig | SEGMENT_DURATION_SEC | 6 | 30 |
| TestConfig | SEGMENT_DURATION_NS | 6_000_000_000 | 30_000_000_000 |
| TestConfig | EXPECTED_SEGMENTS | 10 | 2 |
| TimeoutConfig | FRAGMENT_TIMEOUT | 8 | 60 |
| TimeoutConfig | PIPELINE_COMPLETION | 90 | 120 |

Full changes:
```python
class TestConfig:
    # ...
    SEGMENT_DURATION_SEC = 30
    SEGMENT_DURATION_NS = 30_000_000_000
    MAX_INFLIGHT = 3

    # Expected values for 60-second test fixture
    EXPECTED_SEGMENTS = 2  # 60s / 30s = 2 segments
    # ...

class TimeoutConfig:
    # ...
    PIPELINE_COMPLETION = 120  # Increased for 30s fragments
    # ...
    FRAGMENT_TIMEOUT = 60  # Increased for 30s fragment processing
```

---

### Phase 5: Integration and E2E Tests (P2)

**Priority**: P2 - Validation
**Estimated Duration**: 2-3 hours
**Dependencies**: Phases 1-4 complete

#### 5.1 Update E2E Test Assertions

**File**: `tests/e2e/test_full_pipeline.py`

Review and update any hardcoded expectations for:
- Segment counts (10 -> 2 for 60s fixture)
- Timeout values
- Duration validations
- A/V sync expectations (now < 100ms from pairing, not offset-based)

#### 5.2 Run Full E2E Test Suite

```bash
# Run P1 tests (critical path)
make e2e-test-p1

# Validate segment count
# Expected: 2 segments from 60-second fixture
```

---

## Files to Modify - Complete List

### Media Service (P1)

| File Path | Change Type | Priority |
|-----------|-------------|----------|
| `apps/media-service/src/media_service/models/segments.py` | Constant update | P1 |
| `apps/media-service/src/media_service/models/state.py` | **Major refactor** - remove av_offset, drift correction | P1 |
| `apps/media-service/src/media_service/buffer/segment_buffer.py` | Constant update | P1 |
| `apps/media-service/src/media_service/sts/models.py` | Default update | P1 |
| `apps/media-service/src/media_service/sync/av_sync.py` | **Major refactor** - buffer-and-wait, PTS=0, requires_reencode | P1 |
| `apps/media-service/src/media_service/pipelines/output_pipeline.py` | Configure output muxer for PTS=0, video re-encoding | P1 |
| `apps/media-service/src/media_service/worker/worker_runner.py` | Config update | P1 |

### STS Service (P1)

| File Path | Change Type | Priority |
|-----------|-------------|----------|
| `apps/sts-service/src/sts_service/full/session.py` | Default update | P1 |
| `apps/sts-service/src/sts_service/echo/models/stream.py` | Validation update | P1 |
| `apps/sts-service/src/sts_service/asr/postprocessing.py` | Default update | P2 |

### E2E Tests (P2)

| File Path | Change Type | Priority |
|-----------|-------------|----------|
| `tests/e2e/config.py` | Config update | P2 |
| `tests/e2e/test_full_pipeline.py` | Assertion update | P2 |

### Unit Tests (P0 - Write First)

| File Path | Change Type | Priority |
|-----------|-------------|----------|
| `apps/media-service/tests/unit/test_models_segments.py` | Update assertions | P0 |
| `apps/media-service/tests/unit/test_models_state.py` | **Major update** - remove av_offset tests, add buffer tests | P0 |
| `apps/media-service/tests/unit/test_segment_buffer.py` | Update assertions | P0 |
| `apps/media-service/tests/unit/test_av_sync.py` | **Major update** - buffer-and-wait tests, PTS=0 tests, reencode tests | P0 |
| `apps/media-service/tests/unit/test_output_pipeline.py` | Add PTS=0 output tests, video re-encoding tests | P0 |
| `apps/media-service/tests/unit/test_sts_models.py` | Update assertions | P0 |
| `apps/media-service/tests/unit/test_worker_runner.py` | Update assertions | P0 |
| `apps/sts-service/tests/unit/test_session.py` | Create new tests | P0 |
| `apps/sts-service/tests/unit/test_stream_models.py` | Create new tests | P0 |

---

## Test Strategy

### TDD Workflow (Per Constitution Principle VIII)

1. **Write failing tests first** (Phase 1)
2. **Run tests - verify they FAIL** with current 6s values
3. **Implement changes** (Phases 2-4)
4. **Run tests - verify they PASS** with new 30s values
5. **Check coverage** (80% minimum, 95% for critical paths)

### Test Commands

```bash
# Phase 1: Update and run unit tests (should FAIL before implementation)
make media-test-unit
make sts-test-unit

# Phase 2-4: After implementation (should PASS)
make media-test-unit
make sts-test-unit

# Phase 5: Integration and E2E
make media-test-integration
make e2e-test-p1
make e2e-test-full

# Coverage verification
make media-test-coverage
make sts-test-coverage
```

### Success Criteria Verification

| SC ID | Criteria | Test |
|-------|----------|------|
| SC-001 | 60s fixture produces 2 segments | `test_full_pipeline.py` |
| SC-002 | Duration within 30s +/- 100ms | `test_segment_buffer.py` |
| SC-003 | A/V sync < 100ms (from pairing) | `test_av_sync.py` |
| SC-004 | STS completes within 60s timeout | `test_full_pipeline.py` |
| SC-005 | Unit tests pass | `make media-test-unit` |
| SC-006 | Integration tests pass | `make media-test-integration` |
| SC-007 | E2E tests pass | `make e2e-test-p1` |
| SC-008 | Validation accepts 30000ms | `test_stream_models.py` |
| SC-010 | Output PTS starts from 0 | `test_output_pipeline.py`, `ffprobe` verification |

---

## Risk Assessment

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Memory pressure from buffer-and-wait (162MB peak) | OOM, container restarts | Monitor memory usage; container limits provide signals |
| Timeout misconfiguration | All fragments timeout | Comprehensive unit tests on timeout values |
| Buffer-and-wait logic errors | A/V desync or stuck segments | Extensive unit tests for pairing logic |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| ASR model performance with 30s audio | Slower processing, potential timeouts | Extended 60s timeout provides margin |
| Validation constraint mismatches | Rejected configurations | Contract tests for all payload models |
| Test fixture duration edge cases | False test failures | Use 60s fixture (exactly 2x30s segments) |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Documentation out of sync | Developer confusion | Update docstrings alongside code changes |
| Partial segment edge cases | Minor quality issues | Existing MIN_SEGMENT_DURATION_NS (1s) unchanged |

---

## Rollback Strategy

### Pre-Deployment Checklist

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All P1 E2E tests pass
- [ ] Memory usage validated (~162MB peak acceptable)
- [ ] Git commit with clear feature branch

### Rollback Steps

If issues are detected post-deployment:

1. **Stop all active streams**
   ```bash
   # Signal workers to gracefully stop
   kubectl scale deployment media-service --replicas=0
   ```

2. **Revert to previous images**
   ```bash
   # Revert media-service
   kubectl rollout undo deployment/media-service

   # Revert sts-service
   kubectl rollout undo deployment/sts-service
   ```

3. **Restart services**
   ```bash
   kubectl scale deployment media-service --replicas=<original>
   kubectl scale deployment sts-service --replicas=<original>
   ```

4. **Resume streams**
   - Streams must be restarted from source
   - Mixed-version operation is NOT supported

### Rollback Indicators

Trigger rollback if:
- Fragment timeout rate > 20%
- A/V sync delta consistently > 200ms (buffer pairing failing)
- OOM kills in container logs
- Circuit breaker in OPEN state for > 5 minutes

---

## Implementation Checklist

### Pre-Implementation

- [ ] Read and understand spec.md
- [ ] Review clarifications.md decisions
- [ ] Create feature branch: `021-fragment-length-30s`

### Phase 1: Tests (P0)

- [ ] Update `test_models_segments.py` assertions
- [ ] Update `test_models_state.py` - **remove av_offset tests, add buffer tests**
- [ ] Update `test_segment_buffer.py` assertions
- [ ] Update `test_av_sync.py` - **buffer-and-wait tests, original PTS**
- [ ] Update `test_sts_models.py` assertions
- [ ] Update `test_worker_runner.py` assertions
- [ ] Create `apps/sts-service/tests/unit/test_session.py`
- [ ] Create `apps/sts-service/tests/unit/test_stream_models.py`
- [ ] Run tests and verify they FAIL

### Phase 2: Media Service (P1)

- [ ] Update `models/segments.py` (VideoSegment, AudioSegment constants)
- [ ] Update `buffer/segment_buffer.py` (DEFAULT_SEGMENT_DURATION_NS)
- [ ] **Refactor `models/state.py`** - remove av_offset_ns, drift correction
- [ ] **Refactor `sync/av_sync.py`** - buffer-and-wait, original PTS
- [ ] Update `sts/models.py` (StreamConfig.chunk_duration_ms)
- [ ] Update `worker/worker_runner.py` (WorkerConfig.segment_duration_ns)
- [ ] Run media-service unit tests and verify PASS

### Phase 3: STS Service (P1)

- [ ] Update `full/session.py` (chunk_duration_ms, timeout_ms)
- [ ] Update `echo/models/stream.py` (validation constraints)
- [ ] Update `asr/postprocessing.py` (max_duration_seconds default)
- [ ] Run sts-service unit tests and verify PASS

### Phase 4: E2E Config (P2)

- [ ] Update `tests/e2e/config.py` (all duration/timeout values)
- [ ] Review `test_full_pipeline.py` for hardcoded expectations

### Phase 5: Validation (P2)

- [ ] Run integration tests: `make media-test-integration`
- [ ] Run E2E tests: `make e2e-test-p1`
- [ ] Run full E2E: `make e2e-test-full`
- [ ] Verify coverage: `make media-test-coverage`

### Post-Implementation

- [ ] Update all docstrings to reflect 30s duration and buffer-and-wait
- [ ] Commit with message: `feat(021): increase fragment length from 6s to 30s (buffer-and-wait)`
- [ ] Create PR with spec link

---

## Constitution Check

### Principle VIII - Test-First Development

- **Compliance**: Phase 1 requires tests written before implementation
- **Gate**: Implementation blocked until tests exist and fail
- **Status**: PASS (plan includes TDD workflow)

### Principle III - Spec-Driven Development

- **Compliance**: Implementation follows spec.md requirements
- **Gate**: All FRs traced to code changes
- **Status**: PASS (FR mappings documented)

### Principle VI - A/V Sync Discipline

- **Compliance**: Buffer-and-wait approach per spec D6 decision
- **Gate**: E2E tests validate sync < 100ms
- **Status**: PASS (sync achieved through pairing)

---

## Appendix: Value Change Summary

### Nanosecond Values

| Purpose | Current (ns) | New (ns) | Change |
|---------|--------------|----------|--------|
| Segment Duration | 6,000,000,000 | 30,000,000,000 | 5x |
| A/V Offset | 6,000,000,000 | **REMOVED** | N/A |
| Output PTS | Original stream PTS | 0 | **Reset to 0** |
| Tolerance | 100,000,000 | 100,000,000 | No change |
| Min Partial | 1,000,000,000 | 1,000,000,000 | No change |

### Millisecond Values

| Purpose | Current (ms) | New (ms) | Change |
|---------|--------------|----------|--------|
| Chunk Duration | 6,000 | 30,000 | 5x |
| Session Timeout | 8,000 | 60,000 | 7.5x |
| Max Timeout Validation | 30,000 | 120,000 | 4x |
| Max Chunk Validation | 6,000 | 30,000 | 5x |

### Second Values (E2E Config)

| Purpose | Current (s) | New (s) | Change |
|---------|-------------|---------|--------|
| Segment Duration | 6 | 30 | 5x |
| Fragment Timeout | 8 | 60 | 7.5x |
| Pipeline Completion | 90 | 120 | 1.33x |
| Expected Segments (60s) | 10 | 2 | 0.2x |

### Memory Values

| Component | Current | New | Change |
|-----------|---------|-----|--------|
| Peak In-flight | ~45MB | ~162MB | 3.6x |
| Per-segment Video | ~3MB | ~15MB | 5x |
| Per-segment Audio | ~180KB | ~900KB | 5x |
