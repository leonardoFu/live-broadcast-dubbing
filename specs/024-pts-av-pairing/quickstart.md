# Quickstart: PTS-Based A/V Pairing

**Feature**: 024-pts-av-pairing
**Date**: 2026-01-10

## Test Scenarios

This document provides test scenarios derived from the spec user stories. Use these for TDD implementation.

---

## Scenario 1: Basic PTS Overlap Matching

**User Story**: US1 - PTS Range Overlap Matching (P1)

### Test Case 1.1: Full Overlap

```python
# Setup
video_v0 = VideoSegment(t0_ns=0, duration_ns=6_000_000_000)  # 0-6s
audio_a0 = AudioSegment(t0_ns=0, duration_ns=8_000_000_000)  # 0-8s

# Action
pair = await sync_manager.push_audio(audio_a0, audio_data)
# Then
pair = await sync_manager.push_video(video_v0, video_data)

# Assert
assert pair is not None
assert pair.video_segment.t0_ns == 0
assert pair.audio_segment.t0_ns == 0
```

### Test Case 1.2: Partial Overlap

```python
# Setup
video_v1 = VideoSegment(t0_ns=6_000_000_000, duration_ns=6_000_000_000)  # 6-12s
audio_a0 = AudioSegment(t0_ns=0, duration_ns=8_000_000_000)  # 0-8s

# Action
await sync_manager.push_audio(audio_a0, audio_data)
pair = await sync_manager.push_video(video_v1, video_data)

# Assert
assert pair is not None  # Overlap at 6-8s
```

### Test Case 1.3: No Overlap

```python
# Setup
video_v2 = VideoSegment(t0_ns=12_000_000_000, duration_ns=6_000_000_000)  # 12-18s
audio_a0 = AudioSegment(t0_ns=0, duration_ns=8_000_000_000)  # 0-8s

# Action
await sync_manager.push_audio(audio_a0, audio_data)
pair = await sync_manager.push_video(video_v2, video_data)

# Assert
assert pair is None  # No overlap
assert sync_manager.video_buffer_size == 1  # Buffered waiting for audio
```

### Test Case 1.4: Exact Boundary - No Overlap

```python
# Setup - segments touch at exactly 6s but don't overlap
video_v0 = VideoSegment(t0_ns=0, duration_ns=6_000_000_000)  # 0-6s
audio_a1 = AudioSegment(t0_ns=6_000_000_000, duration_ns=6_000_000_000)  # 6-12s

# Action
await sync_manager.push_audio(audio_a1, audio_data)
pair = await sync_manager.push_video(video_v0, video_data)

# Assert
assert pair is None  # Strict inequality - touching is NOT overlapping
```

---

## Scenario 2: One-to-Many Audio Reuse

**User Story**: US2 - One-to-Many Audio Reuse (P1)

### Test Case 2.1: Audio Pairs with Multiple Videos

```python
# Setup - 12s audio spans two 6s videos
audio_a0 = AudioSegment(t0_ns=0, duration_ns=12_000_000_000)  # 0-12s
video_v0 = VideoSegment(t0_ns=0, duration_ns=6_000_000_000)   # 0-6s
video_v1 = VideoSegment(t0_ns=6_000_000_000, duration_ns=6_000_000_000)  # 6-12s

# Action - Push audio first, then videos
pairs = await sync_manager.push_audio(audio_a0, audio_data)
assert pairs is None  # No video yet

pair_0 = await sync_manager.push_video(video_v0, video_data_0)
pair_1 = await sync_manager.push_video(video_v1, video_data_1)

# Assert
assert pair_0 is not None
assert pair_1 is not None
assert pair_0.audio_segment.t0_ns == pair_1.audio_segment.t0_ns == 0  # Same audio
```

### Test Case 2.2: Third Video Does Not Match

```python
# Setup - continuing from above
video_v2 = VideoSegment(t0_ns=12_000_000_000, duration_ns=6_000_000_000)  # 12-18s

# Action
pair_2 = await sync_manager.push_video(video_v2, video_data_2)

# Assert
assert pair_2 is None  # V2 does not overlap A0 (0-12s)
assert sync_manager.video_buffer_size == 1  # V2 waiting for new audio
```

