"""
Unit tests for PTS-based A/V segment pairing in AvSyncManager.

Tests for:
- AudioBufferEntry and VideoBufferEntry dataclasses
- PTS overlap detection algorithm
- Sorted audio buffer management
- Safe eviction watermark
- One-to-many audio pairing
- Timeout-based fallback

Per spec 024-pts-av-pairing: Replace batch_number matching with PTS range overlap.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from media_service.models.segments import AudioSegment, VideoSegment
from media_service.sync.av_sync import (
    AudioBufferEntry,
    AvSyncManager,
    SyncPair,
    VideoBufferEntry,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def audio_segment_0_8s() -> AudioSegment:
    """Create audio segment spanning 0-8 seconds."""
    return AudioSegment(
        fragment_id="audio-001",
        stream_id="test",
        batch_number=0,
        t0_ns=0,
        duration_ns=8_000_000_000,  # 8 seconds
        file_path=Path("/tmp/test/audio.m4a"),
    )


@pytest.fixture
def audio_segment_6_12s() -> AudioSegment:
    """Create audio segment spanning 6-12 seconds."""
    return AudioSegment(
        fragment_id="audio-002",
        stream_id="test",
        batch_number=1,
        t0_ns=6_000_000_000,
        duration_ns=6_000_000_000,  # 6 seconds
        file_path=Path("/tmp/test/audio2.m4a"),
    )


@pytest.fixture
def audio_segment_0_12s() -> AudioSegment:
    """Create audio segment spanning 0-12 seconds (covers 2 videos)."""
    return AudioSegment(
        fragment_id="audio-long",
        stream_id="test",
        batch_number=0,
        t0_ns=0,
        duration_ns=12_000_000_000,  # 12 seconds
        file_path=Path("/tmp/test/audio_long.m4a"),
    )


@pytest.fixture
def video_segment_0_6s() -> VideoSegment:
    """Create video segment spanning 0-6 seconds."""
    return VideoSegment(
        fragment_id="video-001",
        stream_id="test",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,  # 6 seconds
        file_path=Path("/tmp/test/video.mp4"),
    )


@pytest.fixture
def video_segment_6_12s() -> VideoSegment:
    """Create video segment spanning 6-12 seconds."""
    return VideoSegment(
        fragment_id="video-002",
        stream_id="test",
        batch_number=1,
        t0_ns=6_000_000_000,
        duration_ns=6_000_000_000,  # 6 seconds
        file_path=Path("/tmp/test/video2.mp4"),
    )


@pytest.fixture
def video_segment_12_18s() -> VideoSegment:
    """Create video segment spanning 12-18 seconds."""
    return VideoSegment(
        fragment_id="video-003",
        stream_id="test",
        batch_number=2,
        t0_ns=12_000_000_000,
        duration_ns=6_000_000_000,  # 6 seconds
        file_path=Path("/tmp/test/video3.mp4"),
    )


# =============================================================================
# Phase 2: AudioBufferEntry Tests (T004-T011)
# =============================================================================


class TestAudioBufferEntry:
    """Tests for AudioBufferEntry dataclass."""

    def test_t0_ns_property(self, audio_segment_0_8s: AudioSegment) -> None:
        """Test AudioBufferEntry.t0_ns returns segment start PTS."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_0_8s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        assert entry.t0_ns == 0

    def test_t0_ns_property_with_offset(self, audio_segment_6_12s: AudioSegment) -> None:
        """Test t0_ns property with non-zero start time."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_6_12s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        assert entry.t0_ns == 6_000_000_000

    def test_end_ns_property(self, audio_segment_0_8s: AudioSegment) -> None:
        """Test AudioBufferEntry.end_ns returns t0_ns + duration_ns."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_0_8s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        assert entry.end_ns == 8_000_000_000  # 0 + 8s

    def test_end_ns_property_with_offset(self, audio_segment_6_12s: AudioSegment) -> None:
        """Test end_ns property with non-zero start time."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_6_12s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        assert entry.end_ns == 12_000_000_000  # 6s + 6s

    def test_should_evict_when_below_watermark(self, audio_segment_0_8s: AudioSegment) -> None:
        """Test should_evict returns True when end_ns <= safe_eviction_pts."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_0_8s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        # Audio ends at 8s, watermark at 10s -> should evict
        assert entry.should_evict(safe_eviction_pts=10_000_000_000) is True

    def test_should_evict_exact_boundary(self, audio_segment_0_8s: AudioSegment) -> None:
        """Test should_evict returns True when end_ns == safe_eviction_pts."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_0_8s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        # Audio ends at 8s, watermark at exactly 8s -> should evict
        assert entry.should_evict(safe_eviction_pts=8_000_000_000) is True

    def test_should_not_evict_when_above_watermark(
        self, audio_segment_0_8s: AudioSegment
    ) -> None:
        """Test should_evict returns False when end_ns > safe_eviction_pts."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_0_8s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        # Audio ends at 8s, watermark at 6s -> should NOT evict
        assert entry.should_evict(safe_eviction_pts=6_000_000_000) is False

    def test_duration_ns_property(self, audio_segment_0_8s: AudioSegment) -> None:
        """Test AudioBufferEntry.duration_ns returns segment duration."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_0_8s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        assert entry.duration_ns == 8_000_000_000

    def test_paired_video_pts_starts_empty(self, audio_segment_0_8s: AudioSegment) -> None:
        """Test paired_video_pts is empty on creation."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_0_8s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        assert len(entry.paired_video_pts) == 0

    def test_paired_video_pts_can_add(self, audio_segment_0_8s: AudioSegment) -> None:
        """Test paired_video_pts set can be modified."""
        entry = AudioBufferEntry(
            audio_segment=audio_segment_0_8s,
            audio_data=b"audio_data",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )

        entry.paired_video_pts.add(0)
        entry.paired_video_pts.add(6_000_000_000)

        assert len(entry.paired_video_pts) == 2
        assert 0 in entry.paired_video_pts
        assert 6_000_000_000 in entry.paired_video_pts


