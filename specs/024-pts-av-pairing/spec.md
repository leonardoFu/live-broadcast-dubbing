# Feature Specification: PTS-Based A/V Pairing in AvSyncManager

**Feature Branch**: `024-pts-av-pairing`
**Created**: 2026-01-10
**Status**: Draft
**Input**: User description: "Replace batch_number-based A/V pairing with PTS range overlap matching to support variable-length VAD audio segments"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PTS Range Overlap Matching (Priority: P1)

When video segments arrive with fixed 6-second durations and audio segments arrive with variable durations (1-15 seconds from VAD), the system matches them based on PTS timestamp overlap rather than batch numbers. This ensures that dubbed audio is paired with the correct video frames regardless of segment count misalignment.

**Why this priority**: This is the core functionality that enables VAD audio segmentation to work with the existing video pipeline. Without PTS-based matching, variable-length audio segments cannot be correctly paired with fixed-length video segments, breaking the dubbing pipeline.

**Independent Test**: Verify PTS range overlap detection triggers correct pairing
- **Unit test**: `test_pts_overlap_detection()` validates that segments with overlapping PTS ranges are identified as matching
- **Unit test**: `test_no_overlap_not_matched()` validates that segments without PTS overlap are not paired
- **Contract test**: `test_sync_pair_contains_correct_metadata()` validates SyncPair structure preserves all segment information
- **Integration test**: `test_pts_matching_with_vad_segments()` validates end-to-end pairing with real VAD-generated audio
- **Success criteria**: All tests pass, segments pair correctly based on PTS overlap, 80% coverage achieved

**Acceptance Scenarios**:

1. **Given** video segment V0 (t0=0s, duration=6s) and audio segment A0 (t0=0s, duration=8s), **When** both are pushed to AvSyncManager, **Then** they are paired because PTS ranges [0,6s] and [0,8s] overlap
2. **Given** video segment V1 (t0=6s, duration=6s) and audio segment A0 (t0=0s, duration=8s), **When** both are pushed, **Then** they are paired because PTS ranges [6s,12s] and [0,8s] overlap at [6s,8s]
3. **Given** video segment V2 (t0=12s, duration=6s) and audio segment A0 (t0=0s, duration=8s), **When** both are pushed, **Then** V2 is NOT paired with A0 because ranges [12s,18s] and [0,8s] do not overlap

---

### User Story 2 - One-to-Many Audio Reuse (Priority: P1)

When a single audio segment covers the PTS range of multiple video segments, the system reuses the same audio data for each matching video segment. This handles cases where a 12-second audio segment covers two 6-second video segments.

**Why this priority**: With VAD producing segments up to 15 seconds, a single audio segment will frequently span multiple 6-second video segments. Without one-to-many support, video segments would remain unpaired and the output would stall.

**Independent Test**: Verify audio reuse across multiple video segments
- **Unit test**: `test_audio_reused_for_multiple_videos()` validates same audio pairs with multiple video segments
- **Unit test**: `test_audio_reference_counting()` validates audio is retained until all overlapping videos are processed
- **Contract test**: `test_multiple_sync_pairs_same_audio()` validates each SyncPair contains correct audio reference
- **Success criteria**: All tests pass, no audio data duplication, correct pairing counts

**Acceptance Scenarios**:

1. **Given** audio A0 (t0=0s, duration=12s) and video V0 (t0=0s, duration=6s), **When** V0 arrives, **Then** SyncPair is created with A0
2. **Given** same audio A0 still buffered and video V1 (t0=6s, duration=6s) arrives, **When** V1 is pushed, **Then** SyncPair is created reusing A0
3. **Given** video V2 (t0=12s, duration=6s) arrives, **When** V2 is pushed, **Then** V2 does NOT pair with A0 (no overlap) and waits for A1

---

### User Story 3 - Sorted PTS Audio Buffer (Priority: P1)