---

## Scenario 3: Sorted Audio Buffer

**User Story**: US3 - Sorted PTS Audio Buffer (P1)

### Test Case 3.1: Out-of-Order Insertion

```python
# Setup - Insert A1 before A0
audio_a1 = AudioSegment(t0_ns=6_000_000_000, duration_ns=6_000_000_000)  # 6-12s
audio_a0 = AudioSegment(t0_ns=0, duration_ns=6_000_000_000)  # 0-6s

# Action
await sync_manager.push_audio(audio_a1, audio_data_1)
await sync_manager.push_audio(audio_a0, audio_data_0)

# Assert - Buffer should be sorted [A0, A1]
assert sync_manager.audio_buffer_size == 2
# Internal: _audio_buffer[0].t0_ns == 0, _audio_buffer[1].t0_ns == 6_000_000_000
```

### Test Case 3.2: Range Query Returns Multiple

```python
# Setup
audio_a0 = AudioSegment(t0_ns=0, duration_ns=8_000_000_000)   # 0-8s
audio_a1 = AudioSegment(t0_ns=8_000_000_000, duration_ns=7_000_000_000)  # 8-15s
video_v1 = VideoSegment(t0_ns=6_000_000_000, duration_ns=6_000_000_000)  # 6-12s

# Action
await sync_manager.push_audio(audio_a0, audio_data_0)
await sync_manager.push_audio(audio_a1, audio_data_1)

# V1 (6-12s) overlaps both A0 (0-8s) and A1 (8-15s)
pair = await sync_manager.push_video(video_v1, video_data)

# Assert - Should pair with best overlap (A1 has more overlap: 4s vs 2s)
assert pair is not None
assert pair.audio_segment.t0_ns == 8_000_000_000  # A1 selected
```

---

## Scenario 4: Audio Cleanup

**User Story**: US4 - Audio Cleanup After All Videos Processed (P2)

### Test Case 4.1: Safe Eviction

```python
# Setup
audio_a0 = AudioSegment(t0_ns=0, duration_ns=8_000_000_000)  # 0-8s

# Action - Process multiple videos to advance watermark
await sync_manager.push_audio(audio_a0, audio_data)

# Push V0, V1, V2, V3 to advance max_video_pts_seen
for i in range(4):
    t0 = i * 6_000_000_000
    video = VideoSegment(t0_ns=t0, duration_ns=6_000_000_000)
    await sync_manager.push_video(video, video_data)

# After V3 (18-24s), watermark = 24s - 18s = 6s
# A0 ends at 8s > 6s, so A0 is retained

# Push V4 (24-30s)
video_v4 = VideoSegment(t0_ns=24_000_000_000, duration_ns=6_000_000_000)
await sync_manager.push_video(video_v4, video_data)

# After V4, watermark = 30s - 18s = 12s
# A0 ends at 8s <= 12s, so A0 should be evicted
assert sync_manager.audio_buffer_size == 0  # A0 evicted
```

---

## Scenario 5: Drift Detection

**User Story**: US5 - Drift Detection with PTS-Based Matching (P2)

### Test Case 5.1: Drift Calculated After Pairing

```python
# Setup
sync_manager = AvSyncManager(drift_threshold_ns=120_000_000)  # 120ms
audio = AudioSegment(t0_ns=0, duration_ns=6_000_000_000)
video = VideoSegment(t0_ns=0, duration_ns=6_000_000_000)

# Action
await sync_manager.push_audio(audio, audio_data)
pair = await sync_manager.push_video(video, video_data)

# Assert
assert pair is not None
assert sync_manager.sync_delta_ms < 120  # Within threshold
assert sync_manager.needs_correction is False
```

---

## Scenario 6: Timeout Fallback

**User Story**: US6 - Fallback with PTS-Based Matching (P3)

### Test Case 6.1: Timeout Triggers Fallback

