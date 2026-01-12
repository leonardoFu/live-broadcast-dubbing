"""
Unit tests for VideoSegment and AudioSegment data models.

Tests T012 and T013 from tasks.md - validating segment data models.

Updated for spec 021-fragment-length-30s:
- Segment duration changed from 6s to 30s
- FR-001: VideoSegment.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000
- FR-002: AudioSegment.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from media_service.models.segments import AudioSegment, VideoSegment


class TestVideoSegment:
    """Tests for VideoSegment data model (T012)."""

    def test_create_video_segment_generates_uuid(self, tmp_path: Path) -> None:
        """Test that create() generates a valid UUID for fragment_id."""
        segment = VideoSegment.create(
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            segment_dir=tmp_path,
        )

        # Verify fragment_id is a valid UUID
        assert segment.fragment_id is not None
        UUID(segment.fragment_id)  # Raises if invalid

    def test_create_video_segment_correct_path(self, tmp_path: Path) -> None:
        """Test that create() generates correct file path pattern."""
        segment = VideoSegment.create(
            stream_id="my-stream",
            batch_number=5,
            t0_ns=0,
            duration_ns=6_000_000_000,
            segment_dir=tmp_path,
        )

        expected_path = tmp_path / "my-stream" / "000005_video.mp4"
        assert segment.file_path == expected_path

    def test_create_video_segment_batch_number_padding(self, tmp_path: Path) -> None:
        """Test that batch number is zero-padded to 6 digits."""
        segment = VideoSegment.create(
            stream_id="stream",
            batch_number=123,
            t0_ns=0,
            duration_ns=6_000_000_000,
            segment_dir=tmp_path,
        )

        assert segment.file_path.name == "000123_video.mp4"

    def test_duration_seconds_property(self) -> None:
        """Test duration_seconds calculation."""
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,  # 6 seconds
            file_path=Path("/tmp/test.mp4"),
        )

        assert segment.duration_seconds == 6.0

    def test_duration_ms_property(self) -> None:
        """Test duration_ms calculation."""
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_500_000_000,  # 6.5 seconds
            file_path=Path("/tmp/test.mp4"),
        )

        assert segment.duration_ms == 6500

    def test_exists_property_file_not_exists(self, tmp_path: Path) -> None:
        """Test exists property when file doesn't exist."""
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_path / "nonexistent.mp4",
        )

        assert segment.exists is False

    def test_exists_property_file_exists(self, tmp_path: Path) -> None:
        """Test exists property when file exists."""
        file_path = tmp_path / "test.mp4"
        file_path.write_bytes(b"test data")

        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=file_path,
        )

        assert segment.exists is True

    def test_is_valid_duration_full_segment(self) -> None:
        """Test is_valid_duration for full 30-second segment (spec 021)."""
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=30_000_000_000,  # Exactly 30s (spec 021)
            file_path=Path("/tmp/test.mp4"),
        )

        assert segment.is_valid_duration() is True

    def test_is_valid_duration_with_tolerance(self) -> None:
        """Test is_valid_duration within 100ms tolerance (spec 021)."""
        # 30s - 50ms = 29.95s (within tolerance)
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=29_950_000_000,
            file_path=Path("/tmp/test.mp4"),
        )

        assert segment.is_valid_duration() is True

        # 30s + 50ms = 30.05s (within tolerance)
        segment.duration_ns = 30_050_000_000
        assert segment.is_valid_duration() is True

    def test_is_valid_duration_outside_tolerance(self) -> None:
        """Test is_valid_duration outside tolerance (spec 021)."""
        # 29s (too short for full 30s segment)
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=29_000_000_000,
            file_path=Path("/tmp/test.mp4"),
        )

        assert segment.is_valid_duration() is False

    def test_video_segment_duration_30s(self) -> None:
        """FR-001: VideoSegment.DEFAULT_SEGMENT_DURATION_NS is 30_000_000_000."""
        assert VideoSegment.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000

    def test_is_valid_duration_partial_segment(self) -> None:
        """Test is_valid_duration for partial segments (EOS)."""
        # 2s partial segment (valid when allow_partial=True)
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=2_000_000_000,
            file_path=Path("/tmp/test.mp4"),
        )

        assert segment.is_valid_duration(allow_partial=False) is False
        assert segment.is_valid_duration(allow_partial=True) is True

    def test_is_valid_duration_too_short_partial(self) -> None:
        """Test that partial segments < 1s are invalid."""
        # 500ms (too short even for partial)
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=500_000_000,
            file_path=Path("/tmp/test.mp4"),
        )

        assert segment.is_valid_duration(allow_partial=True) is False

    def test_preserves_t0_ns(self) -> None:
        """Test that t0_ns (PTS) is preserved correctly."""
        t0_ns = 1_234_567_890_123
        segment = VideoSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=t0_ns,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test.mp4"),
        )

        assert segment.t0_ns == t0_ns