# =============================================================================
# Phase 2: VideoBufferEntry Tests (T012-T019)
# =============================================================================


class TestVideoBufferEntry:
    """Tests for VideoBufferEntry dataclass."""

    def test_t0_ns_property(self, video_segment_0_6s: VideoSegment) -> None:
        """Test VideoBufferEntry.t0_ns returns segment start PTS."""
        entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video_data",
            insertion_time_ns=time.time_ns(),
        )

        assert entry.t0_ns == 0

    def test_t0_ns_property_with_offset(self, video_segment_6_12s: VideoSegment) -> None:
        """Test t0_ns property with non-zero start time."""
        entry = VideoBufferEntry(
            video_segment=video_segment_6_12s,
            video_data=b"video_data",
            insertion_time_ns=time.time_ns(),
        )

        assert entry.t0_ns == 6_000_000_000

    def test_end_ns_property(self, video_segment_0_6s: VideoSegment) -> None:
        """Test VideoBufferEntry.end_ns returns t0_ns + duration_ns."""
        entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video_data",
            insertion_time_ns=time.time_ns(),
        )

        assert entry.end_ns == 6_000_000_000  # 0 + 6s

    def test_end_ns_property_with_offset(self, video_segment_6_12s: VideoSegment) -> None:
        """Test end_ns property with non-zero start time."""
        entry = VideoBufferEntry(
            video_segment=video_segment_6_12s,
            video_data=b"video_data",
            insertion_time_ns=time.time_ns(),
        )

        assert entry.end_ns == 12_000_000_000  # 6s + 6s

    def test_duration_ns_property(self, video_segment_0_6s: VideoSegment) -> None:
        """Test VideoBufferEntry.duration_ns returns segment duration."""
        entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video_data",
            insertion_time_ns=time.time_ns(),
        )

        assert entry.duration_ns == 6_000_000_000

    def test_should_fallback_after_timeout(self, video_segment_0_6s: VideoSegment) -> None:
        """Test should_fallback returns True after timeout elapsed."""
        insertion_time = time.time_ns()
        entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video_data",
            insertion_time_ns=insertion_time,
        )

        # Simulate 11 seconds later (> 10s timeout)
        current_time = insertion_time + 11_000_000_000

        assert entry.should_fallback(current_time, timeout_ns=10_000_000_000) is True

    def test_should_fallback_exactly_at_timeout(self, video_segment_0_6s: VideoSegment) -> None:
        """Test should_fallback returns True at exact timeout boundary."""
        insertion_time = time.time_ns()
        entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video_data",
            insertion_time_ns=insertion_time,
        )

        # Exactly at 10 second timeout
        current_time = insertion_time + 10_000_000_000

        assert entry.should_fallback(current_time, timeout_ns=10_000_000_000) is True

    def test_should_not_fallback_before_timeout(
        self, video_segment_0_6s: VideoSegment
    ) -> None:
        """Test should_fallback returns False before timeout."""
        insertion_time = time.time_ns()
        entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video_data",
            insertion_time_ns=insertion_time,
        )

        # 5 seconds later (< 10s timeout)
        current_time = insertion_time + 5_000_000_000

        assert entry.should_fallback(current_time, timeout_ns=10_000_000_000) is False

    def test_should_fallback_custom_timeout(self, video_segment_0_6s: VideoSegment) -> None:
        """Test should_fallback with custom timeout value."""
        insertion_time = time.time_ns()
        entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video_data",
            insertion_time_ns=insertion_time,
        )

        # 3 seconds with 2 second timeout
        current_time = insertion_time + 3_000_000_000

        assert entry.should_fallback(current_time, timeout_ns=2_000_000_000) is True


# =============================================================================
# Phase 3: PTS Overlap Algorithm Tests (T024-T031)
# =============================================================================


