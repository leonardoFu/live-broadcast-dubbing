"""
Unit tests for AvSyncManager class.

Tests T060-T065 from tasks.md - validating A/V synchronization.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_service.models.segments import AudioSegment, VideoSegment
from media_service.sync.av_sync import AvSyncManager, SyncPair


@pytest.fixture
def video_segment() -> VideoSegment:
    """Create a test video segment."""
    return VideoSegment(
        fragment_id="video-001",
        stream_id="test",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,
        file_path=Path("/tmp/test/000000_video.mp4"),
    )


@pytest.fixture
def audio_segment() -> AudioSegment:
    """Create a test audio segment."""
    return AudioSegment(
        fragment_id="audio-001",
        stream_id="test",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,
        file_path=Path("/tmp/test/000000_audio.m4a"),
    )


class TestAvSyncManagerInit:
    """Tests for AvSyncManager initialization."""

    def test_default_values(self) -> None:
        """Test default sync manager values."""
        sync = AvSyncManager()

        assert sync.state.av_offset_ns == 6_000_000_000  # 6 seconds
        assert sync.state.drift_threshold_ns == 120_000_000  # 120ms
        assert sync.max_buffer_size == 10
        assert sync.video_buffer_size == 0
        assert sync.audio_buffer_size == 0

    def test_custom_offset(self) -> None:
        """Test custom A/V offset."""
        sync = AvSyncManager(av_offset_ns=3_000_000_000)

        assert sync.state.av_offset_ns == 3_000_000_000


class TestAvSyncManagerPushVideo:
    """Tests for push_video method."""

    @pytest.mark.asyncio
    async def test_push_video_buffers_when_no_audio(self, video_segment: VideoSegment) -> None:
        """Test push_video buffers video when no matching audio."""
        sync = AvSyncManager()

        pair = await sync.push_video(video_segment, b"video_data")

        assert pair is None
        assert sync.video_buffer_size == 1

    @pytest.mark.asyncio
    async def test_push_video_returns_pair_when_audio_ready(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """Test push_video returns pair when matching audio already buffered."""
        sync = AvSyncManager()

        # First buffer audio
        await sync.push_audio(audio_segment, b"audio_data")
        assert sync.audio_buffer_size == 1

        # Then push video - should pair
        pair = await sync.push_video(video_segment, b"video_data")

        assert pair is not None
        assert isinstance(pair, SyncPair)
        assert pair.video_segment == video_segment
        assert pair.audio_segment == audio_segment
        assert pair.video_data == b"video_data"
        assert pair.audio_data == b"audio_data"
        assert sync.video_buffer_size == 0
        assert sync.audio_buffer_size == 0


class TestAvSyncManagerPushAudio:
    """Tests for push_audio method."""

    @pytest.mark.asyncio
    async def test_push_audio_buffers_when_no_video(self, audio_segment: AudioSegment) -> None:
        """Test push_audio buffers audio when no matching video."""
        sync = AvSyncManager()

        pair = await sync.push_audio(audio_segment, b"audio_data")

        assert pair is None
        assert sync.audio_buffer_size == 1

    @pytest.mark.asyncio
    async def test_push_audio_returns_pair_when_video_ready(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """Test push_audio returns pair when matching video already buffered."""
        sync = AvSyncManager()

        # First buffer video
        await sync.push_video(video_segment, b"video_data")
        assert sync.video_buffer_size == 1

        # Then push audio - should pair
        pair = await sync.push_audio(audio_segment, b"audio_data")

        assert pair is not None
        assert pair.video_segment == video_segment
        assert pair.audio_segment == audio_segment


class TestAvSyncManagerPtsAdjustment:
    """Tests for PTS adjustment in sync pairs."""

    @pytest.mark.asyncio
    async def test_pair_pts_includes_offset(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """Test that sync pair PTS includes A/V offset."""
        sync = AvSyncManager(av_offset_ns=6_000_000_000)  # 6 seconds

        # Video at PTS 0
        await sync.push_video(video_segment, b"video")
        pair = await sync.push_audio(audio_segment, b"audio")

        # PTS should be original (0) + offset (6s)
        assert pair.pts_ns == 6_000_000_000


class TestAvSyncManagerBatchMatching:
    """Tests for batch number matching."""

    @pytest.mark.asyncio
    async def test_matches_by_batch_number(self) -> None:
        """Test segments are matched by batch_number."""
        sync = AvSyncManager()

        video0 = VideoSegment(
            fragment_id="v0",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/000000_video.mp4"),
        )
        video1 = VideoSegment(
            fragment_id="v1",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/000001_video.mp4"),
        )
        audio1 = AudioSegment(
            fragment_id="a1",
            stream_id="test",
            batch_number=1,  # Matches video1
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test/000001_audio.m4a"),
        )

        # Buffer both videos
        await sync.push_video(video0, b"v0")
        await sync.push_video(video1, b"v1")
        assert sync.video_buffer_size == 2

        # Push audio for batch 1 - should match video1, not video0
        pair = await sync.push_audio(audio1, b"a1")

        assert pair is not None
        assert pair.video_segment.batch_number == 1
        assert pair.audio_segment.batch_number == 1
        assert sync.video_buffer_size == 1  # video0 still buffered


class TestAvSyncManagerDriftDetection:
    """Tests for drift detection and correction."""

    @pytest.mark.asyncio
    async def test_needs_correction_when_drift_exceeds_threshold(self) -> None:
        """Test needs_correction returns True when drift exceeds threshold."""
        sync = AvSyncManager(drift_threshold_ns=100_000_000)  # 100ms

        # Manually set drift
        sync.state.sync_delta_ns = 150_000_000  # 150ms

        assert sync.needs_correction is True

    @pytest.mark.asyncio
    async def test_needs_correction_false_when_within_threshold(self) -> None:
        """Test needs_correction returns False when within threshold."""
        sync = AvSyncManager(drift_threshold_ns=100_000_000)

        sync.state.sync_delta_ns = 50_000_000  # 50ms

        assert sync.needs_correction is False


class TestAvSyncManagerGetReadyPairs:
    """Tests for get_ready_pairs method."""

    @pytest.mark.asyncio
    async def test_get_ready_pairs_returns_matches(self) -> None:
        """Test get_ready_pairs returns all matching pairs."""
        sync = AvSyncManager()

        # Create matching video/audio pairs
        for i in range(3):
            video = VideoSegment(
                fragment_id=f"v{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/test/{i:06d}_video.mp4"),
            )
            audio = AudioSegment(
                fragment_id=f"a{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/test/{i:06d}_audio.m4a"),
            )

            await sync.push_video(video, f"v{i}".encode())
            await sync.push_audio(audio, f"a{i}".encode())

        # All should be buffered
        assert sync.video_buffer_size == 0  # Already paired on push
        assert sync.audio_buffer_size == 0


class TestAvSyncManagerReset:
    """Tests for reset method."""

    @pytest.mark.asyncio
    async def test_reset_clears_buffers(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """Test reset clears all buffers."""
        sync = AvSyncManager()

        await sync.push_video(video_segment, b"video")

        # Create a different batch audio
        audio = AudioSegment(
            fragment_id="a-diff",
            stream_id="test",
            batch_number=99,  # Different batch
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/test.m4a"),
        )
        await sync.push_audio(audio, b"audio")

        assert sync.video_buffer_size == 1
        assert sync.audio_buffer_size == 1

        sync.reset()

        assert sync.video_buffer_size == 0
        assert sync.audio_buffer_size == 0


class TestSyncPair:
    """Tests for SyncPair dataclass."""

    def test_sync_pair_attributes(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """Test SyncPair attributes."""
        pair = SyncPair(
            video_segment=video_segment,
            video_data=b"video",
            audio_segment=audio_segment,
            audio_data=b"audio",
            pts_ns=6_000_000_000,
        )

        assert pair.video_segment == video_segment
        assert pair.audio_segment == audio_segment
        assert pair.video_data == b"video"
        assert pair.audio_data == b"audio"
        assert pair.pts_ns == 6_000_000_000
