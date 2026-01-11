# Implementation Plan: PTS-Based A/V Pairing

**Branch**: `024-pts-av-pairing` | **Date**: 2026-01-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/024-pts-av-pairing/spec.md`

## Summary

Replace batch_number-based A/V segment matching with PTS range overlap detection to support variable-length VAD audio segments (1-15s) paired with fixed 6-second video segments. The implementation uses Python's standard `bisect` module for sorted audio buffer management with O(n) insertion and linear scan for overlap queries, acceptable for max_buffer_size=10.

## Technical Context

**Language/Version**: Python 3.10.x (per constitution and pyproject.toml requirement `>=3.10,<3.11`)
**Primary Dependencies**: asyncio (async buffer operations), bisect (sorted list), dataclasses (buffer entries)
**Storage**: In-memory buffers only (sorted list for audio, deque for video)
**Testing**: pytest, pytest-asyncio, pytest-mock
**Target Platform**: Linux/macOS (Docker containers for production)
**Project Type**: Python monorepo - media-service application
**Performance Goals**: Segment pairing completes within 10ms per pair
**Constraints**: A/V sync delta < 120ms, buffer size <= 10 segments per type
**Scale/Scope**: Single stream per worker, max ~3 video segments overlapping single audio

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all user stories (see Test Strategy section)
- [x] Mock patterns documented - no STS events needed, pure unit tests for matching logic
- [x] Coverage targets specified: 95% for av_sync.py (critical A/V sync path)
- [x] Test infrastructure matches constitution requirements (pytest, pytest-asyncio)
- [x] Test organization follows standard structure (apps/media-service/tests/unit/)

**Principle VI - A/V Sync Discipline**:
- [x] Video passthrough preserves original timestamps (no change)
- [x] Audio PTS tracked relative to GStreamer pipeline clock
- [x] Drift detection maintained with PTS-based matching
- [x] Slew correction mechanism unchanged

**Principle I - Real-Time First**:
- [x] O(n) complexity acceptable for max_buffer_size=10
- [x] No blocking operations introduced
- [x] Timeout-based fallback prevents unbounded waiting

**Principle II - Testability Through Isolation**:
- [x] All matching logic unit-testable without external dependencies
- [x] Deterministic test fixtures with known PTS values

## Project Structure

### Documentation (this feature)

```text
specs/024-pts-av-pairing/
├── plan.md              # This file
├── research.md          # N/A - no external research needed
├── data-model.md        # Data structures for buffer entries
├── quickstart.md        # Test scenarios from spec
└── contracts/           # N/A - internal refactoring only
```

### Source Code (repository root)

```text
apps/media-service/
├── src/media_service/
│   ├── sync/
│   │   └── av_sync.py           # PRIMARY: PTS-based matching implementation
│   └── models/
│       ├── segments.py          # UNCHANGED: AudioSegment, VideoSegment
│       └── state.py             # UNCHANGED: AvSyncState
└── tests/
    └── unit/
        ├── test_av_sync.py              # MODIFY: Update existing tests
        └── test_av_sync_pts_matching.py # NEW: PTS matching tests
```

**Structure Decision**: Minimal change footprint - only av_sync.py requires modification. Test file additions follow existing pattern.

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory - 95% coverage for critical path):
- Target: PTS overlap detection, sorted buffer operations, one-to-many pairing, safe eviction
- Tools: pytest, pytest-asyncio
- Coverage: 95% minimum (A/V sync is critical path per constitution)
- Mocking: None needed - pure logic tests
- Location: `apps/media-service/tests/unit/test_av_sync_pts_matching.py`

**Contract Tests** (mandatory):
- Target: SyncPair structure unchanged, AudioBufferEntry interface
- Tools: pytest with dataclass validation
- Coverage: 100% of public interfaces
- Location: `apps/media-service/tests/unit/test_av_sync.py` (existing)

**Integration Tests** (required for workflows):
- Target: End-to-end pairing with simulated VAD segments
- Tools: pytest with async fixtures
- Coverage: Happy path + timeout fallback scenario
- Location: `apps/media-service/tests/integration/test_av_sync_integration.py`

### Test Cases from Spec (User Stories)

**US1 - PTS Range Overlap Matching (P1)**:
```python
# test_pts_overlap_detection()
- V0 (0-6s) + A0 (0-8s) -> paired (overlap at 0-6s)
- V1 (6-12s) + A0 (0-8s) -> paired (overlap at 6-8s)
- V2 (12-18s) + A0 (0-8s) -> NOT paired (no overlap)