class TestPtsOverlap:
    """Tests for PTS range overlap detection."""

    def test_overlaps_full_containment(self) -> None:
        """Test overlap detection when video is fully contained in audio."""
        sync = AvSyncManager()

        # Video 0-6s fully inside Audio 0-8s
        video_t0 = 0
        video_end = 6_000_000_000
        audio_t0 = 0
        audio_end = 8_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is True

    def test_overlaps_partial_start(self) -> None:
        """Test overlap when video starts before audio and ends inside."""
        sync = AvSyncManager()

        # Video 0-6s, Audio 4-12s -> overlap at 4-6s
        video_t0 = 0
        video_end = 6_000_000_000
        audio_t0 = 4_000_000_000
        audio_end = 12_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is True

    def test_overlaps_partial_end(self) -> None:
        """Test overlap when video starts inside audio and ends after."""
        sync = AvSyncManager()

        # Video 6-12s, Audio 0-8s -> overlap at 6-8s
        video_t0 = 6_000_000_000
        video_end = 12_000_000_000
        audio_t0 = 0
        audio_end = 8_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is True

    def test_overlaps_audio_contained_in_video(self) -> None:
        """Test overlap when audio is fully contained in video."""
        sync = AvSyncManager()

        # Video 0-12s contains Audio 2-8s
        video_t0 = 0
        video_end = 12_000_000_000
        audio_t0 = 2_000_000_000
        audio_end = 8_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is True

    def test_no_overlap_before(self) -> None:
        """Test no overlap when video is completely before audio."""
        sync = AvSyncManager()

        # Video 0-6s, Audio 8-14s -> no overlap
        video_t0 = 0
        video_end = 6_000_000_000
        audio_t0 = 8_000_000_000
        audio_end = 14_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is False

    def test_no_overlap_after(self) -> None:
        """Test no overlap when video is completely after audio."""
        sync = AvSyncManager()

        # Video 12-18s, Audio 0-8s -> no overlap
        video_t0 = 12_000_000_000
        video_end = 18_000_000_000
        audio_t0 = 0
        audio_end = 8_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is False

    def test_no_overlap_exact_boundary_video_before(self) -> None:
        """Test strict inequality - video ends exactly when audio starts."""
        sync = AvSyncManager()

        # Video ends at 6s, Audio starts at 6s -> NO overlap (strict inequality)
        video_t0 = 0
        video_end = 6_000_000_000
        audio_t0 = 6_000_000_000
        audio_end = 12_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is False

    def test_no_overlap_exact_boundary_audio_before(self) -> None:
        """Test strict inequality - audio ends exactly when video starts."""
        sync = AvSyncManager()

        # Audio ends at 6s, Video starts at 6s -> NO overlap (strict inequality)
        video_t0 = 6_000_000_000
        video_end = 12_000_000_000
        audio_t0 = 0
        audio_end = 6_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is False

    def test_minimal_overlap_one_nanosecond(self) -> None:
        """Test minimal 1ns overlap is detected."""
        sync = AvSyncManager()

        # Video ends at 6_000_000_001, Audio starts at 6_000_000_000 -> 1ns overlap
        video_t0 = 0
        video_end = 6_000_000_001
        audio_t0 = 6_000_000_000
        audio_end = 12_000_000_000

        assert sync._overlaps(video_t0, video_end, audio_t0, audio_end) is True


# =============================================================================
# Phase 4: Sorted Audio Buffer Tests (T032-T040)
# =============================================================================


