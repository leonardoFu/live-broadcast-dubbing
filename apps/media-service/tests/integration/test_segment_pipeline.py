"""
Integration tests for segment pipeline.

Tests the complete flow from segment creation through writing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_service.audio.segment_writer import AudioSegmentWriter
from media_service.buffer.segment_buffer import SegmentBuffer
from media_service.models.segments import AudioSegment, VideoSegment
from media_service.sync.av_sync import AvSyncManager
from media_service.video.segment_writer import VideoSegmentWriter


@pytest.fixture
def segment_dir(tmp_path: Path) -> Path:
    """Create temporary segment directory."""
    segment_dir = tmp_path / "segments"
    segment_dir.mkdir(parents=True)
    return segment_dir


class TestSegmentBufferToWriterIntegration:
    """Integration tests for SegmentBuffer -> SegmentWriter flow."""

    @pytest.mark.asyncio
    async def test_video_segment_buffer_to_writer(self, segment_dir: Path) -> None:
        """Test complete video segment flow from buffer to disk."""
        # Create buffer and writer
        _buffer = SegmentBuffer(
            stream_id="integration-test",
            segment_dir=segment_dir,
        )
        writer = VideoSegmentWriter(segment_dir)

        # Simulate buffer creating a video segment
        video_segment = VideoSegment(
            fragment_id="test-video-001",
            stream_id="integration-test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=segment_dir / "integration-test" / "000000_video.mp4",
        )

        # Simulate video data
        video_data = b"\x00\x00\x00\x1cftyp" + b"\x00" * 10000

        # Write segment
        result = await writer.write(video_segment, video_data)

        # Verify
        assert result.file_path.exists()
        assert result.file_size == len(video_data)
        assert result.file_path.read_bytes() == video_data

    @pytest.mark.asyncio
    async def test_audio_segment_buffer_to_writer(self, segment_dir: Path) -> None:
        """Test complete audio segment flow from buffer to disk."""
        # Create buffer and writer
        _buffer = SegmentBuffer(
            stream_id="integration-test",
            segment_dir=segment_dir,
        )
        writer = AudioSegmentWriter(segment_dir)

        # Simulate buffer creating an audio segment
        audio_segment = AudioSegment(
            fragment_id="test-audio-001",
            stream_id="integration-test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=segment_dir / "integration-test" / "000000_audio.m4a",
        )

        # Simulate audio data
        audio_data = b"\x00\x00\x00\x1cftyp" + b"\x00" * 5000

        # Write segment
        result = await writer.write(audio_segment, audio_data)

        # Verify
        assert result.file_path.exists()
        assert result.file_size == len(audio_data)
        assert result.file_path.read_bytes() == audio_data


class TestAvSyncIntegration:
    """Integration tests for A/V synchronization with segment writers."""

    @pytest.mark.asyncio
    async def test_av_sync_with_writers(self, segment_dir: Path) -> None:
        """Test A/V sync integration with segment writers."""
        # Create components
        video_writer = VideoSegmentWriter(segment_dir)
        audio_writer = AudioSegmentWriter(segment_dir)
        av_sync = AvSyncManager(
            av_offset_ns=6_000_000_000,
            drift_threshold_ns=120_000_000,
            max_buffer_size=10,
        )

        # Create and write video segment
        video_segment = VideoSegment(
            fragment_id="sync-video-001",
            stream_id="sync-test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=segment_dir / "sync-test" / "000000_video.mp4",
        )
        video_data = b"VIDEO_DATA_" + b"\x00" * 1000
        await video_writer.write(video_segment, video_data)

        # Create and write audio segment
        audio_segment = AudioSegment(
            fragment_id="sync-audio-001",
            stream_id="sync-test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=segment_dir / "sync-test" / "000000_audio.m4a",
        )
        audio_data = b"AUDIO_DATA_" + b"\x00" * 500
        await audio_writer.write(audio_segment, audio_data)

        # Push to A/V sync
        result1 = await av_sync.push_video(video_segment, video_data)
        assert result1 is None  # Waiting for audio

        result2 = await av_sync.push_audio(audio_segment, audio_data)
        assert result2 is not None  # Pair created

        # Verify pair
        assert result2.video_segment == video_segment
        assert result2.audio_segment == audio_segment
        assert result2.video_data == video_data
        assert result2.audio_data == audio_data

    @pytest.mark.asyncio
    async def test_multiple_segment_sync(self, segment_dir: Path) -> None:
        """Test A/V sync with multiple segments."""
        video_writer = VideoSegmentWriter(segment_dir)
        audio_writer = AudioSegmentWriter(segment_dir)
        av_sync = AvSyncManager(max_buffer_size=10)

        # Create 5 segment pairs
        for i in range(5):
            video_segment = VideoSegment(
                fragment_id=f"video-{i:03d}",
                stream_id="multi-test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=segment_dir / "multi-test" / f"{i:06d}_video.mp4",
            )
            audio_segment = AudioSegment(
                fragment_id=f"audio-{i:03d}",
                stream_id="multi-test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=segment_dir / "multi-test" / f"{i:06d}_audio.m4a",
            )

            video_data = f"video_{i}".encode() + b"\x00" * 100
            audio_data = f"audio_{i}".encode() + b"\x00" * 50

            await video_writer.write(video_segment, video_data)
            await audio_writer.write(audio_segment, audio_data)

            # Push video then audio
            await av_sync.push_video(video_segment, video_data)
            pair = await av_sync.push_audio(audio_segment, audio_data)

            assert pair is not None
            assert pair.video_segment.batch_number == i
            assert pair.audio_segment.batch_number == i

        # Buffers should be empty
        assert av_sync.video_buffer_size == 0
        assert av_sync.audio_buffer_size == 0


class TestDubbedAudioIntegration:
    """Integration tests for dubbed audio flow."""

    @pytest.mark.asyncio
    async def test_dubbed_audio_flow(self, segment_dir: Path) -> None:
        """Test complete dubbed audio flow."""
        audio_writer = AudioSegmentWriter(segment_dir)
        av_sync = AvSyncManager()

        # Create original audio segment
        audio_segment = AudioSegment(
            fragment_id="dub-audio-001",
            stream_id="dub-test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=segment_dir / "dub-test" / "000000_audio.m4a",
        )

        # Write original
        original_data = b"ORIGINAL_AUDIO_DATA"
        await audio_writer.write(audio_segment, original_data)

        # Simulate STS response - write dubbed audio
        dubbed_data = b"DUBBED_AUDIO_DATA_ES"
        await audio_writer.write_dubbed(audio_segment, dubbed_data)

        # Verify both files exist
        assert audio_segment.file_path.exists()
        assert audio_segment.dubbed_file_path is not None
        assert audio_segment.dubbed_file_path.exists()
        assert audio_segment.is_dubbed

        # Read back data
        assert audio_segment.file_path.read_bytes() == original_data
        assert audio_segment.dubbed_file_path.read_bytes() == dubbed_data

        # Create video segment
        video_segment = VideoSegment(
            fragment_id="dub-video-001",
            stream_id="dub-test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=segment_dir / "dub-test" / "000000_video.mp4",
        )
        video_data = b"VIDEO_DATA"

        # Push to A/V sync with dubbed audio
        await av_sync.push_video(video_segment, video_data)
        pair = await av_sync.push_audio(audio_segment, dubbed_data)

        assert pair is not None
        assert pair.audio_segment.is_dubbed
        assert pair.audio_data == dubbed_data
