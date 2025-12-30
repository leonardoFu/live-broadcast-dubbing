"""
Comprehensive unit tests for audio segment writer.

Tests M4A segment writing functionality.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_service.audio.segment_writer import AudioSegmentWriter
from media_service.models.segments import AudioSegment


@pytest.fixture
def segment_dir(tmp_path: Path) -> Path:
    """Create a temporary segment directory."""
    segment_dir = tmp_path / "segments"
    segment_dir.mkdir(parents=True)
    return segment_dir


@pytest.fixture
def audio_writer(segment_dir: Path) -> AudioSegmentWriter:
    """Create an AudioSegmentWriter instance."""
    return AudioSegmentWriter(segment_dir)


@pytest.fixture
def audio_segment(segment_dir: Path) -> AudioSegment:
    """Create a test audio segment."""
    return AudioSegment(
        fragment_id="audio-001",
        stream_id="test-stream",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,
        file_path=segment_dir / "test-stream" / "000000_audio.m4a",
    )


class TestAudioSegmentWriterInit:
    """Tests for AudioSegmentWriter initialization."""

    def test_init_sets_segment_dir(self, segment_dir: Path) -> None:
        """Test segment_dir is set correctly."""
        writer = AudioSegmentWriter(segment_dir)
        assert writer.segment_dir == segment_dir


class TestAudioSegmentWriterWrite:
    """Tests for write functionality."""

    @pytest.mark.asyncio
    async def test_write_creates_file(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write creates the file."""
        audio_data = b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100

        await audio_writer.write(audio_segment, audio_data)

        assert audio_segment.file_path.exists()

    @pytest.mark.asyncio
    async def test_write_creates_directory(
        self, audio_writer: AudioSegmentWriter, segment_dir: Path
    ) -> None:
        """Test write creates parent directory if needed."""
        segment = AudioSegment(
            fragment_id="audio-002",
            stream_id="new-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=segment_dir / "new-stream" / "nested" / "000000_audio.m4a",
        )
        audio_data = b"test_audio_data"

        await audio_writer.write(segment, audio_data)

        assert segment.file_path.parent.exists()
        assert segment.file_path.exists()

    @pytest.mark.asyncio
    async def test_write_correct_content(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write stores correct data."""
        audio_data = b"specific_audio_content_12345"

        await audio_writer.write(audio_segment, audio_data)

        assert audio_segment.file_path.read_bytes() == audio_data

    @pytest.mark.asyncio
    async def test_write_updates_file_size(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write updates file_size attribute."""
        audio_data = b"x" * 500

        result = await audio_writer.write(audio_segment, audio_data)

        assert result.file_size == 500

    @pytest.mark.asyncio
    async def test_write_returns_segment(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write returns the updated segment."""
        audio_data = b"audio_data"

        result = await audio_writer.write(audio_segment, audio_data)

        assert result is audio_segment


class TestAudioSegmentWriterWriteWithMux:
    """Tests for write_with_mux functionality."""

    @pytest.mark.asyncio
    async def test_write_with_mux_fallback_when_gst_unavailable(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write_with_mux falls back to raw write when GStreamer unavailable."""
        audio_data = b"raw_audio_data_fallback"

        # This should fall back to raw write if GStreamer not available
        result = await audio_writer.write_with_mux(audio_segment, audio_data)

        assert result.file_path.exists()
        # Content should be written (either muxed or raw)
        assert result.file_path.stat().st_size > 0


class TestAudioSegmentWriterWriteDubbed:
    """Tests for write_dubbed functionality."""

    @pytest.mark.asyncio
    async def test_write_dubbed_creates_file(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write_dubbed creates dubbed file."""
        # First write original
        original_data = b"original_audio"
        await audio_writer.write(audio_segment, original_data)

        # Write dubbed
        dubbed_data = b"dubbed_audio_content"
        result = await audio_writer.write_dubbed(audio_segment, dubbed_data)

        assert result.dubbed_file_path is not None
        assert result.dubbed_file_path.exists()

    @pytest.mark.asyncio
    async def test_write_dubbed_correct_suffix(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write_dubbed uses correct suffix."""
        await audio_writer.write(audio_segment, b"original")
        await audio_writer.write_dubbed(audio_segment, b"dubbed")

        assert "_dubbed.m4a" in str(audio_segment.dubbed_file_path)

    @pytest.mark.asyncio
    async def test_write_dubbed_custom_suffix(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write_dubbed accepts custom suffix."""
        await audio_writer.write(audio_segment, b"original")
        await audio_writer.write_dubbed(audio_segment, b"dubbed", dubbed_suffix="_es")

        assert "_es.m4a" in str(audio_segment.dubbed_file_path)

    @pytest.mark.asyncio
    async def test_write_dubbed_correct_content(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write_dubbed stores correct content."""
        await audio_writer.write(audio_segment, b"original")
        dubbed_data = b"dubbed_audio_12345"
        await audio_writer.write_dubbed(audio_segment, dubbed_data)

        assert audio_segment.dubbed_file_path.read_bytes() == dubbed_data

    @pytest.mark.asyncio
    async def test_write_dubbed_marks_as_dubbed(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test write_dubbed sets is_dubbed flag."""
        await audio_writer.write(audio_segment, b"original")
        await audio_writer.write_dubbed(audio_segment, b"dubbed")

        assert audio_segment.is_dubbed


class TestAudioSegmentWriterDelete:
    """Tests for delete functionality."""

    @pytest.mark.asyncio
    async def test_delete_removes_original_file(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test delete removes original file."""
        await audio_writer.write(audio_segment, b"audio_data")
        assert audio_segment.file_path.exists()

        result = audio_writer.delete(audio_segment)

        assert result is True
        assert not audio_segment.file_path.exists()

    @pytest.mark.asyncio
    async def test_delete_removes_dubbed_file(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test delete removes dubbed file too."""
        await audio_writer.write(audio_segment, b"original")
        await audio_writer.write_dubbed(audio_segment, b"dubbed")
        assert audio_segment.dubbed_file_path.exists()

        result = audio_writer.delete(audio_segment)

        assert result is True
        assert not audio_segment.file_path.exists()
        assert not audio_segment.dubbed_file_path.exists()

    def test_delete_returns_false_when_no_files(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test delete returns False when no files exist."""
        # Don't write anything
        result = audio_writer.delete(audio_segment)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_handles_only_original(
        self, audio_writer: AudioSegmentWriter, audio_segment: AudioSegment
    ) -> None:
        """Test delete works with only original file."""
        await audio_writer.write(audio_segment, b"original")
        # No dubbed file

        result = audio_writer.delete(audio_segment)

        assert result is True
        assert not audio_segment.file_path.exists()
