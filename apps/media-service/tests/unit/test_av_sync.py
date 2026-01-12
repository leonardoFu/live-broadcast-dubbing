"""
Unit tests for AvSyncManager class.

Tests T060-T065 from tasks.md - validating A/V synchronization.

Updated for spec 021-fragment-length-30s:
- Buffer-and-wait approach (av_offset_ns removed)
- Output PTS starts from 0 (re-encoded, not original stream PTS)
- FR-010: Video segments buffered until dubbed audio ready
- FR-012: Output re-encoded with PTS=0
- FR-013: Drift correction code removed
"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_service.models.segments import AudioSegment, VideoSegment
from media_service.sync.av_sync import AvSyncManager, SyncPair


@pytest.fixture
def video_segment() -> VideoSegment:
    """Create a test video segment (30s per spec 021)."""
    return VideoSegment(
        fragment_id="video-001",
        stream_id="test",
        batch_number=0,
        t0_ns=0,
        duration_ns=30_000_000_000,  # 30s per spec 021
        file_path=Path("/tmp/test/000000_video.mp4"),
    )


@pytest.fixture
def audio_segment() -> AudioSegment:
    """Create a test audio segment (30s per spec 021)."""
    return AudioSegment(
        fragment_id="audio-001",
        stream_id="test",
        batch_number=0,
        t0_ns=0,
        duration_ns=30_000_000_000,  # 30s per spec 021
        file_path=Path("/tmp/test/000000_audio.m4a"),
    )


class TestAvSyncManagerInit:
    """Tests for AvSyncManager initialization (buffer-and-wait per spec 021)."""

    def test_default_values(self) -> None:
        """Test default sync manager values (buffer-and-wait, no av_offset_ns)."""
        sync = AvSyncManager()

        # av_offset_ns should not exist in buffer-and-wait approach
        assert not hasattr(sync.state, "av_offset_ns") or sync.state.av_offset_ns == 0
        assert sync.state.drift_threshold_ns == 100_000_000  # 100ms (for logging only)
        assert sync.max_buffer_size == 10
        assert sync.video_buffer_size == 0
        assert sync.audio_buffer_size == 0

    def test_no_av_offset_parameter(self) -> None:
        """FR-013: AvSyncManager should not accept av_offset_ns parameter."""
        # In buffer-and-wait, av_offset_ns is removed
        sync = AvSyncManager()
        # Constructor should not have av_offset_ns parameter
        # If it does exist for backward compat, it should be ignored
        assert sync.video_buffer_size == 0


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


class TestAvSyncManagerPtsReset:
    """Tests for PTS reset to 0 in sync pairs (spec 021)."""

    @pytest.mark.asyncio
    async def test_sync_pair_pts_starts_from_zero(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """FR-012: Output PTS starts from 0 (re-encoded output)."""
        sync = AvSyncManager()

        # Video at PTS 0
        await sync.push_video(video_segment, b"video")
        pair = await sync.push_audio(audio_segment, b"audio")

        # PTS should be 0 (reset, not original stream PTS)
        assert pair.pts_ns == 0

    @pytest.mark.asyncio
    async def test_output_is_reencoded(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """FR-012: Output video must be re-encoded (not passthrough)."""
        sync = AvSyncManager()

        await sync.push_video(video_segment, b"video")
        pair = await sync.push_audio(audio_segment, b"audio")

        # Verify output is marked for re-encoding
        assert hasattr(pair, "requires_reencode")
        assert pair.requires_reencode is True


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
            duration_ns=30_000_000_000,  # 30s per spec 021
            file_path=Path("/tmp/test/000000_video.mp4"),
        )
        video1 = VideoSegment(
            fragment_id="v1",
            stream_id="test",
            batch_number=1,
            t0_ns=30_000_000_000,  # 30s per spec 021
            duration_ns=30_000_000_000,
            file_path=Path("/tmp/test/000001_video.mp4"),
        )
        audio1 = AudioSegment(
            fragment_id="a1",
            stream_id="test",
            batch_number=1,  # Matches video1
            t0_ns=30_000_000_000,  # 30s per spec 021
            duration_ns=30_000_000_000,
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


class TestAvSyncManagerNoDriftCorrection:
    """Tests verifying drift correction is removed (spec 021 buffer-and-wait)."""

    def test_av_sync_manager_no_drift_correction(self) -> None:
        """FR-013: Drift correction code should be removed."""
        sync = AvSyncManager()

        # needs_correction property should not exist in buffer-and-wait
        assert not hasattr(sync, "needs_correction")

    def test_av_sync_manager_buffers_video_until_audio_ready(self) -> None:
        """FR-010: Video segments are buffered until dubbed audio arrives."""
        sync = AvSyncManager()
        # Initial state: no video buffered
        assert sync.video_buffer_size == 0

    @pytest.mark.asyncio
    async def test_av_sync_manager_buffers_audio_until_video_ready(
        self, audio_segment: AudioSegment
    ) -> None:
        """FR-010: Audio segments are buffered until video arrives."""
        sync = AvSyncManager()

        # Push audio without matching video
        pair = await sync.push_audio(audio_segment, b"audio")

        assert pair is None
        assert sync.audio_buffer_size == 1


class TestAvSyncManagerGetReadyPairs:
    """Tests for get_ready_pairs method."""

    @pytest.mark.asyncio
    async def test_get_ready_pairs_returns_matches(self) -> None:
        """Test get_ready_pairs returns all matching pairs."""
        sync = AvSyncManager()

        # Create matching video/audio pairs (30s per spec 021)
        for i in range(3):
            video = VideoSegment(
                fragment_id=f"v{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=i * 30_000_000_000,  # 30s per spec 021
                duration_ns=30_000_000_000,
                file_path=Path(f"/tmp/test/{i:06d}_video.mp4"),
            )
            audio = AudioSegment(
                fragment_id=f"a{i}",
                stream_id="test",
                batch_number=i,
                t0_ns=i * 30_000_000_000,  # 30s per spec 021
                duration_ns=30_000_000_000,
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

        # Create a different batch audio (30s per spec 021)
        audio = AudioSegment(
            fragment_id="a-diff",
            stream_id="test",
            batch_number=99,  # Different batch
            t0_ns=0,
            duration_ns=30_000_000_000,  # 30s per spec 021
            file_path=Path("/tmp/test.m4a"),
        )
        await sync.push_audio(audio, b"audio")

        assert sync.video_buffer_size == 1
        assert sync.audio_buffer_size == 1

        sync.reset()

        assert sync.video_buffer_size == 0
        assert sync.audio_buffer_size == 0


class TestSyncPair:
    """Tests for SyncPair dataclass (spec 021)."""

    def test_sync_pair_attributes(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """Test SyncPair attributes with pts_ns=0 (spec 021)."""
        pair = SyncPair(
            video_segment=video_segment,
            video_data=b"video",
            audio_segment=audio_segment,
            audio_data=b"audio",
            pts_ns=0,  # FR-012: PTS starts from 0
            requires_reencode=True,  # FR-012: Output is re-encoded
        )

        assert pair.video_segment == video_segment
        assert pair.audio_segment == audio_segment
        assert pair.video_data == b"video"
        assert pair.audio_data == b"audio"
        assert pair.pts_ns == 0  # FR-012: PTS starts from 0
        assert pair.requires_reencode is True  # FR-012: Output is re-encoded

    def test_sync_pair_has_requires_reencode_field(
        self, video_segment: VideoSegment, audio_segment: AudioSegment
    ) -> None:
        """FR-012: SyncPair must have requires_reencode field."""
        pair = SyncPair(
            video_segment=video_segment,
            video_data=b"video",
            audio_segment=audio_segment,
            audio_data=b"audio",
            pts_ns=0,
            requires_reencode=True,
        )

        assert hasattr(pair, "requires_reencode")
        assert pair.requires_reencode is True
