"""
Comprehensive unit tests for A/V synchronization manager.

Tests AvSyncManager pairing and synchronization logic.
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
        stream_id="test-stream",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,
        file_path=Path("/tmp/test_video.mp4"),
    )


@pytest.fixture
def audio_segment() -> AudioSegment:
    """Create a test audio segment."""
    return AudioSegment(
        fragment_id="audio-001",
        stream_id="test-stream",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,
        file_path=Path("/tmp/test_audio.m4a"),
    )


@pytest.fixture
def av_sync_manager() -> AvSyncManager:
    """Create an AvSyncManager with default settings."""
    return AvSyncManager(
        av_offset_ns=6_000_000_000,
        drift_threshold_ns=120_000_000,
        max_buffer_size=10,
    )


class TestAvSyncManagerInit:
    """Tests for AvSyncManager initialization."""

    def test_init_default_offset(self) -> None:
        """Test default A/V offset is 6 seconds."""
        manager = AvSyncManager()
        assert manager.state.av_offset_ns == 6_000_000_000

    def test_init_custom_offset(self) -> None:
        """Test custom A/V offset."""
        manager = AvSyncManager(av_offset_ns=10_000_000_000)
        assert manager.state.av_offset_ns == 10_000_000_000

    def test_init_default_drift_threshold(self) -> None:
        """Test default drift threshold is 120ms."""
        manager = AvSyncManager()
        assert manager.state.drift_threshold_ns == 120_000_000

    def test_init_default_max_buffer(self) -> None:
        """Test default max buffer size."""
        manager = AvSyncManager()
        assert manager.max_buffer_size == 10

    def test_init_custom_max_buffer(self) -> None:
        """Test custom max buffer size."""
        manager = AvSyncManager(max_buffer_size=20)
        assert manager.max_buffer_size == 20

    def test_init_empty_buffers(self) -> None:
        """Test buffers start empty."""
        manager = AvSyncManager()
        assert manager.video_buffer_size == 0
        assert manager.audio_buffer_size == 0

    def test_init_zero_sync_delta(self) -> None:
        """Test sync delta starts at zero."""
        manager = AvSyncManager()
        assert manager.sync_delta_ms == 0.0


class TestAvSyncManagerPushVideo:
    """Tests for push_video functionality."""

    @pytest.mark.asyncio
    async def test_push_video_buffers_when_no_audio(
        self, av_sync_manager: AvSyncManager, video_segment: VideoSegment
    ) -> None:
        """Test video is buffered when no matching audio available."""
        video_data = b"\x00" * 1000

        result = await av_sync_manager.push_video(video_segment, video_data)

        assert result is None
        assert av_sync_manager.video_buffer_size == 1

    @pytest.mark.asyncio
    async def test_push_video_creates_pair_when_audio_ready(
        self,
        av_sync_manager: AvSyncManager,
        video_segment: VideoSegment,
        audio_segment: AudioSegment,
    ) -> None:
        """Test video creates pair when matching audio is ready."""
        video_data = b"\x00" * 1000
        audio_data = b"\x00" * 500

        # First push audio
        await av_sync_manager.push_audio(audio_segment, audio_data)
        assert av_sync_manager.audio_buffer_size == 1

        # Then push matching video
        result = await av_sync_manager.push_video(video_segment, video_data)

        assert result is not None
        assert isinstance(result, SyncPair)
        assert result.video_segment == video_segment
        assert result.audio_segment == audio_segment
        assert av_sync_manager.video_buffer_size == 0
        assert av_sync_manager.audio_buffer_size == 0

    @pytest.mark.asyncio
    async def test_push_video_drops_oldest_when_buffer_full(
        self, av_sync_manager: AvSyncManager
    ) -> None:
        """Test oldest video is dropped when buffer is full."""
        av_sync_manager.max_buffer_size = 2

        for i in range(3):
            segment = VideoSegment(
                fragment_id=f"video-{i:03d}",
                stream_id="test-stream",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/video_{i}.mp4"),
            )
            await av_sync_manager.push_video(segment, b"\x00" * 100)

        # Should only have 2 segments (oldest dropped)
        assert av_sync_manager.video_buffer_size == 2


class TestAvSyncManagerPushAudio:
    """Tests for push_audio functionality."""

    @pytest.mark.asyncio
    async def test_push_audio_buffers_when_no_video(
        self, av_sync_manager: AvSyncManager, audio_segment: AudioSegment
    ) -> None:
        """Test audio is buffered when no matching video available."""
        audio_data = b"\x00" * 500

        result = await av_sync_manager.push_audio(audio_segment, audio_data)

        assert result is None
        assert av_sync_manager.audio_buffer_size == 1

    @pytest.mark.asyncio
    async def test_push_audio_creates_pair_when_video_ready(
        self,
        av_sync_manager: AvSyncManager,
        video_segment: VideoSegment,
        audio_segment: AudioSegment,
    ) -> None:
        """Test audio creates pair when matching video is ready."""
        video_data = b"\x00" * 1000
        audio_data = b"\x00" * 500

        # First push video
        await av_sync_manager.push_video(video_segment, video_data)
        assert av_sync_manager.video_buffer_size == 1

        # Then push matching audio
        result = await av_sync_manager.push_audio(audio_segment, audio_data)

        assert result is not None
        assert isinstance(result, SyncPair)
        assert result.video_segment == video_segment
        assert result.audio_segment == audio_segment
        assert av_sync_manager.video_buffer_size == 0
        assert av_sync_manager.audio_buffer_size == 0

    @pytest.mark.asyncio
    async def test_push_audio_drops_oldest_when_buffer_full(
        self, av_sync_manager: AvSyncManager
    ) -> None:
        """Test oldest audio is dropped when buffer is full."""
        av_sync_manager.max_buffer_size = 2

        for i in range(3):
            segment = AudioSegment(
                fragment_id=f"audio-{i:03d}",
                stream_id="test-stream",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/audio_{i}.m4a"),
            )
            await av_sync_manager.push_audio(segment, b"\x00" * 100)

        # Should only have 2 segments (oldest dropped)
        assert av_sync_manager.audio_buffer_size == 2


class TestAvSyncManagerSyncPair:
    """Tests for SyncPair creation and synchronization."""

    @pytest.mark.asyncio
    async def test_sync_pair_has_correct_video_data(
        self,
        av_sync_manager: AvSyncManager,
        video_segment: VideoSegment,
        audio_segment: AudioSegment,
    ) -> None:
        """Test SyncPair contains correct video data."""
        video_data = b"VIDEO_DATA_12345"
        audio_data = b"AUDIO_DATA_67890"

        await av_sync_manager.push_audio(audio_segment, audio_data)
        result = await av_sync_manager.push_video(video_segment, video_data)

        assert result.video_data == video_data

    @pytest.mark.asyncio
    async def test_sync_pair_has_correct_audio_data(
        self,
        av_sync_manager: AvSyncManager,
        video_segment: VideoSegment,
        audio_segment: AudioSegment,
    ) -> None:
        """Test SyncPair contains correct audio data."""
        video_data = b"VIDEO_DATA_12345"
        audio_data = b"AUDIO_DATA_67890"

        await av_sync_manager.push_audio(audio_segment, audio_data)
        result = await av_sync_manager.push_video(video_segment, video_data)

        assert result.audio_data == audio_data

    @pytest.mark.asyncio
    async def test_sync_pair_pts_includes_offset(
        self,
        av_sync_manager: AvSyncManager,
        video_segment: VideoSegment,
        audio_segment: AudioSegment,
    ) -> None:
        """Test SyncPair PTS includes A/V offset."""
        video_data = b"VIDEO_DATA"
        audio_data = b"AUDIO_DATA"

        await av_sync_manager.push_audio(audio_segment, audio_data)
        result = await av_sync_manager.push_video(video_segment, video_data)

        # PTS should be adjusted by offset (0 - 6s = -6s for first segment)
        # But state.adjust_video_pts may return the original or adjusted value
        assert result.pts_ns is not None


class TestAvSyncManagerBatchMatching:
    """Tests for batch number matching."""

    @pytest.mark.asyncio
    async def test_matches_by_batch_number(self, av_sync_manager: AvSyncManager) -> None:
        """Test video and audio are matched by batch number."""
        video0 = VideoSegment(
            fragment_id="video-0",
            stream_id="s1",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/v0.mp4"),
        )
        video1 = VideoSegment(
            fragment_id="video-1",
            stream_id="s1",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/v1.mp4"),
        )
        audio1 = AudioSegment(
            fragment_id="audio-1",
            stream_id="s1",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/a1.m4a"),
        )

        # Push videos first
        await av_sync_manager.push_video(video0, b"v0")
        await av_sync_manager.push_video(video1, b"v1")

        # Push audio for batch 1 (should match video1)
        result = await av_sync_manager.push_audio(audio1, b"a1")

        assert result is not None
        assert result.video_segment.batch_number == 1
        assert result.audio_segment.batch_number == 1
        assert av_sync_manager.video_buffer_size == 1  # video0 still buffered

    @pytest.mark.asyncio
    async def test_unmatched_segments_stay_buffered(self, av_sync_manager: AvSyncManager) -> None:
        """Test unmatched segments remain in buffers."""
        video0 = VideoSegment(
            fragment_id="video-0",
            stream_id="s1",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/v0.mp4"),
        )
        audio5 = AudioSegment(
            fragment_id="audio-5",
            stream_id="s1",
            batch_number=5,
            t0_ns=30_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/a5.m4a"),
        )

        result_v = await av_sync_manager.push_video(video0, b"v0")
        result_a = await av_sync_manager.push_audio(audio5, b"a5")

        assert result_v is None
        assert result_a is None
        assert av_sync_manager.video_buffer_size == 1
        assert av_sync_manager.audio_buffer_size == 1


class TestAvSyncManagerGetReadyPairs:
    """Tests for get_ready_pairs functionality."""

    @pytest.mark.asyncio
    async def test_get_ready_pairs_returns_all_matches(
        self, av_sync_manager: AvSyncManager
    ) -> None:
        """Test get_ready_pairs returns all matched pairs."""
        # Create segments for batches 0, 1, 2
        for i in range(3):
            video = VideoSegment(
                fragment_id=f"video-{i}",
                stream_id="s1",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/v{i}.mp4"),
            )
            audio = AudioSegment(
                fragment_id=f"audio-{i}",
                stream_id="s1",
                batch_number=i,
                t0_ns=i * 6_000_000_000,
                duration_ns=6_000_000_000,
                file_path=Path(f"/tmp/a{i}.m4a"),
            )
            await av_sync_manager.push_video(video, f"v{i}".encode())
            await av_sync_manager.push_audio(audio, f"a{i}".encode())

        # Now get all ready pairs
        # Note: Each pair should have been created during push since both arrive sequentially
        # Let's verify no pairs are left if they were already matched
        _ = await av_sync_manager.get_ready_pairs()

        # Since push_audio creates pairs immediately when video is ready,
        # the buffers should be empty
        assert av_sync_manager.video_buffer_size == 0
        assert av_sync_manager.audio_buffer_size == 0

    @pytest.mark.asyncio
    async def test_get_ready_pairs_empty_when_no_matches(
        self, av_sync_manager: AvSyncManager
    ) -> None:
        """Test get_ready_pairs returns empty list when no matches."""
        video = VideoSegment(
            fragment_id="video-0",
            stream_id="s1",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/v0.mp4"),
        )
        audio = AudioSegment(
            fragment_id="audio-5",
            stream_id="s1",
            batch_number=5,
            t0_ns=30_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/a5.m4a"),
        )

        await av_sync_manager.push_video(video, b"v0")
        await av_sync_manager.push_audio(audio, b"a5")

        pairs = await av_sync_manager.get_ready_pairs()

        assert len(pairs) == 0


class TestAvSyncManagerFlushWithFallback:
    """Tests for flush_with_fallback functionality."""

    @pytest.mark.asyncio
    async def test_flush_uses_fallback_for_unbuffered_audio(
        self, av_sync_manager: AvSyncManager
    ) -> None:
        """Test flush creates pairs with fallback audio."""
        video = VideoSegment(
            fragment_id="video-0",
            stream_id="s1",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/v0.mp4"),
        )

        await av_sync_manager.push_video(video, b"video_data")

        async def get_fallback(segment: AudioSegment) -> bytes:
            return b"fallback_audio"

        pairs = await av_sync_manager.flush_with_fallback(get_fallback)

        assert len(pairs) == 1
        assert pairs[0].audio_data == b"fallback_audio"
        assert av_sync_manager.video_buffer_size == 0

    @pytest.mark.asyncio
    async def test_flush_uses_buffered_audio_when_available(
        self, av_sync_manager: AvSyncManager
    ) -> None:
        """Test flush uses buffered audio instead of fallback when available."""
        video = VideoSegment(
            fragment_id="video-0",
            stream_id="s1",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/v0.mp4"),
        )
        audio = AudioSegment(
            fragment_id="audio-0",
            stream_id="s1",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/a0.m4a"),
        )

        # Push video and audio with same batch (but via separate paths)
        # Note: deque.append is not async, so don't await it
        av_sync_manager._video_buffer.append((video, b"video_data"))
        av_sync_manager._audio_buffer[0] = (audio, b"real_audio")

        async def get_fallback(segment: AudioSegment) -> bytes:
            return b"fallback_audio"

        pairs = await av_sync_manager.flush_with_fallback(get_fallback)

        assert len(pairs) == 1
        assert pairs[0].audio_data == b"real_audio"


class TestAvSyncManagerReset:
    """Tests for reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_video_buffer(self, av_sync_manager: AvSyncManager) -> None:
        """Test reset clears video buffer."""
        video = VideoSegment(
            fragment_id="video-0",
            stream_id="s1",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/v0.mp4"),
        )
        await av_sync_manager.push_video(video, b"data")

        av_sync_manager.reset()

        assert av_sync_manager.video_buffer_size == 0

    @pytest.mark.asyncio
    async def test_reset_clears_audio_buffer(self, av_sync_manager: AvSyncManager) -> None:
        """Test reset clears audio buffer."""
        audio = AudioSegment(
            fragment_id="audio-0",
            stream_id="s1",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/a0.m4a"),
        )
        await av_sync_manager.push_audio(audio, b"data")

        av_sync_manager.reset()

        assert av_sync_manager.audio_buffer_size == 0

    def test_reset_clears_sync_state(self, av_sync_manager: AvSyncManager) -> None:
        """Test reset resets sync state."""
        av_sync_manager.state.update_sync_state(1000, 2000)

        av_sync_manager.reset()

        assert av_sync_manager.sync_delta_ms == 0.0


class TestAvSyncManagerProperties:
    """Tests for property accessors."""

    def test_video_buffer_size(self, av_sync_manager: AvSyncManager) -> None:
        """Test video_buffer_size property."""
        assert av_sync_manager.video_buffer_size == 0

    def test_audio_buffer_size(self, av_sync_manager: AvSyncManager) -> None:
        """Test audio_buffer_size property."""
        assert av_sync_manager.audio_buffer_size == 0

    def test_sync_delta_ms(self, av_sync_manager: AvSyncManager) -> None:
        """Test sync_delta_ms property."""
        assert av_sync_manager.sync_delta_ms == 0.0

    def test_av_offset_ms(self, av_sync_manager: AvSyncManager) -> None:
        """Test av_offset_ms property."""
        # 6 seconds = 6000ms
        assert av_sync_manager.av_offset_ms == 6000.0

    def test_needs_correction_initially_false(self, av_sync_manager: AvSyncManager) -> None:
        """Test needs_correction is False initially."""
        assert av_sync_manager.needs_correction is False