Audio segments are stored in a sorted data structure ordered by start PTS (t0_ns) instead of using batch_number as key. This enables efficient lookup of overlapping audio for any video PTS range.

**Why this priority**: The batch_number-keyed dict cannot support PTS-based matching. A sorted structure is required for the overlap detection algorithm to work efficiently. This is a prerequisite for P1 user stories 1 and 2.

**Independent Test**: Verify sorted buffer maintains order and enables range queries
- **Unit test**: `test_audio_buffer_sorted_by_pts()` validates audio segments are stored in PTS order
- **Unit test**: `test_audio_buffer_range_query()` validates efficient retrieval of overlapping audio
- **Unit test**: `test_audio_buffer_insertion_order_independent()` validates out-of-order arrivals are correctly sorted
- **Success criteria**: All tests pass, O(log n) insertion and query complexity, correct ordering maintained

**Acceptance Scenarios**:

1. **Given** empty audio buffer, **When** audio A1 (t0=6s) then A0 (t0=0s) are pushed, **Then** buffer contains [A0, A1] in PTS order
2. **Given** audio buffer with A0 (0-8s), A1 (8-15s), **When** query for video V1 (6-12s), **Then** both A0 and A1 are returned as overlapping
3. **Given** audio buffer at max capacity, **When** new audio arrives, **Then** oldest audio (lowest t0_ns with no pending overlaps) is evicted

---

### User Story 4 - Audio Cleanup After All Videos Processed (Priority: P2)

When all video segments that overlap with a buffered audio segment have been processed and paired, the audio segment is removed from the buffer to free memory. This prevents unbounded buffer growth.

**Why this priority**: Memory management is important for long-running streams but the system can function temporarily with larger buffers. This is a resource optimization that becomes critical over extended operation.

**Independent Test**: Verify audio cleanup occurs at correct time
- **Unit test**: `test_audio_removed_after_last_overlap()` validates audio evicted when no more overlapping videos expected
- **Unit test**: `test_audio_retained_while_overlaps_pending()` validates audio kept while future videos may overlap
- **Contract test**: `test_buffer_size_bounded()` validates buffer size does not grow unboundedly
- **Success criteria**: All tests pass, buffer size remains bounded, no premature audio eviction

**Acceptance Scenarios**:

1. **Given** audio A0 (0-8s) has paired with V0 (0-6s), **When** V1 (6-12s) arrives and pairs with A0, **Then** A0 is removed from buffer (no more videos will overlap)
2. **Given** audio A0 (0-8s) has paired with V0 (0-6s), **When** buffer cleanup runs, **Then** A0 is retained because V1 (6-12s) has not arrived yet
3. **Given** audio A0 (0-8s) and video arrives out of order, **When** V1 (6-12s) arrives before V0 (0-6s), **Then** A0 is retained until both V0 and V1 have paired

---

### User Story 5 - Drift Detection with PTS-Based Matching (Priority: P2)

The existing drift detection mechanism continues to work with PTS-based matching. Drift is measured between video output PTS and audio output PTS, with slew correction applied when threshold is exceeded.

**Why this priority**: Drift detection and correction maintain A/V synchronization quality. While critical for output quality, the basic pairing functionality works without it, making this a P2 enhancement.

**Independent Test**: Verify drift detection compatibility with PTS matching
- **Unit test**: `test_drift_detection_with_pts_matching()` validates sync_delta_ns calculated correctly
- **Unit test**: `test_slew_correction_with_variable_audio()` validates correction works with variable-length segments
- **Contract test**: `test_drift_metrics_exposed()` validates Prometheus metrics track drift correctly
- **Success criteria**: All tests pass, drift stays within 120ms threshold, correction applied when needed

**Acceptance Scenarios**:

1. **Given** video and audio paired with PTS-based matching, **When** pair is created, **Then** sync_delta_ns is updated correctly
2. **Given** sync_delta_ns exceeds 120ms threshold, **When** needs_correction() is called, **Then** True is returned
3. **Given** drift correction is needed, **When** slew_correction is applied, **Then** av_offset_ns is adjusted by slew_rate_ns

