"""
Comprehensive unit tests for video segment writer.

Tests MP4 segment writing functionality.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_service.models.segments import VideoSegment
from media_service.video.segment_writer import VideoSegmentWriter


@pytest.fixture
def segment_dir(tmp_path: Path) -> Path:
    """Create a temporary segment directory."""
    segment_dir = tmp_path / "segments"
    segment_dir.mkdir(parents=True)
    return segment_dir


@pytest.fixture
def video_writer(segment_dir: Path) -> VideoSegmentWriter:
    """Create a VideoSegmentWriter instance."""
    return VideoSegmentWriter(segment_dir)


@pytest.fixture
def video_segment(segment_dir: Path) -> VideoSegment:
    """Create a test video segment."""
    return VideoSegment(
        fragment_id="video-001",
        stream_id="test-stream",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,
        file_path=segment_dir / "test-stream" / "000000_video.mp4",
    )


class TestVideoSegmentWriterInit:
    """Tests for VideoSegmentWriter initialization."""

    def test_init_sets_segment_dir(self, segment_dir: Path) -> None:
        """Test segment_dir is set correctly."""
        writer = VideoSegmentWriter(segment_dir)
        assert writer.segment_dir == segment_dir


class TestVideoSegmentWriterWrite:
    """Tests for write functionality."""

    @pytest.mark.asyncio
    async def test_write_creates_file(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test write creates the file."""
        video_data = b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100

        await video_writer.write(video_segment, video_data)

        assert video_segment.file_path.exists()

    @pytest.mark.asyncio
    async def test_write_creates_directory(
        self, video_writer: VideoSegmentWriter, segment_dir: Path
    ) -> None:
        """Test write creates parent directory if needed."""
        segment = VideoSegment(
            fragment_id="video-002",
            stream_id="new-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=segment_dir / "new-stream" / "nested" / "000000_video.mp4",
        )
        video_data = b"test_video_data"

        await video_writer.write(segment, video_data)

        assert segment.file_path.parent.exists()
        assert segment.file_path.exists()

    @pytest.mark.asyncio
    async def test_write_correct_content(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test write stores correct data."""
        video_data = b"specific_video_content_12345"

        await video_writer.write(video_segment, video_data)

        assert video_segment.file_path.read_bytes() == video_data

    @pytest.mark.asyncio
    async def test_write_updates_file_size(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test write updates file_size attribute."""
        video_data = b"x" * 1000

        result = await video_writer.write(video_segment, video_data)

        assert result.file_size == 1000

    @pytest.mark.asyncio
    async def test_write_returns_segment(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test write returns the updated segment."""
        video_data = b"video_data"

        result = await video_writer.write(video_segment, video_data)

        assert result is video_segment

    @pytest.mark.asyncio
    async def test_write_large_file(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test write handles large files."""
        # Simulate a 1MB video segment
        video_data = b"x" * (1024 * 1024)

        result = await video_writer.write(video_segment, video_data)

        assert result.file_path.exists()
        assert result.file_size == 1024 * 1024


class TestVideoSegmentWriterWriteWithMux:
    """Tests for write_with_mux functionality."""

    @pytest.mark.asyncio
    async def test_write_with_mux_fallback_when_gst_unavailable(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test write_with_mux falls back to raw write when GStreamer unavailable."""
        video_data = b"raw_video_data_fallback"

        # This should fall back to raw write if GStreamer not available
        result = await video_writer.write_with_mux(video_segment, video_data)

        assert result.file_path.exists()
        # Content should be written (either muxed or raw)
        assert result.file_path.stat().st_size > 0


class TestVideoSegmentWriterDelete:
    """Tests for delete functionality."""

    @pytest.mark.asyncio
    async def test_delete_removes_file(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test delete removes the file."""
        await video_writer.write(video_segment, b"video_data")
        assert video_segment.file_path.exists()

        result = video_writer.delete(video_segment)

        assert result is True
        assert not video_segment.file_path.exists()

    def test_delete_returns_false_when_no_file(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test delete returns False when file doesn't exist."""
        # Don't write anything
        result = video_writer.delete(video_segment)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_only_target_file(
        self, video_writer: VideoSegmentWriter, segment_dir: Path
    ) -> None:
        """Test delete only removes the specified segment's file."""
        segment1 = VideoSegment(
            fragment_id="video-1", stream_id="s1", batch_number=0,
            t0_ns=0, duration_ns=6_000_000_000,
            file_path=segment_dir / "s1" / "000000_video.mp4",
        )
        segment2 = VideoSegment(
            fragment_id="video-2", stream_id="s1", batch_number=1,
            t0_ns=6_000_000_000, duration_ns=6_000_000_000,
            file_path=segment_dir / "s1" / "000001_video.mp4",
        )

        await video_writer.write(segment1, b"video1")
        await video_writer.write(segment2, b"video2")

        # Delete only segment1
        video_writer.delete(segment1)

        assert not segment1.file_path.exists()
        assert segment2.file_path.exists()


class TestVideoSegmentWriterMultipleWrites:
    """Tests for multiple segment writes."""

    @pytest.mark.asyncio
    async def test_write_multiple_segments(
        self, video_writer: VideoSegmentWriter, segment_dir: Path
    ) -> None:
        """Test writing multiple segments sequentially."""
        segments = []
        for i in range(5):
            segment = VideoSegment(
                fragment_id=f"video-{i:03d}",
                stream_id="test-stream",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=segment_dir / "test-stream" / f"{i:06d}_video.mp4",
            )
            segments.append(segment)

        for i, segment in enumerate(segments):
            await video_writer.write(segment, f"video_data_{i}".encode())

        # All files should exist
        for segment in segments:
            assert segment.file_path.exists()

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(
        self, video_writer: VideoSegmentWriter, video_segment: VideoSegment
    ) -> None:
        """Test that writing to same path overwrites."""
        original_data = b"original_video"
        new_data = b"new_video_content_longer"

        await video_writer.write(video_segment, original_data)
        await video_writer.write(video_segment, new_data)

        assert video_segment.file_path.read_bytes() == new_data
        assert video_segment.file_size == len(new_data)
