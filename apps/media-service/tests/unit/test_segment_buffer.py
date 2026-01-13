"""
Unit tests for SegmentBuffer class.

Tests T031-T039 from tasks.md - validating segment buffering.

Updated for spec 021-fragment-length-30s:
- Default segment duration changed from 6s to 30s
- FR-003: SegmentBuffer.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000
"""

from __future__ import annotations

from pathlib import Path

from media_service.buffer.segment_buffer import BufferAccumulator, SegmentBuffer
from media_service.models.segments import AudioSegment, VideoSegment


class TestBufferAccumulator:
    """Tests for BufferAccumulator helper class."""

    def test_default_values(self) -> None:
        """Test default accumulator values."""
        acc = BufferAccumulator()

        assert acc.is_empty() is True
        assert len(acc.data) == 0
        assert acc.t0_ns == 0
        assert acc.duration_ns == 0
        assert acc.buffer_count == 0

    def test_accumulate_data(self) -> None:
        """Test data accumulation."""
        acc = BufferAccumulator()

        acc.data.extend(b"hello")
        acc.t0_ns = 1_000_000_000
        acc.duration_ns = 100_000_000
        acc.buffer_count = 1

        assert acc.is_empty() is False
        assert len(acc.data) == 5
        assert acc.duration_ns == 100_000_000

    def test_reset(self) -> None:
        """Test reset clears all values."""
        acc = BufferAccumulator()

        acc.data.extend(b"data")
        acc.t0_ns = 100
        acc.duration_ns = 200
        acc.buffer_count = 5

        acc.reset()

        assert acc.is_empty() is True
        assert acc.t0_ns == 0
        assert acc.duration_ns == 0
        assert acc.buffer_count == 0


class TestSegmentBufferInit:
    """Tests for SegmentBuffer initialization."""

    def test_creates_segment_directory(self, tmp_path: Path) -> None:
        """Test that segment directory is created on init."""
        segment_dir = tmp_path / "segments"
        _buffer = SegmentBuffer(
            stream_id="test-stream",
            segment_dir=segment_dir,
        )

        assert segment_dir.exists()
        assert (segment_dir / "test-stream").exists()

    def test_default_segment_duration(self, tmp_path: Path) -> None:
        """Test default segment duration is 30 seconds (spec 021)."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
        )

        assert buffer.segment_duration_ns == 30_000_000_000

    def test_segment_buffer_accumulates_30s(self, tmp_path: Path) -> None:
        """FR-003: SegmentBuffer emits at 30s threshold (spec 021)."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
        )
        assert buffer.segment_duration_ns == 30_000_000_000
        assert SegmentBuffer.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000

    def test_custom_segment_duration(self, tmp_path: Path) -> None:
        """Test custom segment duration is respected."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
            segment_duration_ns=3_000_000_000,  # 3 seconds
        )

        assert buffer.segment_duration_ns == 3_000_000_000


class TestSegmentBufferVideo:
    """Tests for video buffer accumulation."""

    def test_push_video_returns_none_before_full(self, tmp_path: Path) -> None:
        """Test push_video returns None until segment full."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
        )

        # Push 1 second of data
        segment, data = buffer.push_video(
            buffer_data=b"video_data",
            pts_ns=0,
            duration_ns=1_000_000_000,
        )

        assert segment is None
        assert data == b""

    def test_push_video_returns_segment_when_full(self, tmp_path: Path) -> None:
        """Test push_video returns segment when duration reached and keyframe arrives."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
            segment_duration_ns=2_000_000_000,  # 2 seconds
        )

        # Push first second
        segment, data = buffer.push_video(
            buffer_data=b"frame1",
            pts_ns=0,
            duration_ns=1_000_000_000,
        )
        assert segment is None

        # Push second second - duration reached but waiting for keyframe
        segment, data = buffer.push_video(
            buffer_data=b"frame2",
            pts_ns=1_000_000_000,
            duration_ns=1_000_000_000,
        )
        # With keyframe alignment, segment waits for keyframe
        assert segment is None

        # Push keyframe - should emit segment and start new one with keyframe
        segment, data = buffer.push_video(
            buffer_data=b"keyframe",
            pts_ns=2_000_000_000,
            duration_ns=1_000_000_000,
            is_keyframe=True,
        )

        assert segment is not None
        assert isinstance(segment, VideoSegment)
        assert data == b"frame1frame2"  # Keyframe is NOT included (starts next segment)
        assert segment.batch_number == 0
        assert segment.stream_id == "test"
        assert segment.t0_ns == 0
        assert segment.duration_ns == 2_000_000_000

    def test_video_batch_number_increments(self, tmp_path: Path) -> None:
        """Test video batch number increments with each segment."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
            segment_duration_ns=1_000_000_000,  # 1 second
        )

        # Push first second of data (reaches threshold)
        segment1, _ = buffer.push_video(b"data", 0, 1_000_000_000)
        assert segment1 is None  # Waiting for keyframe

        # Push keyframe to emit first segment
        segment1, _ = buffer.push_video(b"keyframe1", 1_000_000_000, 1_000_000_000, is_keyframe=True)
        assert segment1 is not None
        assert segment1.batch_number == 0

        # Continue accumulating (keyframe1 started new segment)
        # Push more data to reach threshold again
        segment2, _ = buffer.push_video(b"data2", 2_000_000_000, 1_000_000_000)
        assert segment2 is None  # Waiting for keyframe

        # Push keyframe to emit second segment
        segment2, _ = buffer.push_video(b"keyframe2", 3_000_000_000, 1_000_000_000, is_keyframe=True)
        assert segment2 is not None
        assert segment2.batch_number == 1

    def test_flush_video_returns_partial(self, tmp_path: Path) -> None:
        """Test flush_video returns partial segment."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
        )

        # Push 2 seconds (less than 6)
        buffer.push_video(b"data1", 0, 1_000_000_000)
        buffer.push_video(b"data2", 1_000_000_000, 1_000_000_000)

        # Flush
        segment, data = buffer.flush_video()

        assert segment is not None
        assert data == b"data1data2"
        assert segment.duration_ns == 2_000_000_000

    def test_flush_video_discards_too_short(self, tmp_path: Path) -> None:
        """Test flush_video discards segments < 1 second."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
        )

        # Push only 500ms
        buffer.push_video(b"short", 0, 500_000_000)

        # Flush should discard
        segment, data = buffer.flush_video()

        assert segment is None
        assert data == b""