---

### User Story 6 - Fallback with PTS-Based Matching (Priority: P3)

When the circuit breaker trips or stream ends, the flush_with_fallback method works correctly with PTS-based matching to pair remaining video segments with original audio.

**Why this priority**: Fallback handling is an edge case that occurs during error conditions. While important for resilience, it does not affect normal operation.

**Independent Test**: Verify fallback compatibility with PTS matching
- **Unit test**: `test_flush_fallback_with_pts_buffer()` validates remaining videos paired with original audio
- **Unit test**: `test_fallback_audio_pts_calculation()` validates fallback AudioSegment has correct PTS
- **Integration test**: `test_circuit_breaker_fallback_with_vad()` validates end-to-end fallback flow
- **Success criteria**: All tests pass, all buffered videos flushed, no segments lost

**Acceptance Scenarios**:

1. **Given** video buffer contains V5 (30-36s) with no matching dubbed audio, **When** flush_with_fallback is called, **Then** fallback audio segment is created with matching t0_ns and duration_ns
2. **Given** circuit breaker opens during stream, **When** new video arrives, **Then** video is paired with original audio via fallback mechanism

---

### Edge Cases

- **Video arrives before overlapping audio**: Video is buffered until matching audio arrives. If video age exceeds timeout (10 seconds) without audio match, fallback to original audio is triggered.
- **Audio arrives before overlapping video**: Audio is buffered in sorted structure. When video arrives, overlap query finds matching audio.
- **Audio gap (no audio covers video PTS range)**: Video remains buffered for timeout duration (10 seconds). If no matching audio arrives within timeout, fallback to original audio is triggered.
- **Audio segment spans video gap**: Audio pairs with all overlapping videos regardless of missing intermediate videos. Example: A0 (0-15s) pairs with both V0 (0-6s) and V2 (12-18s) even if V1 (6-12s) is missing. Pairing is purely based on PTS overlap.
- **Exact PTS boundary alignment**: Segments touching at exact boundaries do NOT overlap (strict inequality per overlap algorithm). Example: V0 ending at exactly 6.000s and A1 starting at exactly 6.000s are NOT paired.
- **Audio segments with very short duration (1s)**: Multiple short audio segments may overlap with single video. System uses the audio segment with maximum overlap for pairing.
- **Audio segments with maximum duration (15s)**: Single audio may pair with multiple videos (up to 3 for 15s audio with 6s video). Reference counting ensures audio retained until all pairs processed.
- **Out-of-order segment arrival**: Both video and audio buffers handle out-of-order arrival within tolerance window (3 video segment durations = 18s). Sorted audio buffer and indexed video buffer enable correct pairing regardless of arrival order.
- **PTS timestamp wrap-around**: System handles 64-bit nanosecond timestamps which wrap after ~584 years. Not a practical concern.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST match video and audio segments based on PTS range overlap using strict inequalities, where overlap is defined as: video.t0_ns < audio.t0_ns + audio.duration_ns AND audio.t0_ns < video.t0_ns + video.duration_ns (segments touching at exact boundaries do NOT overlap)
- **FR-002**: System MUST store audio segments in a sorted list using bisect module (standard library) ordered by t0_ns for efficient range queries
- **FR-003**: System MUST support one-to-many relationships where a single audio segment is reused for multiple overlapping video segments (audio pairs with all overlapping videos regardless of gaps in video sequence)
- **FR-004**: System MUST retain audio segments in buffer until all overlapping video segments have been processed
- **FR-005**: System MUST remove audio segments from buffer using safe eviction watermark: audio evicted when audio_end_ns <= (max_video_pts_seen - 3 * VIDEO_SEGMENT_DURATION_NS), accounting for out-of-order arrival tolerance
- **FR-006**: System MUST maintain existing drift detection logic using the output PTS from paired segments
- **FR-007**: System MUST maintain existing slew correction mechanism for A/V synchronization
- **FR-008**: System MUST support the existing flush_with_fallback interface for circuit breaker fallback
- **FR-009**: System MUST calculate fallback audio segment PTS to match the video segment's t0_ns and duration_ns
- **FR-010**: System MUST NOT use batch_number for segment matching (batch_number may be removed from matching logic entirely)
- **FR-011**: System MUST handle out-of-order segment arrival for both video and audio within tolerance window (3 video segment durations = 18s)
- **FR-012**: System MUST enforce max_buffer_size limits on both video and audio buffers with appropriate eviction policies
- **FR-013**: System MUST select the audio segment with maximum overlap when multiple audio segments overlap a single video
- **FR-014**: System MUST log segment pairing decisions at DEBUG level for troubleshooting
- **FR-015**: System MUST expose audio_buffer_size property for monitoring
- **FR-016**: System MUST trigger fallback to original audio when buffered video age exceeds timeout (10 seconds) without finding matching dubbed audio