class TestSortedAudioBuffer:
    """Tests for sorted audio buffer operations."""

    def test_insert_maintains_sorted_order(self) -> None:
        """Test insertions maintain PTS order in audio buffer."""
        sync = AvSyncManager()

        # Insert in order: 0s, 6s, 12s
        for i in range(3):
            segment = AudioSegment(
                fragment_id=f"a{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/test/a{i}.m4a"),
            )
            entry = AudioBufferEntry(
                audio_segment=segment,
                audio_data=f"audio{i}".encode(),
                paired_video_pts=set(),
                insertion_time_ns=time.time_ns(),
            )
            sync._insert_audio(entry)

        assert len(sync._audio_buffer) == 3
        assert sync._audio_buffer[0].t0_ns == 0
        assert sync._audio_buffer[1].t0_ns == 6_000_000_000
        assert sync._audio_buffer[2].t0_ns == 12_000_000_000

    def test_insert_out_of_order_arrivals(self) -> None:
        """Test out-of-order audio insertions are correctly sorted."""
        sync = AvSyncManager()

        # Insert out of order: 12s, 0s, 6s
        pts_order = [12_000_000_000, 0, 6_000_000_000]
        for i, t0 in enumerate(pts_order):
            segment = AudioSegment(
                fragment_id=f"a{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=t0,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/test/a{i}.m4a"),
            )
            entry = AudioBufferEntry(
                audio_segment=segment,
                audio_data=f"audio{i}".encode(),
                paired_video_pts=set(),
                insertion_time_ns=time.time_ns(),
            )
            sync._insert_audio(entry)

        # Should be sorted: [0s, 6s, 12s]
        assert len(sync._audio_buffer) == 3
        assert sync._audio_buffer[0].t0_ns == 0
        assert sync._audio_buffer[1].t0_ns == 6_000_000_000
        assert sync._audio_buffer[2].t0_ns == 12_000_000_000

    def test_find_overlapping_audio_single_match(
        self, video_segment_0_6s: VideoSegment
    ) -> None:
        """Test finding single overlapping audio entry."""
        sync = AvSyncManager()

        # Add audio 0-8s
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=8_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        entry = AudioBufferEntry(
            audio_segment=audio,
            audio_data=b"audio0",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry)

        # Video 0-6s overlaps audio 0-8s
        video_entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video",
            insertion_time_ns=time.time_ns(),
        )

        overlapping = sync._find_overlapping_audio(video_entry)

        assert len(overlapping) == 1
        assert overlapping[0].t0_ns == 0

    def test_find_overlapping_audio_multiple_matches(
        self, video_segment_6_12s: VideoSegment
    ) -> None:
        """Test finding multiple overlapping audio entries."""
        sync = AvSyncManager()

        # Add audio 0-8s and 8-15s
        for i, (t0, dur) in enumerate([(0, 8_000_000_000), (8_000_000_000, 7_000_000_000)]):
            audio = AudioSegment(
                fragment_id=f"a{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=t0,
                duration_ns=dur,
                file_path=Path(f"/tmp/test/a{i}.m4a"),
            )
            entry = AudioBufferEntry(
                audio_segment=audio,
                audio_data=f"audio{i}".encode(),
                paired_video_pts=set(),
                insertion_time_ns=time.time_ns(),
            )
            sync._insert_audio(entry)

        # Video 6-12s overlaps both
        video_entry = VideoBufferEntry(
            video_segment=video_segment_6_12s,
            video_data=b"video",
            insertion_time_ns=time.time_ns(),
        )

        overlapping = sync._find_overlapping_audio(video_entry)

        assert len(overlapping) == 2

    def test_find_overlapping_audio_no_matches(
        self, video_segment_12_18s: VideoSegment
    ) -> None:
        """Test finding no overlapping audio entries."""
        sync = AvSyncManager()

        # Add audio 0-8s
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=8_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        entry = AudioBufferEntry(
            audio_segment=audio,
            audio_data=b"audio0",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry)

        # Video 12-18s does not overlap audio 0-8s
        video_entry = VideoBufferEntry(
            video_segment=video_segment_12_18s,
            video_data=b"video",
            insertion_time_ns=time.time_ns(),
        )

        overlapping = sync._find_overlapping_audio(video_entry)

        assert len(overlapping) == 0

    def test_find_best_overlap_when_multiple(
        self, video_segment_6_12s: VideoSegment
    ) -> None:
        """Test selecting audio with maximum overlap amount."""
        sync = AvSyncManager()

        # Add audio 0-8s (2s overlap with video 6-12s)
        audio1 = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=8_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        entry1 = AudioBufferEntry(
            audio_segment=audio1,
            audio_data=b"audio0",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry1)

        # Add audio 8-15s (4s overlap with video 6-12s)
        audio2 = AudioSegment(
            fragment_id="a1",
            stream_id="test",
            batch_number=1,
            t0_ns=8_000_000_000,
            duration_ns=7_000_000_000,
            file_path=Path("/tmp/test/a1.m4a"),
        )
        entry2 = AudioBufferEntry(
            audio_segment=audio2,
            audio_data=b"audio1",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry2)

        # Video 6-12s
        video_entry = VideoBufferEntry(
            video_segment=video_segment_6_12s,
            video_data=b"video",
            insertion_time_ns=time.time_ns(),
        )

        overlapping = sync._find_overlapping_audio(video_entry)
        best = sync._select_best_overlap(video_entry, overlapping)

        # A1 (8-15s) has 4s overlap vs A0 (0-8s) with 2s overlap
        assert best is not None
        assert best.t0_ns == 8_000_000_000

    def test_select_best_overlap_empty_candidates(
        self, video_segment_0_6s: VideoSegment
    ) -> None:
        """Test select_best_overlap returns None for empty candidates."""
        sync = AvSyncManager()

        video_entry = VideoBufferEntry(
            video_segment=video_segment_0_6s,
            video_data=b"video",
            insertion_time_ns=time.time_ns(),
        )

        best = sync._select_best_overlap(video_entry, [])

        assert best is None


# =============================================================================
# Phase 5: Safe Eviction Watermark Tests (T041-T046)
# =============================================================================