class TestAudioSegment:
    """Tests for AudioSegment data model (T013)."""

    def test_create_audio_segment_generates_uuid(self, tmp_path: Path) -> None:
        """Test that create() generates a valid UUID for fragment_id."""
        segment = AudioSegment.create(
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            segment_dir=tmp_path,
        )

        # Verify fragment_id is a valid UUID
        assert segment.fragment_id is not None
        UUID(segment.fragment_id)  # Raises if invalid

    def test_create_audio_segment_correct_path(self, tmp_path: Path) -> None:
        """Test that create() generates correct M4A file path pattern."""
        segment = AudioSegment.create(
            stream_id="my-stream",
            batch_number=7,
            t0_ns=0,
            duration_ns=6_000_000_000,
            segment_dir=tmp_path,
        )

        expected_path = tmp_path / "my-stream" / "000007_audio.m4a"
        assert segment.file_path == expected_path

    def test_create_audio_segment_batch_number_padding(self, tmp_path: Path) -> None:
        """Test that batch number is zero-padded to 6 digits."""
        segment = AudioSegment.create(
            stream_id="stream",
            batch_number=42,
            t0_ns=0,
            duration_ns=6_000_000_000,
            segment_dir=tmp_path,
        )

        assert segment.file_path.name == "000042_audio.m4a"

    def test_duration_seconds_property(self) -> None:
        """Test duration_seconds calculation."""
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,  # 6 seconds
            file_path=Path("/tmp/test.m4a"),
        )

        assert segment.duration_seconds == 6.0

    def test_duration_ms_property(self) -> None:
        """Test duration_ms calculation."""
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_500_000_000,  # 6.5 seconds
            file_path=Path("/tmp/test.m4a"),
        )

        assert segment.duration_ms == 6500

    def test_exists_property_file_not_exists(self, tmp_path: Path) -> None:
        """Test exists property when file doesn't exist."""
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_path / "nonexistent.m4a",
        )

        assert segment.exists is False

    def test_exists_property_file_exists(self, tmp_path: Path) -> None:
        """Test exists property when file exists."""
        file_path = tmp_path / "test.m4a"
        file_path.write_bytes(b"test m4a data")

        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=file_path,
        )

        assert segment.exists is True

    def test_get_m4a_data_file_exists(self, tmp_path: Path) -> None:
        """Test get_m4a_data returns file contents."""
        file_path = tmp_path / "test.m4a"
        test_data = b"test m4a audio data"
        file_path.write_bytes(test_data)

        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=file_path,
        )

        assert segment.get_m4a_data() == test_data

    def test_get_m4a_data_file_not_exists(self, tmp_path: Path) -> None:
        """Test get_m4a_data returns empty bytes if file doesn't exist."""
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_path / "nonexistent.m4a",
        )

        assert segment.get_m4a_data() == b""

    def test_set_dubbed(self, tmp_path: Path) -> None:
        """Test set_dubbed marks segment as dubbed."""
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_path / "original.m4a",
        )

        assert segment.is_dubbed is False
        assert segment.dubbed_file_path is None

        dubbed_path = tmp_path / "dubbed.m4a"
        segment.set_dubbed(dubbed_path)

        assert segment.is_dubbed is True
        assert segment.dubbed_file_path == dubbed_path

    def test_output_file_path_not_dubbed(self, tmp_path: Path) -> None:
        """Test output_file_path returns original when not dubbed."""
        original_path = tmp_path / "original.m4a"
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=original_path,
        )

        assert segment.output_file_path == original_path

    def test_output_file_path_dubbed(self, tmp_path: Path) -> None:
        """Test output_file_path returns dubbed path when dubbed."""
        original_path = tmp_path / "original.m4a"
        dubbed_path = tmp_path / "dubbed.m4a"

        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=original_path,
        )
        segment.set_dubbed(dubbed_path)

        assert segment.output_file_path == dubbed_path

    def test_is_valid_duration_full_segment(self) -> None:
        """Test is_valid_duration for full 30-second segment (spec 021)."""
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=30_000_000_000,  # 30 seconds (spec 021)
            file_path=Path("/tmp/test.m4a"),
        )

        assert segment.is_valid_duration() is True

    def test_is_valid_duration_partial_segment(self) -> None:
        """Test is_valid_duration for partial segments (EOS)."""
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=3_000_000_000,  # 3 seconds
            file_path=Path("/tmp/test.m4a"),
        )

        assert segment.is_valid_duration(allow_partial=False) is False
        assert segment.is_valid_duration(allow_partial=True) is True

    def test_audio_segment_duration_30s(self) -> None:
        """FR-002: AudioSegment.DEFAULT_SEGMENT_DURATION_NS is 30_000_000_000."""
        assert AudioSegment.DEFAULT_SEGMENT_DURATION_NS == 30_000_000_000

    def test_preserves_t0_ns(self) -> None:
        """Test that t0_ns (PTS) is preserved correctly."""
        t0_ns = 9_876_543_210_987
        segment = AudioSegment(
            fragment_id="test-id",
            stream_id="test",
            batch_number=0,
            t0_ns=t0_ns,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test.m4a"),
        )

        assert segment.t0_ns == t0_ns

    def test_increments_batch_number(self, tmp_path: Path) -> None:
        """Test that batch numbers increment correctly."""
        segments = []
        for i in range(3):
            segment = AudioSegment.create(
                stream_id="test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                segment_dir=tmp_path,
            )
            segments.append(segment)

        assert segments[0].batch_number == 0
        assert segments[1].batch_number == 1
        assert segments[2].batch_number == 2

        # Verify file paths have incrementing batch numbers
        assert "000000_audio.m4a" in str(segments[0].file_path)
        assert "000001_audio.m4a" in str(segments[1].file_path)
        assert "000002_audio.m4a" in str(segments[2].file_path)