# test_no_overlap_not_matched()
- V0 ending at 6.000s, A1 starting at 6.000s -> NOT paired (strict inequality)
```

**US2 - One-to-Many Audio Reuse (P1)**:
```python
# test_audio_reused_for_multiple_videos()
- A0 (0-12s) pairs with V0 (0-6s) -> SyncPair created
- Same A0 still buffered, pairs with V1 (6-12s) -> second SyncPair
- V2 (12-18s) does NOT pair with A0 -> waits for A1

# test_audio_reference_counting()
- Track paired_video_pts set grows with each pairing
```

**US3 - Sorted PTS Audio Buffer (P1)**:
```python
# test_audio_buffer_sorted_by_pts()
- Insert A1 (t0=6s) then A0 (t0=0s) -> buffer order is [A0, A1]

# test_audio_buffer_range_query()
- Buffer has A0 (0-8s), A1 (8-15s)
- Query for V1 (6-12s) -> returns both A0 and A1

# test_audio_buffer_insertion_order_independent()
- Out-of-order insertions maintain sorted order
```

**US4 - Audio Cleanup After All Videos Processed (P2)**:
```python
# test_audio_removed_after_last_overlap()
- A0 (0-8s) paired with V0, V1
- After V1 (6-12s) paired, safe_eviction_pts advances
- A0 evicted when audio_end <= safe_eviction_pts

# test_audio_retained_while_overlaps_pending()
- A0 retained until max_video_pts_seen sufficiently advanced
```

**US5 - Drift Detection with PTS-Based Matching (P2)**:
```python
# test_drift_detection_with_pts_matching()
- Verify sync_delta_ns calculated correctly after PTS pair creation
- Verify needs_correction() triggers at threshold
```

**US6 - Fallback with PTS-Based Matching (P3)**:
```python
# test_flush_fallback_with_pts_buffer()
- Video buffer has V5 (30-36s), no matching audio
- flush_with_fallback creates fallback AudioSegment with correct t0_ns

# test_video_timeout_triggers_fallback()
- Video buffered > 10 seconds triggers fallback
```

### Coverage Enforcement

**Pre-commit**: Run `pytest --cov=media_service.sync.av_sync --cov-fail-under=95`
**CI**: Block merge if coverage < 95% for av_sync.py
**Critical paths**: A/V sync matching logic requires 95% minimum

### Test Naming Conventions

Follow conventions from constitution:
- `test_<function>_happy_path()` - Normal operation
- `test_<function>_error_<condition>()` - Error handling
- `test_<function>_edge_<case>()` - Boundary conditions

## Data Model Changes

### New: AudioBufferEntry

```python
@dataclass
class AudioBufferEntry:
    """Wrapper for buffered audio with reference tracking."""
    audio_segment: AudioSegment
    audio_data: bytes
    paired_video_pts: set[int]  # t0_ns of videos that have paired
    insertion_time_ns: int  # Timestamp when audio was buffered

    @property
    def t0_ns(self) -> int:
        """Key for sorting - audio start PTS."""
        return self.audio_segment.t0_ns

    @property
    def end_ns(self) -> int:
        """Audio end PTS for overlap calculation."""
        return self.audio_segment.t0_ns + self.audio_segment.duration_ns

    def should_evict(self, safe_eviction_pts: int) -> bool:
        """Check if audio can be evicted (no future overlaps possible)."""
        return self.end_ns <= safe_eviction_pts
