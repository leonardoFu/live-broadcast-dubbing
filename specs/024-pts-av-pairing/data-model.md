# Data Model: PTS-Based A/V Pairing

**Feature**: 024-pts-av-pairing
**Date**: 2026-01-10

## Overview

This document defines the data structures for PTS-based A/V segment pairing. The key change is replacing the batch_number-keyed dictionary with a sorted list structure to support variable-length audio segments from VAD.

## Entities

### AudioBufferEntry (NEW)

Wrapper for buffered audio segments with reference counting for one-to-many pairing support.

```python
from dataclasses import dataclass, field
from media_service.models.segments import AudioSegment

@dataclass
class AudioBufferEntry:
    """Wrapper for buffered audio with reference tracking.

    Supports one-to-many pairing where a single audio segment
    can pair with multiple video segments that overlap its PTS range.

    Attributes:
        audio_segment: The underlying AudioSegment metadata
        audio_data: Raw audio bytes
        paired_video_pts: Set of video t0_ns values that have paired with this audio
        insertion_time_ns: Wall-clock time when audio was buffered (for debugging)

    Invariants:
        - audio_segment.t0_ns is immutable after creation
        - audio_segment.duration_ns is immutable after creation
        - paired_video_pts only grows (videos are never "unpaired")
    """

    audio_segment: AudioSegment
    audio_data: bytes
    paired_video_pts: set[int] = field(default_factory=set)
    insertion_time_ns: int = 0

    @property
    def t0_ns(self) -> int:
        """Start PTS in nanoseconds - key for sorting."""
        return self.audio_segment.t0_ns

    @property
    def end_ns(self) -> int:
        """End PTS in nanoseconds - for overlap calculation."""
        return self.audio_segment.t0_ns + self.audio_segment.duration_ns

    @property
    def duration_ns(self) -> int:
        """Duration in nanoseconds."""
        return self.audio_segment.duration_ns

    def overlaps_video(self, video_t0_ns: int, video_end_ns: int) -> bool:
        """Check if this audio overlaps with a video PTS range.

        Uses strict inequality per spec: segments touching at exact
        boundaries do NOT overlap.

        Args:
            video_t0_ns: Video start PTS
            video_end_ns: Video end PTS

        Returns:
            True if ranges overlap (not just touch)
        """
        return video_t0_ns < self.end_ns and self.t0_ns < video_end_ns

    def overlap_amount(self, video_t0_ns: int, video_end_ns: int) -> int:
        """Calculate amount of overlap with a video PTS range.

        Args:
            video_t0_ns: Video start PTS
            video_end_ns: Video end PTS

        Returns:
            Overlap duration in nanoseconds (0 if no overlap)
        """
        overlap_start = max(self.t0_ns, video_t0_ns)
        overlap_end = min(self.end_ns, video_end_ns)
        return max(0, overlap_end - overlap_start)

    def should_evict(self, safe_eviction_pts: int) -> bool:
        """Check if audio can be safely evicted.

        Audio is evicted when its end PTS is at or before the safe
        eviction watermark, meaning no future videos can overlap.

        Args:
            safe_eviction_pts: Watermark calculated as
                max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS)

        Returns:
            True if audio should be evicted
        """
        return self.end_ns <= safe_eviction_pts
```

### VideoBufferEntry (NEW)

Wrapper for buffered video segments with timeout tracking for fallback support.

```python
from dataclasses import dataclass
from media_service.models.segments import VideoSegment

@dataclass
class VideoBufferEntry:
    """Wrapper for buffered video with timeout tracking.

    Videos are buffered when they arrive before matching audio.
    Timeout tracking enables fallback to original audio when
    dubbed audio is not available within threshold.

    Attributes:
        video_segment: The underlying VideoSegment metadata
        video_data: Raw video bytes
        insertion_time_ns: Wall-clock time when video was buffered

    Invariants:
        - video_segment.t0_ns is immutable after creation
        - video_segment.duration_ns is immutable after creation
        - insertion_time_ns is wall-clock, NOT PTS
    """

    video_segment: VideoSegment
    video_data: bytes
    insertion_time_ns: int = 0

    @property
    def t0_ns(self) -> int:
        """Start PTS in nanoseconds."""
        return self.video_segment.t0_ns

    @property
    def end_ns(self) -> int:
        """End PTS in nanoseconds."""
        return self.video_segment.t0_ns + self.video_segment.duration_ns

    @property
    def duration_ns(self) -> int:
        """Duration in nanoseconds."""
        return self.video_segment.duration_ns

    def should_fallback(
        self,
        current_time_ns: int,
        timeout_ns: int = 10_000_000_000
    ) -> bool:
        """Check if video has waited too long for matching audio.

        Args:
            current_time_ns: Current wall-clock time in nanoseconds
            timeout_ns: Maximum wait time (default 10 seconds)

        Returns:
            True if video should use fallback audio
        """
        age_ns = current_time_ns - self.insertion_time_ns
        return age_ns >= timeout_ns
```