### Key Entities

- **AvSyncManager**: Manages A/V synchronization with PTS-based matching. Maintains sorted audio buffer and indexed video buffer. Orchestrates pairing logic and drift detection.
- **SyncPair**: Output entity containing paired video and audio segments with data and output PTS. Unchanged from current implementation.
- **AudioBufferEntry**: Internal entity wrapping AudioSegment with reference counting for one-to-many support. Tracks which videos have already paired with this audio.
- **PtsRange**: Value object representing a PTS time range (t0_ns, t0_ns + duration_ns) with overlap detection methods.
- **OverlapQuery**: Query object for finding audio segments that overlap with a given video PTS range. Returns sorted list of overlapping AudioBufferEntry instances.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A/V pairing works correctly with VAD-generated variable-length audio segments (1-15s) paired with fixed 6s video segments
- **SC-002**: All existing unit tests for AvSyncManager pass after refactoring (with updated assertions for PTS-based matching)
- **SC-003**: New unit tests achieve 80%+ coverage on PTS matching logic
- **SC-004**: Audio buffer memory bounded: buffer size never exceeds max_buffer_size regardless of segment timing patterns
- **SC-005**: One-to-many pairing works correctly: 15s audio segment successfully pairs with 2-3 video segments covering its range
- **SC-006**: Drift detection continues to function: sync_delta_ms stays within 120ms threshold during normal operation
- **SC-007**: E2E pipeline produces synchronized A/V output with VAD audio segments, verified by ffprobe analysis showing A/V delta < 120ms
- **SC-008**: No regression in pipeline latency: segment pairing completes within 10ms per pair
- **SC-009**: Integration tests pass with real VAD-segmented audio streams

## Assumptions

- Video segments continue to use fixed 6-second duration as per existing spec-003
- Audio segments from VAD have accurate t0_ns and duration_ns values in nanoseconds
- Audio segments from VAD arrive in roughly PTS-order (minor out-of-order acceptable within buffer size)
- The existing AvSyncState class for drift detection remains unchanged
- SyncPair dataclass structure remains unchanged
- Video segments continue to have accurate t0_ns values from GStreamer pipeline
- batch_number field remains on segments for backward compatibility but is not used for matching

## Dependencies

- spec-023 VAD Audio Segmentation (provides variable-length audio segments)
- spec-003 GStreamer Stream Worker (provides video segment structure)
- Python 3.10.x runtime
- pytest for unit testing
- asyncio for async buffer operations (existing pattern)

## Clarifications

### Session 2026-01-10

- Q: Should audio segment pair with all overlapping videos even when there are gaps in video sequence (e.g., A0 overlaps V0 and V2, but V1 is missing)?
  → A: Yes. Pairing is purely based on PTS overlap. Missing video segments are a separate pipeline concern handled by buffer timeout logic.