```python
import time

# Setup
sync_manager = AvSyncManager()
video = VideoSegment(t0_ns=30_000_000_000, duration_ns=6_000_000_000)  # 30-36s

# Action - Push video, no matching audio
await sync_manager.push_video(video, video_data)
assert sync_manager.video_buffer_size == 1

# Simulate time passing (10+ seconds)
async def mock_get_original_audio(segment):
    return b"fallback_audio_data"

# Trigger timeout check with simulated future time
current_time = time.time_ns() + 11_000_000_000  # 11 seconds later
fallback_pairs = await sync_manager.check_timeouts(
    mock_get_original_audio,
    current_time_ns=current_time
)

# Assert
assert len(fallback_pairs) == 1
assert fallback_pairs[0].audio_segment.t0_ns == 30_000_000_000  # Matches video
assert fallback_pairs[0].audio_data == b"fallback_audio_data"
assert sync_manager.video_buffer_size == 0  # Video consumed
```

---

## Edge Case Scenarios

### Edge Case: Audio Gap

```python
# Video arrives but no audio covers its range
video = VideoSegment(t0_ns=100_000_000_000, duration_ns=6_000_000_000)  # 100-106s
audio = AudioSegment(t0_ns=0, duration_ns=8_000_000_000)  # 0-8s (no overlap)

await sync_manager.push_audio(audio, audio_data)
pair = await sync_manager.push_video(video, video_data)

assert pair is None
assert sync_manager.video_buffer_size == 1  # Buffered
# Will eventually timeout and use fallback
```

### Edge Case: Multiple Short Audio Segments

```python
# Multiple 2s audio segments, 6s video
audio_a0 = AudioSegment(t0_ns=0, duration_ns=2_000_000_000)  # 0-2s
audio_a1 = AudioSegment(t0_ns=2_000_000_000, duration_ns=2_000_000_000)  # 2-4s
audio_a2 = AudioSegment(t0_ns=4_000_000_000, duration_ns=2_000_000_000)  # 4-6s
video = VideoSegment(t0_ns=0, duration_ns=6_000_000_000)  # 0-6s

await sync_manager.push_audio(audio_a0, audio_data)
await sync_manager.push_audio(audio_a1, audio_data)
await sync_manager.push_audio(audio_a2, audio_data)

pair = await sync_manager.push_video(video, video_data)

# Video overlaps all three, but should pick one with max overlap
# All have equal overlap (2s each), so first in sorted order
assert pair is not None
```

### Edge Case: 15-Second Audio Spans Three Videos

```python
# Maximum VAD segment covers 3 videos
audio = AudioSegment(t0_ns=0, duration_ns=15_000_000_000)  # 0-15s
videos = [
    VideoSegment(t0_ns=0, duration_ns=6_000_000_000),   # 0-6s
    VideoSegment(t0_ns=6_000_000_000, duration_ns=6_000_000_000),  # 6-12s
    VideoSegment(t0_ns=12_000_000_000, duration_ns=6_000_000_000), # 12-18s (partial)
]

await sync_manager.push_audio(audio, audio_data)

pairs = []
for v in videos:
    pair = await sync_manager.push_video(v, video_data)
    if pair:
        pairs.append(pair)

# All three videos should pair with the same audio
assert len(pairs) == 3
assert all(p.audio_segment.t0_ns == 0 for p in pairs)
```

---

## Running Tests

```bash
# Run all PTS matching tests
pytest apps/media-service/tests/unit/test_av_sync_pts_matching.py -v

# Run with coverage
pytest apps/media-service/tests/unit/test_av_sync_pts_matching.py \
    --cov=media_service.sync.av_sync \
    --cov-fail-under=95

# Run specific test class
pytest apps/media-service/tests/unit/test_av_sync_pts_matching.py::TestPtsOverlap -v

# Run integration tests
pytest apps/media-service/tests/integration/test_av_sync_integration.py -v
```

## Debugging Tips

1. **Enable debug logging**: Set `LOG_LEVEL=DEBUG` to see pairing decisions
2. **Check buffer sizes**: Use `sync_manager.video_buffer_size` and `sync_manager.audio_buffer_size`
3. **Inspect internal state**: Access `sync_manager._audio_buffer` for sorted entries
4. **Verify PTS values**: All timestamps should be in nanoseconds (multiply seconds by 1e9)