class TestSegmentBufferAudio:
    """Tests for audio buffer accumulation."""

    def test_push_audio_returns_none_before_full(self, tmp_path: Path) -> None:
        """Test push_audio returns None until segment full."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
        )

        segment, data = buffer.push_audio(
            buffer_data=b"audio_chunk",
            pts_ns=0,
            duration_ns=1_000_000_000,
        )

        assert segment is None

    def test_push_audio_returns_segment_when_full(self, tmp_path: Path) -> None:
        """Test push_audio returns segment when duration reached."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
            segment_duration_ns=2_000_000_000,
        )

        buffer.push_audio(b"chunk1", 0, 1_000_000_000)
        segment, data = buffer.push_audio(b"chunk2", 1_000_000_000, 1_000_000_000)

        assert segment is not None
        assert isinstance(segment, AudioSegment)
        assert data == b"chunk1chunk2"
        assert segment.batch_number == 0
        assert segment.file_path.suffix == ".m4a"

    def test_flush_audio_returns_partial(self, tmp_path: Path) -> None:
        """Test flush_audio returns partial segment."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
        )

        buffer.push_audio(b"audio", 0, 2_000_000_000)

        segment, data = buffer.flush_audio()

        assert segment is not None
        assert data == b"audio"


class TestSegmentBufferReset:
    """Tests for SegmentBuffer reset."""

    def test_reset_clears_accumulators(self, tmp_path: Path) -> None:
        """Test reset clears both video and audio accumulators."""
        buffer = SegmentBuffer(
            stream_id="test",
            segment_dir=tmp_path,
        )

        buffer.push_video(b"video", 0, 1_000_000_000)
        buffer.push_audio(b"audio", 0, 1_000_000_000)

        assert buffer.video_accumulated_duration_ns == 1_000_000_000
        assert buffer.audio_accumulated_duration_ns == 1_000_000_000

        buffer.reset()

        assert buffer.video_accumulated_duration_ns == 0
        assert buffer.audio_accumulated_duration_ns == 0
        assert buffer.video_batch_number == 0
        assert buffer.audio_batch_number == 0