- Q: How to determine safe audio eviction when videos arrive out-of-order?
  → A: Use safe eviction watermark: `safe_eviction_pts = max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS)`. This provides 18s tolerance for out-of-order arrivals while still evicting stale audio.

- Q: Should segments touching at exact PTS boundaries be considered overlapping?
  → A: No. Use strict inequalities (`<`, not `<=`) per standard interval overlap definition. Segments with exact boundary alignment (e.g., [0,6s) and [6s,12s)) do NOT overlap.

- Q: When should system trigger fallback to original audio if no dubbed audio overlap found?
  → A: Timeout-based fallback. Track video insertion timestamp. If video age exceeds 10 seconds without finding matching dubbed audio, trigger fallback pairing with original audio.

- Q: Which sorted buffer implementation should be used for audio buffer?
  → A: `list` with `bisect` module (standard library). Use `bisect.insort_left()` for insertion, linear scan for overlap queries. O(n) complexity acceptable for max_buffer_size=10. Avoids external dependencies.

## Technical Notes

### PTS Overlap Algorithm

Two PTS ranges overlap when:
```
range_a.start < range_b.end AND range_b.start < range_a.end
```

For segments:
```python
def overlaps(video: VideoSegment, audio: AudioSegment) -> bool:
    video_end = video.t0_ns + video.duration_ns
    audio_end = audio.t0_ns + audio.duration_ns
    return video.t0_ns < audio_end and audio.t0_ns < video_end
```

### Sorted Audio Buffer Implementation

Replace `dict[int, tuple[AudioSegment, bytes]]` with sorted list structure using Python's bisect module (standard library):

**Selected Implementation: `list` with `bisect` module**
- Use `bisect.insort_left()` for O(n) insertion maintaining sort order by t0_ns
- Linear scan for overlap queries (acceptable for max_buffer_size=10)
- Standard library only, no external dependencies
- Sufficient performance for expected buffer sizes

**Eviction with Safe Watermark**:
```python
# Track highest video PTS seen
max_video_pts_seen: int = 0

# Calculate safe eviction watermark (3 video segment tolerance)
VIDEO_SEGMENT_DURATION_NS = 6_000_000_000  # 6 seconds
safe_eviction_pts = max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS)

# Evict audio that cannot overlap with future videos
for entry in audio_buffer:
    audio_end = entry.audio_segment.t0_ns + entry.audio_segment.duration_ns
    if audio_end <= safe_eviction_pts:
        audio_buffer.remove(entry)
```

### Audio Reference Counting

Track which videos have paired with each audio:
```python
@dataclass
class AudioBufferEntry:
    audio_segment: AudioSegment
    audio_data: bytes
    paired_video_pts: set[int]  # t0_ns of videos that have paired
    insertion_time_ns: int  # Timestamp when audio was buffered

    def should_evict(self, safe_eviction_pts: int) -> bool:
        """
        Evict if no future videos can overlap.
        Uses safe watermark: max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS)
        """
        audio_end = self.audio_segment.t0_ns + self.audio_segment.duration_ns
        return audio_end <= safe_eviction_pts
```

### Video Buffer Timeout

Track video insertion time for fallback triggering:
```python
@dataclass
class VideoBufferEntry:
    video_segment: VideoSegment
    video_data: bytes
    insertion_time_ns: int  # Timestamp when video was buffered

    def should_fallback(self, current_time_ns: int, timeout_ns: int = 10_000_000_000) -> bool:
        """
        Trigger fallback if video has waited too long without audio match.
        Default timeout: 10 seconds
        """
        age_ns = current_time_ns - self.insertion_time_ns
        return age_ns >= timeout_ns
```

### Migration Strategy

1. Add new PTS-based matching alongside batch_number matching (feature flag)
2. Update tests to verify both methods produce same results for aligned segments
3. Remove batch_number matching once PTS-based is validated
4. Clean up batch_number usage if no other consumers