```

### New: VideoBufferEntry

```python
@dataclass
class VideoBufferEntry:
    """Wrapper for buffered video with timeout tracking."""
    video_segment: VideoSegment
    video_data: bytes
    insertion_time_ns: int  # Timestamp when video was buffered

    @property
    def t0_ns(self) -> int:
        """Video start PTS."""
        return self.video_segment.t0_ns

    @property
    def end_ns(self) -> int:
        """Video end PTS."""
        return self.video_segment.t0_ns + self.video_segment.duration_ns

    def should_fallback(self, current_time_ns: int, timeout_ns: int = 10_000_000_000) -> bool:
        """Check if video has waited too long for audio match."""
        age_ns = current_time_ns - self.insertion_time_ns
        return age_ns >= timeout_ns
```

### Modified: AvSyncManager

```python
class AvSyncManager:
    # Change from:
    _audio_buffer: dict[int, tuple[AudioSegment, bytes]]

    # Change to:
    _audio_buffer: list[AudioBufferEntry]  # Sorted by t0_ns
    _video_buffer: list[VideoBufferEntry]  # With timeout tracking
    _max_video_pts_seen: int = 0  # For safe eviction watermark

    # Constants
    VIDEO_SEGMENT_DURATION_NS: int = 6_000_000_000  # 6 seconds
    FALLBACK_TIMEOUT_NS: int = 10_000_000_000  # 10 seconds
```

## Implementation Phases

### Phase 1: Add New Data Structures (TDD)

**Tests First** (`test_av_sync_pts_matching.py`):
```python
class TestAudioBufferEntry:
    def test_t0_ns_property()
    def test_end_ns_property()
    def test_should_evict_when_below_watermark()
    def test_should_not_evict_when_above_watermark()

class TestVideoBufferEntry:
    def test_should_fallback_after_timeout()
    def test_should_not_fallback_before_timeout()
```

**Implementation**:
1. Add `AudioBufferEntry` dataclass to `av_sync.py`
2. Add `VideoBufferEntry` dataclass to `av_sync.py`
3. Add constants: `VIDEO_SEGMENT_DURATION_NS`, `FALLBACK_TIMEOUT_NS`

### Phase 2: Implement PTS Overlap Algorithm (TDD)

**Tests First**:
```python
class TestPtsOverlap:
    def test_overlaps_full_containment()
    def test_overlaps_partial_start()
    def test_overlaps_partial_end()
    def test_no_overlap_before()
    def test_no_overlap_after()
    def test_no_overlap_exact_boundary()  # Strict inequality
```

**Implementation**:
```python
def _overlaps(self, video: VideoBufferEntry, audio: AudioBufferEntry) -> bool:
    """Check if video and audio PTS ranges overlap (strict inequality)."""
    return video.t0_ns < audio.end_ns and audio.t0_ns < video.end_ns
```

### Phase 3: Sorted Audio Buffer with bisect (TDD)

**Tests First**:
```python
class TestSortedAudioBuffer:
    def test_insert_maintains_sorted_order()
    def test_insert_out_of_order_arrivals()
    def test_find_overlapping_audio()
    def test_find_best_overlap_when_multiple()
    def test_buffer_eviction_with_watermark()
```

**Implementation**:
```python
import bisect

def _insert_audio(self, entry: AudioBufferEntry) -> None:
    """Insert audio maintaining sorted order by t0_ns."""
    # Use bisect for O(n) insertion
    keys = [e.t0_ns for e in self._audio_buffer]
    idx = bisect.bisect_left(keys, entry.t0_ns)
    self._audio_buffer.insert(idx, entry)

def _find_overlapping_audio(self, video: VideoBufferEntry) -> list[AudioBufferEntry]:
    """Find all audio entries that overlap with video PTS range."""
    return [a for a in self._audio_buffer if self._overlaps(video, a)]

def _select_best_overlap(self, video: VideoBufferEntry, candidates: list[AudioBufferEntry]) -> AudioBufferEntry | None:
    """Select audio with maximum overlap when multiple candidates exist."""
    if not candidates:
        return None

    def overlap_amount(audio: AudioBufferEntry) -> int:
        overlap_start = max(video.t0_ns, audio.t0_ns)
        overlap_end = min(video.end_ns, audio.end_ns)
        return max(0, overlap_end - overlap_start)

    return max(candidates, key=overlap_amount)