class TestSafeEviction:
    """Tests for safe eviction watermark."""

    def test_eviction_watermark_calculation(self) -> None:
        """Test safe_eviction_pts = max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS)."""
        sync = AvSyncManager()

        # max_video_pts_seen = 30s (5 videos processed)
        sync._max_video_pts_seen = 30_000_000_000

        # Watermark should be 30s - 18s = 12s
        expected_watermark = 30_000_000_000 - (3 * 6_000_000_000)
        assert expected_watermark == 12_000_000_000

        # Add audio ending at 10s - should be evicted (10s <= 12s)
        audio1 = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=10_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        entry1 = AudioBufferEntry(
            audio_segment=audio1,
            audio_data=b"audio0",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry1)

        # Add audio ending at 20s - should NOT be evicted (20s > 12s)
        audio2 = AudioSegment(
            fragment_id="a1",
            stream_id="test",
            batch_number=1,
            t0_ns=10_000_000_000,
            duration_ns=10_000_000_000,
            file_path=Path("/tmp/test/a1.m4a"),
        )
        entry2 = AudioBufferEntry(
            audio_segment=audio2,
            audio_data=b"audio1",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry2)

        assert len(sync._audio_buffer) == 2

        sync._evict_stale_audio()

        assert len(sync._audio_buffer) == 1
        assert sync._audio_buffer[0].t0_ns == 10_000_000_000

    def test_audio_evicted_when_end_below_watermark(self) -> None:
        """Test audio evicted when audio.end_ns <= safe_eviction_pts."""
        sync = AvSyncManager()

        # Add audio ending at 6s
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        entry = AudioBufferEntry(
            audio_segment=audio,
            audio_data=b"audio0",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry)

        # Set watermark to allow eviction (24s - 18s = 6s, audio ends at 6s)
        sync._max_video_pts_seen = 24_000_000_000

        sync._evict_stale_audio()

        assert len(sync._audio_buffer) == 0

    def test_audio_retained_when_end_above_watermark(self) -> None:
        """Test audio retained when audio.end_ns > safe_eviction_pts."""
        sync = AvSyncManager()

        # Add audio ending at 10s
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=10_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        entry = AudioBufferEntry(
            audio_segment=audio,
            audio_data=b"audio0",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry)

        # Set watermark below audio end (24s - 18s = 6s, audio ends at 10s > 6s)
        sync._max_video_pts_seen = 24_000_000_000

        sync._evict_stale_audio()

        assert len(sync._audio_buffer) == 1

    def test_eviction_with_out_of_order_video(self) -> None:
        """Test eviction handles 18-second out-of-order tolerance."""
        sync = AvSyncManager()

        # Add audio ending at 8s
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=8_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        entry = AudioBufferEntry(
            audio_segment=audio,
            audio_data=b"audio0",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry)

        # Video at 24s - watermark is 24s - 18s = 6s
        # Audio ends at 8s > 6s, so retained
        sync._max_video_pts_seen = 24_000_000_000
        sync._evict_stale_audio()
        assert len(sync._audio_buffer) == 1

        # Video at 30s - watermark is 30s - 18s = 12s
        # Audio ends at 8s <= 12s, so evicted
        sync._max_video_pts_seen = 30_000_000_000
        sync._evict_stale_audio()
        assert len(sync._audio_buffer) == 0

    def test_no_eviction_when_watermark_negative(self) -> None:
        """Test no eviction when watermark is <= 0."""
        sync = AvSyncManager()

        # Add audio
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        entry = AudioBufferEntry(
            audio_segment=audio,
            audio_data=b"audio0",
            paired_video_pts=set(),
            insertion_time_ns=time.time_ns(),
        )
        sync._insert_audio(entry)

        # Watermark would be 12s - 18s = -6s (negative)
        sync._max_video_pts_seen = 12_000_000_000

        sync._evict_stale_audio()

        # No eviction when watermark <= 0
        assert len(sync._audio_buffer) == 1


# =============================================================================
# Phase 6: Push Video with PTS Matching Tests (T047-T052)
# =============================================================================


class TestPushVideoWithPts:
    """Tests for push_video with PTS-based matching."""

    @pytest.mark.asyncio
    async def test_push_video_pairs_with_overlapping_audio(
        self, video_segment_0_6s: VideoSegment, audio_segment_0_8s: AudioSegment
    ) -> None:
        """Test push_video returns pair when overlapping audio exists."""
        sync = AvSyncManager()

        # Buffer audio first
        await sync.push_audio(audio_segment_0_8s, b"audio_data")
        assert sync.audio_buffer_size == 1

        # Push video - should pair
        pair = await sync.push_video(video_segment_0_6s, b"video_data")

        assert pair is not None
        assert isinstance(pair, SyncPair)
        assert pair.video_segment.t0_ns == 0
        assert pair.audio_segment.t0_ns == 0

    @pytest.mark.asyncio
    async def test_push_video_buffers_when_no_overlap(
        self, video_segment_12_18s: VideoSegment, audio_segment_0_8s: AudioSegment
    ) -> None:
        """Test push_video buffers when no overlapping audio."""
        sync = AvSyncManager()

        # Buffer audio 0-8s
        await sync.push_audio(audio_segment_0_8s, b"audio_data")

        # Push video 12-18s - no overlap
        pair = await sync.push_video(video_segment_12_18s, b"video_data")

        assert pair is None
        assert sync.video_buffer_size == 1

    @pytest.mark.asyncio
    async def test_push_video_updates_max_pts_seen(
        self, video_segment_6_12s: VideoSegment
    ) -> None:
        """Test push_video updates _max_video_pts_seen."""
        sync = AvSyncManager()

        assert sync._max_video_pts_seen == 0

        await sync.push_video(video_segment_6_12s, b"video_data")

        # Video ends at 12s
        assert sync._max_video_pts_seen == 12_000_000_000

    @pytest.mark.asyncio
    async def test_push_video_updates_max_pts_to_maximum(self) -> None:
        """Test _max_video_pts_seen tracks maximum of all videos."""
        sync = AvSyncManager()

        # Push video 0-6s
        video1 = VideoSegment(
            fragment_id="v1",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v1.mp4"),
        )
        await sync.push_video(video1, b"v1")
        assert sync._max_video_pts_seen == 6_000_000_000

        # Push video 6-12s
        video2 = VideoSegment(
            fragment_id="v2",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v2.mp4"),
        )
        await sync.push_video(video2, b"v2")
        assert sync._max_video_pts_seen == 12_000_000_000

    @pytest.mark.asyncio
    async def test_push_video_triggers_eviction(self) -> None:
        """Test push_video triggers audio eviction."""
        sync = AvSyncManager()

        # Buffer audio ending at 6s
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        await sync.push_audio(audio, b"audio")
        assert sync.audio_buffer_size == 1

        # Push videos to advance watermark past audio end
        for i in range(5):  # 0-6, 6-12, 12-18, 18-24, 24-30
            video = VideoSegment(
                fragment_id=f"v{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/test/v{i}.mp4"),
            )
            await sync.push_video(video, f"v{i}".encode())

        # After v4 (24-30s), watermark = 30s - 18s = 12s
        # Audio ends at 6s <= 12s, should be evicted
        assert sync.audio_buffer_size == 0