### SyncPair (UNCHANGED)

The output entity remains unchanged - it pairs video and audio for output.

```python
@dataclass
class SyncPair:
    """Paired video and audio segments for output.

    Attributes:
        video_segment: VideoSegment with video data
        video_data: Raw video buffer data
        audio_segment: AudioSegment (dubbed or original)
        audio_data: Audio data for output
        pts_ns: Output PTS in nanoseconds
    """

    video_segment: VideoSegment
    video_data: bytes
    audio_segment: AudioSegment
    audio_data: bytes
    pts_ns: int
```

## Buffer Structures

### Audio Buffer

**Before (batch_number-keyed)**:
```python
_audio_buffer: dict[int, tuple[AudioSegment, bytes]]
# Key: batch_number (int)
# Value: (segment metadata, audio data)
```

**After (PTS-sorted list)**:
```python
_audio_buffer: list[AudioBufferEntry]
# Sorted by AudioBufferEntry.t0_ns (ascending)
# Insertion uses bisect.bisect_left for O(n) sorted insert
# Query uses linear scan for overlap detection
```

### Video Buffer

**Before (simple deque)**:
```python
_video_buffer: deque[tuple[VideoSegment, bytes]]
```

**After (list with timeout tracking)**:
```python
_video_buffer: list[VideoBufferEntry]
# Order: insertion order (FIFO for processing)
# Each entry tracks insertion_time_ns for timeout detection
```

## State Variables

### New State in AvSyncManager

```python
class AvSyncManager:
    # Existing
    state: AvSyncState
    max_buffer_size: int
    _lock: asyncio.Lock
    _ready_pairs: deque[SyncPair]

    # Changed
    _audio_buffer: list[AudioBufferEntry]  # Was dict[int, tuple]
    _video_buffer: list[VideoBufferEntry]  # Was deque[tuple]

    # New
    _max_video_pts_seen: int = 0  # For safe eviction watermark

    # Constants
    VIDEO_SEGMENT_DURATION_NS: ClassVar[int] = 6_000_000_000  # 6 seconds
    FALLBACK_TIMEOUT_NS: ClassVar[int] = 10_000_000_000  # 10 seconds
```

## Algorithms

### PTS Overlap Detection

```
OVERLAP(video, audio):
    video_end = video.t0_ns + video.duration_ns
    audio_end = audio.t0_ns + audio.duration_ns

    # Strict inequality - touching boundaries do NOT overlap
    RETURN video.t0_ns < audio_end AND audio.t0_ns < video_end
```

### Safe Eviction Watermark

```
EVICTION_WATERMARK:
    # Account for out-of-order video arrival (3 segment tolerance)
    watermark = max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS)

    FOR each audio IN audio_buffer:
        IF audio.end_ns <= watermark:
            EVICT audio
```

### Best Overlap Selection

```
SELECT_BEST_OVERLAP(video, candidates):
    IF candidates IS EMPTY:
        RETURN None

    best = None
    best_overlap = 0

    FOR each audio IN candidates:
        overlap = OVERLAP_AMOUNT(video, audio)
        IF overlap > best_overlap:
            best = audio
            best_overlap = overlap

    RETURN best
```

## Relationships

```
                      1                 *
    VideoSegment ─────────────────────────── SyncPair
         │                                      │
         │                                      │
         ▼                                      ▼
  VideoBufferEntry                        AudioSegment
         │                                      │
         │                                      │
         │         PTS Overlap                  ▼
         └─────────────────────────── AudioBufferEntry
                   * : *                        │
                                               │
                                               ▼
                                    paired_video_pts: set[int]
```

**Key Relationships**:
- One audio can pair with multiple videos (one-to-many via PTS overlap)
- One video pairs with at most one audio (best overlap selection)
- Audio tracks which videos have paired via `paired_video_pts` set
- SyncPair contains references to both original segments

## Validation Rules

### AudioBufferEntry

1. `audio_segment.t0_ns >= 0` - PTS must be non-negative
2. `audio_segment.duration_ns > 0` - Duration must be positive
3. `audio_segment.duration_ns <= 15_000_000_000` - Max 15 seconds (VAD limit)
4. `audio_segment.duration_ns >= 1_000_000_000` - Min 1 second (VAD limit)

### VideoBufferEntry

1. `video_segment.t0_ns >= 0` - PTS must be non-negative
2. `video_segment.duration_ns > 0` - Duration must be positive
3. `video_segment.duration_ns ~= 6_000_000_000` - Fixed 6 seconds (+/- 100ms)

### Buffer Constraints

1. `len(_audio_buffer) <= max_buffer_size` - Enforce buffer limit
2. `len(_video_buffer) <= max_buffer_size` - Enforce buffer limit
3. Audio buffer maintains sorted order by `t0_ns`
4. Video buffer maintains insertion order (FIFO)