```

### Phase 4: Update push_video with PTS Matching (TDD)

**Tests First**:
```python
class TestPushVideoWithPts:
    async def test_push_video_pairs_with_overlapping_audio()
    async def test_push_video_buffers_when_no_overlap()
    async def test_push_video_updates_max_pts_seen()
    async def test_push_video_triggers_eviction()
```

**Implementation**:
```python
async def push_video(self, segment: VideoSegment, data: bytes) -> SyncPair | None:
    async with self._lock:
        entry = VideoBufferEntry(
            video_segment=segment,
            video_data=data,
            insertion_time_ns=time.time_ns(),
        )

        # Update max video PTS seen for eviction watermark
        self._max_video_pts_seen = max(self._max_video_pts_seen, entry.end_ns)

        # Find overlapping audio
        candidates = self._find_overlapping_audio(entry)
        best_audio = self._select_best_overlap(entry, candidates)

        if best_audio is not None:
            # Track that this video paired with this audio
            best_audio.paired_video_pts.add(entry.t0_ns)

            # Run eviction check
            self._evict_stale_audio()

            return self._create_pair(
                entry.video_segment, entry.video_data,
                best_audio.audio_segment, best_audio.audio_data
            )

        # Buffer video for later matching
        self._buffer_video(entry)
        return None
```

### Phase 5: Update push_audio with PTS Matching (TDD)

**Tests First**:
```python
class TestPushAudioWithPts:
    async def test_push_audio_pairs_with_overlapping_video()
    async def test_push_audio_buffers_when_no_overlap()
    async def test_push_audio_one_to_many_pairing()
    async def test_push_audio_sorted_insertion()