# =============================================================================
# Phase 7: Push Audio with PTS Matching & One-to-Many Tests (T053-T061)
# =============================================================================


class TestPushAudioWithPts:
    """Tests for push_audio with PTS-based matching and one-to-many support."""

    @pytest.mark.asyncio
    async def test_push_audio_pairs_with_overlapping_video(
        self, video_segment_0_6s: VideoSegment, audio_segment_0_8s: AudioSegment
    ) -> None:
        """Test push_audio returns pairs when overlapping videos exist."""
        sync = AvSyncManager()

        # Buffer video first
        await sync.push_video(video_segment_0_6s, b"video_data")
        assert sync.video_buffer_size == 1

        # Push audio - should pair
        pairs = await sync.push_audio(audio_segment_0_8s, b"audio_data")

        assert pairs is not None
        assert len(pairs) == 1
        assert pairs[0].video_segment.t0_ns == 0
        assert pairs[0].audio_segment.t0_ns == 0
        assert sync.video_buffer_size == 0

    @pytest.mark.asyncio
    async def test_push_audio_buffers_when_no_overlap(
        self, audio_segment_0_8s: AudioSegment
    ) -> None:
        """Test push_audio buffers when no overlapping videos."""
        sync = AvSyncManager()

        # No videos buffered
        pairs = await sync.push_audio(audio_segment_0_8s, b"audio_data")

        assert pairs is None
        assert sync.audio_buffer_size == 1

    @pytest.mark.asyncio
    async def test_push_audio_one_to_many_pairing(
        self,
        video_segment_0_6s: VideoSegment,
        video_segment_6_12s: VideoSegment,
        audio_segment_0_12s: AudioSegment,
    ) -> None:
        """Test single audio pairs with multiple overlapping videos."""
        sync = AvSyncManager()

        # Buffer two videos
        await sync.push_video(video_segment_0_6s, b"v0")
        await sync.push_video(video_segment_6_12s, b"v1")
        assert sync.video_buffer_size == 2

        # Push 12s audio - should pair with both
        pairs = await sync.push_audio(audio_segment_0_12s, b"audio")

        assert pairs is not None
        assert len(pairs) == 2
        assert sync.video_buffer_size == 0

    @pytest.mark.asyncio
    async def test_push_audio_sorted_insertion(self) -> None:
        """Test audio maintains sorted order in buffer."""
        sync = AvSyncManager()

        # Push audio out of order
        audio2 = AudioSegment(
            fragment_id="a2",
            stream_id="test",
            batch_number=2,
            t0_ns=12_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/a2.m4a"),
        )
        await sync.push_audio(audio2, b"a2")

        audio0 = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        await sync.push_audio(audio0, b"a0")

        audio1 = AudioSegment(
            fragment_id="a1",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/a1.m4a"),
        )
        await sync.push_audio(audio1, b"a1")

        # Should be sorted
        assert sync._audio_buffer[0].t0_ns == 0
        assert sync._audio_buffer[1].t0_ns == 6_000_000_000
        assert sync._audio_buffer[2].t0_ns == 12_000_000_000

    @pytest.mark.asyncio
    async def test_audio_reused_for_multiple_videos(self) -> None:
        """Test acceptance scenario: same audio pairs with multiple videos."""
        sync = AvSyncManager()

        # 12s audio spanning two video segments
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=12_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        await sync.push_audio(audio, b"audio")

        # Push V0 (0-6s) - should pair with A0
        video0 = VideoSegment(
            fragment_id="v0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v0.mp4"),
        )
        pair0 = await sync.push_video(video0, b"v0")
        assert pair0 is not None
        assert pair0.audio_segment.t0_ns == 0

        # A0 should still be in buffer for future matches
        assert sync.audio_buffer_size == 1

        # Push V1 (6-12s) - should also pair with A0
        video1 = VideoSegment(
            fragment_id="v1",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v1.mp4"),
        )
        pair1 = await sync.push_video(video1, b"v1")
        assert pair1 is not None
        assert pair1.audio_segment.t0_ns == 0  # Same audio

        # V2 (12-18s) should NOT pair with A0 (ends at 12s)
        video2 = VideoSegment(
            fragment_id="v2",
            stream_id="test",
            batch_number=2,
            t0_ns=12_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v2.mp4"),
        )
        pair2 = await sync.push_video(video2, b"v2")
        assert pair2 is None  # No overlap
        assert sync.video_buffer_size == 1  # V2 buffered

    @pytest.mark.asyncio
    async def test_audio_reference_counting(self) -> None:
        """Test paired_video_pts set grows with each pairing."""
        sync = AvSyncManager()

        # 12s audio
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=12_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        await sync.push_audio(audio, b"audio")

        # Pair with V0
        video0 = VideoSegment(
            fragment_id="v0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v0.mp4"),
        )
        await sync.push_video(video0, b"v0")

        # Check paired_video_pts has V0
        assert 0 in sync._audio_buffer[0].paired_video_pts

        # Pair with V1
        video1 = VideoSegment(
            fragment_id="v1",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v1.mp4"),
        )
        await sync.push_video(video1, b"v1")

        # Check paired_video_pts has both V0 and V1
        assert 0 in sync._audio_buffer[0].paired_video_pts
        assert 6_000_000_000 in sync._audio_buffer[0].paired_video_pts


# =============================================================================
# Phase 8: Timeout-Based Fallback Tests (T062-T066)
# =============================================================================


class TestTimeoutFallback:
    """Tests for timeout-based fallback mechanism."""

    @pytest.mark.asyncio
    async def test_video_timeout_triggers_fallback(
        self, video_segment_0_6s: VideoSegment
    ) -> None:
        """Test video > 10s old triggers fallback."""
        sync = AvSyncManager()

        # Push video with known insertion time
        insertion_time = time.time_ns()
        sync._video_buffer.append(
            VideoBufferEntry(
                video_segment=video_segment_0_6s,
                video_data=b"video",
                insertion_time_ns=insertion_time,
            )
        )

        async def get_original_audio(segment: AudioSegment) -> bytes:
            return b"fallback_audio"

        # Check with time 11 seconds later
        current_time = insertion_time + 11_000_000_000

        pairs = await sync.check_timeouts(get_original_audio, current_time_ns=current_time)

        assert len(pairs) == 1
        assert pairs[0].audio_data == b"fallback_audio"
        assert sync.video_buffer_size == 0

    @pytest.mark.asyncio
    async def test_check_timeouts_returns_all_timed_out_videos(self) -> None:
        """Test check_timeouts identifies all expired videos."""
        sync = AvSyncManager()

        insertion_time = time.time_ns()

        # Add 3 videos
        for i in range(3):
            video = VideoSegment(
                fragment_id=f"v{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/test/v{i}.mp4"),
            )
            sync._video_buffer.append(
                VideoBufferEntry(
                    video_segment=video,
                    video_data=f"v{i}".encode(),
                    insertion_time_ns=insertion_time,
                )
            )

        async def get_original_audio(segment: AudioSegment) -> bytes:
            return b"fallback"

        # 11 seconds later - all should timeout
        current_time = insertion_time + 11_000_000_000

        pairs = await sync.check_timeouts(get_original_audio, current_time_ns=current_time)

        assert len(pairs) == 3
        assert sync.video_buffer_size == 0

    @pytest.mark.asyncio
    async def test_check_timeouts_leaves_fresh_videos(self) -> None:
        """Test check_timeouts does not affect fresh videos."""
        sync = AvSyncManager()

        old_time = time.time_ns()
        new_time = old_time + 11_000_000_000

        # Add old video
        old_video = VideoSegment(
            fragment_id="v_old",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v_old.mp4"),
        )
        sync._video_buffer.append(
            VideoBufferEntry(
                video_segment=old_video,
                video_data=b"old",
                insertion_time_ns=old_time,
            )
        )

        # Add fresh video
        fresh_video = VideoSegment(
            fragment_id="v_fresh",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v_fresh.mp4"),
        )
        sync._video_buffer.append(
            VideoBufferEntry(
                video_segment=fresh_video,
                video_data=b"fresh",
                insertion_time_ns=new_time,
            )
        )

        async def get_original_audio(segment: AudioSegment) -> bytes:
            return b"fallback"

        # Check at new_time + 1s (old video timed out, fresh is only 1s old)
        current_time = new_time + 1_000_000_000

        pairs = await sync.check_timeouts(get_original_audio, current_time_ns=current_time)

        assert len(pairs) == 1
        assert pairs[0].video_segment.fragment_id == "v_old"
        assert sync.video_buffer_size == 1
        assert sync._video_buffer[0].video_segment.fragment_id == "v_fresh"

    @pytest.mark.asyncio
    async def test_fallback_audio_has_correct_pts(
        self, video_segment_6_12s: VideoSegment
    ) -> None:
        """Test fallback AudioSegment has video's t0_ns and duration_ns."""
        sync = AvSyncManager()

        insertion_time = time.time_ns()
        sync._video_buffer.append(
            VideoBufferEntry(
                video_segment=video_segment_6_12s,
                video_data=b"video",
                insertion_time_ns=insertion_time,
            )
        )

        async def get_original_audio(segment: AudioSegment) -> bytes:
            # Verify the segment passed has correct PTS
            assert segment.t0_ns == 6_000_000_000
            assert segment.duration_ns == 6_000_000_000
            return b"fallback"

        current_time = insertion_time + 11_000_000_000

        pairs = await sync.check_timeouts(get_original_audio, current_time_ns=current_time)

        assert len(pairs) == 1
        assert pairs[0].audio_segment.t0_ns == 6_000_000_000
        assert pairs[0].audio_segment.duration_ns == 6_000_000_000


# =============================================================================
# Phase 9: Drift Detection Compatibility Tests (T067-T072)
# =============================================================================