```

**Implementation**:
```python
async def push_audio(self, segment: AudioSegment, data: bytes) -> list[SyncPair]:
    """Push audio and return ALL matching pairs (one-to-many support)."""
    async with self._lock:
        entry = AudioBufferEntry(
            audio_segment=segment,
            audio_data=data,
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        pairs: list[SyncPair] = []
        matched_video_indices: list[int] = []

        # Find all overlapping videos
        for i, video in enumerate(self._video_buffer):
            if self._overlaps(video, entry):
                entry.paired_video_pts.add(video.t0_ns)
                matched_video_indices.append(i)
                pairs.append(self._create_pair(
                    video.video_segment, video.video_data,
                    entry.audio_segment, entry.audio_data
                ))

        # Remove matched videos (reverse order)
        for i in reversed(matched_video_indices):
            del self._video_buffer[i]

        # Buffer audio for future video matching
        self._insert_audio(entry)

        # Run eviction
        self._evict_stale_audio()

        return pairs if pairs else None
```

### Phase 6: Safe Eviction Watermark (TDD)

**Tests First**:
```python
class TestSafeEviction:
    def test_eviction_watermark_calculation()
    def test_audio_evicted_when_end_below_watermark()
    def test_audio_retained_when_end_above_watermark()
    def test_eviction_with_out_of_order_video()
```

**Implementation**:
```python
def _evict_stale_audio(self) -> None:
    """Remove audio that cannot overlap with future videos."""
    # Safe eviction watermark: 3 video segment tolerance for out-of-order
    safe_eviction_pts = self._max_video_pts_seen - (3 * self.VIDEO_SEGMENT_DURATION_NS)

    if safe_eviction_pts <= 0:
        return

    # Remove audio entries that end before watermark
    self._audio_buffer = [
        entry for entry in self._audio_buffer
        if not entry.should_evict(safe_eviction_pts)
    ]
```

### Phase 7: Timeout-Based Fallback (TDD)

**Tests First**:
```python
class TestTimeoutFallback:
    async def test_video_timeout_triggers_fallback()
    async def test_check_timeouts_returns_timed_out_videos()
    async def test_fallback_audio_has_correct_pts()
```

**Implementation**:
```python
async def check_timeouts(
    self,
    get_original_audio: Callable[[AudioSegment], Awaitable[bytes]],
    current_time_ns: int | None = None,
) -> list[SyncPair]:
    """Check for timed-out videos and create fallback pairs."""
    if current_time_ns is None:
        current_time_ns = time.time_ns()

    pairs: list[SyncPair] = []
    timed_out_indices: list[int] = []

    async with self._lock:
        for i, video in enumerate(self._video_buffer):
            if video.should_fallback(current_time_ns, self.FALLBACK_TIMEOUT_NS):
                timed_out_indices.append(i)

                # Create fallback audio segment with matching PTS
                fallback_segment = AudioSegment(
                    fragment_id=f"{video.video_segment.fragment_id}_fallback",
                    stream_id=video.video_segment.stream_id,
                    batch_number=video.video_segment.batch_number,
                    t0_ns=video.video_segment.t0_ns,
                    duration_ns=video.video_segment.duration_ns,
                    file_path=Path("/tmp/fallback.m4a"),
                )
                fallback_data = await get_original_audio(fallback_segment)

                pairs.append(self._create_pair(
                    video.video_segment, video.video_data,
                    fallback_segment, fallback_data
                ))

        # Remove timed-out videos
        for i in reversed(timed_out_indices):
            del self._video_buffer[i]

    return pairs
```

### Phase 8: Update Existing Tests (Compatibility)

**Modify** `test_av_sync.py`:
1. Update tests that rely on batch_number matching to use PTS-based assertions
2. Keep backward compatibility where batch_number still matches PTS alignment
3. Add deprecation warnings in tests for batch_number-specific assertions

### Phase 9: Integration Testing

**Create** `tests/integration/test_av_sync_integration.py`:
```python
class TestAvSyncIntegration:
    async def test_pts_matching_with_vad_segments()
    async def test_variable_length_audio_pairing()
    async def test_one_to_many_pairing_full_flow()
    async def test_timeout_fallback_integration()
```

## Complexity Tracking

No constitution violations. Implementation uses:
- Standard library only (bisect, dataclasses, asyncio)
- O(n) complexity acceptable for max_buffer_size=10
- No new external dependencies
- No new services or architectural changes

## Migration Strategy

1. **Parallel Implementation**: Add PTS-based matching alongside existing batch_number matching
2. **Feature Flag**: Not needed - this is a breaking change for VAD support
3. **Test Coverage**: Ensure all existing tests pass with updated assertions
4. **Gradual Rollout**: Deploy with E2E test validation before production

## API Changes

### Modified Methods

**`push_audio` Return Type Change**:
```python
# Before
async def push_audio(segment, data) -> SyncPair | None

# After (one-to-many support)
async def push_audio(segment, data) -> list[SyncPair] | None
```

**New Method**:
```python
async def check_timeouts(
    get_original_audio: Callable[[AudioSegment], Awaitable[bytes]],
    current_time_ns: int | None = None,
) -> list[SyncPair]
```

### Unchanged Methods
- `push_video` - signature unchanged, returns single SyncPair or None
- `get_ready_pairs` - unchanged
- `flush_with_fallback` - unchanged
- `reset` - unchanged
- Properties: `video_buffer_size`, `audio_buffer_size`, `sync_delta_ms`, etc.

## Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `apps/media-service/src/media_service/sync/av_sync.py` | MODIFY | Add PTS-based matching, buffer entries, eviction |
| `apps/media-service/tests/unit/test_av_sync.py` | MODIFY | Update existing tests for PTS matching |
| `apps/media-service/tests/unit/test_av_sync_pts_matching.py` | CREATE | New comprehensive PTS matching tests |
| `apps/media-service/tests/integration/test_av_sync_integration.py` | CREATE | Integration tests with VAD segments |

## Definition of Done

- [ ] All existing unit tests pass (with updated assertions)
- [ ] New unit tests achieve 95% coverage on av_sync.py
- [ ] PTS overlap algorithm correctly handles all edge cases from spec
- [ ] One-to-many audio pairing works correctly
- [ ] Safe eviction watermark prevents premature audio removal
- [ ] Timeout fallback triggers at 10 second threshold
- [ ] Integration tests validate VAD segment pairing
- [ ] No regression in pipeline latency (<10ms per pair)
- [ ] Code review confirms constitution compliance