class TestDriftDetectionWithPts:
    """Tests for drift detection with PTS-based matching."""

    @pytest.mark.asyncio
    async def test_drift_detection_with_pts_matching(
        self, video_segment_0_6s: VideoSegment, audio_segment_0_8s: AudioSegment
    ) -> None:
        """Test sync_delta_ns calculated after PTS pair creation."""
        sync = AvSyncManager(drift_threshold_ns=120_000_000)

        await sync.push_audio(audio_segment_0_8s, b"audio")
        pair = await sync.push_video(video_segment_0_6s, b"video")

        assert pair is not None
        # Sync delta should be calculated (may be 0 for identical PTS)
        assert hasattr(sync.state, "sync_delta_ns")

    @pytest.mark.asyncio
    async def test_needs_correction_with_pts_pairing(self) -> None:
        """Test needs_correction works with PTS-paired segments."""
        sync = AvSyncManager(drift_threshold_ns=100_000_000)

        # Manually set drift above threshold
        sync.state.sync_delta_ns = 150_000_000

        assert sync.needs_correction is True

    @pytest.mark.asyncio
    async def test_needs_correction_false_within_threshold(self) -> None:
        """Test needs_correction is False when within threshold."""
        sync = AvSyncManager(drift_threshold_ns=100_000_000)

        # Set drift below threshold
        sync.state.sync_delta_ns = 50_000_000

        assert sync.needs_correction is False


# =============================================================================
# Phase 13: Performance & Edge Case Tests (T086-T091)
# =============================================================================


class TestPerformanceAndEdgeCases:
    """Performance and edge case tests."""

    @pytest.mark.asyncio
    async def test_pairing_latency(self) -> None:
        """Verify pairing completes within 10ms."""
        import time

        sync = AvSyncManager()

        # Pre-buffer audio
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=8_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        await sync.push_audio(audio, b"audio")

        video = VideoSegment(
            fragment_id="v0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v0.mp4"),
        )

        start = time.perf_counter_ns()
        await sync.push_video(video, b"video")
        elapsed_ns = time.perf_counter_ns() - start

        # Should complete within 10ms = 10_000_000ns
        assert elapsed_ns < 10_000_000

    def test_exact_boundary_no_overlap(self) -> None:
        """Test strict inequality - exact boundaries do NOT overlap."""
        sync = AvSyncManager()

        # Video 0-6s, Audio 6-12s - touching but not overlapping
        assert sync._overlaps(0, 6_000_000_000, 6_000_000_000, 12_000_000_000) is False

        # Audio 0-6s, Video 6-12s - touching but not overlapping
        assert sync._overlaps(6_000_000_000, 12_000_000_000, 0, 6_000_000_000) is False

    @pytest.mark.asyncio
    async def test_very_short_audio_segment(self) -> None:
        """Test 1-second audio pairing."""
        sync = AvSyncManager()

        # 1 second audio
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=2_000_000_000,  # 2-3 seconds
            duration_ns=1_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        await sync.push_audio(audio, b"audio")

        # 6 second video 0-6s overlaps audio 2-3s
        video = VideoSegment(
            fragment_id="v0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/v0.mp4"),
        )
        pair = await sync.push_video(video, b"video")

        assert pair is not None
        assert pair.audio_segment.t0_ns == 2_000_000_000

    @pytest.mark.asyncio
    async def test_maximum_duration_audio(self) -> None:
        """Test 15-second audio with 2-3 videos."""
        sync = AvSyncManager()

        # 15 second audio
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=15_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        await sync.push_audio(audio, b"audio")

        pairs = []
        for i in range(3):
            video = VideoSegment(
                fragment_id=f"v{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/test/v{i}.mp4"),
            )
            pair = await sync.push_video(video, f"v{i}".encode())
            if pair:
                pairs.append(pair)

        # All 3 videos should pair with the 15s audio
        assert len(pairs) == 3
        assert all(p.audio_segment.t0_ns == 0 for p in pairs)

    @pytest.mark.asyncio
    async def test_out_of_order_segment_arrival(self) -> None:
        """Test both audio and video arriving out-of-order."""
        sync = AvSyncManager()

        # Push videos out of order: V2, V0, V1
        videos = [
            VideoSegment(
                fragment_id="v2",
                stream_id="test",
                batch_number=2,
                t0_ns=12_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path("/tmp/test/v2.mp4"),
            ),
            VideoSegment(
                fragment_id="v0",
                stream_id="test",
                batch_number=0,
                t0_ns=0,
                duration_ns=6_000_000_000,
                file_path=Path("/tmp/test/v0.mp4"),
            ),
            VideoSegment(
                fragment_id="v1",
                stream_id="test",
                batch_number=1,
                t0_ns=6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path("/tmp/test/v1.mp4"),
            ),
        ]

        for v in videos:
            await sync.push_video(v, b"video")

        # Push audio that spans V0 and V1
        audio = AudioSegment(
            fragment_id="a0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=12_000_000_000,
            file_path=Path("/tmp/test/a0.m4a"),
        )
        pairs = await sync.push_audio(audio, b"audio")

        # Should pair with V0 and V1 (0-12s overlap)
        assert pairs is not None
        assert len(pairs) == 2
        # V2 should still be buffered
        assert sync.video_buffer_size == 1
        assert sync._video_buffer[0].t0_ns == 12_000_000_000
